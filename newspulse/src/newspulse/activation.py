"""Draft and review opportunity assets using explicit saved context."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from sqlalchemy import select,update
from . import asset_evidence,assets,journalists,outreach,profile,quoting,twin,workspaces
from .analyzer import invoke_with_fallback
from .models import (Angle,Asset,Client,ClientFact,Contact,JournalistProfile,OpportunityAssetRun,OpportunityEvent,
                     OpportunityWorkspace,Outreach)
from .pitch import PitchTarget

FORMATS=[('kundenmail','Kundenmail'),('pitch','Journalistenpitch'),('statement','Statement'),
    ('pressemitteilung','Pressemitteilung'),('qa','Q&A'),('gastbeitrag','Gastbeitrag'),
    ('interviewangebot','Interviewangebot'),('linkedin','LinkedIn-Post'),('interview_briefing','Briefing'),('custom','Eigene Aktion')]


def fingerprint(session,workspace):
    client=session.get(Client,workspace.client_id)
    contacts=[(c.id,c.updated_at.isoformat(),p.revision if (p:=session.get(JournalistProfile,c.id)) else 0)
        for c in session.scalars(select(Contact).where(Contact.id.in_(workspace.contact_ids)))]
    return hashlib.sha256(json.dumps(dict(revision=workspace.revision,guide=client.comms_guide,contacts=contacts,
        statements=[(r.id,r.revision) for r in twin.all_statements(session,client.id)]),sort_keys=True).encode()).hexdigest()


def context_for(session,workspace,*,contact_id=None,instruction=''):
    client=session.get(Client,workspace.client_id)
    all_facts=twin.all_statements(session,client.id)
    available={r.id:r for r in workspaces.speakers(session,client.id)}
    speaker=available.get(workspace.speaker_statement_id)
    if workspace.speaker_statement_id and speaker is None:
        raise ValueError('Der gewählte Sprecher ist nicht mehr verwendbar. Auswahl im Workspace prüfen.')
    target=None;person=None
    if contact_id:
        contact=session.get(Contact,contact_id)
        if contact is None:raise ValueError('Kontakt nicht mehr vorhanden.')
        p=session.get(JournalistProfile,contact_id)
        if p and p.relationship_status=='Nicht kontaktieren':raise ValueError('Dieser Kontakt darf nicht kontaktiert werden.')
        person=journalists.profile_data(session,contact)
        since=dt.datetime.now(dt.UTC)-dt.timedelta(days=42)
        person['articles']=[a for a in person['articles'] if since<=dt.datetime.fromisoformat(a['published_at'])<=dt.datetime.now(dt.UTC)][:8]
        target=PitchTarget(outlet=contact.outlet,journalist=contact.name,reason='Explizit im Workspace ausgewählt',
            evidence=tuple(a['title'] for a in person['articles']),about_client=None,contact_id=contact.id,contact_email=contact.email)
        # Only the fields the writer needs; no addresses or unrelated private notes.
        person['contact']={k:person['contact'][k] for k in ('id','name','outlet','position','beat')}
        person['relationship']['timeline']=person['relationship']['timeline'][:20]
    sources=list(workspace.data.get('sources',[]))
    angle=session.get(Angle,workspace.angle_id)
    if angle:
        from .models import Article
        sources += [journalists.article_dict(a) for a in session.scalars(select(Article).where(Article.id.in_(angle.article_ids))) if journalists.public_url(a.url)]
    if person:sources+=person['articles']
    sources=list({s['url']:s for s in sources}.values())[:40]
    context=dict(workspace_id=workspace.id,workspace_revision=workspace.revision,client_id=client.id,
        storyline=workspace.storyline,speaker=twin.snapshot(speaker) if speaker else None,
        statements=[twin.snapshot(r) for r in all_facts],sources=sources,guide=client.comms_guide or '',
        journalist=person,instruction=instruction,fingerprint=fingerprint(session,workspace))
    return json.loads(json.dumps(context,default=str)),target



def writing_facts(session,workspace,context):
    facts=profile.stored(session,workspace.client_id)
    for key,row in list(facts.items()):
        if twin.externally_blocked(row):del facts[key]
    if context['speaker']:
        facts['ceo']=session.get(ClientFact,context['speaker']['id'])
    return facts

def writing_context(context):
    # The checker sees the full Twin; the writer only gets externally usable
    # statements. Their classification and approval requirements remain attached.
    allowed=[r for r in context['statements'] if r['fact_status'] not in twin.INACTIVE
        and r['external_use']!='Internal Only' and r['confidentiality'] not in
        {'Client Confidential','RAUTE Internal','Highly Restricted'}]
    data={**context,'statements':allowed}
    return ('WORKSPACE-AUFTRAG\nDie gewählte Storyline und der gewählte Sprecher gelten für diesen Entwurf. '
        'Journalistenangaben dienen der konkreten Ansprache. Keine fehlende Veröffentlichung behaupten. '
        'Twin-Aussagen behalten Herkunft, Status und Freigabegrenzen. Vertrauliche oder rein interne Aussagen '
        'nicht aus einer Gelegenheit rekonstruieren. Kundenmail: Vorschlag zur Freigabe, keine behauptete Zusage.\n'
        +quoting.fence(json.dumps(data,ensure_ascii=False,default=str),label='Gespeicherter Workspace-Kontext'))


def text_row(session,job):
    return session.get(Asset,job.asset_id) if job.asset_id else session.get(Outreach,job.outreach_id) if job.outreach_id else None


def text_parts(row):
    return (row.title,row.body) if isinstance(row,Asset) else (row.subject,row.message)



def current_draft(session,workspace,kind,target):
    if kind=='pitch':
        row=session.scalar(select(Outreach).where(Outreach.angle_id==workspace.angle_id,
            Outreach.journalist==target.journalist,Outreach.outlet==target.outlet,Outreach.released_at.is_(None))
            .order_by(Outreach.id.desc()).limit(1).with_for_update())
    else:
        row=session.scalar(select(Asset).where(Asset.angle_id==workspace.angle_id,Asset.kind==kind,
            Asset.released_at.is_(None)).order_by(Asset.id.desc()).limit(1).with_for_update())
    return [row.id,asset_evidence.digest(*text_parts(row))] if row else None

def run(session,identity,*,invoke=invoke_with_fallback,review_invoke=None):
    job=session.get(OpportunityAssetRun,identity)
    if job is None or job.status!='running':return
    workspace=session.get(OpportunityWorkspace,job.workspace_id)
    client=session.get(Client,workspace.client_id)
    angle=session.get(Angle,workspace.angle_id)
    if angle is None:raise ValueError('Aktivierung im Workspace fehlt.')
    options=dict(job.context)
    context,target=context_for(session,workspace,contact_id=options.get('contact_id'),instruction=options.get('instruction',''))
    context['contact_id']=options.get('contact_id')
    context['operation']=options.get('operation','generate')
    prior=current_draft(session,workspace,job.kind,target) if context['operation']=='generate' else None
    job.context=context
    session.commit()
    def call_model(prompt,**kwargs):
        session.commit()
        return invoke(prompt,**kwargs)
    def call_reviewer(prompt,**kwargs):
        session.commit()
        return (review_invoke or invoke)(prompt,**kwargs)
    if context['operation']=='check':
        row=text_row(session,job)
        if row is None:raise ValueError('Text nicht mehr vorhanden.')
        title,body=text_parts(row)
        expected=asset_evidence.digest(title,body)
    else:
        if job.kind=='pitch':
            drafted=outreach.draft(session,client,angle,target,invoke=call_model,extra_context=writing_context(context))
        else:
            fmt=assets.REGISTRY[job.kind]
            facts=writing_facts(session,workspace,context)
            drafted=assets.write(session,fmt,client,angle,invoke=call_model,facts=facts,target=target,
                headlines=target.evidence if target else (),extra_context=writing_context(context))
        session.expire_all()
        # A delayed worker cannot create output after its request was replaced.
        if not session.execute(update(OpportunityAssetRun).where(OpportunityAssetRun.id==identity,
            OpportunityAssetRun.status=='running').values(status='running')).rowcount:
            session.rollback();return
        if current_draft(session,workspace,job.kind,target)!=prior:
            job.status='failed';job.note='Der vorhandene Entwurf wurde während der Erstellung geändert. Er bleibt erhalten.'
            job.finished_at=dt.datetime.now(dt.UTC);session.commit();return
        if job.kind=='pitch':
            row=outreach.store(session,client,angle,drafted,target,commit=False)
            job.outreach_id=row.id
        else:
            row=assets.store(session,fmt,client,angle,drafted,commit=False)
            job.asset_id=row.id
        title,body=text_parts(row)
        expected=asset_evidence.digest(title,body)
        job.text_digest=expected
        session.add(OpportunityEvent(workspace_id=workspace.id,kind='text_created',detail=dict(
            kind=job.kind,asset_id=job.asset_id,outreach_id=job.outreach_id,contact_id=options.get('contact_id'))))
        session.commit()  # Preserve a paid-for draft even if its checker fails.
    try:
        quality=asset_evidence.review(title,body,context,invoke=call_reviewer)
    except Exception:
        quality=dict(status='failed',findings=[],warnings=None,note='Aussagenprüfung konnte nicht abgeschlossen werden. Text ist ungeprüft.')
    session.expire_all()
    job=session.get(OpportunityAssetRun,identity)
    row=text_row(session,job)
    if job.status!='running':return
    if row is None or row.released_at or asset_evidence.digest(*text_parts(row))!=expected:
        job.status='stale';job.note='Text wurde während der Prüfung geändert oder freigegeben. Die vorherige Fassung bleibt unverändert.'
    else:
        job.quality=quality;job.text_digest=expected;job.status='complete'
        job.note=quality['note']
        model=Asset if isinstance(row,Asset) else Outreach
        title_column=model.title if model is Asset else model.subject
        body_column=model.body if model is Asset else model.message
        session.execute(update(model).where(model.id==row.id,model.released_at.is_(None),
            model.reviewed_by=='',title_column==title,body_column==body).values(
            review=quality['note'],review_ok=False).execution_options(synchronize_session=False))
        session.expire(row)
        if context['operation']=='check':
            session.add(OpportunityEvent(workspace_id=workspace.id,kind='text_checked',detail=dict(asset_id=job.asset_id,outreach_id=job.outreach_id)))
    job.finished_at=dt.datetime.now(dt.UTC)
    session.commit()


def read(session,workspace):
    jobs=list(session.scalars(select(OpportunityAssetRun).where(OpportunityAssetRun.workspace_id==workspace.id)
        .order_by(OpportunityAssetRun.id.desc()).limit(100)))
    current_fingerprint=fingerprint(session,workspace)
    texts=[];seen=set()
    for job in jobs:
        row=text_row(session,job)
        if row is None:continue
        key=('asset' if job.asset_id else 'outreach',row.id)
        if key in seen:continue
        seen.add(key)
        title,body=text_parts(row)
        texts.append(dict(id=row.id,type=key[0],kind=job.kind,title=title,body=body,released_at=row.released_at,
            digest=asset_evidence.digest(title,body),quality=job.quality,
            quality_stale=job.text_digest!=asset_evidence.digest(title,body) or job.context.get('fingerprint')!=current_fingerprint,
            contact_id=job.context.get('contact_id'),
            evidence_sources=job.context.get('sources',[]),
            evidence_statements=[r for r in job.context.get('statements',[]) if r['id'] in {identity for f in job.quality.get('findings',[]) for identity in f['statement_ids']+f['contradiction_ids']}],
            href=f'/client/{workspace.client_id}/advice?eintrag=anlass-{workspace.angle_id}#'+('asset-' if job.asset_id else 'outreach-')+str(row.id)))
    return dict(formats=[dict(key=k,label=v) for k,v in FORMATS],texts=texts,
        latest=dict(id=jobs[0].id,status=jobs[0].status,kind=jobs[0].kind,note=jobs[0].note,started_at=jobs[0].started_at) if jobs else None)
