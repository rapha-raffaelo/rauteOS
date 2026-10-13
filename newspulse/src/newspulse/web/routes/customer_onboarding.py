"""Isolated customer surface: bearer links never grant dashboard access."""
import datetime as dt
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from ... import customer_onboarding, twin
from ...evidence import Confidentiality, ExternalUse, InputOwner, SourceType
from ...models import Client, ClientFact, CustomerOnboardingInvite
from ..app import get_db, templates
from ..frontend import page_assets
from ..mandates import mandate_or_404

router = APIRouter()
HEADERS = {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
           'X-Robots-Tag': 'noindex, nofollow', 'X-Frame-Options': 'DENY'}


def result(data):
    return JSONResponse(data, headers=HEADERS)


def commit(session):
    try:
        session.commit()
    except StaleDataError:
        session.rollback()
        raise HTTPException(409, 'Der Fragebogen wurde parallel geändert. Bitte erneut versuchen.')


def invite_for(request: Request, session: Session):
    token = request.headers.get('X-Onboarding-Token', '')
    if len(token) != 43:
        raise HTTPException(401, 'Dieser Link ist ungültig oder abgelaufen.')
    invite = session.scalar(select(CustomerOnboardingInvite).where(
        CustomerOnboardingInvite.token_hash == hashlib.sha256(token.encode()).hexdigest()))
    if not invite or invite.revoked or invite.expires_at <= dt.datetime.now(dt.UTC):
        raise HTTPException(401, 'Dieser Link ist ungültig oder abgelaufen.')
    client = session.get(Client, invite.client_id)
    if not client or not client.active or client.is_competitor:
        raise HTTPException(401, 'Dieser Link ist ungültig oder abgelaufen.')
    return invite, client


