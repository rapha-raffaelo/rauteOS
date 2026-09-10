"""Human-maintained journalist profiles and explicitly requested research."""
from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from ... import contacts, journalists
from ...models import Contact, JournalistProfile, JournalistResearch
from ..app import get_db
from ..mandates import mandate_or_404
from ..spawn import start_or_release

router = APIRouter(tags=['journalists'])
Kind = Literal['detected', 'developed']
Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ContactInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: Short
    outlet: str = Field(default='', max_length=200)
    first_name: str = Field(default='', max_length=100)
    last_name: str = Field(default='', max_length=100)
    email: str = Field(default='', max_length=320)
    phone: str = Field(default='', max_length=64)
    beat: str = Field(default='', max_length=400)
    position: str = Field(default='', max_length=200)
    notes: str = Field(default='', max_length=10000)


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    topics: list[Short] = Field(default_factory=list, max_length=50)
    specialties: list[Short] = Field(default_factory=list, max_length=50)
    story_types: list[Short] = Field(default_factory=list, max_length=50)
    companies: list[Short] = Field(default_factory=list, max_length=50)
    source_aliases: list[Short] = Field(default_factory=list, max_length=30)
    preferences: str = Field(default='', max_length=5000)
    relationship_status: str = 'Unbekannt'
    last_interaction_at: AwareDatetime | None = None

    @field_validator('relationship_status')
    @classmethod
    def relationship(cls, value):
        if value not in journalists.RELATIONSHIPS:
            raise ValueError('Unbekannter Beziehungsstatus')
        return value


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    contact: ContactInput
    profile: ProfileInput
    revision: int = Field(ge=0)
    contact_updated_at: AwareDatetime


class ResearchInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    context_kind: Kind
    context_id: int = Field(gt=0)
    query: str = Field(min_length=3, max_length=300)

    @field_validator('query')
    @classmethod
    def searchable(cls, value):
        if not journalists.terms(value):
            raise ValueError('Mindestens einen konkreten Suchbegriff eingeben')
        return value


def contact_or_404(session, identity):
    row = session.get(Contact, identity)
    if row is None:
        raise HTTPException(404, 'Kontakt nicht gefunden.')
    return row


@router.get('/api/v1/journalists')
def list_profiles(response: Response, q: str = Query(default='', max_length=200), session: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    rows = contacts.list_all(session, search=q)
    return {'contacts': [dict(id=c.id, name=c.name, outlet=c.outlet, beat=c.beat, has_details=c.has_details) for c in rows]}


@router.post('/api/v1/journalists', status_code=201)
def create_profile(body: ContactInput, session: Session = Depends(get_db)):
    row = Contact(**body.model_dump())
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, 'Dieser Kontakt existiert bereits. Bitte im Kontaktbuch öffnen.')
    contacts._link_released_letters(session, row)
    return journalists.profile_data(session, row)


@router.get('/api/v1/journalists/{contact_id}')
def read_profile(contact_id: int, response: Response, session: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return journalists.profile_data(session, contact_or_404(session, contact_id))


@router.put('/api/v1/journalists/{contact_id}')
def save_profile(contact_id: int, body: ProfileUpdate, session: Session = Depends(get_db)):
    contact = contact_or_404(session, contact_id)
    profile = session.get(JournalistProfile, contact_id)
    if (profile.revision if profile else 0) != body.revision:
        raise HTTPException(409, 'Profil wurde inzwischen geändert. Neu laden und vergleichen.')
    try:
        # Compare-and-swap also catches edits made through the legacy contact book.
        count = session.execute(update(Contact).where(Contact.id == contact_id,
            Contact.updated_at == body.contact_updated_at).values(**body.contact.model_dump(),
            updated_at=dt.datetime.now(dt.UTC)).execution_options(synchronize_session=False)).rowcount
        if count != 1:
            session.rollback()
            raise HTTPException(409, 'Kontakt wurde inzwischen geändert. Neu laden und vergleichen.')
        if profile is None:
            profile = JournalistProfile(contact_id=contact_id)
            session.add(profile)
        for key, value in body.profile.model_dump().items():
            setattr(profile, key, value)
        session.commit()
    except (IntegrityError, StaleDataError):
        session.rollback()
        raise HTTPException(409, 'Kontakt existiert bereits oder wurde inzwischen geändert. Neu laden und vergleichen.')
    session.refresh(contact)
    contacts._link_released_letters(session, contact)
    return journalists.profile_data(session, contact)


def research_data(row):
    return {key: getattr(row, key) for key in ('id', 'client_id', 'context_kind', 'context_id', 'query',
        'status', 'started_at', 'finished_at', 'providers', 'results', 'note')}


def fail(factory, identity):
    with factory() as session:
        session.execute(update(JournalistResearch).where(JournalistResearch.id == identity,
            JournalistResearch.status == 'running').values(status='failed', finished_at=dt.datetime.now(dt.UTC),
            note='Recherche konnte nicht abgeschlossen werden. Bitte erneut versuchen.'))
        session.commit()


def worker(factory, identity):
    try:
        with factory() as session:
            journalists.run(session, identity)
    except Exception:
        # Rollback on session exit; do not leak provider credentials in errors.
        fail(factory, identity)


@router.get('/api/v1/clients/{client_id}/journalist-research')
def latest_research(client_id: int, context_kind: Kind, context_id: int, response: Response,
                    session: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    mandate_or_404(session, client_id)
    context = journalists.context(session, client_id, context_kind, context_id)
    if context is None:
        raise HTTPException(404, 'Gelegenheit nicht gefunden.')
    row = session.scalar(select(JournalistResearch).where(JournalistResearch.client_id == client_id,
        JournalistResearch.context_kind == context_kind, JournalistResearch.context_id == context_id)
        .order_by(JournalistResearch.id.desc()).limit(1))
    return {'context': context, 'research': research_data(row) if row else None}


@router.post('/api/v1/clients/{client_id}/journalist-research', status_code=202)
def start_research(client_id: int, body: ResearchInput, session: Session = Depends(get_db)):
    mandate_or_404(session, client_id)
    if journalists.context(session, client_id, body.context_kind, body.context_id) is None:
        raise HTTPException(404, 'Gelegenheit nicht gefunden.')
    scope = (JournalistResearch.client_id == client_id, JournalistResearch.context_kind == body.context_kind,
             JournalistResearch.context_id == body.context_id)
    now = dt.datetime.now(dt.UTC)
    session.execute(update(JournalistResearch).where(*scope, JournalistResearch.status == 'running',
        JournalistResearch.started_at < now-dt.timedelta(minutes=10)).values(status='failed', finished_at=now,
        note='Recherche unterbrochen oder Zeitlimit überschritten.'))
    row = JournalistResearch(client_id=client_id, **body.model_dump())
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, 'Für diese Gelegenheit läuft bereits eine Recherche.')
    payload = research_data(row)
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    try:
        start_or_release(worker, args=(factory, row.id), name=f'journalist-research-{row.id}',
                         release=lambda: fail(factory, row.id))
    except RuntimeError:
        raise HTTPException(503, 'Recherche konnte nicht gestartet werden. Bitte erneut versuchen.')
    return payload
