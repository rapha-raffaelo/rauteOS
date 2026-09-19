"""Explicit custom drafts with live previews; storing never releases or sends."""
from __future__ import annotations

import json
import logging
import queue
import threading
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker

from ... import assets
from ...streaming import StreamEvent, stream_assistant, preview_body
from ..app import get_db
from ..mandates import mandate_or_404
from ..spawn import start_or_release
from . import assets_view

router = APIRouter()
_log = logging.getLogger(__name__)


class CustomInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    instruction: str = Field(min_length=1, max_length=5000)
    version: str = Field(default='', max_length=200)


def current(session, angle_id):
    return assets.current(session, [angle_id]).get(angle_id, {}).get('custom')


def unchanged(session, angle_id, version):
    row = current(session, angle_id)
    if (assets.version(row) if row else '') != version:
        raise assets.Refused('Der vorhandene Text wurde inzwischen geändert. Bitte neu laden.')
    if row and row.released:
        raise assets.Refused('Die eigene Nachricht ist bereits freigegeben und kann nicht ersetzt werden.')


def work(factory, client_id, angle_id, body, events, cancelled):
    def emit(event):
        # Keep memory bounded even when a browser reads slowly or disconnects.
        while True:
            try:
                events.put_nowait(event)
                return
            except queue.Full:
                try:
                    events.get_nowait()
                except queue.Empty:
                    pass
    stored = None
    try:
        with assets_view._sweep_free() as free:
            if not free:
                raise assets.Refused(assets_view._SWEEP_RUNNING)
            with factory() as session:
                client = mandate_or_404(session, client_id)
                angle = assets_view._impulse_or_404(session, client_id, angle_id)
                unchanged(session, angle_id, body.version)
                emit(StreamEvent('status', 'Quellen und Auftrag werden vorbereitet …'))

                def invoke(prompt, *, timeout):
                    raw = ''
                    previous = ''
                    complete = False
                    emit(StreamEvent('preview', ''))  # reset on a structural retry
                    emit(StreamEvent('status', 'Nachricht wird geschrieben …'))
                    stream = stream_assistant(prompt, timeout=timeout)
                    try:
                        for event in stream:
                            if cancelled.is_set():
                                raise InterruptedError('Schreiben abgebrochen.')
                            if event.kind == 'error':
                                raise RuntimeError('Die Texterstellung wurde unterbrochen. Bitte erneut versuchen.')
                            if event.kind == 'text':
                                raw += event.data
                                if len(raw) > 60000:
                                    raise RuntimeError('Der Text ist zu lang.')
                                preview = preview_body(raw)
                                if preview != previous:
                                    emit(StreamEvent('preview', preview))
                                    previous = preview
                            if event.kind == 'done':
                                complete = True
                    finally:
                        stream.close()
                    if not complete:
                        raise RuntimeError('Die Texterstellung wurde unterbrochen. Bitte erneut versuchen.')
                    return raw

                fmt = assets.definition('custom')
                draft = assets.write(session, fmt, client, angle, invoke=invoke,
                    extra_context='NUTZERAUFTRAG (keine neue Faktenquelle):\n' + body.instruction)
                if cancelled.is_set():
                    return
                session.expire_all()
                unchanged(session, angle_id, body.version)
                stored = assets.store(session, fmt, client, angle, draft)
                emit(StreamEvent('preview', stored.body))
                emit(StreamEvent('status', 'Entwurf gespeichert. Quellen und Formulierungen werden geprüft …'))
                try:
                    assets.recheck(session, client, stored)
                except Exception:
                    session.rollback()
                    _log.exception('Custom draft %s saved, but checking failed', stored.id)
                session.refresh(stored)
                emit(StreamEvent('saved', json.dumps({
                    'id': stored.id, 'title': stored.title, 'body': stored.body,
                    'version': assets.version(stored),
                    'notice': 'Entwurf gespeichert. Bitte Text und Prüfhinweise vor Verwendung lesen.',
                    'url': f'/client/{client_id}/advice?' + urlencode({'eintrag': f'anlass-{angle_id}', 'entwurf': stored.id, 'stand': assets.version(stored)}) + f'#pane-{angle_id}-custom',
                })))
    except Exception as exc:
        _log.exception('Custom draft failed for impulse %s', angle_id)
        message = str(exc) if isinstance(exc, (assets.Refused, assets.RequirementsMissing, InterruptedError)) else 'Die Nachricht konnte nicht fertiggestellt werden. Bitte erneut versuchen.'
        emit(StreamEvent('error', message))
    finally:
        emit(None)
        assets_view._generating.release()


@router.post('/api/v1/clients/{client_id}/impulses/{angle_id}/custom-draft')
def generate(client_id: int, angle_id: int, body: CustomInput, session: Session = Depends(get_db)):
    mandate_or_404(session, client_id)
    assets_view._impulse_or_404(session, client_id, angle_id)
    try:
        unchanged(session, angle_id, body.version)
    except assets.Refused as exc:
        raise HTTPException(409, str(exc)) from exc
    if not assets_view._generating.acquire(blocking=False):
        raise HTTPException(409, 'Es wird bereits ein Text geschrieben. Bitte kurz warten.')
    events = queue.Queue(maxsize=32)
    cancelled = threading.Event()
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    try:
        start_or_release(work, args=(factory, client_id, angle_id, body, events, cancelled),
            name=f'custom-draft-{angle_id}', release=assets_view._generating.release)
    except RuntimeError as exc:
        raise HTTPException(503, 'Die Texterstellung konnte nicht gestartet werden.') from exc

    def response():
        try:
            while True:
                try:
                    event = events.get(timeout=1)
                except queue.Empty:
                    yield ': keepalive\n\n'
                    continue
                if event is None:
                    return
                yield event.to_sse()
        finally:
            cancelled.set()

    return StreamingResponse(response(), media_type='text/event-stream',
        headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
