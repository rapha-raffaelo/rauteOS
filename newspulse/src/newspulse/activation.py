"""Draft and review opportunity assets using explicit saved context."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from sqlalchemy import select,update
from . import asset_evidence,assets,gemini,journalists,outreach,profile,quoting,twin,workspaces
from .analyzer import invoke_with_fallback
from .models import (Angle,Asset,Client,ClientFact,ClientPerson,Contact,JournalistProfile,OpportunityAssetRun,OpportunityEvent,
                     OpportunityWorkspace,Outreach)
from .pitch import PitchTarget

FORMATS=[('kundenmail','Kundenmail'),('pitch','Journalistenpitch'),('statement','Statement'),
    ('pressemitteilung','Pressemitteilung'),('qa','Q&A'),('gastbeitrag','Gastbeitrag'),
    ('interviewangebot','Interviewangebot'),('linkedin','LinkedIn-Post'),('interview_briefing','Briefing'),('custom','Eigene Aktion')]


def fingerprint(session,workspace):
    client=session.get(Client,workspace.client_id)
    contacts=[(c.id,c.updated_at.isoformat(),p.revision if (p:=session.get(JournalistProfile,c.id)) else 0)
        for c in session.scalars(select(Contact).where(Contact.id.in_(workspace.contact_ids)))]
    person=session.get(ClientPerson,workspace.speaker_person_id) if workspace.speaker_person_id else None
    return hashlib.sha256(json.dumps(dict(storyline=workspace.storyline,speaker_statement_id=workspace.speaker_statement_id,
        selected_storylines=(workspace.data or {}).get('selected_storylines',[]),guide=client.comms_guide,contacts=contacts,
        speaker_person=(person.id,person.updated_at.isoformat()) if person else None,
        statements=[(r.id,r.revision) for r in twin.all_statements(session,client.id)]),sort_keys=True).encode()).hexdigest()



def topic_rows(session,workspace,topic_ids=None,*,require_active=True):
    ids=list(dict.fromkeys([workspace.id] if topic_ids is None else topic_ids))
    if not ids:raise ValueError('Bitte mindestens ein Thema auswählen.')
    rows=[]
    for identity in ids:
        row=session.get(OpportunityWorkspace,identity)
        if row is None or row.client_id!=workspace.client_id or not row.angle_id:
            raise ValueError('Ein ausgewähltes Thema ist für diesen Kunden nicht verfügbar.')
        flow=(row.data or {}).get('workflow',{})
        if require_active and (row.status!='active' or flow.get('deactivated_at') or flow.get('completed_at')):
            raise ValueError('Bitte nur aktive Themen auswählen.')
        rows.append(row)
    return rows


def topic_choices(session,workspace):
    choices=[]
    for row,angle in session.execute(select(OpportunityWorkspace,Angle).join(Angle,Angle.id==OpportunityWorkspace.angle_id)
        .where(OpportunityWorkspace.client_id==workspace.client_id,OpportunityWorkspace.status=='active')
        .order_by(Angle.generated_at.desc(),OpportunityWorkspace.id.desc())):
        flow=(row.data or {}).get('workflow',{})
        if flow.get('deactivated_at') or flow.get('completed_at'):continue
        choices.append(dict(id=row.id,title=angle.subject,summary=row.storyline or angle.thesis))
    return choices


def topic_fingerprint(session,workspace,topic_ids=None):
    if topic_ids is None:return fingerprint(session,workspace)
    rows=topic_rows(session,workspace,topic_ids,require_active=False)
    parts=[fingerprint(session,workspace)]
    for row in rows:
        angle=session.get(Angle,row.angle_id)
        parts.append(dict(id=row.id,context=fingerprint(session,row),status=row.status,
            title=angle.subject,message=angle.message,context_text=angle.context,thesis=angle.thesis,
            overclaim=angle.overclaim,credibility=angle.credibility,statements=angle.statements,
            article_ids=angle.article_ids,sources=(row.data or {}).get('sources',[]),
            research=(row.data or {}).get('workflow',{}).get('research',{})))
    return hashlib.sha256(json.dumps(parts,sort_keys=True,default=str).encode()).hexdigest()


def topic_angle(session,workspace,topic_ids=None):
    """Compose selected topic content without editing their stored records.

    The resulting asset is still filed in the open workspace. Only selected
    topics supply the writer's subject, arguments and source articles.
    """
    rows=topic_rows(session,workspace,topic_ids,require_active=False)
    angles=[session.get(Angle,row.angle_id) for row in rows]
    join=lambda values:'\n\n'.join(value for value in values if value)
    return Angle(id=workspace.angle_id,client_id=workspace.client_id,
        subject=join([a.subject for a in angles]),message=join([a.message for a in angles]),
        context=join([a.context for a in angles]),credibility=join([a.credibility for a in angles]),
        thesis=join([row.storyline or a.thesis or a.subject for row,a in zip(rows,angles)]),
        overclaim=join([a.overclaim for a in angles]),
        statements=list(dict.fromkeys(value for a in angles for value in (a.statements or []))),
        article_ids=list(dict.fromkeys(value for a in angles for value in (a.article_ids or []))))


def context_for(session,workspace,*,contact_id=None,instruction='',topic_ids=None,require_active_topics=False):
    selected=topic_rows(session,workspace,topic_ids,require_active=require_active_topics)
    client=session.get(Client,workspace.client_id)
    all_facts=twin.all_statements(session,client.id)
    available={r.id:r for r in workspaces.speakers(session,client.id)}
    speaker=available.get(workspace.speaker_statement_id)
    from . import people
    spokesperson=None
    if workspace.speaker_person_id:
        spokesperson={p.id:p for p in people.book(session,client.id)}.get(workspace.speaker_person_id)
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
    learnings=[]
    for previous in session.scalars(select(OpportunityWorkspace).where(OpportunityWorkspace.client_id==client.id).order_by(OpportunityWorkspace.id.desc()).limit(30)):
        flow=(previous.data or {}).get('workflow',{})
        if flow.get('completed_at') and flow.get('result'):
            learnings.append(dict(theme=previous.storyline, assessment=flow['result'], evidence_type='Human-confirmed retrospective; not an external fact'))
    sources=[];topics=[]
    from .models import Article
    for selected_workspace in selected:
        sources+=list((selected_workspace.data or {}).get('sources',[]))
        for research in (selected_workspace.data or {}).get('workflow',{}).get('research',{}).values():
            sources+=research.get('sources',[])
        angle=session.get(Angle,selected_workspace.angle_id)
        sources += [journalists.article_dict(a) for a in session.scalars(select(Article).where(Article.id.in_(angle.article_ids or []))) if journalists.public_url(a.url)]
        topics.append(dict(id=selected_workspace.id,title=angle.subject,storyline=selected_workspace.storyline or angle.thesis or angle.subject))
    if person:sources+=person['articles']
    sources=list({s['url']:s for s in sources}.values())[:40]
    context=dict(workspace_id=workspace.id,workspace_revision=workspace.revision,client_id=client.id,
        storyline='\n\n'.join(t['storyline'] for t in topics),topics=topics,topic_ids=[t.id for t in selected],
        selected_storylines=[line for t in selected for line in (t.data or {}).get('selected_storylines',[])],
        speaker=person_speaker(spokesperson) if spokesperson else twin.snapshot(speaker) if speaker else None,
        statements=[twin.snapshot(r) for r in all_facts],sources=sources,guide=client.comms_guide or '',
        journalist=person,learnings=learnings[:10],instruction=instruction,fingerprint=topic_fingerprint(session,workspace,[t.id for t in selected]))
    return json.loads(json.dumps(context,default=str)),target



def person_speaker(person):
    """A profile contact in the shape the writer reads a speaker in:
    the client's own entry, for outside use."""
    from . import people
    return dict(id=None,person_id=person.id,key='ceo',value=people.label(person),topics=person.topics,
        evidence_type='Client Statement',external_use='Allowed' if person.media_contact else 'Internal Only', media_contact=person.media_contact)


