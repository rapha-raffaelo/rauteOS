import datetime as dt
from types import SimpleNamespace
from test_topic_workflow import setup, write
from test_opportunity_workspace import db, web, base
from newspulse import topic_automation as automation, topic_workflow, gmail_link
from newspulse.models import OpportunityWorkspace, Outreach, OutreachState, Contact


def letters(web, db):
    d, _ = setup(web, db)
    contact=Contact(name='Reporter',outlet='Paper',email='reporter@example.org')
    db.add(contact);db.flush()
    a=Outreach(client_id=1,angle_id=1,journalist='Reporter',outlet='Paper',contact_id=contact.id,subject='Subject',message='Approved text')
    b=Outreach(client_id=1,angle_id=1,journalist='Other',subject='Other',message='Other text')
    db.add_all([a,b]);db.commit()
    return d,a,b


def test_exclusive_enforces_first_recipient_and_expiry(web,db):
    d,a,b=letters(web,db)
    r=write(web,d['revision'],action='exclusive',text_id=a.id);assert r.status_code==200
    import pytest
    with pytest.raises(ValueError,match='Exklusivphase'):automation.gate(db,b)
    d=r.json()
    r=write(web,d['revision'],action='exclusive_release',note='No reply');assert r.status_code==422
    r=write(web,d['revision'],action='pitch_approval',text_id=a.id,digest=topic_workflow.digest(a),reviewer='Client',note='Email');assert r.status_code==200
    r=write(web,r.json()['revision'],action='sent',text_id=a.id,digest=topic_workflow.digest(a),note='Sent manually');assert r.status_code==200
    assert r.json()['workflow']['exclusive']['until']
    assert write(web,r.json()['revision'],action='exclusive_release',note='No reply').status_code==422


def test_real_send_is_confirmed_once_and_stamped(web,db,monkeypatch):
    d,a,b=letters(web,db)
    d=write(web,d['revision'],action='pitch_approval',text_id=a.id,digest=topic_workflow.digest(a),reviewer='Client',note='Email').json()
    calls=[]
    monkeypatch.setattr(gmail_link,'connected',lambda:SimpleNamespace(is_connected=True,may_send=True))
    monkeypatch.setattr(gmail_link,'create_draft',lambda *args,**kw:(calls.append(args) or gmail_link.Draft('draft','message','thread')))
    monkeypatch.setattr(gmail_link,'send',lambda *args: gmail_link.Sent('sent','thread',dt.datetime.now(dt.UTC)))
    payload=dict(action='send',text_id=a.id,digest=topic_workflow.digest(a),note='wrong@example.org')
    assert write(web,d['revision'],**payload).status_code==422;assert not calls
    payload['note']='reporter@example.org'
    r=write(web,d['revision'],**payload);assert r.status_code==200,r.text
    assert len(calls)==1 and calls[0][1:] == ('Subject','Approved text')
    db.refresh(a);assert a.released_at and a.gmail_message_id=='sent'
    assert write(web,r.json()['revision'],**payload).status_code==422
    assert len(calls)==1


def test_uncertain_delivery_cannot_be_retried(web,db,monkeypatch):
    d,a,b=letters(web,db)
    d=write(web,d['revision'],action='pitch_approval',text_id=a.id,digest=topic_workflow.digest(a),reviewer='Client',note='Email').json()
    monkeypatch.setattr(gmail_link,'connected',lambda:SimpleNamespace(is_connected=True,may_send=True))
    monkeypatch.setattr(gmail_link,'create_draft',lambda *a,**kw:gmail_link.Draft('draft','message','thread'))
    def fail(*args):raise RuntimeError('Lost response')
    monkeypatch.setattr(gmail_link,'send',fail)
    payload=dict(action='send',text_id=a.id,digest=topic_workflow.digest(a),note='reporter@example.org')
    assert write(web,d['revision'],**payload).status_code==422
    d=web.get(base()+'/developed/1').json()
    assert d['workflow']['sending'][str(a.id)]['status']=='uncertain'
    assert write(web,d['revision'],**payload).status_code==422


def test_due_research_records_sources_and_does_not_send(web,db):
    d,a,b=letters(web,db)
    now=dt.datetime.now(dt.UTC)
    a.released_at=now-dt.timedelta(days=3);a.state=OutreachState.RAUS;db.commit()
    calls=[]
    item=SimpleNamespace(published_at=now-dt.timedelta(hours=5),link='https://example.org/new',title='New development',source='Paper',author='Reporter',summary='Evidence')
    def fetch(term):calls.append(term);return [item]
    automation.tick(db,now=now,providers=[('Test',True,fetch)],invoke=lambda *a,**kw:'{"ideas":[{"title":"Neue Daten","reason":"Bezug prüfen","source_ids":[0]}]}')
    db.expire_all();w=db.get(OpportunityWorkspace,d['id'])
    research=w.data['workflow']['research'][str(a.id)]
    assert research['status']=='ready' and len(research['sources'])==1
    assert research['ideas'][0]['title']=='Neue Daten'
    automation.tick(db,now=now,providers=[('Test',True,fetch)],invoke=lambda *a,**kw:'{"ideas":[{"title":"Neue Daten","reason":"Bezug prüfen","source_ids":[0]}]}')
    assert len(calls)==5
    assert not b.released_at and not a.gmail_message_id


def test_expired_exclusive_requires_reason_then_releases_rest(web,db):
    d,a,b=letters(web,db)
    w=db.get(OpportunityWorkspace,d['id'])
    w.data={**w.data,'workflow':{'exclusive':{'text_id':a.id,'until':(dt.datetime.now(dt.UTC)-dt.timedelta(hours=1)).isoformat()}}}
    db.commit()
    assert write(web,w.revision,action='exclusive_release').status_code==422
    r=write(web,w.revision,action='exclusive_release',note='No response; expiry checked')
    assert r.status_code==200,r.text
    automation.gate(db,b)


def test_reconciliation_records_a_lost_confirmation_without_resending(web,db,monkeypatch):
    d,a,b=letters(web,db)
    a.gmail_thread_id='thread'
    w=db.get(OpportunityWorkspace,d['id'])
    w.data={**w.data,'workflow':{'sending':{str(a.id):{'status':'uncertain'}}}}
    db.commit()
    monkeypatch.setattr(gmail_link,'sent_in_thread',lambda thread:gmail_link.Sent('already-sent',thread,dt.datetime.now(dt.UTC)))
    def must_not_send(*a,**kw):raise AssertionError('Must only read the mailbox')
    monkeypatch.setattr(gmail_link,'send',must_not_send)
    r=write(web,w.revision,action='send_reconcile',text_id=a.id)
    assert r.status_code==200,r.text
    db.refresh(a);assert a.released_at and a.gmail_message_id=='already-sent'


def test_confirmed_reply_does_not_keep_old_research_as_next_step(web,db):
    d,a,b=letters(web,db)
    a.released_at=dt.datetime.now(dt.UTC);a.state=OutreachState.ANTWORT
    w=db.get(OpportunityWorkspace,d['id'])
    w.data={**w.data,'workflow':{'research':{str(a.id):{'status':'ready'}}}}
    db.commit()
    assert topic_workflow.summary(db,w)['label']!='Follow-up bereit'