@router.post('/client/{client_id}/onboarding-invites')
def create_invite(client_id: int, session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    if not client.active:
        raise HTTPException(409, 'Bitte das Mandat zuerst aktivieren.')
    try:
        prefill, warning, missing = customer_onboarding.prepare(session, client)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(409, str(exc))
    token = secrets.token_urlsafe(32)
    invite = CustomerOnboardingInvite(client_id=client_id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(days=14), answers={}, prefill=prefill)
    session.add(invite)
    commit(session)
    # Fragment never travels in request URLs, server access logs or Referrer.
    return result(dict(id=invite.id, path='/onboarding#' + token,
                       expires_at=invite.expires_at.isoformat(), research_warning=warning,
                       missing_public_fields=missing, prefilled=len(prefill)))


@router.get('/client/{client_id}/onboarding-invites')
def list_invites(client_id: int, session: Session = Depends(get_db)):
    mandate_or_404(session, client_id)
    rows = session.scalars(select(CustomerOnboardingInvite).where(
        CustomerOnboardingInvite.client_id == client_id).order_by(CustomerOnboardingInvite.id.desc()))
    return result([dict(id=r.id, expires_at=r.expires_at.isoformat(), revoked=r.revoked,
                        answered=sum(bool(r.answers.get(k, {}).get('value')) for k in customer_onboarding.QUESTION_KEYS),
                        total=len(customer_onboarding.QUESTION_KEYS),
                        completed=bool(r.completed_at)) for r in rows])


@router.post('/client/{client_id}/onboarding-invites/{invite_id}/revoke')
def revoke(client_id: int, invite_id: int, session: Session = Depends(get_db)):
    mandate_or_404(session, client_id)
    row = session.get(CustomerOnboardingInvite, invite_id)
    if not row or row.client_id != client_id:
        raise HTTPException(404)
    row.revoked = True
    commit(session)
    return result({'ok': True})


@router.get('/onboarding')
def page(request: Request):
    assets = page_assets('onboarding')
    if not assets:
        raise HTTPException(503, 'Der Fragebogen wird vorbereitet. Bitte später erneut öffnen.')
    return templates.TemplateResponse(request, 'customer_onboarding.html',
                                      {'frontend': assets}, headers=HEADERS)


@router.get('/api/onboarding')
def read(request: Request, session: Session = Depends(get_db)):
    invite, client = invite_for(request, session)
    # Never return existing facts or other invites' answers to a link holder.
    return result(dict(customer=client.name, questions=customer_onboarding.questions(),
        prefill=[{k: v for k, v in item.items() if k not in {'fact_id', 'correction_fact_id'}} for item in invite.prefill],
        prefill_confirmed=invite.prefill_confirmed,
        answers={k: {'value': a['value'], 'skipped': a['skipped']} for k, a in invite.answers.items()},
        completed=bool(invite.completed_at)))


class Answer(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    value: str = Field(default='', max_length=20000)
    skipped: bool = False


class PrefillReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    corrections: dict[str, str] = Field(default_factory=dict, max_length=200)


@router.post('/api/onboarding/prefill')
def confirm_prefill(data: PrefillReview, request: Request, session: Session = Depends(get_db)):
    invite, client = invite_for(request, session)
    allowed = {item['key'] for item in invite.prefill}
    if any(key not in allowed or not value.strip() or len(value) > 20000
           for key, value in data.corrections.items()):
        raise HTTPException(422, 'Bitte nur die vorbereiteten Angaben korrigieren; leere Antworten sind nicht möglich.')
    updated = []
    for original in invite.prefill:
        item = dict(original)
        value = data.corrections.get(item['key'], item.get('customer_value', item['value'])).strip()
        if value != item.get('customer_value', item['value']):
            # Keep the web evidence intact; CEO corrections are separate statements.
            row = twin.apply(session, client.id, twin.StatementInput(key=item['key'], value=value,
                source_title='Kunden-Onboarding · Korrektur', source_type=SourceType.CLIENT_INTERVIEW,
                input_owner=InputOwner.CLIENT_MANAGEMENT), 'Kunde · Onboarding')
            item.update(customer_value=value, correction_fact_id=row.id)
        updated.append(item)
    invite.prefill = updated
    invite.prefill_confirmed = True
    commit(session)
    return result({'ok': True})


@router.put('/api/onboarding/answers/{key}')
def save(key: str, data: Answer, request: Request, session: Session = Depends(get_db)):
    invite, client = invite_for(request, session)
    if key not in customer_onboarding.QUESTION_KEYS:
        raise HTTPException(404, 'Unbekannte Frage.')
    if data.skipped and data.value or not data.skipped and not data.value:
        raise HTTPException(422, 'Bitte antworten oder die Frage überspringen.')
    prior = invite.answers.get(key, {})
    if data.skipped and prior.get('value'):
        raise HTTPException(409, 'Eine gespeicherte Antwort kann bearbeitet, aber nicht übersprungen werden.')
    fact_id = prior.get('fact_id')
    if not data.skipped and data.value != prior.get('value'):
        row = session.get(ClientFact, fact_id) if fact_id else None
        if row and (row.client_id != client.id or row.key != key):
            raise HTTPException(409, 'Antwort konnte nicht zugeordnet werden.')
        # Preserve later agency edits or verification as separate evidence.
        if row and (row.value != prior.get('value') or row.verified_at is not None):
            row = None
        field = twin.CATALOG_BY_KEY[key]
        statement = twin.StatementInput(key=key, value=data.value,
            source_title='Kunden-Onboarding', source_type=SourceType.CLIENT_INTERVIEW,
            input_owner=InputOwner(field['input_owner']),
            confidentiality=Confidentiality.HIGHLY_RESTRICTED if key == 'B07.11' else Confidentiality.CLIENT_CONFIDENTIAL,
            external_use=ExternalUse.INTERNAL_ONLY if key == 'B07.11' else ExternalUse.APPROVAL_REQUIRED)
        row = twin.apply(session, client.id, statement, 'Kunde · Onboarding', row=row)
        fact_id = row.id
    invite.answers = {**invite.answers, key: dict(value=data.value, skipped=data.skipped, fact_id=fact_id)}
    invite.completed_at = None
    commit(session)
    return result({'value': data.value, 'skipped': data.skipped})


@router.post('/api/onboarding/complete')
def complete(request: Request, session: Session = Depends(get_db)):
    invite, _ = invite_for(request, session)
    if not invite.prefill_confirmed or any(key not in invite.answers for key in customer_onboarding.QUESTION_KEYS):
        raise HTTPException(409, 'Bitte alle Fragen beantworten oder überspringen.')
    invite.completed_at = dt.datetime.now(dt.UTC)
    commit(session)
    return result({'ok': True})


class ContactInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    contact_name: str = Field(default='', max_length=255)
    contact_email: str = Field(default='', max_length=320, pattern=r'^$|^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$')
    contact_role: str = Field(default='', max_length=255)
    contact_phone: str = Field(default='', max_length=80)


@router.get('/client/{client_id}/onboarding-workflow')
def workflow_status(client_id: int, session: Session = Depends(get_db)):
    from ... import onboarding_workflow
    client = mandate_or_404(session, client_id)
    return result(onboarding_workflow.status(session, client))


@router.post('/client/{client_id}/onboarding-workflow', status_code=202)
def workflow_start(client_id: int, session: Session = Depends(get_db)):
    from ... import onboarding_workflow
    client = mandate_or_404(session, client_id)
    if not client.active: raise HTTPException(409, 'Bitte das Mandat aktivieren.')
    onboarding_workflow.enqueue(session, client, retry=True)
    session.commit()
    return JSONResponse(onboarding_workflow.status(session, client), status_code=202, headers=HEADERS)


@router.post('/client/{client_id}/onboarding-workflow/link')
def workflow_link(client_id: int, session: Session = Depends(get_db)):
    from ... import onboarding_workflow
    from ...models import CustomerOnboardingJob
    client = mandate_or_404(session, client_id)
    job = session.get(CustomerOnboardingJob, client_id)
    if not job or job.status != 'ready' or not client.active:
        raise HTTPException(409, 'Bitte zuerst die Recherche abschließen.')
    prefill, _, _ = customer_onboarding.prepare(session, client, research=False)
    previous = session.get(CustomerOnboardingInvite, job.invite_id) if job.invite_id else None
    invite = onboarding_workflow.issue_invite(session, client_id, prefill)
    if previous:
        # A renewed link resumes its predecessor's saved answers.
        invite.answers = dict(previous.answers)
        invite.prefill_confirmed = previous.prefill_confirmed
        invite.prefill = list(previous.prefill)
        invite.completed_at = previous.completed_at
        previous.revoked = True
    job.invite_id = invite.id
    commit(session)
    return result(onboarding_workflow.status(session, client))


@router.put('/client/{client_id}/onboarding-contact')
def workflow_contact(client_id: int, data: ContactInput, session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    for key, value in data.model_dump().items(): setattr(client, key, value)
    session.commit()
    return result(data.model_dump())
