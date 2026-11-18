"""Workflow records retain mandate, version and human-confirmation boundaries."""
import datetime as dt
from sqlalchemy import select,func
from test_opportunity_workspace import db,web,base,choice
from newspulse import topic_workflow,activation
from newspulse.models import Asset,Angle,Outreach,OutreachState,OpportunityWorkspace,OpportunityEvent,ClientAction


def setup(web,db):
    d=web.post(base()+'/developed/1/activate',json=choice()).json()
    a=Asset(client_id=1,angle_id=1,kind='statement',title='Position',body='Current text')
    db.add(a);db.commit()
    return d,a


def write(web,revision,**data):
    return web.put(base()+'/developed/1/workflow',json=dict(revision=revision,**data))


def test_approval_is_bound_to_exact_asset_and_does_not_release_or_deliver(web,db):
    d,a=setup(web,db)
    fingerprint=activation.fingerprint(db,db.get(OpportunityWorkspace,d['id']))
    reply=write(web,d['revision'],action='approval',text_id=a.id,digest=topic_workflow.digest(a),status='approved',reviewer='Client Person',note='Email approval dated today')
    assert reply.status_code==200,reply.text
    d=reply.json();assert d['workflow']['approvals'][f'asset-{a.id}']['status']=='approved'
    assert not d['workflow']['approvals'][f'asset-{a.id}']['stale']
    assert activation.fingerprint(db,db.get(OpportunityWorkspace,d['id']))==fingerprint
    assert a.released_at is None
    assert db.scalar(select(func.count()).select_from(ClientAction))==0
    a.body='Changed';db.commit()
    d=web.get(base()+'/developed/1').json()
    assert d['workflow']['approvals'][f'asset-{a.id}']['stale']
    assert d['workflow_summary']['step']=='freigabe'


def test_approval_requires_evidence_current_revision_and_current_text(web,db):
    d,a=setup(web,db)
    payload=dict(action='approval',text_id=a.id,digest=topic_workflow.digest(a),status='approved')
    assert write(web,d['revision'],**payload).status_code==422
    assert write(web,d['revision']+10,**payload).status_code==409
    payload.update(reviewer='Client Person',note='Approved by email',digest='0'*64)
    assert write(web,d['revision'],**payload).status_code==422
    assert web.get(base()+'/developed/1').json()['workflow']['approvals']=={}


def test_cannot_record_another_mandates_text_or_unsent_reply(web,db):
    d,a=setup(web,db)
    db.add(Angle(client_id=2,subject='Other theme',message='Other',context='Other context'));db.flush()
    foreign=Asset(client_id=2,angle_id=2,kind='statement',body='Other')
    letter=Outreach(client_id=1,angle_id=1,journalist='Example',message='Draft')
    db.add_all([foreign,letter]);db.commit()
    assert write(web,d['revision'],action='approval',text_id=foreign.id,digest=topic_workflow.digest(foreign),status='internal').status_code==422
    assert write(web,d['revision'],action='outcome',text_id=letter.id,status='antwort',note='Reply').status_code==422
    assert web.put(base(2)+'/developed/1/workflow',json=dict(revision=d['revision'],action='complete',note='Done')).status_code==404


def test_followup_and_confirmed_outcome_persist_on_sent_letter(web,db):
    d,a=setup(web,db)
    letter=Outreach(client_id=1,angle_id=1,journalist='Example',message='Sent text',released_at=dt.datetime.now(dt.UTC),state=OutreachState.RAUS)
    db.add(letter);db.commit()
    reply=write(web,d['revision'],action='followup',text_id=letter.id,status='planned',due_date='2026-12-01',note='Research recent articles')
    assert reply.status_code==200,reply.text
    d=reply.json();assert d['workflow']['followups'][str(letter.id)]['due_date']=='2026-12-01'
    reply=write(web,d['revision'],action='outcome',text_id=letter.id,status='veroeffentlicht',note='Article https://example.org/story')
    assert reply.status_code==200,reply.text
    assert reply.json()['letters'][0]['state']=='veroeffentlicht'
    assert reply.json()['letters'][0]['outcome_note'].endswith('/story')


def test_completion_visible_in_listing_and_can_be_reopened_without_lost_context(web,db):
    d,a=setup(web,db)
    assert write(web,d['revision'],action='complete').status_code==422
    reply=write(web,d['revision'],action='complete',note='No suitable hook, revisit next month',due_date='2026-12-01')
    assert reply.status_code==200,reply.text
    d=reply.json();assert d['workflow_summary']['completed']
    assert web.get(base()).json()['opportunities'][0]['workflow_summary']['completed']
    payload=choice();payload['revision']=d['revision']
    assert web.put(base()+'/developed/1',json=payload).status_code==409
    assert web.post(base()+'/developed/1/activation',json={'kind':'kundenmail'}).status_code==409
    reopened=write(web,d['revision'],action='reopen').json()
    assert not reopened['workflow_summary']['completed']
    assert reopened['storyline']==d['storyline']
    assert reopened['workflow']['result']=='No suitable hook, revisit next month'


def test_two_selected_angles_flow_into_writer_context_and_legacy_choices_preserve_them(web,db):
    payload=choice(selected_storylines=['Economic impact','Practical advice'])
    d=web.post(base()+'/developed/1/activate',json=payload).json()
    assert d['selected_storylines']==['Economic impact','Practical advice']
    context,_=activation.context_for(db,db.get(OpportunityWorkspace,d['id']))
    assert context['selected_storylines']==d['selected_storylines']
    legacy=choice();legacy['revision']=d['revision']
    assert web.put(base()+'/developed/1',json=legacy).json()['selected_storylines']==d['selected_storylines']
    legacy['selected_storylines']=['one','two','three']
    assert web.put(base()+'/developed/1',json=legacy).status_code==422


def test_pitch_dispatch_is_a_versioned_human_record_not_an_automatic_send(web,db):
    d,a=setup(web,db)
    letter=Outreach(client_id=1,angle_id=1,journalist='Example',message='Pitch text',contact_id=1)
    db.add(letter);db.commit()
    payload=dict(text_id=letter.id,digest=topic_workflow.digest(letter),note='Sent through own mailbox at 10:30')
    assert write(web,d['revision'],action='sent',**payload).status_code==422
    reply=write(web,d['revision'],action='pitch_approval',reviewer='Client Person',**payload)
    assert reply.status_code==200,reply.text
    d=reply.json();assert letter.released_at is None
    previous=payload['digest'];letter.message='Revised pitch';db.commit()
    assert write(web,d['revision'],action='sent',**payload).status_code==422
    payload['digest']=topic_workflow.digest(letter)
    assert write(web,d['revision'],action='sent',**payload).status_code==422
    d=write(web,d['revision'],action='pitch_approval',reviewer='Client Person',**payload).json()
    reply=write(web,d['revision'],action='sent',**payload)
    assert reply.status_code==200,reply.text
    assert reply.json()['letters'][0]['state']=='raus'
    assert reply.json()['workflow_summary']['step']=='followup'
    assert letter.gmail_message_id==''
    assert write(web,reply.json()['revision'],action='sent',**payload).status_code==422


def test_preexisting_assets_are_editable_inside_the_topic_without_a_generation_job(web,db):
    d,a=setup(web,db)
    path=base()+'/developed/1/activation'
    data=web.get(path).json()
    text=next(t for t in data['texts'] if t['id']==a.id and t['type']=='asset')
    result=web.put(path+f'/asset/{a.id}',json={'digest':text['digest'],'title':text['title'],'body':'Updated existing text'})
    assert result.status_code==200,result.text
    assert result.json()['texts'][0]['body']=='Updated existing text'
