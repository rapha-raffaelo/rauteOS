"""Customer links only expose their own answers and persist attributed statements."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from newspulse import config, profile
from newspulse.models import Base, Client, ClientFact, CustomerOnboardingInvite
from newspulse.web.app import create_app, get_db
from newspulse.customer_onboarding import QUESTION_KEYS


def topic(client_id, value, key='R05.01', **extra):
    return ClientFact(**{**dict(client_id=client_id, key=key, value=value, confidentiality='Public',
                      source_type='Website', source_url='https://example.org/about'), **extra})


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(config, 'AUTH_USER', 'agency')
    monkeypatch.setattr(config, 'AUTH_PASSWORD', 'test-password')
    from newspulse.web import google_auth
    monkeypatch.setattr(google_auth, 'is_configured', lambda: False)
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    with factory() as s:
        s.add_all([Client(name='First'),Client(name='Second')]);s.commit()
        s.add_all([topic(1,'Public services'),topic(2,'Second services')]);s.commit()
    app=create_app()
    def db():
        with factory() as s: yield s
    app.dependency_overrides[get_db]=db
    return TestClient(app),factory


def invite(web, client=1):
    r=web.post(f'/client/{client}/onboarding-invites',auth=('agency','test-password'))
    assert r.status_code==200
    return r.json(), {'X-Onboarding-Token':r.json()['path'].split('#')[1].split('/')[0]}


def test_link_scope_resume_and_fact_provenance(setup):
    web,factory=setup
    first,header=invite(web)
    _,second=invite(web,2)
    _,another=invite(web)
    assert web.get('/api/onboarding').status_code==401
    assert web.post('/client/1/onboarding-invites').status_code==401
    assert web.get('/client/1/twin',headers=header).status_code==401
    response=web.put('/api/onboarding/answers/Q01.02',headers=header,json={'value':'Roboter'})
    assert response.status_code==200
    assert web.get('/api/onboarding',headers=header).json()['answers']['Q01.02']['value']=='Roboter'
    assert web.get('/api/onboarding',headers=second).json()['answers']=={}
    assert web.get('/api/onboarding',headers=another).json()['answers']=={}
    assert web.put('/api/onboarding/answers/C01.01',headers=header,json={'value':'internal'}).status_code==404
    assert web.put('/api/onboarding/answers/Q01.02',headers=header,json={'value':'Roboter und Service'}).status_code==200
    assert web.put('/api/onboarding/answers/Q01.02',headers=header,json={'skipped':True}).status_code==409
    with factory() as s:
        rows=list(s.scalars(select(ClientFact).where(ClientFact.source_title=='Kunden-Onboarding')))
        assert len(rows)==1
        assert rows[0].client_id==1
        assert rows[0].value=='Roboter und Service'
        assert rows[0].source_title=='Kunden-Onboarding'
        assert rows[0].external_use=='Approval Required'
        assert rows[0].fact_status=='Needs Verification'
        assert rows[0].verified_at is None
        stored=s.get(CustomerOnboardingInvite,first['id'])
        assert stored.token_hash!=header['X-Onboarding-Token']
    assert web.get('/api/onboarding',headers=header).headers['cache-control']=='no-store'


def test_revocation_expiry_and_completion(setup):
    web,factory=setup
    first,header=invite(web)
    assert web.post('/api/onboarding/complete',headers=header).status_code==409
    assert web.post('/api/onboarding/prefill',headers=header,json={'corrections':{}}).status_code==200
    for key in QUESTION_KEYS:
        assert web.put('/api/onboarding/answers/'+key,headers=header,json={'skipped':True}).status_code==200
    assert web.post('/api/onboarding/complete',headers=header).status_code==200
    assert web.get('/api/onboarding',headers=header).json()['completed']
    assert web.post(f"/client/2/onboarding-invites/{first['id']}/revoke",auth=('agency','test-password')).status_code==404
    assert web.post(f"/client/1/onboarding-invites/{first['id']}/revoke",auth=('agency','test-password')).status_code==200
    assert web.get('/api/onboarding',headers=header).status_code==401
    expired,header=invite(web)
    with factory() as s:
        s.get(CustomerOnboardingInvite,expired['id']).expires_at=dt.datetime.now(dt.UTC)-dt.timedelta(seconds=1);s.commit()
    assert web.put('/api/onboarding/answers/Q01.02',headers=header,json={'value':'Test'}).status_code==401


def test_validation_origin_and_existing_facts_are_preserved(setup):
    web,factory=setup
    with factory() as s:
        s.add(ClientFact(client_id=1,key='Q01.02',value='Internal research',is_primary=True));s.commit()
    _,header=invite(web)
    for body in ({'value':''},{'value':'x'*20001},{'value':'test','client_id':2}):
        assert web.put('/api/onboarding/answers/Q01.02',headers=header,json=body).status_code==422
    assert web.put('/api/onboarding/answers/Q01.02',headers={**header,'Origin':'https://evil.example'},json={'value':'x'}).status_code==403
    assert web.put('/api/onboarding/answers/Q01.02',headers=header,json={'value':'Client answer'}).status_code==200
    with factory() as s:
        rows=list(s.scalars(select(ClientFact).where(ClientFact.key=='Q01.02').order_by(ClientFact.id)))
        assert rows[0].value=='Internal research' and rows[0].is_primary
        assert rows[1].value=='Client answer' and not rows[1].is_primary


def test_agency_edits_survive_customer_revision(setup):
    web,factory=setup
    _,header=invite(web)
    web.put('/api/onboarding/answers/Q01.02',headers=header,json={'value':'Original'})
    with factory() as s:
        row=s.scalar(select(ClientFact).where(ClientFact.key=='Q01.02'))
        row.value='Agency correction'
        s.commit()
    web.put('/api/onboarding/answers/Q01.02',headers=header,json={'value':'Customer revision'})
    with factory() as s:
        values=list(s.scalars(select(ClientFact.value).where(ClientFact.key=='Q01.02').order_by(ClientFact.id)))
        assert values==['Agency correction','Customer revision']


def test_concurrent_invite_changes_cannot_silently_lose_answers(setup):
    from fastapi import HTTPException
    from newspulse.web.routes.customer_onboarding import commit
    web,factory=setup
    created,_=invite(web)
    with factory() as first, factory() as second:
        a=first.get(CustomerOnboardingInvite,created['id'])
        b=second.get(CustomerOnboardingInvite,created['id'])
        a.answers={'A01.01':{'value':'First','skipped':False}}
        commit(first)
        b.answers={'Q01.02':{'value':'Second','skipped':False}}
        with pytest.raises(HTTPException) as caught:
            commit(second)
        assert caught.value.status_code==409
    with factory() as s:
        assert 'A01.01' in s.get(CustomerOnboardingInvite,created['id']).answers


def test_public_prefills_are_sourced_and_ceo_answers_are_never_guessed(setup):
    web,factory=setup
    _,headers=invite(web)
    data=web.get('/api/onboarding',headers=headers).json()
    assert len(data['questions'])==22
    assert all(q['key'].startswith('Q') and q['help'] for q in data['questions'])
    assert data['answers']=={}
    assert data['prefill'][0]['value']=='Public services'
    assert data['prefill'][0]['label']=='Unternehmensbeschreibung'
    assert data['prefill'][0]['source_url']=='https://example.org/about'
    assert 'fact_id' not in data['prefill'][0]
    assert not data['prefill_confirmed']
    assert web.post('/api/onboarding/prefill',headers=headers,json={'corrections':{'Q01.02':'Not a public field'}}).status_code==422
    assert web.post('/api/onboarding/prefill',headers=headers,json={'corrections':{'R05.01':'CEO correction'}}).status_code==200
    with factory() as s:
        rows=list(s.scalars(select(ClientFact).where(ClientFact.client_id==1,ClientFact.key=='R05.01').order_by(ClientFact.id)))
        assert [r.value for r in rows]==['Public services','CEO correction']
        assert rows[0].source_url=='https://example.org/about'
        assert rows[1].source_title=='Kunden-Onboarding · Korrektur'
        assert rows[1].confidentiality=='Client Confidential'
    assert web.get('/api/onboarding',headers=headers).json()['prefill_confirmed']
    assert web.put('/api/onboarding/answers/R05.01',headers=headers,json={'value':'public question'}).status_code==404


def test_links_need_researched_topics_and_never_expose_internal_data(setup):
    web,factory=setup
    with factory() as s:
        s.add(Client(name='Third'));s.commit()
        s.add(topic(3,'Secret plans',confidentiality='Client Confidential'))
        s.add(ClientFact(client_id=3,key='A03.01',value='Old catalogue field',
            confidentiality='Public',source_type='Website',source_url='https://example.org'))
        s.commit()
    r=web.post('/client/3/onboarding-invites',auth=('agency','test-password'))
    assert r.status_code==409
    with factory() as s:
        assert s.scalar(select(CustomerOnboardingInvite).where(CustomerOnboardingInvite.client_id==3)) is None
        s.add(topic(3,'Public product',key='R06.01'));s.commit()
    r=web.post('/client/3/onboarding-invites',auth=('agency','test-password'))
    assert r.status_code==200
    assert 'Unternehmensidentität' in r.json()['missing_public_fields']
    header={'X-Onboarding-Token':r.json()['path'].split('#')[1].split('/')[0]}
    snapshot=web.get('/api/onboarding',headers=header).json()
    assert 'Secret plans' not in str(snapshot)
    assert 'Old catalogue field' not in str(snapshot)
    assert [p['value'] for p in snapshot['prefill']]==['Public product']


def test_reads_never_start_research_and_confirmation_is_required(setup,monkeypatch):
    web,_=setup
    _,header=invite(web)
    def forbidden(client): raise AssertionError('GET must not research')
    monkeypatch.setattr(profile,'research',forbidden)
    assert web.get('/api/onboarding',headers=header).status_code==200
    for key in QUESTION_KEYS:
        web.put('/api/onboarding/answers/'+key,headers=header,json={'skipped':True})
    assert web.post('/api/onboarding/complete',headers=header).status_code==409
    web.post('/api/onboarding/prefill',headers=header,json={})
    assert web.post('/api/onboarding/complete',headers=header).status_code==200


@pytest.mark.parametrize('key',['Q01.06','Q01.19'])
def test_unannounced_plans_and_risks_are_internal_only(setup,key):
    web,factory=setup
    _,header=invite(web)
    assert web.put('/api/onboarding/answers/'+key,headers=header,json={'value':'Unannounced acquisition'}).status_code==200
    with factory() as s:
        row=s.scalar(select(ClientFact).where(ClientFact.key==key))
        assert row.external_use=='Internal Only'
        assert row.confidentiality=='Highly Restricted'


def test_every_question_is_optional_and_gaps_stay_open(setup):
    web,factory=setup
    created,header=invite(web)
    web.post('/api/onboarding/prefill',headers=header,json={})
    assert web.put('/api/onboarding/answers/Q01.02',headers=header,json={'value':'Wachstum'}).status_code==200
    assert web.post('/api/onboarding/complete',headers=header).status_code==200
    links=web.get('/client/1/onboarding-invites',auth=('agency','test-password')).json()
    assert links[0]['answered']==1 and links[0]['total']==22 and links[0]['completed']


def test_answers_to_retired_questions_are_not_shown_or_counted(setup):
    web,factory=setup
    created,header=invite(web)
    with factory() as s:
        s.get(CustomerOnboardingInvite,created['id']).answers={'B01.01':{'value':'Old','skipped':False}};s.commit()
    assert web.get('/api/onboarding',headers=header).json()['answers']=={}
    assert web.get('/client/1/onboarding-invites',auth=('agency','test-password')).json()[0]['answered']==0


def test_demo_is_public_and_contains_only_fictional_data(setup):
    web, factory = setup
    with factory() as session:
        facts = len(list(session.scalars(select(ClientFact))))
    response = web.get('/onboarding/demo')
    assert response.status_code == 200
    assert 'Nordlicht Studio' in response.text
    assert 'onboarding-demo' in response.text
    assert 'First' not in response.text and 'Second' not in response.text
    assert 'onboarding-demo' not in web.get('/onboarding').text
    assert web.get('/api/onboarding').status_code == 401
    with factory() as session:
        assert list(session.scalars(select(CustomerOnboardingInvite))) == []
        assert len(list(session.scalars(select(ClientFact)))) == facts
