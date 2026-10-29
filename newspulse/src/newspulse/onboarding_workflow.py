"""Durable onboarding queue: crawl, grounded workbook research, personal link."""
import base64
import datetime as dt
import hashlib
import hmac
import logging
import os
import secrets
import re
import unicodedata
import threading
import tempfile
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import or_, select, update
from . import config, customer_onboarding, onboarding_crawler, twin
from .quota import is_quota_error
from .db import session_factory
from .evidence import Confidentiality, EvidenceType, SourceType
from .logos import fetch_logo
from .models import Client, ClientFact, CustomerOnboardingInvite, CustomerOnboardingJob

_log = logging.getLogger(__name__)
LEASE = dt.timedelta(minutes=8)
# A spent search quota parks the job instead of failing it. A per-minute
# limit clears quickly; anything longer is usually the daily cap.
PAUSE_MINUTE = dt.timedelta(seconds=90)
PAUSE_LONG = dt.timedelta(hours=1)


class Superseded(Exception):
    pass


def signing_key():
    # Lives beside SQLite on Railway's persistent volume, never in the browser.
    path = Path(config.DATABASE_PATH).parent / '.onboarding-link-key'
    if not path.exists():
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.onboarding-key-', delete=False) as file:
            temp = Path(file.name)
            file.write(secrets.token_bytes(32)); file.flush(); os.fsync(file.fileno())
        try:
            try: os.link(temp, path)
            except FileExistsError: pass
        finally:
            temp.unlink()
    key = path.read_bytes()
    if len(key) != 32: raise RuntimeError('Invalid onboarding signing key')
    return key


def invite_token(invite):
    return base64.urlsafe_b64encode(hmac.new(signing_key(),
        f'raute-onboarding:{invite.id}:{invite.client_id}:{invite.expires_at.isoformat()}'.encode(), hashlib.sha256).digest()).decode().rstrip('=')


def customer_link(token, name):
    name = name.lower().replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    slug = re.sub(r'[^a-z0-9]+', '-', name).strip('-')[:100].rstrip('-') or 'kunde'
    return '/onboarding#' + token + '/' + slug


def invite_path(invite, name='kunde'):
    if not invite or invite.revoked or invite.expires_at <= dt.datetime.now(dt.UTC): return None
    token = invite_token(invite)
    if not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), invite.token_hash): return None
    return customer_link(token, name)


def issue_invite(session, client_id, prefill):
    row = CustomerOnboardingInvite(client_id=client_id, token_hash=secrets.token_hex(32),
        expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(days=14), prefill=prefill, answers={})
    session.add(row); session.flush()
    token = invite_token(row)
    row.token_hash = hashlib.sha256(token.encode()).hexdigest()
    return row


def enqueue(session, client, *, retry=False):
    row = session.get(CustomerOnboardingJob, client.id)
    if not row:
        row = CustomerOnboardingJob(client_id=client.id)
        session.add(row); session.flush()
    elif retry and (row.status == 'failed' or row.status == 'ready' and outdated(row.checkpoint)):
        row.status = 'queued'; row.note = ''; row.token = ''; row.lease_until = None
        if outdated(row.checkpoint):
            row.checkpoint = {k: v for k, v in row.checkpoint.items() if k == 'pages'}
        elif row.checkpoint.get('next_batch', 0) >= len(onboarding_crawler.BATCHES):
            row.checkpoint = {}  # A completed but empty search must be retryable.
    return row


def outdated(checkpoint):
    """Research run under an earlier topic layout; its batch index means nothing now."""
    return bool(checkpoint) and checkpoint.get('version') != onboarding_crawler.VERSION


def claim(session):
    now = dt.datetime.now(dt.UTC)
    # A queued job's lease_until is its earliest start, set while a quota recovers.
    eligible = or_((CustomerOnboardingJob.status == 'queued')
        & (CustomerOnboardingJob.lease_until.is_(None) | (CustomerOnboardingJob.lease_until < now)),
        (CustomerOnboardingJob.status == 'running') & (CustomerOnboardingJob.lease_until < now))
    for identity in session.scalars(select(CustomerOnboardingJob.client_id).where(eligible)
                                   .order_by(CustomerOnboardingJob.created_at)).all():
        token = secrets.token_hex(24)
        changed = session.execute(update(CustomerOnboardingJob).where(
            CustomerOnboardingJob.client_id == identity, eligible).values(status='running', token=token,
            lease_until=now + LEASE, updated_at=now, attempts=CustomerOnboardingJob.attempts + 1)).rowcount
        session.commit()
        if changed: return identity, token
    return None


