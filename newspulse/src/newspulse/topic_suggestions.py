"""Keep a source-backed proposal available without blocking the Themen page."""
import datetime as dt
import json
import logging
from importlib import resources
from string import Template

from pydantic import BaseModel, Field, StrictInt

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from . import angles, brain, guide, quoting, prose
from .models import Angle, Article, Client, OpportunityWorkspace, Setting, TopicHit, Analysis

log = logging.getLogger(__name__)
WINDOW = dt.timedelta(days=28)


class TopicIdea(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    situation: str = Field(min_length=1, max_length=3000)
    relevance: str = Field(min_length=1, max_length=3000)
    pitch: str = Field(min_length=1, max_length=3000)
    evidence: list[StrictInt] = Field(min_length=1, max_length=10)


class Suggestions(BaseModel):
    topics: list[TopicIdea] = Field(max_length=2)
    note: str = ''


def _parse(raw):
    from .analyzer import strip_code_fence
    return Suggestions.model_validate_json(strip_code_fence(raw))


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
            Article.published_at >= now - WINDOW, Article.published_at <= now).order_by(Article.published_at.desc()).limit(100)))
        if not articles:
            finish(session, client_id, lease, 'empty', 'Noch keine neuen Meldungen der letzten vier Wochen für einen weiteren Themenvorschlag.')
            return
        from .analyzer import invoke_with_fallback
        written_under = brain.version(session)
        template = resources.files('newspulse').joinpath('prompts/topic_suggestions.txt').read_text('utf-8')
        material = '\n'.join(f'[{i}] {a.published_at:%d.%m.%Y} | {a.source}: {a.title}\n{(a.summary_text or "")[:800]}'
                             for i, a in enumerate(articles))
        prompt = Template(brain.compose(template)).substitute(profile=angles._client_profile(client),
            guide=guide.for_prompt(client), articles=quoting.fence(material, label='MELDUNGEN'))
        call = invoke or invoke_with_fallback
        try:
            result = _parse(call(prompt, timeout=300))
        except ValueError:
            result = _parse(call(prompt + "\nFORMAT: Genau ein JSON-Objekt nach dem Schema, mit topics und note, ohne weiteren Text.", timeout=300))
        if not result.topics:
            finish(session, client_id, lease, 'empty', result.note or 'Aus den aktuellen Meldungen ergibt sich noch kein belastbares Thema.')
            return
        # Validate every citation before saving any of the proposals.
        if any(any(i < 0 or i >= len(articles) for i in idea.evidence) for idea in result.topics):
            raise ValueError('Proposal contains an unknown source reference')
        for idea in result.topics:
            session.add(Angle(client_id=client_id, subject=prose.plain(idea.title),
                message=prose.plain(idea.pitch), thesis=prose.plain(idea.pitch),
                context=prose.plain(idea.situation), credibility=prose.plain(idea.relevance),
                statements=[prose.plain(idea.pitch)], article_ids=list(dict.fromkeys(articles[i].id for i in idea.evidence)),
                brain_version=brain.stamp(written_under, what='this automatic topic suggestion')))
        finish(session, client_id, lease, 'ready', '')
    except Exception:
        session.rollback()
        log.exception('Automatic Themen suggestion failed for client %s', client_id)
        finish(session, client_id, lease, 'failed', 'Der Themenvorschlag konnte nicht erstellt werden. RAUTE versucht es beim nächsten Öffnen nach 30 Minuten erneut.')
