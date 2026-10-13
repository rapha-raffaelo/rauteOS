"""Token-scoped customer audio; original files are never public static assets."""
import datetime as dt
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ... import customer_onboarding, onboarding_audio as audio
from ...models import CustomerOnboardingAudio as Audio
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
    return result([audio.describe(row) for row in session.scalars(select(Audio).where(Audio.client_id == client_id).order_by(Audio.created_at.desc()))])


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
