import datetime as dt
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse import onboarding_crawler as crawler, onboarding_workflow as flow
from newspulse.models import Base, Client, ClientFact, CustomerOnboardingInvite, CustomerOnboardingJob
from newspulse.web.app import create_app, get_db


@pytest.fixture
def setup(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    monkeypatch.setattr(flow,'signing_key',lambda:b'test-key'*4)
    monkeypatch.setattr(crawler,'BATCHES',[[{'key':'A02.01'}],[{'key':'A03.01'}]])
    app=create_app()
    def db():
        with factory() as s: yield s
    app.dependency_overrides[get_db]=db
    return TestClient(app),factory


def create(web):
    r=web.post('/mandant/neu',data={'name':'Example AG','website':'example.org','country':'DE',
        'contact_name':'Alex Beispiel','contact_email':'alex@example.org','contact_role':'CEO','contact_phone':'+49 123'},follow_redirects=False)
    assert r.status_code==303
    assert r.headers['location']=='/client/1/twin#kunden-onboarding'


def researched(client,fields,pages):
    return [dict(key=fields[0]['key'],value='Public '+fields[0]['key'],source_url='https://example.org/about')]


def test_create_research_link_customer_answer_end_to_end(setup):
    web,factory=setup
    create(web)
    with factory() as s:
        assert s.get(Client,1).contact_email=='alex@example.org'
        assert s.get(CustomerOnboardingJob,1).status=='queued'
        claimed=flow.claim(s)
    flow.work(factory,*claimed,crawl=lambda site:[{'url':site,'text':'Public website'}],research=researched)
    status=web.get('/client/1/onboarding-workflow').json()
    assert status['status']=='ready' and status['researched_fields']==2
    assert 'checkpoint' not in status and 'token' not in status
    path=status['path']
    assert path==web.get('/client/1/onboarding-workflow').json()['path']
    header={'X-Onboarding-Token':path.split('#')[1]}
    customer=web.get('/api/onboarding',headers=header).json()
    assert customer['customer']=='Example AG'
    assert 'alex@example.org' not in str(customer)
    assert len(customer['prefill'])==2
    assert web.post('/api/onboarding/prefill',headers=header,json={}).status_code==200
    assert web.put('/api/onboarding/answers/B01.01',headers=header,json={'value':'CEO ambition'}).status_code==200
    for q in customer['questions'][1:]:
        assert web.put('/api/onboarding/answers/'+q['key'],headers=header,json={'skipped':True}).status_code==200
    assert web.post('/api/onboarding/complete',headers=header).status_code==200
    assert web.get('/client/1/onboarding-workflow').json()['completed']
    with factory() as s:
        assert s.scalar(select(ClientFact.value).where(ClientFact.key=='B01.01'))=='CEO ambition'
        assert len(list(s.scalars(select(CustomerOnboardingInvite))))==1
    renewed=web.post('/client/1/onboarding-workflow/link').json()['path']
    assert renewed!=path
    assert web.get('/api/onboarding',headers=header).status_code==401
    resumed=web.get('/api/onboarding',headers={'X-Onboarding-Token':renewed.split('#')[1]}).json()
    assert resumed['answers']['B01.01']['value']=='CEO ambition'


def test_failed_batch_resumes_without_repeating_saved_work(setup):
    web,factory=setup
    create(web)
    calls=[]
    def partial(client,fields,pages):
        calls.append(fields[0]['key'])
        if fields[0]['key']=='A03.01':raise TimeoutError()
        return researched(client,fields,pages)
    with factory() as s: claimed=flow.claim(s)
    flow.work(factory,*claimed,crawl=lambda site:[],research=partial)
    with factory() as s:
        job=s.get(CustomerOnboardingJob,1)
        assert job.status=='failed' and job.checkpoint['next_batch']==1
        assert len(list(s.scalars(select(ClientFact))))==1
    assert web.post('/client/1/onboarding-workflow').status_code==202
    with factory() as s: claimed=flow.claim(s)
    resumed=[]
    def finish(c,f,p):resumed.append(f[0]['key']);return researched(c,f,p)
    flow.work(factory,*claimed,crawl=lambda _:pytest.fail('crawl repeated'),research=finish)
    assert resumed==['A03.01']
    assert web.get('/client/1/onboarding-workflow').json()['status']=='ready'


def test_expired_worker_is_fenced_after_restart(setup):
    web,factory=setup
    create(web)
    with factory() as s:
        old=flow.claim(s)
        assert flow.claim(s) is None
        s.get(CustomerOnboardingJob,1).lease_until=dt.datetime.now(dt.UTC)-dt.timedelta(seconds=1);s.commit()
        new=flow.claim(s)
        assert new[1]!=old[1]
        with pytest.raises(flow.Superseded):flow.own(s,*old)
    flow.work(factory,*new,crawl=lambda _:[],research=researched)
    with factory() as s:assert len(list(s.scalars(select(CustomerOnboardingInvite))))==1


def test_invalid_contact_does_not_create_partial_customer(setup):
    web,factory=setup
    r=web.post('/mandant/neu',data={'name':'Broken','website':'example.org','contact_email':'not-an-email'})
    assert r.status_code==200
    with factory() as s:
        assert s.scalar(select(Client)) is None
        assert s.scalar(select(CustomerOnboardingJob)) is None


def test_crawler_respects_robots_and_avoids_news_articles():
    requested=[]
    def get(url):
        requested.append(url)
        if url.endswith('robots.txt'):return 'User-agent: *\nDisallow: /team','text/plain',url
        return '<script>secret()</script>Public business<a href="/team">Team</a><a href="/news/article">News</a><a href="http://127.0.0.1/about">Bad</a><a href="/products">Products</a>','text/html',url
    pages=crawler.crawl('https://example.org',get=get)
    assert requested==['https://example.org/robots.txt','https://example.org/','https://example.org/products']
    assert all('secret()' not in p['text'] for p in pages)


def test_research_accepts_only_requested_fields_and_real_source_urls():
    context=SimpleNamespace(name='Example',website='https://example.org',industry='',country='DE')
    def search(prompt):
        return json.dumps({'answers':[
            {'key':'A02.01','value':'Supported','source_url':'https://example.org/about'},
            {'key':'B01.01','value':'Private plan','source_url':'https://example.org/about'},
            {'key':'A03.01','value':'Invented','source_url':'https://invented.example'}]}),[]
    answers=crawler.research_batch(context,[{'key':'A02.01','label':'Business'},{'key':'A03.01','label':'Product'}],
        [{'url':'https://example.org/about','text':'Source'}],search=search)
    assert answers==[dict(key='A02.01',value='Supported',source_url='https://example.org/about')]


def test_completed_empty_research_can_be_retried(setup):
    web,factory=setup
    create(web)
    with factory() as s: item=flow.claim(s)
    flow.work(factory,*item,crawl=lambda _:[],research=lambda *args:[])
    assert web.get('/client/1/onboarding-workflow').json()['status']=='failed'
    web.post('/client/1/onboarding-workflow')
    with factory() as s:
        assert s.get(CustomerOnboardingJob,1).checkpoint=={}
        item=flow.claim(s)
    flow.work(factory,*item,crawl=lambda _:[],research=researched)
    assert web.get('/client/1/onboarding-workflow').json()['status']=='ready'
