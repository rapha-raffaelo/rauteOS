"""Durable, source-checked default drafts, independent of an open browser."""
from __future__ import annotations

import datetime as dt
import itertools
import logging
import threading
import time
import uuid

from sqlalchemy import case, exists, or_, select, update
from sqlalchemy.orm import aliased
from sqlalchemy.exc import IntegrityError

from . import assets
from .db import get_session
from .models import Angle, Asset, Client, DefaultDraftJob
from .streaming import preview_body, stream_assistant

_log = logging.getLogger(__name__)
_LEASE = dt.timedelta(minutes=10)
_FAILURE = 'Die Pressemitteilung konnte nicht fertiggestellt werden. Bitte erneut versuchen.'


class Superseded(RuntimeError):
    pass


def enqueue(session, client, angle, *, retry=False):
    """One durable job per impulse. Never rewrite a saved text or loop on failures."""
    if not client.active or client.is_competitor or angle.dismissed_at:
        return None
    if assets.current(session, [angle.id]).get(angle.id, {}).get('pressemitteilung'):
        return None
    job = session.get(DefaultDraftJob, angle.id)
    if job is None:
        try:
            with session.begin_nested():
                job = DefaultDraftJob(angle_id=angle.id, client_id=client.id)
                session.add(job)
                session.flush()
        except IntegrityError:
            job = session.get(DefaultDraftJob, angle.id)
    elif job.status in {'blocked', 'skipped'} or (retry and job.status == 'failed'):
        readiness = assets.requirements_met(session, assets.definition('pressemitteilung'), client, angle)
        if readiness.ok:
            session.execute(update(DefaultDraftJob).where(
                DefaultDraftJob.angle_id == angle.id,
                DefaultDraftJob.status == job.status,
            ).values(status='queued', stage='queued', note='', preview='', token='', lease_until=None))
    session.commit()
    return job


def discover(session):
    """Backfill every visible impulse; newest per mandate first, then round robin."""
    missing = ~exists().where(Asset.angle_id == Angle.id, Asset.kind == 'pressemitteilung')
    candidates = session.scalars(select(Angle).join(Client).where(
        Client.active.is_(True), Client.is_competitor.is_(False),
        Angle.dismissed_at.is_(None), missing,
    ).order_by(Angle.generated_at.desc(), Angle.id.desc())).all()
    by_client = {}
    for angle in candidates:
        by_client.setdefault(angle.client_id, []).append(angle)
    for group in itertools.zip_longest(*by_client.values()):
        for angle in group:
            if angle is not None:
                enqueue(session, session.get(Client, angle.client_id), angle)


def claim(session):
    """Compare-and-swap protects a job across processes; stale leases can resume."""
    now = dt.datetime.now(dt.UTC)
    eligible = or_(DefaultDraftJob.status == 'queued',
        (DefaultDraftJob.status == 'running') & (DefaultDraftJob.lease_until < now))
    newer = aliased(Angle)
    has_newer = exists().where(newer.client_id == Angle.client_id, newer.dismissed_at.is_(None),
        or_(newer.generated_at > Angle.generated_at,
            (newer.generated_at == Angle.generated_at) & (newer.id > Angle.id)))
    # A new daily impulse must not wait behind the historical backlog.
    for identity in session.scalars(select(DefaultDraftJob.angle_id).join(Angle).where(eligible)
            .order_by(case((~has_newer, 0), else_=1), DefaultDraftJob.created_at, DefaultDraftJob.angle_id)).all():
        token = str(uuid.uuid4())
        changed = session.execute(update(DefaultDraftJob).where(
            DefaultDraftJob.angle_id == identity, eligible,
        ).values(status='running', stage='preparing', preview='', note='', token=token,
                 attempts=DefaultDraftJob.attempts + 1, updated_at=now, lease_until=now + _LEASE)).rowcount
        session.commit()
        if changed:
            return identity, token
    return None