def writing_facts(session,workspace,context):
    facts=profile.stored(session,workspace.client_id)
    for key,row in list(facts.items()):
        if twin.externally_blocked(row):del facts[key]
    if context['speaker'] and context['speaker'].get('person_id') and context['speaker'].get('media_contact'):
        # Not added to the session: it names the speaker for this draft only.
        facts['ceo']=ClientFact(client_id=workspace.client_id,key='ceo',value=context['speaker']['value'])
    elif context['speaker'] and not context['speaker'].get('person_id'):
        facts['ceo']=session.get(ClientFact,context['speaker']['id'])
    else:
        facts.pop('ceo', None)
        facts.pop('sprecher', None)
    return facts

def writing_context(context):
    # The checker sees the full Twin; the writer only gets externally usable
    # statements. Their classification and approval requirements remain attached.
    allowed=[r for r in context['statements'] if r['fact_status'] not in twin.INACTIVE
        and r['external_use']!='Internal Only' and r['confidentiality'] not in
        {'Client Confidential','RAUTE Internal','Highly Restricted'}]
    data={**context,'statements':allowed}
    return ('WORKSPACE-AUFTRAG\nDie gewählte Storyline gilt für diesen Entwurf. Die Ansprechperson ist optional. Ohne Auswahl keine Person oder Zitate automatisch ergänzen. Eine Ansprechperson ohne media_contact=true dient nur der internen Abstimmung und darf nicht als zitierfähiger Sprecher dargestellt werden. '
        'Journalistenangaben dienen der konkreten Ansprache. Keine fehlende Veröffentlichung behaupten. '
        'Twin-Aussagen behalten Herkunft, Status und Freigabegrenzen. Vertrauliche oder rein interne Aussagen '
        'nicht aus einer Gelegenheit rekonstruieren. Kundenmail: Vorschlag zur Freigabe, keine behauptete Zusage.\n'
        +quoting.fence(json.dumps(data,ensure_ascii=False,default=str),label='Gespeicherter Workspace-Kontext'))


