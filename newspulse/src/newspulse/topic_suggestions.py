"""Keep a source-backed proposal available without blocking the Themen page."""
import datetime as dt
import json
import logging

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from . import angles
from .models import Angle, Article, Client, OpportunityWorkspace, Setting, TopicHit, Analysis

log = logging.getLogger(__name__)
WINDOW = dt.timedelta(days=28)


def key(client_id):
    return f'themen-suggestions:{client_id}'


def state(session, client_id):
    row = session.get(Setting, key(client_id))
    return json.loads(row.value) if row and row.value else {'status': 'idle', 'note': ''}


def claim(session, client_id, now=None):
    """Database compare-and-swap lease: concurrent tabs/workers share one call."""
    now = now or dt.datetime.now(dt.UTC)
    row = session.get(Setting, key(client_id))
    previous = row.value if row else None
    old = json.loads(previous) if previous else {}
    if old.get('checked_at'):
        age = now - dt.datetime.fromisoformat(old['checked_at'])
        wait = dt.timedelta(minutes=15 if old['status'] == 'running' else 30 if old['status'] == 'failed' else 360)
        if age < wait:
            return None
    job = dict(status='running', checked_at=now.isoformat(), note='RAUTE prüft die Meldungen der letzten vier Wochen.')
    value = json.dumps(job)
    if row:
        changed = session.execute(update(Setting).where(Setting.key == key(client_id), Setting.value == previous).values(value=value)).rowcount
        session.commit()
        if not changed:
            return None
    else:
        session.add(Setting(key=key(client_id), value=value))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return None
    return job


def finish(session, client_id, lease, status, note):
    session.execute(update(Setting).where(Setting.key == key(client_id), Setting.value == json.dumps(lease)).values(
        value=json.dumps({**lease, 'status': status, 'note': note})))
    session.commit()


def generate(session, client_id, lease, *, invoke=None):
    now = dt.datetime.fromisoformat(lease['checked_at'])
    try:
        client = session.get(Client, client_id)
        if not client or not client.active or client.is_competitor:
            finish(session, client_id, lease, 'empty', 'Für diesen Kunden werden keine Vorschläge erstellt.')
            return
        previous = list(session.scalars(select(Angle).where(Angle.client_id == client_id)))
        starred = set(session.scalars(select(OpportunityWorkspace.context_id).where(
            OpportunityWorkspace.client_id == client_id, OpportunityWorkspace.context_kind == 'developed',
            OpportunityWorkspace.data['origin'].as_string() == 'medien')))
        if any(a.dismissed_at is None and a.generated_at >= now - WINDOW and a.id not in starred for a in previous):
            finish(session, client_id, lease, 'ready', '')
            return
        # Never resurrect an archived proposal or pitch the same reports again.
        used = {identity for a in previous for identity in (a.article_ids or [])}
        linked = select(TopicHit.article_id).where(TopicHit.client_id == client_id).union(
            select(Analysis.article_id).where(Analysis.client_id == client_id, Analysis.is_relevant.is_(True), Analysis.dismissed_at.is_(None)))
        articles = list(session.scalars(select(Article).where(Article.id.in_(linked), Article.id.not_in(used),
            Article.published_at >= now - WINDOW, Article.published_at <= now).order_by(Article.published_at.desc()).limit(50)))
        if not articles:
            finish(session, client_id, lease, 'empty', 'Noch keine neuen Meldungen der letzten vier Wochen für einen weiteren Themenvorschlag.')
            return
        from .analyzer import ParseError, invoke_with_fallback
        def validated_invoke(prompt, **kwargs):
            call = invoke or invoke_with_fallback
            raw = call(prompt, **kwargs)
            try:
                angles._parse(raw)
            except ParseError:
                raw = call(prompt + "\n\nFORMAT: Antworte ausschließlich mit genau einem JSON-Objekt nach dem Schema. Keine weiteren Objekte, keine Erläuterung außerhalb des JSON.", **kwargs)
            return raw
        notes = []
        result = angles.suggest(session, client, [(a, a.source) for a in articles], note=notes.append,
                                invoke=validated_invoke)
        if result is None:
            finish(session, client_id, lease, 'empty', notes[-1] if notes else 'Aus den aktuellen Meldungen ergibt sich noch kein belastbares Thema.')
            return
        draft, numbered = result
        # angles.suggest strips invented citation IDs. No citation means no proposal.
        if not draft.evidence:
            raise ValueError('Proposal has no valid source references')
        angles.store(session, client, draft, numbered)
        finish(session, client_id, lease, 'ready', '')
    except Exception:
        session.rollback()
        log.exception('Automatic Themen suggestion failed for client %s', client_id)
        finish(session, client_id, lease, 'failed', 'Der Themenvorschlag konnte nicht erstellt werden. RAUTE versucht es beim nächsten Öffnen nach 30 Minuten erneut.')
