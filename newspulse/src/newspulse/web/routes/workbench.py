"""React primary destinations backed by existing ledgers and client management."""
import datetime as dt
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from ... import desk, workspaces
from ...models import Client, Asset, Outreach, ClientAction, Report, OpportunityWorkspace, OpportunityEvent
from .. import frontend
from ..app import get_db, templates
from ..mandates import mandate_or_404
from .today import _fetch_last_run, _local_tz
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


@router.get('/client/{client_id}/overview')
@router.get('/client/{client_id}/actions')
def client_page(client_id: int, request: Request, session: Session = Depends(get_db)):
    return render(request, session, request.url.path.rsplit('/', 1)[-1], mandate_or_404(session, client_id))


def texts(session, client_id=None, released_only=False):
    items = []
    for kind, model in [('asset', Asset), ('outreach', Outreach)]:
        query = select(model, Client.name).join(Client, Client.id == model.client_id).where(Client.is_competitor.is_(False))
        if released_only:
            query = query.where(model.released_at.is_not(None))
        if client_id is not None:
            query = query.where(model.client_id == client_id)
        for row, name in session.execute(query.order_by(model.generated_at.desc()).limit(100)):
            workspace = session.scalar(select(OpportunityWorkspace).where(
                OpportunityWorkspace.client_id == row.client_id,
                OpportunityWorkspace.angle_id == row.angle_id)) if row.angle_id else None
            href = (f'/client/{row.client_id}/opportunities?kind={workspace.context_kind}&context={workspace.context_id}&view=assets&text={kind}-{row.id}'
                if workspace else f'/client/{row.client_id}/advice?eintrag=anlass-{row.angle_id}'
                if row.angle_id else f'/client/{row.client_id}/krise')
            items.append(dict(id=row.id, type=kind, client_id=row.client_id, client=name,
                title=row.title if kind == 'asset' else row.subject,
                format=row.kind if kind == 'asset' else 'pitch', generated_at=row.generated_at,
                released_at=row.released_at,
                href=href))
    return sorted(items, key=lambda r: r['generated_at'], reverse=True)[:100]


@router.get('/api/v1/workbench/clients')
def clients(response: Response, session: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return {'clients': [MandateSummary.model_validate(r) for r in desk.build(session).rows]}


@router.get('/api/v1/workbench/assets')
def assets(response: Response, session: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return {'texts': texts(session), 'limit': 100}


@router.get('/api/v1/workbench/clients/{client_id}')
def overview(client_id: int, response: Response, session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    response.headers['Cache-Control'] = 'no-store'
    summary = next((r for r in desk.build(session).rows if r.client.id == client_id), None)
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
        opportunities=workspaces.listings(session, client_id)[:30], texts=items,
        activity=activity, logged_actions=actions, released_reports=reports, released_texts=texts(session, client_id, released_only=True), limit=100)


# Client management uses the same validation and soft deletion as Settings.
def client_settings(client):
    keys = ('name', 'industry', 'country', 'aliases', 'keywords', 'alert_topics',
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
        fields = _parse_client_form(**body.model_dump(exclude={'revision'}))
        count = fields['actions_per_quarter']
        if body.actions_per_quarter.strip() and (count is None or count > 2147483647):
            raise ValueError('Bitte eine gültige ganze Zahl ab 0 für die Quartalszusage eingeben.')
        update_client(session, client_id, **fields)
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
