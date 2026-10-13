"""Durable onboarding queue: crawl, grounded workbook research, personal link."""
import base64
import datetime as dt
import hashlib
import hmac
import logging
import os
import secrets
import threading
import tempfile
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import or_, select, update
from . import config, customer_onboarding, onboarding_crawler, twin
from .db import session_factory
from .evidence import Confidentiality, EvidenceType, SourceType
from .models import Client, ClientFact, CustomerOnboardingInvite, CustomerOnboardingJob

_log = logging.getLogger(__name__)
LEASE = dt.timedelta(minutes=8)


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


def invite_path(invite):
    if not invite or invite.revoked or invite.expires_at <= dt.datetime.now(dt.UTC): return None
    token = invite_token(invite)
    if not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), invite.token_hash): return None
    return '/onboarding#' + token


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
    elif retry and row.status == 'failed':
        row.status = 'queued'; row.note = ''; row.token = ''; row.lease_until = None
        if row.checkpoint.get('next_batch', 0) >= len(onboarding_crawler.BATCHES):
            row.checkpoint = {}  # A completed but empty search must be retryable.
    return row


def claim(session):
    now = dt.datetime.now(dt.UTC)
    eligible = or_(CustomerOnboardingJob.status == 'queued',
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
                                      country=client.country, industry=client.industry)
            checkpoint = dict(job.checkpoint)
            session.commit()
        if 'pages' not in checkpoint:
            with factory() as session:
                own(session, identity, token, stage='Unternehmenswebsite wird gelesen'); session.commit()
            pages = crawl(context.website)
            checkpoint.update(pages=pages, next_batch=0, answered_keys=[], sources=[])
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
            prefill, _, _ = customer_onboarding.prepare(session, client, research=False)
            invite = issue_invite(session, identity, prefill)
            job.invite_id = invite.id; job.status = 'ready'; job.stage = 'Bereit für den Kunden'
            job.note = ''; job.lease_until = None
            session.commit()
    except Superseded:
        return
    except Exception:
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
    return dict(status=job.status, stage=job.stage, note=job.note,
        completed_batches=checkpoint.get('next_batch', 0), total_batches=len(onboarding_crawler.BATCHES),
        researched_fields=len(checkpoint.get('answered_keys', [])), total_fields=len(onboarding_crawler.PUBLIC_FIELDS),
        sources=len(checkpoint.get('sources', [])), pages=len(checkpoint.get('pages', [])),
        path=invite_path(invite), invite_id=job.invite_id, expires_at=invite.expires_at.isoformat() if invite else None,
        answered=sum(bool(a.get('value')) for a in invite.answers.values()) if invite else 0,
        completed=bool(invite and invite.completed_at), contact=contact)


def start():
    stop = threading.Event()
    def loop():
        factory = session_factory()
        while not stop.is_set():
            try:
                with factory() as session: item = claim(session)
                if item: work(factory, *item)
            except Exception:
                _log.exception('Customer onboarding queue tick failed')
            stop.wait(3)
    threading.Thread(target=loop, daemon=True, name='customer-onboarding').start()
    return stop
