"""Read-only, bounded context for Ask RAUTE's four scopes."""
from __future__ import annotations
import json
from sqlalchemy import select
from . import desk, twin, workspaces, quoting
from .models import Client, Asset, Outreach, OpportunityAssetRun, JournalistResearch


def build(session, *, client_id=None, scope=None, opportunity_kind=None,
          opportunity_id=None, asset_type=None, asset_id=None):
    scope = scope or ('client' if client_id else 'global')
    if scope not in {'global', 'client', 'opportunity', 'asset'}:
        raise ValueError('Unbekannter Kontext')
    if scope == 'global' and client_id is not None:
        raise ValueError('Globaler Kontext enthält keinen Mandanten')
    for value in (client_id, opportunity_id, asset_id):
        if value is not None and not 0 < value <= 2**63 - 1:
            raise LookupError('Kontext nicht gefunden')
    client = session.get(Client, client_id) if client_id else None
    if scope != 'global' and (client is None or client.is_competitor):
        raise LookupError('Mandant nicht gefunden')
    if scope != 'opportunity' and (opportunity_kind is not None or opportunity_id is not None):
        raise ValueError('Opportunity gehört nicht zu diesem Kontext')
    if scope != 'asset' and (asset_type is not None or asset_id is not None):
        raise ValueError('Text gehört nicht zu diesem Kontext')
    data = {'scope': scope, 'client': client.name if client else None}
    if scope == 'global':
        view = desk.build(session)
        data['as_of'] = view.generated_at
        data['scope_note'] = 'Bis zu 60 Mandate und 30 offene Entscheidungen.'
        data['mandates'] = [dict(client_id=r.client.id, name=r.client.name,
            opportunities=r.opportunities, delivered_quarter=r.actions_quarter.total,
            promised_quarter=r.promised_quarter, on_track=r.on_track,
            twin_gaps=r.twin.gaps) for r in view.rows[:60]]
        data['decisions'] = [dict(title=r.title, detail=r.detail, href=r.href) for r in view.decisions[:30]]
    else:
        rows = twin.all_statements(session, client_id)
        data['twin_completeness'] = twin.completeness(rows)
        if scope == 'client':
            data['opportunities'] = workspaces.listings(session, client_id)[:30]
        elif scope == 'opportunity':
            workspace = workspaces.read(session, client_id, opportunity_kind, opportunity_id)
            if workspace is None:
                raise LookupError('Opportunity nicht gefunden')
            workspace['contacts'] = [c for c in workspace['contacts'] if c['id'] in workspace['contact_ids']][:20]
            workspace['events'] = workspace['events'][:20]
            workspace['assets'] = workspace['assets'][:20]
            data['opportunity'] = workspace
            research = session.scalar(select(JournalistResearch).where(
                JournalistResearch.client_id == client_id,
                JournalistResearch.context_kind == opportunity_kind,
                JournalistResearch.context_id == opportunity_id)
                .order_by(JournalistResearch.started_at.desc()).limit(1))
            if research:
                data['journalist_research'] = dict(status=research.status,
                    finished_at=research.finished_at, providers=research.providers,
                    results=research.results[:10], note=research.note)
        else:
            model = Asset if asset_type == 'asset' else Outreach if asset_type == 'outreach' else None
            row = session.get(model, asset_id) if model and asset_id else None
            if row is None or row.client_id != client_id:
                raise LookupError('Text nicht gefunden')
            data['asset'] = dict(id=row.id, type=asset_type,
                title=row.title if asset_type == 'asset' else row.subject,
                body=(row.body if asset_type == 'asset' else row.message)[:40000],
                released_at=row.released_at)
            field = OpportunityAssetRun.asset_id if asset_type == 'asset' else OpportunityAssetRun.outreach_id
            run = session.scalar(select(OpportunityAssetRun).where(field == row.id)
                .order_by(OpportunityAssetRun.id.desc()).limit(1))
            if run:
                data['dated_check'] = dict(quality=run.quality, checked_at=run.finished_at,
                    text_digest=run.text_digest, note='Historischer Vergleich; kann nach Änderungen veraltet sein.')
                data['source_context'] = {k: v for k, v in run.context.items() if k not in {'statements', 'guide'}}
    # JSON is quoted material, never instructions. Avoid chopping serialized JSON.
    return scope, quoting.fence(json.dumps(data, ensure_ascii=False, default=str), label='ASK RAUTE KONTEXT')
