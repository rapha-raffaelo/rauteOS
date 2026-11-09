"""Token-scoped customer audio; original files are never public static assets."""
import datetime as dt
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from ... import customer_onboarding, onboarding_audio as audio, twin
from ...evidence import Confidentiality, ExternalUse, SourceType
from ...models import CustomerOnboardingAudio as Audio, CustomerOnboardingInvite as Invite, ClientFact
from ..app import get_db
from ..mandates import mandate_or_404
from .customer_onboarding import HEADERS, invite_for, result, commit

router = APIRouter()


def media_for(session, invite, identity):
    row = session.get(Audio, identity)
    if not row or row.client_id != invite.client_id or not (row.invite_id == invite.id or
            invite.answers.get(row.question_key, {}).get('audio_id') == identity):
        raise HTTPException(404, 'Audio nicht gefunden.')
    return row


def audio_response(row):
    if row.content is None: raise HTTPException(404, 'Die Audiodatei wurde nicht aufbewahrt.')
    return Response(row.content, media_type=row.mime, headers={**HEADERS,
        'X-Content-Type-Options': 'nosniff', 'Content-Disposition': 'inline; filename="onboarding-audio"'})


@router.post('/api/onboarding/audio/{key}')
async def upload(key: str, request: Request, mode: str = 'transcript', filename: str = 'Aufnahme', session: Session = Depends(get_db)):
    invite, client = invite_for(request, session)
    if key not in customer_onboarding.QUESTION_KEYS: raise HTTPException(404, 'Unbekannte Frage.')
    if mode not in {'transcript', 'audio'}: raise HTTPException(422, 'Unbekanntes Speicherformat.')
    if mode == 'transcript' and not audio.configured():
        raise HTTPException(503, 'Transkription wird eingerichtet. Sie können Audio speichern oder Text eingeben.')
    count, size = session.execute(select(func.count(Audio.id), func.coalesce(func.sum(Audio.size), 0)).where(Audio.invite_id == invite.id)).one()
    if count >= 20 or size >= 100 * 1024 * 1024:
        raise HTTPException(429, 'Upload-Limit erreicht. Bitte das raute+kopf-Team kontaktieren.')
    # End the read transaction before receiving a potentially slow upload.
    invite_id, client_id = invite.id, client.id
    session.rollback()
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > audio.MAX_BYTES: raise HTTPException(413, 'Audio darf höchstens 25 MB groß sein.')
        body.extend(chunk)
    if len(body) < 16: raise HTTPException(422, 'Die Aufnahme ist leer oder unvollständig.')
    try: mime = audio.mime_type(body)
    except ValueError as exc: raise HTTPException(415, str(exc))
    # Revalidate the link after upload (revocation/expiry may have changed).
    invite, _ = invite_for(request, session)
    count, size = session.execute(select(func.count(Audio.id), func.coalesce(func.sum(Audio.size), 0)).where(Audio.invite_id == invite.id)).one()
    if count >= 20 or size + len(body) > 100 * 1024 * 1024:
        raise HTTPException(429, 'Upload-Limit erreicht. Bitte das raute+kopf-Team kontaktieren.')
    invite.version += 1  # Serialize concurrent uploads against this link's quota.
    row = Audio(id=secrets.token_hex(16), client_id=client_id, invite_id=invite_id,
        question_key=key, mode=mode, filename=filename.replace('\\', '/').split('/')[-1][:200] or 'Audio',
        mime=mime, size=len(body), content=bytes(body))
    session.add(row); commit(session)
    return result(audio.describe(row))


@router.get('/api/onboarding/audio/{identity}')
def status(identity: str, request: Request, session: Session = Depends(get_db)):
    invite, _ = invite_for(request, session)
    return result(audio.describe(media_for(session, invite, identity)))


@router.get('/api/onboarding/audio/{identity}/content')
def content(identity: str, request: Request, session: Session = Depends(get_db)):
    invite, _ = invite_for(request, session)
    return audio_response(media_for(session, invite, identity))


@router.delete('/api/onboarding/audio/{identity}')
def delete(identity: str, request: Request, session: Session = Depends(get_db)):
    invite, _ = invite_for(request, session)
    row = media_for(session, invite, identity)
    remove_audio(session, row)
    commit(session)
    answer = invite.answers.get(row.question_key)
    return result({'answer': {k:v for k,v in answer.items() if k != 'fact_id'} if answer else None})