def own(session, identity, token, **values):
    now = dt.datetime.now(dt.UTC)
    changed = session.execute(update(CustomerOnboardingJob).where(CustomerOnboardingJob.client_id == identity,
        CustomerOnboardingJob.token == token, CustomerOnboardingJob.status == 'running',
        CustomerOnboardingJob.lease_until > now).values(updated_at=now, lease_until=now + LEASE, **values)).rowcount
    if not changed: raise Superseded()
    return session.get(CustomerOnboardingJob, identity)


def store_facts(session, client_id, answers):
    for answer in answers:
        existing = session.scalar(select(ClientFact.id).where(ClientFact.client_id == client_id,
            ClientFact.key == answer['key'], ClientFact.value == answer['value'],
            ClientFact.source_url == answer['source_url'], ClientFact.filled_by == 'recherche'))
        if existing: continue
        row = twin.apply(session, client_id, twin.StatementInput(**answer,
            source_title='Öffentliche Onboarding-Recherche', source_type=SourceType.EXTERNAL_RESEARCH,
            evidence_type=EvidenceType.EXTERNAL_OBSERVATION,
            confidentiality=Confidentiality.PUBLIC), 'Webrecherche · Onboarding')
        row.filled_by = 'recherche'


def work(factory, identity, token, *, crawl=None, research=None):
    crawl = crawl or onboarding_crawler.crawl
    research = research or onboarding_crawler.research_batch
    try:
        with factory() as session:
            job = own(session, identity, token)
            client = session.get(Client, identity)
            if not client or not client.active or client.is_competitor:
                raise ValueError('Mandat ist nicht aktiv.')
            context = SimpleNamespace(name=client.name, website=client.website,
                                      country=client.country, industry=client.industry,
                                      has_logo=bool(client.logo_url))
            checkpoint = dict(job.checkpoint)
            if outdated(checkpoint):
                # Keep the crawled pages, research every topic afresh.
                checkpoint = {k: v for k, v in checkpoint.items() if k == 'pages'}
                if 'pages' in checkpoint:
                    checkpoint.update(next_batch=0, answered_keys=[], sources=[])
            checkpoint['version'] = onboarding_crawler.VERSION
            session.commit()
        if not context.has_logo and context.website:
            # First thing after creation, so the mandate carries its mark while
            # the research is still running. Cosmetic: never fails the job.
            logo = fetch_logo(context.website)
            if logo:
                with factory() as session:
                    own(session, identity, token)
                    session.get(Client, identity).logo_url = logo
                    session.commit()
        if 'pages' not in checkpoint:
            with factory() as session:
                own(session, identity, token, stage='Unternehmenswebsite wird gelesen'); session.commit()
            pages = crawl(context.website)
            checkpoint.update(pages=pages, next_batch=0, answered_keys=[], sources=[], version=onboarding_crawler.VERSION)
            with factory() as session:
                own(session, identity, token, checkpoint=checkpoint); session.commit()
        for index in range(checkpoint.get('next_batch', 0), len(onboarding_crawler.BATCHES)):
            with factory() as session:
                own(session, identity, token, stage=f'Öffentliche Recherche {index + 1}/{len(onboarding_crawler.BATCHES)}'); session.commit()
            answers = research(context, onboarding_crawler.BATCHES[index], checkpoint['pages'])
            checkpoint = {**checkpoint, 'next_batch': index + 1,
                'answered_keys': sorted(set(checkpoint.get('answered_keys', [])) | {a['key'] for a in answers}),
                'sources': sorted(set(checkpoint.get('sources', [])) | {a['source_url'] for a in answers})}
            with factory() as session:
                own(session, identity, token, checkpoint=checkpoint)
                store_facts(session, identity, answers)
                session.commit()
        with factory() as session:
            job = own(session, identity, token, stage='Persönlicher Link wird vorbereitet')
            client = session.get(Client, identity)
            if not client.active or client.is_competitor: raise ValueError('Mandat ist nicht aktiv.')
            prefill, _ = customer_onboarding.prepare(session, client)
            invite = session.get(CustomerOnboardingInvite, job.invite_id) if job.invite_id else None
            if not invite_path(invite):
                invite = issue_invite(session, identity, prefill)
            elif not invite.prefill_confirmed:
                invite.prefill = prefill
            job.invite_id = invite.id; job.status = 'ready'; job.stage = 'Bereit für den Kunden'
            job.note = ''; job.lease_until = None
            session.commit()
    except Superseded:
        return
    except Exception as exc:
        if is_quota_error(exc):
            pause = PAUSE_MINUTE if 'per minute' in str(exc).lower() else PAUSE_LONG
            _log.warning('Onboarding research for client %s paused %s: search quota spent', identity, pause)
            with factory() as session:
                try:
                    own(session, identity, token)
                    session.execute(update(CustomerOnboardingJob).where(CustomerOnboardingJob.client_id == identity,
                        CustomerOnboardingJob.token == token).values(status='queued', token='',
                        stage='Wartet auf Recherche-Kontingent', lease_until=dt.datetime.now(dt.UTC) + pause))
                    session.commit()
                except Superseded:
                    session.rollback()
            return
        _log.exception('Customer onboarding failed for client %s', identity)
        with factory() as session:
            try:
                own(session, identity, token, status='failed', stage='Recherche unterbrochen',
                    note='Die Recherche konnte nicht abgeschlossen werden. Website und Recherche-Zugang prüfen und fortsetzen. Gespeicherte Ergebnisse bleiben erhalten.')
                session.commit()
            except Superseded:
                session.rollback()


