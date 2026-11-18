"""Keep a source-backed proposal available without blocking the Themen page."""
import datetime as dt
import json
import hashlib
import logging
from importlib import resources
from string import Template

from pydantic import BaseModel, Field, StrictInt

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from . import angles, brain, guide, quoting, prose, coverage_identity
from .models import Angle, Article, Client, OpportunityWorkspace, Setting, TopicHit, Analysis

log = logging.getLogger(__name__)
WINDOW = dt.timedelta(days=28)


class TopicIdea(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    situation: str = Field(min_length=1, max_length=3000)
    relevance: str = Field(min_length=1, max_length=3000)
    pitch: str = Field(min_length=1, max_length=3000)
    evidence: list[StrictInt] = Field(min_length=1, max_length=10)
    next_steps: list[str] = Field(default_factory=list,max_length=4)


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


def material(session,client_id,now):
    linked=select(TopicHit.article_id).where(TopicHit.client_id==client_id).union(
        select(Analysis.article_id).where(Analysis.client_id==client_id,Analysis.is_relevant.is_(True),Analysis.dismissed_at.is_(None)))
    return list(session.scalars(select(Article).where(Article.id.in_(linked),Article.published_at>=now-WINDOW,
        Article.published_at<=now).order_by(Article.published_at.desc(),Article.id.desc()).limit(100)))


def claim(session, client_id, now=None):
    """Database compare-and-swap lease: concurrent tabs/workers share one call."""
    now = now or dt.datetime.now(dt.UTC)
    signature=hashlib.sha256(','.join(str(a.id) for a in material(session,client_id,now)).encode()).hexdigest()
    row = session.get(Setting, key(client_id))
    previous = row.value if row else None
    old = json.loads(previous) if previous else {}
    if old.get('checked_at'):
        age = now - dt.datetime.fromisoformat(old['checked_at'])
        wait = dt.timedelta(minutes=15 if old['status'] == 'running' else 30 if old['status'] == 'failed' else 360)
        same_input=old.get('input_signature')==signature and old.get('version')==2
        if age < wait and (old['status'] in {'running','failed'} or same_input):
            return None
    job = dict(status='running', checked_at=now.isoformat(),input_signature=signature,version=2,note='RAUTE prüft die Meldungen der letzten vier Wochen.')
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
        # Existing open suggestions must never prevent considering new reports.
        # Used sources (including dismissed topics and alternate section URLs)
        # remain excluded, so refreshing does not resurrect prior proposals.
        used={identity for angle in previous for identity in (angle.article_ids or [])}
        used_keys={coverage_identity.identity(a) for a in session.scalars(select(Article).where(Article.id.in_(used)))}
        articles=[];seen=set(used_keys)
        for article in material(session,client_id,now):
            identity=coverage_identity.identity(article)
            if identity in seen:continue
            seen.add(identity);articles.append(article)
        if not articles:
            finish(session, client_id, lease, 'empty', 'Noch keine neuen Meldungen der letzten vier Wochen für einen weiteren Themenvorschlag.')
            return
        from .analyzer import invoke_with_fallback
        written_under = brain.version(session)
        template = resources.files('newspulse').joinpath('prompts/topic_suggestions.txt').read_text('utf-8')
        article_text = '\n'.join(f'[{i}] {a.published_at:%d.%m.%Y} | {a.source}: {a.title}\n{(a.summary_text or "")[:800]}'
                             for i, a in enumerate(articles))
        prompt = Template(brain.compose(template)).substitute(profile=angles._client_profile(client),
            guide=guide.for_prompt(client), articles=quoting.fence(article_text, label='MELDUNGEN'))
        prompt += '\nBereits vorhandene oder archivierte Themen, nicht erneut vorschlagen:\n' + quoting.fence(json.dumps([a.subject for a in previous[-50:]],ensure_ascii=False),label='BISHERIGE THEMEN')
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
            angle=Angle(client_id=client_id, subject=prose.plain(idea.title),
                message=prose.plain(idea.pitch), thesis=prose.plain(idea.pitch),
                context=prose.plain(idea.situation), credibility=prose.plain(idea.relevance),
                statements=[prose.plain(idea.pitch)], article_ids=list(dict.fromkeys(articles[i].id for i in idea.evidence)),
                brain_version=brain.stamp(written_under, what='this automatic topic suggestion'))
            session.add(angle);session.flush()
            steps=[prose.plain(step.strip())[:1500] for step in idea.next_steps if step.strip()]
            session.add(OpportunityWorkspace(client_id=client_id,context_kind='developed',context_id=angle.id,
                angle_id=angle.id,status='draft',data=dict(origin='pitch',situation=angle.context,relevance=angle.credibility,
                    storylines=[angle.thesis],next_steps=steps,
                    sources=[dict(article_id=articles[i].id,title=articles[i].title,url=articles[i].url,source=articles[i].source,
                        published_at=articles[i].published_at.isoformat()) for i in dict.fromkeys(idea.evidence)])))
        finish(session, client_id, lease, 'ready', '')
    except Exception:
        session.rollback()
        log.exception('Automatic Themen suggestion failed for client %s', client_id)
        finish(session, client_id, lease, 'failed', 'Der Themenvorschlag konnte nicht erstellt werden. RAUTE versucht es nach 30 Minuten erneut.')


def refresh(session):
    """Check new material independently of somebody opening the Themen page."""
    ids=list(session.scalars(select(Client.id).where(Client.active.is_(True),Client.is_competitor.is_(False))))
    for client_id in ids:
        lease=claim(session,client_id)
        if lease:generate(session,client_id,lease)


def agenda_steps(session,client_id):
    items=[]
    workspaces=session.scalars(select(OpportunityWorkspace).where(OpportunityWorkspace.client_id==client_id)
        .order_by(OpportunityWorkspace.created_at.desc()))
    for workspace in workspaces:
        data=workspace.data or {};flow=data.get('workflow',{})
        steps=data.get('next_steps',[])
        if not steps or workspace.status=='closed' or flow.get('completed_at') or flow.get('deactivated_at'):continue
        angle=session.get(Angle,workspace.angle_id) if workspace.angle_id else None
        if not angle or angle.dismissed_at:continue
        items.append(dict(id=f'topic-{workspace.id}',kind='topic',title=angle.subject,reason=angle.credibility,next_steps=steps,
            month=workspace.created_at.strftime('%Y-%m'),day=None,format='',state='angenommen' if workspace.status=='active' else 'vorgeschlagen',
            href=f'/client/{client_id}/themen?kind={workspace.context_kind}&context={workspace.context_id}&step={"assets" if workspace.status=="active" else "blickwinkel"}'))
    return items[:12]