def publish(session, identity, token, **values):
    now = dt.datetime.now(dt.UTC)
    changed = session.execute(update(DefaultDraftJob).where(
        DefaultDraftJob.angle_id == identity, DefaultDraftJob.token == token,
        DefaultDraftJob.status == 'running', DefaultDraftJob.lease_until > now,
    ).values(updated_at=now, lease_until=now + _LEASE, **values)).rowcount
    session.commit()
    if not changed:
        raise Superseded('Another worker owns this draft')


def work(session, identity, token, *, stream=None):
    """Stream real body text to the ledger, then validate/check/store as usual."""
    try:
        angle = session.get(Angle, identity)
        client = session.get(Client, angle.client_id) if angle else None
        if not client or not client.active or client.is_competitor or angle.dismissed_at:
            publish(session, identity, token, status='skipped', stage='skipped')
            return
        fmt = assets.definition('pressemitteilung')
        readiness = assets.requirements_met(session, fmt, client, angle)
        if not readiness.ok:
            publish(session, identity, token, status='blocked', stage='blocked', note=readiness.reason)
            return
        def invoke(prompt, *, timeout):
            raw, previous, completed, last = '', '', False, time.monotonic()
            publish(session, identity, token, stage='writing', preview='')
            events = (stream or stream_assistant)(prompt, timeout=timeout)
            try:
                for event in events:
                    if event.kind == 'error':
                        raise RuntimeError('Draft provider interrupted')
                    if event.kind == 'text':
                        raw += event.data
                        if len(raw) > 60000:
                            raise RuntimeError('Draft exceeds output limit')
                        body = preview_body(raw)
                        if body != previous and time.monotonic() - last >= .75:
                            publish(session, identity, token, stage='writing', preview=body)
                            previous, last = body, time.monotonic()
                    if event.kind == 'done':
                        completed = True
            finally:
                events.close()
            if not completed:
                raise RuntimeError('Incomplete draft stream')
            publish(session, identity, token, stage='writing', preview=preview_body(raw))
            return raw
        def progress(stage, body):
            # Also renew/check ownership immediately before storing a result.
            publish(session, identity, token, stage=stage, preview=body)
        row = assets.produce(session, fmt, client, angle, only_if_missing=True,
                             invoke=invoke, progress=progress)
        publish(session, identity, token, status='ready', stage='ready', preview=row.body, note='')
    except Superseded:
        session.rollback()
    except Exception as exc:
        session.rollback()
        _log.warning('Default draft failed: angle=%s type=%s', identity, type(exc).__name__)
        try:
            state = 'blocked' if isinstance(exc, assets.RequirementsMissing) else 'failed'
            reason = str(exc) if isinstance(exc, (assets.RequirementsMissing, assets.Malformed)) else _FAILURE
            publish(session, identity, token, status=state, stage=state, note=reason)
        except Superseded:
            session.rollback()


def status(session, angle_id):
    job = session.get(DefaultDraftJob, angle_id)
    if not job:
        return None
    state = job.status
    if state == 'running' and job.lease_until < dt.datetime.now(dt.UTC):
        state = 'queued'
    if state == 'skipped':
        return dict(status='blocked', reason='Dieser Impuls ist nicht mehr aktiv.')
    return dict(status=state, stage=job.stage, preview=job.preview,
                words=len(job.preview.split()), reason=job.note)


def tick():
    """One draft at a time, yielding to existing writes and source collection."""
    from .web.routes import assets_view
    from .web import runlock
    with get_session() as session:
        discover(session)
    if not assets_view._generating.acquire(blocking=False):
        return
    try:
        if not runlock.guard.acquire(blocking=False):
            return
        try:
            with get_session() as session:
                claimed = claim(session)
                if claimed:
                    work(session, *claimed)
        finally:
            runlock.guard.release()
    finally:
        assets_view._generating.release()


def start():
    """Start with the web service, including when the feed scheduler is disabled."""
    stop = threading.Event()
    def loop():
        while not stop.is_set():
            try:
                tick()
            except Exception:
                _log.exception('Default draft queue tick failed')
            stop.wait(5)
    threading.Thread(target=loop, daemon=True, name='newspulse-default-drafts').start()
    return stop