def remove_audio(session, row):
    identity = row.id
    for link in session.scalars(select(Invite).where(Invite.client_id == row.client_id)):
        answers = dict(link.answers)
        for key, answer in list(answers.items()):
            if answer.get('audio_id') != identity: continue
            if answer.get('value'):
                answers[key] = {k: v for k, v in answer.items() if k not in {'audio_id', 'mode'}}
            else:
                del answers[key]
            link.answers = answers
            link.completed_at = None
    session.delete(row)


def retry_row(row, session):
    if row.status not in {'failed', 'expired'}: raise HTTPException(409, 'Transkription läuft bereits oder ist abgeschlossen.')
    if row.content is None: raise HTTPException(409, 'Bitte die Aufnahme erneut hochladen.')
    row.status = 'queued'; row.note = ''; row.token = ''; row.lease_until = None
    row.updated_at = dt.datetime.now(dt.UTC)
    session.commit()
    return result(audio.describe(row))


@router.post('/api/onboarding/audio/{identity}/retry')
def retry(identity: str, request: Request, session: Session = Depends(get_db)):
    invite, _ = invite_for(request, session)
    return retry_row(media_for(session, invite, identity), session)


@router.get('/client/{client_id}/onboarding-audio')
def agency_list(client_id: int, session: Session = Depends(get_db)):
    mandate_or_404(session, client_id)
    return result([agency_description(row, session) for row in session.scalars(select(Audio).where(Audio.client_id == client_id).order_by(Audio.created_at.desc()))])


def agency_row(client_id, identity, session):
    mandate_or_404(session, client_id)
    row = session.get(Audio, identity)
    if not row or row.client_id != client_id: raise HTTPException(404)
    return row


@router.get('/client/{client_id}/onboarding-audio/{identity}/content')
def agency_content(client_id: int, identity: str, session: Session = Depends(get_db)):
    return audio_response(agency_row(client_id, identity, session))


@router.post('/client/{client_id}/onboarding-audio/{identity}/retry')
def agency_retry(client_id: int, identity: str, session: Session = Depends(get_db)):
    return retry_row(agency_row(client_id, identity, session), session)


def agency_description(row, session):
    fact = session.get(ClientFact, row.answer_fact_id) if row.answer_fact_id else None
    return {**audio.describe(row), 'review': row.review,
            'question': twin.CATALOG_BY_KEY.get(row.question_key, {}).get('label', row.question_key),
            'answer': fact.value if fact and fact.client_id == row.client_id else '',
            'created_at': row.created_at.isoformat()}


class ReviewedAnswer(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    value: str = Field(min_length=1, max_length=20000)


@router.post('/client/{client_id}/onboarding-audio/{identity}/answer')
def agency_answer(client_id: int, identity: str, data: ReviewedAnswer, session: Session = Depends(get_db)):
    row = agency_row(client_id, identity, session)
    # Claim the review in the same transaction as the answer: retries cannot
    # create duplicate statements, and a failed save cannot archive the audio.
    changed = session.execute(update(Audio).where(Audio.id == identity, Audio.review == '').values(review='archiviert')).rowcount
    if not changed:
        raise HTTPException(409, 'Diese Aufnahme wurde bereits archiviert. Bitte die Liste aktualisieren.')
    restricted = row.question_key in customer_onboarding.RESTRICTED
    fact = twin.apply(session, client_id, twin.StatementInput(
        key=row.question_key, value=data.value,
        source_title='Kunden-Onboarding · geprüfte Audioantwort',
        source_type=SourceType.CLIENT_INTERVIEW,
        confidentiality=Confidentiality.HIGHLY_RESTRICTED if restricted else Confidentiality.CLIENT_CONFIDENTIAL,
        external_use=ExternalUse.INTERNAL_ONLY if restricted else ExternalUse.APPROVAL_REQUIRED,
    ), 'Agentur · Audioantwort')
    row.answer_fact_id = fact.id
    row.updated_at = dt.datetime.now(dt.UTC)
    commit(session)
    return result(agency_description(row, session))


@router.delete('/client/{client_id}/onboarding-audio/{identity}')
def agency_delete(client_id: int, identity: str, session: Session = Depends(get_db)):
    row = agency_row(client_id, identity, session)
    remove_audio(session, row)
    commit(session)
    return result({'ok': True})
