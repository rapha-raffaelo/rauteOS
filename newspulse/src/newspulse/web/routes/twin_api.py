"""The React Twin API: statement identity, revisions and reviewed import batches."""
from __future__ import annotations

import datetime as dt
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from ... import evidence, twin, twin_import
from ...models import ClientFact, ClientFactHistory
from ..app import get_db
from ..mandates import mandate_or_404

router = APIRouter(prefix="/api/v1/clients/{client_id}/twin", tags=["twin"])


class StatementRead(BaseModel):
    id: int
    key: str
    value: str
    revision: int
    source_url: str
    source_title: str
    filled_by: str
    updated_at: dt.datetime
    is_primary: bool
    evidence_type: str | None
    source_type: str | None
    confidence: str | None
    confidentiality: str | None
    external_use: str | None
    fact_status: str | None
    input_owner: str | None
    as_of: dt.datetime | None
    note: str
    verification_note: str
    verified_by: str | None
    verified_at: dt.datetime | None
    model_config = ConfigDict(from_attributes=True)


class FieldRead(BaseModel):
    key: str
    label: str
    section: str
    group: str
    requirement: str
    input_owner: str
    legacy_key: str | None


class ProgressRead(BaseModel):
    percent: int
    required_filled: int
    required_total: int
    answered_total: int
    missing: list[str]
    verified: int


class TwinRead(BaseModel):
    client: dict[str, str | int]
    fields: list[FieldRead]
    statements: list[StatementRead]
    progress: ProgressRead
    options: dict[str, list[str]]


class StatementUpdate(twin.StatementInput):
    revision: int = Field(ge=1)


class RevisionAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    note: str = Field(default="", max_length=5000)


class ImportCommit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_id: str = Field(min_length=1, max_length=36)
    selected: list[int] = Field(min_length=1, max_length=twin_import.MAX_ROWS)


def _person(request: Request):
    return str(request.scope.get("user_email") or "mensch")[:200]


def _row(session, client_id, statement_id, revision=None):
    mandate_or_404(session, client_id)
    row = session.get(ClientFact, statement_id)
    if row is None or row.client_id != client_id:
        raise HTTPException(404, "Aussage nicht gefunden.")
    if revision is not None and row.revision != revision:
        raise HTTPException(409, "Aussage wurde inzwischen geändert. Neu laden und Änderungen vergleichen.")
    return row


def _commit(session):
    try:
        session.commit()
    except (StaleDataError, IntegrityError):
        session.rollback()
        raise HTTPException(409, "Daten wurden inzwischen geändert. Bitte neu laden.") from None


@router.get("", response_model=TwinRead)
def read_twin(client_id: int, response: Response, session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    response.headers['Cache-Control'] = 'no-store'
    rows = twin.all_statements(session, client_id)
    return dict(client=dict(id=client.id, name=client.name), fields=twin.fields(), statements=rows,
                progress=twin.completeness(rows), options={
                    name: list(enum) for name, enum in {
                        'evidence_type': evidence.EvidenceType, 'source_type': evidence.SourceType,
                        'confidence': evidence.Confidence, 'confidentiality': evidence.Confidentiality,
                        'external_use': evidence.ExternalUse, 'fact_status': evidence.FactStatus,
                        'input_owner': evidence.InputOwner}.items()})


@router.post("/statements", response_model=StatementRead, status_code=201)
def create_statement(client_id: int, data: twin.StatementInput, request: Request,
                     session: Session = Depends(get_db)):
    mandate_or_404(session, client_id)
    try:
        row = twin.apply(session, client_id, data, _person(request))
        _commit(session)
    except (StaleDataError, IntegrityError):
        session.rollback()
        raise HTTPException(409, "Gleichzeitige Änderung. Bitte erneut versuchen.") from None
    return row


@router.put("/statements/{statement_id}", response_model=StatementRead)
def update_statement(client_id: int, statement_id: int, data: StatementUpdate,
                     request: Request, session: Session = Depends(get_db)):
    row = _row(session, client_id, statement_id, data.revision)
    try:
        twin.apply(session, client_id, twin.StatementInput.model_validate(data.model_dump(exclude={'revision'})),
                   _person(request), row=row)
        _commit(session)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(422, str(exc)) from None
    except StaleDataError:
        session.rollback()
        raise HTTPException(409, "Aussage wurde inzwischen geändert.") from None
    return row


@router.post("/statements/{statement_id}/{action}", response_model=StatementRead)
def transition(client_id: int, statement_id: int, action: str, data: RevisionAction,
               request: Request, session: Session = Depends(get_db)):
    row = _row(session, client_id, statement_id, data.revision)
    try:
        if action == 'confirm':
            twin.confirm(session, row, _person(request), data.note)
        elif action in {'reject', 'archive'}:
            twin.remember(session, row, _person(request))
            row.fact_status = evidence.FactStatus.REJECTED if action == 'reject' else evidence.FactStatus.ARCHIVED
            row.updated_at = dt.datetime.now(dt.UTC)
        else:
            raise HTTPException(404, "Unbekannte Aktion.")
        _commit(session)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(422, str(exc)) from None
    except StaleDataError:
        session.rollback()
        raise HTTPException(409, "Aussage wurde inzwischen geändert.") from None
    return row


@router.get("/statements/{statement_id}/history")
def history(client_id: int, statement_id: int, response: Response, session: Session = Depends(get_db)):
    _row(session, client_id, statement_id)
    response.headers['Cache-Control'] = 'no-store'
    rows = session.scalars(select(ClientFactHistory).where(
        ClientFactHistory.client_id == client_id, ClientFactHistory.fact_id == statement_id
    ).order_by(ClientFactHistory.id.desc()))
    return [dict(changed_at=r.changed_at, changed_by=r.changed_by, snapshot=r.snapshot) for r in rows]


@router.post("/import/preview")
async def import_preview(client_id: int, response: Response, file: UploadFile = File(...),
                         mapping: str = Form('{}'), session: Session = Depends(get_db)):
    mandate_or_404(session, client_id)
    response.headers['Cache-Control'] = 'no-store'
    data = await file.read(twin_import.MAX_BYTES + 1)
    await file.close()
    try:
        mapped = json.loads(mapping)
        if not isinstance(mapped, dict): raise ValueError('Spaltenzuordnung muss ein Objekt sein.')
        return twin_import.preview(session, client_id, data, file.filename or '', mapped)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(422, str(exc)) from None


@router.post("/import/commit")
def import_commit(client_id: int, data: ImportCommit, request: Request, session: Session = Depends(get_db)):
    mandate_or_404(session, client_id)
    try:
        return twin_import.commit(session, client_id, data.preview_id, data.selected, _person(request))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except ValueError as exc:
        session.rollback()
        raise HTTPException(422, str(exc)) from None
    except (IntegrityError, StaleDataError):
        session.rollback()
        raise HTTPException(409, 'Gleichzeitiger Import. Vorschau erneut laden.') from None
