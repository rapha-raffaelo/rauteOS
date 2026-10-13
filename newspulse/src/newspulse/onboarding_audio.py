"""Private persisted audio and restartable Deepgram Nova-3 transcription."""
import datetime as dt
import json
import logging
import os
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request
from sqlalchemy import or_, select, update
from .db import session_factory
from .models import Client, CustomerOnboardingAudio as Audio, CustomerOnboardingInvite

_log = logging.getLogger(__name__)
MAX_BYTES = 25 * 1024 * 1024
LEASE = dt.timedelta(minutes=8)


def configured():
    return bool(os.environ.get('DEEPGRAM_API_KEY') or os.environ.get('NEWSPULSE_DEEPGRAM_API_KEY'))


def mime_type(body):
    if body[:4] == b'RIFF' and body[8:12] == b'WAVE': return 'audio/wav'
    if body[:4] == b'OggS': return 'audio/ogg'
    if body[:4] == b'\x1aE\xdf\xa3': return 'audio/webm'
    if body[:4] == b'fLaC': return 'audio/flac'
    if body[4:8] == b'ftyp': return 'audio/mp4'
    if body[:3] == b'ID3' or len(body) > 1 and body[0] == 255 and body[1] & 0xe0 == 0xe0: return 'audio/mpeg'
    raise ValueError('Bitte eine Audio-Datei hochladen: MP3, M4A, WAV, WebM, OGG oder FLAC.')


def describe(row):
    return dict(id=row.id, question_key=row.question_key, mode=row.mode, filename=row.filename,
        mime=row.mime, size=row.size, status=row.status, transcript=row.transcript,
        note=row.note, duration=row.duration, retained=row.mode == 'audio',
        transcription_configured=configured())


def transcribe(content, mime, company):
    key = os.environ.get('DEEPGRAM_API_KEY') or os.environ.get('NEWSPULSE_DEEPGRAM_API_KEY')
    if not key: raise ValueError('Die Transkription ist noch nicht eingerichtet.')
    params = [('model', 'nova-3'), ('language', 'multi'), ('smart_format', 'true'),
              ('punctuate', 'true'), ('mip_opt_out', 'true'), ('keyterm', company[:150])]
    request = urllib.request.Request('https://api.deepgram.com/v1/listen?' + urllib.parse.urlencode(params),
        data=content, headers={'Authorization': 'Token ' + key, 'Content-Type': mime}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read(5 * 1024 * 1024))
        transcript = payload['results']['channels'][0]['alternatives'][0]['transcript'].strip()
        duration = round(payload.get('metadata', {}).get('duration', 0))
    except (urllib.error.URLError, KeyError, IndexError, ValueError):
        raise ValueError('Deepgram konnte die Aufnahme nicht verarbeiten. Bitte erneut versuchen.') from None
    if not transcript: raise ValueError('Keine Sprache erkannt. Bitte Aufnahme prüfen.')
    if len(transcript) > 20000: raise ValueError('Die Aufnahme ist zu lang. Bitte in kürzere Antworten aufteilen.')
    return transcript, duration


def claim(session):
    now = dt.datetime.now(dt.UTC)
    eligible = or_(Audio.status == 'queued', (Audio.status == 'processing') & (Audio.lease_until < now))
    for identity in session.scalars(select(Audio.id).where(eligible).order_by(Audio.created_at).limit(10)):
        token = secrets.token_hex(24)
        changed = session.execute(update(Audio).where(Audio.id == identity, eligible).values(
            status='processing', token=token, lease_until=now + LEASE, updated_at=now)).rowcount
        session.commit()
        if changed: return identity, token
    return None


def work(factory, identity, token, invoke=None):
    invoke = invoke or transcribe
    try:
        with factory() as session:
            row = session.get(Audio, identity)
            if not row or row.status != 'processing' or row.token != token: return
            client = session.get(Client, row.client_id)
            if not client or not client.active: raise ValueError('Mandat ist nicht aktiv.')
            content, mime, company = row.content, row.mime, client.name
        if not content: raise ValueError('Die Audiodatei ist nicht mehr verfügbar.')
        transcript, duration = invoke(content, mime, company)
        with factory() as session:
            now = dt.datetime.now(dt.UTC)
            changed = session.execute(update(Audio).where(Audio.id == identity, Audio.token == token,
                Audio.status == 'processing', Audio.lease_until > now).values(status='ready',
                transcript=transcript, duration=duration, note='', lease_until=None, updated_at=now)).rowcount
            if not changed: session.rollback(); return
            row = session.get(Audio, identity)
            if row.mode == 'transcript': row.content = None
            # Only submitted audio answers become evidence. Transcripts requested
            # for editing remain drafts until the customer explicitly saves them.
            from .web.routes.customer_onboarding import Answer, store_answer
            client = session.get(Client, row.client_id)
            for invite in session.scalars(select(CustomerOnboardingInvite).where(
                    CustomerOnboardingInvite.client_id == row.client_id, CustomerOnboardingInvite.revoked == False)):
                prior = invite.answers.get(row.question_key, {})
                if prior.get('audio_id') == row.id and prior.get('mode') == 'audio':
                    store_answer(session, invite, client, row.question_key,
                        Answer(value=transcript, audio_id=row.id, mode='audio'))
            session.commit()
    except Exception as exc:
        note = str(exc) if isinstance(exc, ValueError) else 'Transkription unterbrochen. Bitte erneut versuchen.'
        _log.warning('Onboarding audio %s failed (%s)', identity, type(exc).__name__)
        with factory() as session:
            session.execute(update(Audio).where(Audio.id == identity, Audio.token == token,
                Audio.status == 'processing').values(status='failed', note=note, lease_until=None,
                    updated_at=dt.datetime.now(dt.UTC)))
            session.commit()


def start():
    stop = threading.Event()
    def loop():
        factory = session_factory()
        while not stop.is_set():
            try:
                if configured():
                    with factory() as session: item = claim(session)
                    if item: work(factory, *item)
                # Discard abandoned transcription-only uploads after 24 hours.
                # Explicitly retained audio is never deleted by this sweep.
                with factory() as session:
                    session.execute(update(Audio).where(Audio.mode == 'transcript',
                        Audio.created_at < dt.datetime.now(dt.UTC) - dt.timedelta(days=1),
                        Audio.status.in_(['queued', 'failed'])).values(content=None, status='expired',
                            note='Temporäre Aufnahme abgelaufen. Bitte neu aufnehmen.'))
                    session.commit()
            except Exception as exc:
                _log.warning('Audio queue tick failed (%s)', type(exc).__name__)
            stop.wait(3)
    threading.Thread(target=loop, daemon=True, name='onboarding-audio').start()
    return stop
