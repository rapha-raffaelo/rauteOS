"""A unified read model around detected opportunities and developed angles."""
from __future__ import annotations
import datetime as dt
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import journalists, twin
from .models import (Angle, Article, Asset, ClientFact, Contact, NewsjackOpportunity, OpportunityEvent,
                     OpportunityWorkspace, Standing)

SPEAKER_KEYS={'ceo','sprecher','pressekontakt','A11.01'}


def anchor(session,client_id,kind,identity):
    model=NewsjackOpportunity if kind=='detected' else Angle if kind=='developed' else None
    row=session.get(model,identity) if model else None
    if row is None or row.client_id!=client_id:
        return None
    if kind=='detected' and row.standing!=Standing.BELEGT:
        return None
    return row


def stored(session,client_id,kind,identity):
    return session.scalar(select(OpportunityWorkspace).where(OpportunityWorkspace.client_id==client_id,
        OpportunityWorkspace.context_kind==kind,OpportunityWorkspace.context_id==identity))


def speakers(session,client_id):
    return [r for r in twin.all_statements(session,client_id) if r.key in SPEAKER_KEYS
            and r.value.strip() and not twin.externally_blocked(r)]


def ended(row,kind,now):
    return bool(row.dismissed_at or (kind=='detected' and row.window_ends_at<=now))


def read(session: Session,client_id,kind,identity):
    row=anchor(session,client_id,kind,identity)
    if row is None:
        return None
    saved=stored(session,client_id,kind,identity)
    info=saved.data if saved else {}
    now=dt.datetime.now(dt.UTC)
    article=session.get(Article,row.article_id) if kind=='detected' else None
    angle=row if kind=='developed' else session.scalar(select(Angle).where(Angle.newsjack_id==identity))
    sources=info.get('sources',[])
    if not sources:
        ids=[row.article_id] if kind=='detected' else row.article_ids
        sources=[dict(journalists.article_dict(a),article_id=a.id) for a in session.scalars(select(Article).where(Article.id.in_(ids)))
                 if journalists.public_url(a.url)]
    assets=list(session.scalars(select(Asset).where(Asset.angle_id==angle.id).order_by(Asset.generated_at.desc()))) if angle else []
    events=list(session.scalars(select(OpportunityEvent).where(OpportunityEvent.workspace_id==saved.id)
        .order_by(OpportunityEvent.created_at.desc(),OpportunityEvent.id.desc()).limit(200))) if saved else []
    title=article.title if article else row.reason if kind=='detected' else row.subject
    status='closed' if ended(row,kind,now) else saved.status if saved else 'draft'
    return dict(client_id=client_id,context_kind=kind,context_id=identity,id=saved.id if saved else None,
        title=title,revision=saved.revision if saved else 0,status=status,
        evidence_type=info.get('evidence_type','External Observation' if kind=='detected' else 'RAUTE Hypothesis'),
        situation=info.get('situation',article.title if article else row.context if kind=='developed' else row.reason),
        relevance=info.get('relevance',row.reason if kind=='detected' else row.credibility or row.message),
        why_now=info.get('why_now','Aktuelles Nachrichtenfenster' if kind=='detected' else 'Zeitfenster noch zu prüfen'),
        window_ends_at=row.window_ends_at if kind=='detected' else None,
        proposed_window_days=info.get('window_days'),storylines=info.get('storylines',angle.statements if angle else []),
        storyline=saved.storyline if saved else angle.thesis if angle else '',
        speaker_statement_id=saved.speaker_statement_id if saved else None,
        speakers=[dict(id=r.id,value=r.value,evidence_type=r.evidence_type,external_use=r.external_use) for r in speakers(session,client_id)],
        contact_ids=saved.contact_ids if saved else [],
        contacts=[dict(id=c.id,name=c.name,outlet=c.outlet) for c in session.scalars(select(Contact).order_by(Contact.name))],
        recommended_actions=info.get('recommended_actions',['kundenmail','pitch','statement']),
        risks=info.get('risks',[angle.overclaim] if angle and angle.overclaim else ['Belege und Freigaben vor Verwendung prüfen.']),
        sources=sources,research=info.get('research',[]),research_at=info.get('research_at'),
        proof_points=[twin.snapshot(r) for r in session.scalars(select(ClientFact).where(ClientFact.client_id==client_id,
            ClientFact.id.in_(info.get('proof_statement_ids',[]))))],
        assets=[dict(id=a.id,kind=a.kind,title=a.title,generated_at=a.generated_at,released_at=a.released_at,
                     href=f'/client/{client_id}/advice?eintrag=anlass-{angle.id}#asset-{a.id}') for a in assets],
        events=[dict(id=e.id,kind=e.kind,detail=e.detail,actor=e.actor,created_at=e.created_at) for e in events],
        legacy_href=f'/client/{client_id}/advice?eintrag=anlass-{angle.id}#impulse-{angle.id}' if angle else f'/client/{client_id}/gelegenheit/{identity}')


def listings(session,client_id):
    result=[]
    workspaces={(w.context_kind,w.context_id):w for w in session.scalars(select(OpportunityWorkspace).where(OpportunityWorkspace.client_id==client_id))}
    for kind,model,order in [('detected',NewsjackOpportunity,NewsjackOpportunity.created_at),('developed',Angle,Angle.generated_at)]:
        stmt=select(model).where(model.client_id==client_id)
        if kind=='detected':stmt=stmt.where(model.standing==Standing.BELEGT)
        else:stmt=stmt.where(model.newsjack_id.is_(None))
        for row in session.scalars(stmt.order_by(order.desc()).limit(100)):
            workspace=workspaces.get((kind,row.id))
            article=session.get(Article,row.article_id) if kind=='detected' else None
            result.append(dict(context_kind=kind,context_id=row.id,title=article.title if article else row.reason if kind=='detected' else row.subject,
                status='closed' if ended(row,kind,dt.datetime.now(dt.UTC)) else workspace.status if workspace else 'draft',
                created_at=row.created_at if kind=='detected' else row.generated_at))
    return sorted(result,key=lambda r:r['created_at'],reverse=True)
