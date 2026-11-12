"""A unified read model around detected opportunities and developed angles."""
from __future__ import annotations
import datetime as dt
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import journalists, twin
from .models import (Angle, Article, Asset, Client, ClientFact, Contact, NewsjackOpportunity, OpportunityEvent, Outreach,
                     OpportunityWorkspace, Standing)

_log=logging.getLogger(__name__)
SPEAKER_KEYS={'ceo','sprecher','pressekontakt','A11.01'}


def anchor(session,client_id,kind,identity):
    model=NewsjackOpportunity if kind=='detected' else Angle if kind=='developed' else None
    row=session.get(model,identity) if model else None
    if row is None or row.client_id!=client_id:
        return None
    if kind=='detected' and row.standing!=Standing.BELEGT:
        return None
    return row


def advice_href(client_id,angle_id,anchor=''):
    """The advice page on one occasion. It shows a single occasion, the newest
    unless ``eintrag`` names one, so a link without it lands somewhere else."""
    return f'/client/{client_id}/advice?eintrag=anlass-{angle_id}'+(f'#{anchor}' if anchor else '')


def text_href(session,row,kind='asset'):
    """Where a stored text or letter is read: in its chance if it has one, else
    on its occasion's advice page, and a crisis text in the crisis."""
    if not row.angle_id:
        return f'/client/{row.client_id}/krise'
    if kind=='asset':
        workspace=session.scalar(select(OpportunityWorkspace).where(OpportunityWorkspace.client_id==row.client_id,
            OpportunityWorkspace.angle_id==row.angle_id))
        if workspace:
            return (f'/client/{row.client_id}/assets?kind={workspace.context_kind}&context={workspace.context_id}'
                    f'&text=asset-{row.id}')
        return advice_href(row.client_id,row.angle_id,f'asset-text-{row.id}')
    return advice_href(row.client_id,row.angle_id,f'letter-text-{row.id}')


def stored(session,client_id,kind,identity):
    return session.scalar(select(OpportunityWorkspace).where(OpportunityWorkspace.client_id==client_id,
        OpportunityWorkspace.context_kind==kind,OpportunityWorkspace.context_id==identity))


def speakers(session,client_id):
    """Profile statements that name someone who may be quoted. With media
    contacts in the phone book, "Sprecher" is only their names run together
    (people.sync_profile), so the people are offered instead of that line."""
    from . import people
    keys=SPEAKER_KEYS-{'sprecher'} if people.media(session,client_id) else SPEAKER_KEYS
    return [r for r in twin.all_statements(session,client_id) if r.key in keys
            and r.value.strip() and not twin.externally_blocked(r)]


