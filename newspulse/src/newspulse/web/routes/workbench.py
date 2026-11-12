"""React primary destinations backed by existing ledgers and client management."""
import datetime as dt
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ... import desk, profile as profiles, worklists, workspaces
from ...assets import CRISIS_REGISTRY, REGISTRY
from .desk_api import DecisionSummary
from ...models import Client, Asset, Outreach, ClientAction, Report, OpportunityWorkspace, OpportunityEvent, Article, Analysis, LinkedInPost, visible_coverage
from .. import frontend
from ..app import get_db, templates
from ..mandates import mandate_or_404
from .today import _fetch_last_run, _local_tz, _day_bounds_utc
from .desk_api import MandateSummary
router = APIRouter()


def render(request, session, page, client=None):
    return templates.TemplateResponse(request, 'workbench_react.html', dict(
        client=client, page=page, frontend=frontend.page_assets('workbench'),
        last_run=_fetch_last_run(session), header_date=dt.datetime.now(_local_tz()).date()))


@router.get('/clients')
@router.get('/assets')
@router.get('/ask')
def global_page(request: Request, session: Session = Depends(get_db)):
    if request.url.path == '/clients' and (request.query_params.get('view') == 'classic' or not frontend.page_assets('workbench')):
        from .client import clients_index
        return clients_index(request, session)
    return render(request, session, request.url.path.strip('/'))


@router.get('/client/{client_id}/monitoring/kpis')
@router.get('/client/{client_id}/monitoring/social')
@router.get('/client/{client_id}/overview')
@router.get('/client/{client_id}/actions')
def client_page(client_id: int, request: Request, session: Session = Depends(get_db)):
    return render(request, session, 'monitoring_kpis' if request.url.path.endswith('/monitoring/kpis') else 'monitoring_social' if request.url.path.endswith('/monitoring/social') else request.url.path.rsplit('/', 1)[-1], mandate_or_404(session, client_id))


def texts(session, client_id=None, released_only=False):
    items = []
    for kind, model in [('asset', Asset), ('outreach', Outreach)]:
        query = select(model, Client.name).join(Client, Client.id == model.client_id).where(Client.is_competitor.is_(False))
        if released_only:
            query = query.where(model.released_at.is_not(None))
        if client_id is not None:
            query = query.where(model.client_id == client_id)
        for row, name in session.execute(query.order_by(model.generated_at.desc()).limit(100)):
            href = workspaces.text_href(session, row, kind)
            fmt = row.kind if kind == 'asset' else 'pitch'
            known = REGISTRY.get(fmt) or CRISIS_REGISTRY.get(fmt)
            title = row.title if kind == 'asset' else row.subject
            items.append(dict(id=row.id, type=kind, client_id=row.client_id, client=name,
                # Formats without a title of their own (LinkedIn, statement, Q&A)
                # are named by their first line rather than "Ohne Titel".
                title=title or worklists.first_line(row.body if kind == 'asset' else row.message),
                format=fmt, format_name=known.name if known else 'Pitch' if fmt == 'pitch' else fmt,
                generated_at=row.generated_at,
                released_at=row.released_at,
                href=href))
    return sorted(items, key=lambda r: r['generated_at'], reverse=True)[:100]