def text_row(session,job):
    return session.get(Asset,job.asset_id) if job.asset_id else session.get(Outreach,job.outreach_id) if job.outreach_id else None


def text_parts(row):
    return (row.title,row.body) if isinstance(row,Asset) else (row.subject,row.message)



def run(session,identity,*,invoke=invoke_with_fallback,review_invoke=None):
    job=session.get(OpportunityAssetRun,identity)
    if job is None or job.status!='running':return
    workspace=session.get(OpportunityWorkspace,job.workspace_id)
    client=session.get(Client,workspace.client_id)
    angle=session.get(Angle,workspace.angle_id)
    if angle is None:raise ValueError('Aktivierung im Workspace fehlt.')
    options=dict(job.context)
    # A retried worker must not create a second asset for the same accepted run.
    if options.get('operation','generate')!='check' and (job.asset_id or job.outreach_id):return
    context,target=context_for(session,workspace,contact_id=options.get('contact_id'),instruction=options.get('instruction',''),
        topic_ids=options.get('topic_ids'),require_active_topics=options.get('operation','generate')=='generate')
    writing_angle=topic_angle(session,workspace,context['topic_ids'])
    context['contact_id']=options.get('contact_id')
    context['operation']=options.get('operation','generate')
    job.context=context
    session.commit()
    def call_model(prompt,**kwargs):
        session.commit()
        return invoke(prompt,**kwargs)
    def call_reviewer(prompt,**kwargs):
        # Always the second model, never the one that wrote the text: a model
        # reading its own draft reliably answers "looks good". Without a
        # reviewer configured this raises, and the text stays marked unchecked.
        session.commit()
        return (review_invoke or gemini.reviewer())(prompt,**kwargs)
    if context['operation']=='check':
        row=text_row(session,job)
        if row is None:raise ValueError('Text nicht mehr vorhanden.')
        title,body=text_parts(row)
        expected=asset_evidence.digest(title,body)
    else:
        if job.kind=='pitch':
            drafted=outreach.draft(session,client,writing_angle,target,invoke=call_model,extra_context=writing_context(context))
        else:
            fmt=assets.workspace_format(job.kind)
            facts=writing_facts(session,workspace,context)
            drafted=assets.write(session,fmt,client,writing_angle,invoke=call_model,facts=facts,target=target,
                headlines=target.evidence if target else (),extra_context=writing_context(context))
        session.expire_all()
        # A delayed worker cannot create output after its request was replaced.
        if not session.execute(update(OpportunityAssetRun).where(OpportunityAssetRun.id==identity,
            OpportunityAssetRun.status=='running',OpportunityAssetRun.asset_id.is_(None),
            OpportunityAssetRun.outreach_id.is_(None)).values(status='running')).rowcount:
            session.rollback();return
        if job.kind=='pitch':
            row=outreach.store(session,client,angle,drafted,target,commit=False,new_draft=True)
            job.outreach_id=row.id
        else:
            row=assets.store(session,fmt,client,angle,drafted,commit=False,new_draft=True)
            job.asset_id=row.id
        title,body=text_parts(row)
        expected=asset_evidence.digest(title,body)
        job.text_digest=expected
        session.add(OpportunityEvent(workspace_id=workspace.id,kind='text_created',detail=dict(
            kind=job.kind,asset_id=job.asset_id,outreach_id=job.outreach_id,contact_id=options.get('contact_id'))))
        session.commit()  # Preserve a paid-for draft even if its checker fails.
    try:
        quality=asset_evidence.review(title,body,context,invoke=call_reviewer)
    except RuntimeError as exc:
        quality=dict(status='failed',findings=[],warnings=None,note=f'{exc} Text ist ungeprüft.')
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
    texts=[];seen=set()
    for job in jobs:
        row=text_row(session,job)
        if row is None:continue
        key=('asset' if job.asset_id else 'outreach',row.id)
        if key in seen:continue
        seen.add(key)
        title,body=text_parts(row)
        try:current_fingerprint=topic_fingerprint(session,workspace,job.context.get('topic_ids'))
        except ValueError:current_fingerprint=None
        texts.append(dict(id=row.id,type=key[0],kind=job.kind,title=title,body=body,released_at=row.released_at,
            digest=asset_evidence.digest(title,body),quality=job.quality,
            quality_stale=job.text_digest!=asset_evidence.digest(title,body) or job.context.get('fingerprint')!=current_fingerprint,
            contact_id=job.context.get('contact_id'),topics=job.context.get('topics',[]),
            evidence_sources=job.context.get('sources',[]),
            evidence_statements=[r for r in job.context.get('statements',[]) if r['id'] in {identity for f in job.quality.get('findings',[]) for identity in f['statement_ids']+f['contradiction_ids']}],
            href=f'/client/{workspace.client_id}/advice?eintrag=anlass-{workspace.angle_id}#'+('asset-' if job.asset_id else 'outreach-')+str(row.id)))
    # Existing drafts (for example the automatically prepared press release)
    # belong to the same workspace even when no activation job created them.
    if workspace.angle_id:
        for model,text_type in ((Asset,'asset'),(Outreach,'outreach')):
            for row in session.scalars(select(model).where(model.client_id==workspace.client_id,model.angle_id==workspace.angle_id).order_by(model.generated_at.desc())):
                if (text_type,row.id) in seen:continue
                title,body=text_parts(row)
                texts.append(dict(id=row.id,type=text_type,kind=row.kind if text_type=='asset' else 'pitch',
                    title=title,body=body,released_at=row.released_at,digest=asset_evidence.digest(title,body),
                    quality={},quality_stale=True,contact_id=getattr(row,'contact_id',None),
                    evidence_sources=[],evidence_statements=[],href=workspaces.text_href(session,row,text_type)))
    from . import worklists
    for item in texts:
        row = session.get(Asset if item['type']=='asset' else Outreach,item['id'])
        task = worklists.asset_task(session,row,item['type'])
        item['stage'] = task.status if task else 'offen'
        item['task_id'] = task.id if task else None
    session.commit()
    return dict(formats=[dict(key=k,label=v) for k,v in FORMATS],texts=texts,
        topics=topic_choices(session,workspace),default_topic_id=workspace.id,
        latest=dict(id=jobs[0].id,status=jobs[0].status,kind=jobs[0].kind,note=jobs[0].note,started_at=jobs[0].started_at) if jobs else None)