def speaker_people(session,client_id,title,about,saved):
    """Profile contacts on offer; recommendations remain limited to media contacts."""
    from . import people
    offered=[dict(id=p.id,label=people.label(p),topics=p.topics) for p in people.book(session,client_id)]
    chosen=saved is not None and (saved.speaker_person_id or saved.speaker_statement_id)
    found=None if chosen else people.proposal(session,client_id,f"{title} {about}")
    return offered,(dict(person_id=found[0].id,reason=found[1]) if found else None)


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
    # The pitches written for this chance are letters, not assets; without them a
    # story with a pitch out still reads "Assets" on its steps.
    letters=list(session.scalars(select(Outreach).where(Outreach.angle_id==angle.id).order_by(Outreach.generated_at.desc()))) if angle else []
    events=list(session.scalars(select(OpportunityEvent).where(OpportunityEvent.workspace_id==saved.id)
        .order_by(OpportunityEvent.created_at.desc(),OpportunityEvent.id.desc()).limit(200))) if saved else []
    title=article.title if article else row.reason if kind=='detected' else row.subject
    storyline=saved.storyline if saved else angle.thesis if angle else ''
    about=' '.join([storyline,row.message if kind=='developed' else row.reason,info.get('situation','')])
    people_offered,proposed=speaker_people(session,client_id,title,about,saved)
    status='closed' if ended(row,kind,now) else saved.status if saved else 'draft'
    return dict(client_id=client_id,context_kind=kind,context_id=identity,id=saved.id if saved else None,
        title=title,revision=saved.revision if saved else 0,status=status,angle_id=angle.id if angle else None,
        evidence_type=info.get('evidence_type','External Observation' if kind=='detected' else 'RAUTE Hypothesis'),
        situation=info.get('situation',article.title if article else row.context if kind=='developed' else row.reason),
        relevance=info.get('relevance',row.reason if kind=='detected' else row.credibility or row.message),
        why_now=info.get('why_now',''),
        window_ends_at=row.window_ends_at if kind=='detected' else None,
        proposed_window_days=info.get('window_days'),storylines=info.get('storylines',angle.statements if angle else []),
        storyline=storyline,
        speaker_statement_id=saved.speaker_statement_id if saved else None,
        speaker_person_id=saved.speaker_person_id if saved else None,
        people=people_offered,speaker_proposal=proposed,
        speakers=[dict(id=r.id,value=r.value,evidence_type=r.evidence_type,external_use=r.external_use) for r in speakers(session,client_id)],
        contact_ids=saved.contact_ids if saved else [],
        contacts=[dict(id=c.id,name=c.name,outlet=c.outlet) for c in session.scalars(select(Contact).order_by(Contact.name))],
        recommended_actions=info.get('recommended_actions',[]),
        risks=info.get('risks',[angle.overclaim] if angle and angle.overclaim else []),
        sources=sources,research=info.get('research',[]),research_at=info.get('research_at'),
        proof_points=[twin.snapshot(r) for r in session.scalars(select(ClientFact).where(ClientFact.client_id==client_id,
            ClientFact.id.in_(info.get('proof_statement_ids',[]))))],
        assets=[dict(id=a.id,kind=a.kind,title=a.title,generated_at=a.generated_at,released_at=a.released_at,
                     href=advice_href(client_id,angle.id,f'asset-text-{a.id}')) for a in assets],
        letters=[dict(id=o.id,subject=o.subject,journalist=o.journalist,outlet=o.outlet,state=o.state.value,
                      generated_at=o.generated_at,released_at=o.released_at,href=text_href(session,o,'outreach')) for o in letters],
        events=[dict(id=e.id,kind=e.kind,detail=e.detail,actor=e.actor,created_at=e.created_at) for e in events],
        recipients=recipients(session,client_id,angle),deep_dive=info.get('deep_dive',''),
        origin=_origin(kind,row,saved),starred_by=info.get('starred_by',''),
        legacy_href=advice_href(client_id,angle.id,f'impulse-{angle.id}') if angle else f'/client/{client_id}/gelegenheit/{identity}')


def recipients(session,client_id,angle,limit=3):
    """Who to talk to about this Thema: the bylines of its stories first, then
    the outlets that cover the field (:func:`newspulse.pitch.targets_for`).
    Never a guessed name: an outlet without a byline is named as the outlet."""
    from . import pitch
    try:
        targets=pitch.targets_for(session,session.get(Client,client_id),angle)
    except Exception:  # noqa: BLE001 - the Deep Dive reads without it
        _log.warning('pitch targets for client %s failed',client_id,exc_info=True)
        return []
    return [dict(name=t.journalist or t.outlet,outlet=t.outlet if t.journalist else '',reason=t.reason) for t in targets[:limit]]


def _origin(kind,row,workspace):
    """Where an opportunity came from, which decides its column under Aktivitäten.

    ``anlass``: a market story, detected or drafted by the topic radar.
    ``pitch``: a theme RAUTE developed on request. ``plan``: opened from a plan hook.
    """
    if kind=='detected':return 'anlass'
    if workspace and (workspace.data or {}).get('origin')=='medien':return 'medien'
    if row.plan_hook_id:return 'plan'
    if workspace and (workspace.data or {}).get('development_id'):return 'pitch'
    return 'anlass'


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
            # The story it rests on: the detected one's own article, or the
            # first market report an impulse cites. Shown on the card's hover.
            occasion=article or (session.get(Article,row.article_ids[0]) if kind=='developed' and row.article_ids else None)
            result.append(dict(context_kind=kind,context_id=row.id,title=article.title if article else row.reason if kind=='detected' else row.subject,
                status='closed' if ended(row,kind,dt.datetime.now(dt.UTC)) else workspace.status if workspace else 'draft',
                created_at=row.created_at if kind=='detected' else row.generated_at,
                origin=_origin(kind,row,workspace),
                starred_by=(workspace.data or {}).get('starred_by','') if workspace else '',
                summary=(row.reason if kind=='detected' else row.message or row.context or '')[:400],
                occasion=dict(title=occasion.title,source=occasion.source,published_at=occasion.published_at,url=occasion.url) if occasion else None))
    return sorted(result,key=lambda r:r['created_at'],reverse=True)