def status(session, client):
    job = session.get(CustomerOnboardingJob, client.id)
    contact = {key: getattr(client, key) for key in ('contact_name', 'contact_email', 'contact_role', 'contact_phone')}
    if not job: return dict(status='not_started', contact=contact)
    invite = session.get(CustomerOnboardingInvite, job.invite_id) if job.invite_id else None
    checkpoint = job.checkpoint
    return dict(status=job.status, stage=job.stage, note=job.note, outdated=outdated(checkpoint),
        completed_batches=checkpoint.get('next_batch', 0), total_batches=len(onboarding_crawler.BATCHES),
        researched_fields=len(checkpoint.get('answered_keys', [])), total_fields=len(onboarding_crawler.PUBLIC_FIELDS),
        sources=len(checkpoint.get('sources', [])), pages=len(checkpoint.get('pages', [])),
        path=invite_path(invite, client.name), invite_id=job.invite_id, expires_at=invite.expires_at.isoformat() if invite else None,
        answered=customer_onboarding.answered(invite.answers) if invite else 0,
        total_questions=len(customer_onboarding.QUESTION_KEYS),
        completed=bool(invite and invite.completed_at), contact=contact)


def backfill(session):
    """Queue the topic research once for every active mandate that has not had it.

    Covers mandates created before the onboarding queue existed and those
    researched under the old field catalogue. A failed run is picked up again
    where it stopped: once per restart, so a broken one never loops.
    """
    queued = 0
    for client in session.scalars(select(Client).where(Client.active.is_(True), Client.is_competitor.is_(False))):
        job = session.get(CustomerOnboardingJob, client.id)
        if job is None or job.status == 'failed' or job.status == 'ready' and outdated(job.checkpoint):
            enqueue(session, client, retry=True)
            queued += 1
    session.commit()
    return queued


def start():
    stop = threading.Event()
    def loop():
        factory = session_factory()
        try:
            with factory() as session:
                if queued := backfill(session):
                    _log.info('Topic research queued for %d existing mandate(s)', queued)
        except Exception:
            _log.exception('Topic research backfill failed')
        while not stop.is_set():
            try:
                with factory() as session: item = claim(session)
                if item: work(factory, *item)
            except Exception:
                _log.exception('Customer onboarding queue tick failed')
            stop.wait(3)
    threading.Thread(target=loop, daemon=True, name='customer-onboarding').start()
    return stop
