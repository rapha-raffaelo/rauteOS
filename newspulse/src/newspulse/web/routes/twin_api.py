"""The React Twin API: statement identity, revisions and reviewed import batches."""
from __future__ import annotations

import datetime as dt
import json
import logging
import traceback

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from ... import evidence, twin, twin_import, twin_ai
from ...analyzer import AnalyzerError, ParseError
from ...models import ClientFact, ClientFactHistory, TwinImportPreview
from ..app import get_db
from ..mandates import mandate_or_404
from ..spawn import start_or_release

router = APIRouter(prefix="/api/v1/clients/{client_id}/twin", tags=["twin"])
_log = logging.getLogger(__name__)


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

# AI drafts share the reviewed-import ledger; only explicit commit creates facts.


class AIImportInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    text: str = Field(default='', max_length=30000)
    source_title: str = Field(default='', max_length=300)
    section: str = Field(default='', max_length=100)
    web: bool = True


def ai_failed(factory, identity, generation, error=None):
    if error is None:
        code, note = 'start_failed', 'Der KI-Import konnte nicht gestartet werden. Bitte erneut versuchen.'
    elif isinstance(error, (ParseError, json.JSONDecodeError)):
        code, note = 'invalid_response', 'Der KI-Dienst hat keine gültigen Antwortvorschläge geliefert. Bitte erneut versuchen; es wurden keine Antworten übernommen.'
    elif isinstance(error, TimeoutError) or isinstance(error, AnalyzerError) and 'timed out' in str(error).lower():
        code, note = 'timeout', 'Der KI-Dienst hat zu lange gebraucht. Bitte erneut versuchen oder einen einzelnen Bereich auswählen.'
    elif isinstance(error, AnalyzerError):
        code, note = 'provider_unavailable', 'Der KI-Dienst ist momentan nicht verfügbar. Bitte später erneut versuchen.'
    else:
        code, note = 'internal_error', 'Der KI-Import wurde durch einen technischen Fehler unterbrochen. Bitte erneut versuchen; es wurden keine Antworten übernommen.'
    # Log diagnostic locations without exception text, source excerpts or model output.
    frames = traceback.extract_tb(error.__traceback__) if error is not None else []
    _log.error('AI import failed: job=%s generation=%s code=%s exception=%s frames=%s',
               identity, generation, code, type(error).__name__,
               ','.join(f'{frame.name}:{frame.lineno}' for frame in frames))
    with factory() as session:
        twin_ai.finish(session, identity, generation, dict(status='failed',
            error_code=code, note=note))


def ai_worker(factory, identity, generation):
    try:
        with factory() as session:
            twin_ai.generate(session, identity, generation)
    except Exception as exc:
        ai_failed(factory, identity, generation, exc)


@router.post('/ai-import', status_code=202)
def ai_start(client_id: int, body: AIImportInput, response: Response, session: Session = Depends(get_db)):
    mandate_or_404(session, client_id)
    response.headers['Cache-Control'] = 'no-store'
    if body.section and body.section not in {f['section'] for f in twin.CATALOG}:
        raise HTTPException(422, 'Unbekannter Fragebogen-Bereich.')
    try:
        row = twin_ai.start(session, client_id, body.model_dump())
    except (ValueError, IntegrityError):
        session.rollback()
        raise HTTPException(409, 'Für diesen Mandanten läuft bereits ein KI-Import.') from None
    result = twin_ai.job_data(row)
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    try:
        start_or_release(ai_worker, args=(factory, row.id, result['generation']), name=f'twin-ai-{client_id}',
            release=lambda: ai_failed(factory, row.id, result['generation']))
    except RuntimeError:
        raise HTTPException(503, 'KI-Import konnte nicht gestartet werden.') from None
    return result


@router.get('/ai-import')
def ai_status(client_id: int, response: Response, session: Session = Depends(get_db), preview_id: str = ''):
    mandate_or_404(session, client_id)
    response.headers['Cache-Control'] = 'no-store'
    row = session.get(TwinImportPreview, twin_ai.slot_id(client_id))
    job = twin_ai.job_data(row) if row else None
    if job and job['status'] == 'running' and row.expires_at < dt.datetime.now(dt.UTC):
        job.update(status='failed', note='Import unterbrochen oder Zeitlimit überschritten. Bitte erneut starten.')
    preview = session.get(TwinImportPreview, job.get('preview_id')) if job and job.get('preview_id') else None
    if not preview or preview.committed_at:
        preview = session.scalar(select(TwinImportPreview).where(
            TwinImportPreview.client_id == client_id, TwinImportPreview.committed_at.is_(None),
            TwinImportPreview.payload['kind'].as_string() == 'ai'
        ).order_by(TwinImportPreview.created_at.desc()).limit(1))
    previews = list(session.scalars(select(TwinImportPreview).where(
        TwinImportPreview.client_id == client_id, TwinImportPreview.committed_at.is_(None),
        TwinImportPreview.payload['kind'].as_string() == 'ai'
    ).order_by(TwinImportPreview.created_at.desc())))
    if preview_id:
        preview = next((p for p in previews if p.id == preview_id), None)
        if preview is None:
            raise HTTPException(404, 'Gespeicherter Import nicht gefunden.')
    result = None
    if preview and preview.client_id == client_id and not preview.committed_at:
        result = dict(id=preview.id, **preview.payload)
    return dict(job=job, preview=result, previews=[dict(id=p.id, created_at=p.created_at.isoformat(), count=len(p.payload['rows'])) for p in previews])


@router.post('/ai-import/resume', status_code=202)
def ai_resume(client_id: int, response: Response, session: Session = Depends(get_db)):
    mandate_or_404(session, client_id)
    response.headers['Cache-Control'] = 'no-store'
    try:
        row = twin_ai.resume(session, client_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    result = twin_ai.job_data(row)
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    try:
        start_or_release(ai_worker, args=(factory, row.id, result['generation']), name=f'twin-ai-{client_id}',
            release=lambda: ai_failed(factory, row.id, result['generation']))
    except RuntimeError:
        raise HTTPException(503, 'KI-Import konnte nicht fortgesetzt werden.') from None
    return result


def recover_ai_imports():
    """Single-process server startup recovery; generation fencing rejects old workers."""
    from ...db import get_session
    with get_session() as session:
        clients = list(session.scalars(select(TwinImportPreview.client_id).where(
            TwinImportPreview.payload['kind'].as_string() == 'ai-job',
            TwinImportPreview.payload['status'].as_string() == 'running')))
    for client_id in clients:
        with get_session() as session:
            try:
                mandate_or_404(session, client_id)
                row = twin_ai.resume(session, client_id, recovering=True)
            except (ValueError, HTTPException):
                continue
            identity, generation = row.id, row.payload['generation']
        try:
            start_or_release(ai_worker, args=(get_session, identity, generation), name=f'twin-ai-{client_id}',
                release=lambda i=identity, g=generation: ai_failed(get_session, i, g))
        except RuntimeError:
            _log.error('AI import restart failed: client=%s', client_id)
