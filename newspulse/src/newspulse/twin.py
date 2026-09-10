"""Twin statement lifecycle and the workbook's required-field catalogue."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .evidence import Confidence, Confidentiality, EvidenceType, ExternalUse, FactStatus, InputOwner, SourceType
from .models import ClientFact, ClientFactHistory

CATALOG = json.loads(Path(__file__).with_name("twin_catalog.json").read_text())
CATALOG_BY_KEY = {field["key"]: field for field in CATALOG}
INACTIVE = {FactStatus.REJECTED, FactStatus.ARCHIVED}
INDEPENDENT = {SourceType.MEDIA, SourceType.EXTERNAL_RESEARCH, SourceType.STUDY, SourceType.PUBLIC_DATABASE}


def fields() -> list[dict]:
    from .profile import FIELDS
    return CATALOG + [dict(key=f.key, label=f.label, section="Profil", group="Bestehendes Profil",
                           requirement="Optional", input_owner="RAUTE", legacy_key=None) for f in FIELDS]


class StatementInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=20000)
    source_url: str = Field(default="", max_length=2000)
    source_title: str = Field(default="", max_length=2000)
    evidence_type: EvidenceType = EvidenceType.CLIENT_STATEMENT
    source_type: SourceType = SourceType.OTHER
    confidence: Confidence = Confidence.UNKNOWN
    confidentiality: Confidentiality = Confidentiality.CLIENT_CONFIDENTIAL
    external_use: ExternalUse = ExternalUse.APPROVAL_REQUIRED
    fact_status: FactStatus = FactStatus.NEEDS_VERIFICATION
    input_owner: InputOwner = InputOwner.RAUTE
    as_of: dt.date | None = None
    note: str = Field(default="", max_length=5000)
    verification_note: str = Field(default="", max_length=5000)

    @field_validator("key")
    @classmethod
    def known_key(cls, value):
        from .profile import FIELDS_BY_KEY
        if value not in CATALOG_BY_KEY and value not in FIELDS_BY_KEY:
            raise ValueError("Unbekanntes Twin-Feld")
        return value

    @field_validator("source_url")
    @classmethod
    def source_is_web_url(cls, value):
        from urllib.parse import urlsplit
        if value and (urlsplit(value).scheme not in {"http", "https"} or not urlsplit(value).netloc):
            raise ValueError("Quelle muss eine http(s)-URL sein")
        return value


def all_statements(session: Session, client_id: int) -> list[ClientFact]:
    return list(session.scalars(select(ClientFact).where(ClientFact.client_id == client_id)
                              .order_by(ClientFact.key, ClientFact.is_primary.desc(), ClientFact.id)))


def snapshot(row: ClientFact) -> dict:
    return {column.name: (value.isoformat() if isinstance(value := getattr(row, column.name), dt.datetime) else value)
            for column in ClientFact.__table__.columns}


def remember(session: Session, row: ClientFact, person: str):
    session.add(ClientFactHistory(client_id=row.client_id, fact_id=row.id,
                                  changed_by=person[:200], snapshot=snapshot(row)))


def apply(session: Session, client_id: int, data: StatementInput, person: str,
          *, row: ClientFact | None = None) -> ClientFact:
    if row is None:
        primary = session.scalar(select(ClientFact.id).where(
            ClientFact.client_id == client_id, ClientFact.key == data.key, ClientFact.is_primary.is_(True)))
        row = ClientFact(client_id=client_id, key=data.key, is_primary=primary is None)
    else:
        if row.key != data.key:
            raise ValueError("Das Feld einer bestehenden Aussage kann nicht geändert werden.")
        remember(session, row, person)
    for name, value in data.model_dump().items():
        if name == "as_of" and value:
            value = dt.datetime.combine(value, dt.time(12), tzinfo=dt.UTC)
        setattr(row, name, value)
    # A changed sentence is not verified merely because its predecessor was.
    row.verified_by = None
    row.verified_at = None
    row.filled_by = "mensch"
    row.updated_at = dt.datetime.now(dt.UTC)
    session.add(row)
    session.flush()
    return row


def confirm(session: Session, row: ClientFact, person: str, note: str):
    if row.fact_status in INACTIVE:
        raise ValueError("Verworfene oder archivierte Aussagen zuerst bearbeiten.")
    if not (row.source_url or row.source_title) or row.source_type not in INDEPENDENT or not note.strip():
        raise ValueError("Bestätigung braucht eine unabhängige Quelle und einen Prüfvermerk.")
    remember(session, row, person)
    row.evidence_type = EvidenceType.FACT
    row.fact_status = FactStatus.COMPLETE
    row.confidence = Confidence.HIGH
    row.verification_note = note.strip()
    row.verified_by = person[:200]
    row.verified_at = row.updated_at = dt.datetime.now(dt.UTC)
    row.filled_by = "mensch"
    session.flush()


def completeness(rows: list[ClientFact]) -> dict:
    answered = {row.key for row in rows if row.value.strip() and row.fact_status not in
                INACTIVE | {FactStatus.OUTDATED, FactStatus.CONTRADICTORY}}
    # Only exact equivalent legacy fields count; never infer a questionnaire
    # answer from a broad neighbouring topic.
    answered |= {f["key"] for f in CATALOG if f["legacy_key"] and f["legacy_key"] in answered}
    required = [f for f in CATALOG if f["requirement"] == "Pflicht"]
    filled = sum(f["key"] in answered for f in required)
    return dict(percent=round(100 * filled / len(required)), required_filled=filled,
                required_total=len(required), answered_total=len(answered),
                missing=[f["key"] for f in required if f["key"] not in answered],
                verified=sum(bool(r.verified_at) and r.fact_status not in INACTIVE for r in rows))


def prompt_line(row: ClientFact, label: str) -> str:
    """Keep the assertion, provenance and permission together in every prompt."""
    kind = row.evidence_type or "Unbekannt"
    status = row.fact_status or "Needs Verification"
    verified = bool(row.verified_at) and kind == EvidenceType.FACT and status == FactStatus.COMPLETE
    source = row.source_url or row.source_title or "keine Quelle"
    current = row.as_of.date().isoformat() if row.as_of else "Stand unbekannt"
    qualifier = "unabhängig bestätigt" if verified else "nicht unabhängig bestätigt; nicht als Fakt behaupten"
    return (f"- {label}: {row.value.strip()}\n"
            f"  [Aussage {row.id}; {kind}; {qualifier}; {status}; Confidence: {row.confidence or 'Unknown'}; "
            f"Quelle: {source}; {current}; Vertraulichkeit: {row.confidentiality or 'unbekannt'}; "
            f"Externe Nutzung: {row.external_use or 'Freigabe erforderlich'}]")


def externally_blocked(row: ClientFact) -> bool:
    return row.fact_status in INACTIVE or row.external_use == ExternalUse.INTERNAL_ONLY or row.confidentiality in {
        Confidentiality.CLIENT_CONFIDENTIAL, Confidentiality.RAUTE_INTERNAL, Confidentiality.HIGHLY_RESTRICTED}