@router.get('/api/v1/workbench/clients')
def clients(response: Response, session: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return {'clients': [MandateSummary.model_validate(r) for r in desk.build(session).rows]}


@router.get('/api/v1/workbench/assets')
def assets(response: Response, session: Session = Depends(get_db), client_id: int | None = None):
    response.headers['Cache-Control'] = 'no-store'
    if client_id is not None:
        mandate_or_404(session, client_id)
    clients = session.scalars(select(Client).where(Client.is_competitor.is_(False)).order_by(Client.name)).all()
    counts = {}
    for model in (Asset, Outreach):
        for cid, count in session.execute(select(model.client_id, func.count()).group_by(model.client_id)):
            counts[cid] = counts.get(cid, 0) + count
    total = sum(counts.get(c.id, 0) for c in clients)
    selected_total = counts.get(client_id, 0) if client_id is not None else total
    return {'texts': texts(session, client_id), 'limit': 100,
            'clients': [dict(id=c.id, name=c.name, count=counts.get(c.id, 0)) for c in clients],
            'total': total, 'truncated': selected_total > 100}


@router.get('/api/v1/workbench/clients/{client_id}')
def overview(client_id: int, response: Response, session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    response.headers['Cache-Control'] = 'no-store'
    board = desk.build(session)
    summary = next((r for r in board.rows if r.client.id == client_id), None)
    items = texts(session, client_id)
    actions = [dict(id=r.id, title=r.title, happened_at=r.happened_at, note=r.note)
        for r in session.scalars(select(ClientAction).where(ClientAction.client_id == client_id)
            .order_by(ClientAction.happened_at.desc()).limit(100))]
    reports = [dict(id=r.id, title=f'Bericht {r.period_start:%m.%Y}', happened_at=r.released_at)
        for r in session.scalars(select(Report).where(Report.client_id == client_id,
            Report.released_at.is_not(None)).order_by(Report.released_at.desc()).limit(100))]
    activity = [dict(id=event.id, kind=event.kind, actor=event.actor,
        happened_at=event.created_at, title=event.detail.get('title', ''),
        format=event.detail.get('kind', ''),
        selected_journalists=len(event.detail.get('contact_ids', [])),
        href=f'/client/{client_id}/opportunities?kind={workspace.context_kind}&context={workspace.context_id}')
        for event, workspace in session.execute(select(OpportunityEvent, OpportunityWorkspace)
            .join(OpportunityWorkspace, OpportunityWorkspace.id == OpportunityEvent.workspace_id)
            .where(OpportunityWorkspace.client_id == client_id)
            .order_by(OpportunityEvent.created_at.desc(), OpportunityEvent.id.desc()).limit(100))]
    return dict(client={'id': client.id, 'name': client.name},
        summary=MandateSummary.model_validate(summary) if summary else None,
        # Closed ones left out before the cut, so thirty closed ones cannot hide an open one.
        opportunities=[r for r in workspaces.listings(session, client_id) if r['status'] != 'closed'][:30], texts=items,
        company=company(session, client),
        today_news=today_news(session, client_id),
        next_steps=next_steps(board, client_id),
        activity=activity, logged_actions=actions, released_reports=reports, released_texts=texts(session, client_id, released_only=True), limit=100)


#: How many entries "Nächste Schritte" carries on a mandate's overview.
NEXT_STEPS_SHOWN = 5


def next_steps(board, client_id: int) -> list[dict]:
    """The mandate's open tasks, due first, then its open decisions (spec 10)."""
    tasks = [dict(kind='aufgabe', title=t.title, href=t.href,
                  detail=' · '.join(filter(None, [', '.join(f'@{a}' for a in t.assignees),
                                                  f'fällig {t.due_on:%d.%m.%Y}' if t.due_on else ''])),
                  since=None)
             for t in board.all_tasks if t.client and t.client.id == client_id]
    decisions = [DecisionSummary.model_validate(d).model_dump() for d in board.decisions if d.client.id == client_id]
    return (tasks + decisions)[:NEXT_STEPS_SHOWN]


#: How many running stories head "Stories & Content" (spec 09).
STORIES_SHOWN = 9


def stories(session: Session) -> list[dict]:
    """The open opportunities of every active mandate, newest first: the
    prototype's story cards. The Desk's own list, only longer."""
    mandates = session.scalars(select(Client).where(Client.active.is_(True), Client.is_competitor.is_(False))).all()
    return [dict(client=dict(id=c.client.id, name=c.client.name), kind=c.kind, title=c.title,
                 status=c.status, since=c.since, href=c.href)
            for c in desk._chances(session, {m.id: m for m in mandates}, limit=STORIES_SHOWN)]


#: What the overview's "Das Unternehmen" card reads: the researched
#: description and the client's own answer on its goals (spec 09).
DESCRIPTION_KEY, GOAL_KEY = 'R05.01', 'Q01.02'
#: A card, not the profile: the first sentences up to this many characters.
CARD_CHARS = 280


def _clip(text: str, limit: int = CARD_CHARS) -> str:
    text = ' '.join((text or '').split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '))
    return cut[:end + 1] if end > limit // 3 else cut.rsplit(' ', 1)[0] + ' …'


def company(session: Session, client: Client) -> dict:
    facts = profiles.stored(session, client.id)
    value = lambda key: facts[key].value if key in facts else ''
    tags = [t for t in [client.industry, *(client.keywords or [])[:3]] if t]
    return dict(description=_clip(value(DESCRIPTION_KEY)), goal=_clip(value(GOAL_KEY), 200), tags=tags[:4],
                legal_name=client.legal_name)


# Client management uses the same validation and soft deletion as Settings.
def client_settings(client):
    keys = ('name', 'legal_name', 'industry', 'country', 'aliases', 'keywords', 'alert_topics',
            'excluded_terms', 'required_terms', 'actions_per_quarter')
    values = {}
    for key in keys:
        value = getattr(client, key)
        values[key] = ', '.join(value or []) if isinstance(value, list) else str(value) if value is not None else ''
    revision = hashlib.sha256(json.dumps([values, client.active], sort_keys=True).encode()).hexdigest()
    return dict(values=values, revision=revision)


class ClientSettingsInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str
    industry: str
    country: str
    aliases: str
    keywords: str
    alert_topics: str
    excluded_terms: str
    required_terms: str
    actions_per_quarter: str
    legal_name: str = ''
    revision: str


@router.get('/api/v1/workbench/clients/{client_id}/settings')
def read_client_settings(client_id: int, response: Response, session: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return client_settings(mandate_or_404(session, client_id))


@router.put('/api/v1/workbench/clients/{client_id}/settings')
def save_client_settings(client_id: int, body: ClientSettingsInput, session: Session = Depends(get_db)):
    from ...clients import update_client
    from .settings import _parse_client_form
    client = mandate_or_404(session, client_id)
    if not client.active or body.revision != client_settings(client)['revision']:
        raise HTTPException(409, 'Der Mandant wurde inzwischen geändert. Bitte schließen und erneut öffnen.')
    try:
        fields = _parse_client_form(**body.model_dump(exclude={'revision', 'legal_name'}))
        count = fields['actions_per_quarter']
        if body.actions_per_quarter.strip() and (count is None or count > 2147483647):
            raise ValueError('Bitte eine gültige ganze Zahl ab 0 für die Quartalszusage eingeben.')
        update_client(session, client_id, **fields)
        from .settings import _set_legal_name
        _set_legal_name(session, client_id, body.legal_name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return dict(id=client.id, name=client.name)


class ClientDeleteInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str


@router.delete('/api/v1/workbench/clients/{client_id}')
def delete_client(client_id: int, body: ClientDeleteInput, session: Session = Depends(get_db)):
    from ...clients import deactivate_client
    client = mandate_or_404(session, client_id)
    if body.name != client.name:
        raise HTTPException(409, 'Der Mandantenname wurde inzwischen geändert. Bitte die Liste neu laden.')
    deactivate_client(session, client_id)
    return dict(id=client.id, deleted=True)


def today_news(session, client_id, *, now=None):
    day = (now or dt.datetime.now(_local_tz())).astimezone(_local_tz()).date()
    start, end = _day_bounds_utc(day)
    where = (Analysis.client_id == client_id, visible_coverage(), Article.published_at >= start, Article.published_at < end)
    total = session.scalar(select(func.count()).select_from(Analysis).join(Article).where(*where))
    rows = session.execute(select(Article, Analysis).join(Analysis, Analysis.article_id == Article.id).where(*where)
        .order_by(Article.published_at.desc(), Article.id.desc()))
    # The archive's newest rows before today, so a quiet morning still shows
    # what the press wrote last; the Überblick tops today up to RECENT_SHOWN.
    earlier = session.execute(select(Article, Analysis).join(Analysis, Analysis.article_id == Article.id)
        .where(Analysis.client_id == client_id, visible_coverage(), Article.published_at < start)
        .order_by(Article.published_at.desc(), Article.id.desc()).limit(RECENT_SHOWN))
    return dict(date=day, total=total, items=[_news(a, v) for a, v in rows],
                earlier=[_news(a, v) for a, v in earlier])


#: How many articles the Überblick shows when today has fewer.
RECENT_SHOWN = 5


def _news(a, v):
    return dict(id=a.id, analysis_id=v.id, title=a.title, url=a.url, source=a.source,
                published_at=a.published_at, summary=v.summary or '', important=v.is_alert,
                category=v.category.value, importance=v.importance_score)


@router.get('/api/v1/workbench/clients/{client_id}/monitoring/social')
def social_monitoring(client_id: int, response: Response, session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    response.headers['Cache-Control'] = 'no-store'
    rows = session.scalars(select(LinkedInPost).where(LinkedInPost.client_id == client_id,
        LinkedInPost.status == 'veroeffentlicht').order_by(LinkedInPost.updated_at.desc()).limit(100)).all()
    return dict(client=dict(id=client.id,name=client.name),metrics_connected=False,limit=100,
        posts=[dict(id=r.id,title=r.title,author=r.author,url=r.published_url,recorded_at=r.updated_at) for r in rows])
