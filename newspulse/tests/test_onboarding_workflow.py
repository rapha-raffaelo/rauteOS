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
    monkeypatch.setattr(flow,'fetch_logo',lambda site:None)
    monkeypatch.setattr(crawler,'BATCHES',[[{'key':'R01.01'}],[{'key':'R05.01'}]])
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
    header={'X-Onboarding-Token':path.split('#')[1].split('/')[0]}
    customer=web.get('/api/onboarding',headers=header).json()
    assert customer['customer']=='Example AG'
    assert 'alex@example.org' not in str(customer)
    assert len(customer['prefill'])==2
    assert web.post('/api/onboarding/prefill',headers=header,json={}).status_code==200
    assert web.put('/api/onboarding/answers/Q01.01',headers=header,json={'value':'CEO ambition'}).status_code==200
    for q in customer['questions'][1:]:
        assert web.put('/api/onboarding/answers/'+q['key'],headers=header,json={'skipped':True}).status_code==200
    assert web.post('/api/onboarding/complete',headers=header).status_code==200
    assert web.get('/client/1/onboarding-workflow').json()['completed']
    with factory() as s:
        assert s.scalar(select(ClientFact.value).where(ClientFact.key=='Q01.01'))=='CEO ambition'
        assert len(list(s.scalars(select(CustomerOnboardingInvite))))==1
    renewed=web.post('/client/1/onboarding-workflow/link').json()['path']
    assert renewed!=path
    assert web.get('/api/onboarding',headers=header).status_code==401
    resumed=web.get('/api/onboarding',headers={'X-Onboarding-Token':renewed.split('#')[1].split('/')[0]}).json()
    assert resumed['answers']['Q01.01']['value']=='CEO ambition'


def test_failed_batch_resumes_without_repeating_saved_work(setup):
    web,factory=setup
    create(web)
    calls=[]
    def partial(client,fields,pages):
        calls.append(fields[0]['key'])
        if fields[0]['key']=='R05.01':raise ValueError('Ungültige Recherche-Antwort')
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
    assert resumed==['R05.01']
    assert web.get('/client/1/onboarding-workflow').json()['status']=='ready'


def test_a_spent_search_quota_pauses_the_research_instead_of_failing_it(setup):
    from newspulse.analyzer import BackendError
    web,factory=setup
    create(web)
    def limited(client,fields,pages):
        if fields[0]['key']=='R05.01':
            raise BackendError('Gemini HTTP 429: Quota exceeded, Generate content requests per minute limit exceeded')
        return researched(client,fields,pages)
    with factory() as s: claimed=flow.claim(s)
    flow.work(factory,*claimed,crawl=lambda site:[],research=limited)
    with factory() as s:
        job=s.get(CustomerOnboardingJob,1)
        assert job.status=='queued' and job.stage=='Wartet auf Recherche-Kontingent'
        assert job.checkpoint['next_batch']==1 and job.note==''
        assert flow.claim(s) is None
        job.lease_until=dt.datetime.now(dt.UTC)-dt.timedelta(seconds=1);s.commit()
        claimed=flow.claim(s)
    resumed=[]
    flow.work(factory,*claimed,crawl=lambda _:pytest.fail('crawl repeated'),
              research=lambda c,f,p:resumed.append(f[0]['key']) or researched(c,f,p))
    assert resumed==['R05.01']
    assert web.get('/client/1/onboarding-workflow').json()['status']=='ready'


def test_a_slow_search_is_retried_and_a_topic_that_keeps_failing_is_skipped(setup):
    from newspulse.analyzer import BackendError
    web,factory=setup
    create(web)
    calls=[]
    def slow(client,fields,pages):
        calls.append(fields[0]['key'])
        if fields[0]['key']=='R01.01':raise BackendError('Gemini timed out after 180.0s')
        return researched(client,fields,pages)
    for attempt in range(flow.TOPIC_TRIES):
        with factory() as s:
            job=s.get(CustomerOnboardingJob,1)
            if attempt:
                assert job.status=='queued' and job.stage=='Recherche wird gleich fortgesetzt'
                job.lease_until=dt.datetime.now(dt.UTC)-dt.timedelta(seconds=1);s.commit()
            claimed=flow.claim(s)
        flow.work(factory,*claimed,crawl=lambda site:[],research=slow)
    assert calls==['R01.01']*flow.TOPIC_TRIES+['R05.01']
    status=web.get('/client/1/onboarding-workflow').json()
    assert status['status']=='ready' and status['researched_fields']==1


def test_broken_json_from_the_search_is_retried_rather_than_failing_the_research(setup):
    """Gemini once answered topic 16 for Zalando with a missing comma, and the
    whole onboarding stopped as "Recherche unterbrochen"."""
    import json
    web,factory=setup
    create(web)
    calls=[]
    def flaky(client,fields,pages):
        calls.append(fields[0]['key'])
        if len(calls)==1:json.loads('{"answers":[{"key":"R01.01" "value":"x"}]}')
        return researched(client,fields,pages)
    with factory() as s:claimed=flow.claim(s)
    flow.work(factory,*claimed,crawl=lambda site:[],research=flaky)
    with factory() as s:
        job=s.get(CustomerOnboardingJob,1)
        assert job.status=='queued' and job.stage=='Recherche wird gleich fortgesetzt'
        job.lease_until=dt.datetime.now(dt.UTC)-dt.timedelta(seconds=1);s.commit()
        claimed=flow.claim(s)
    flow.work(factory,*claimed,crawl=lambda site:[],research=flaky)
    assert calls==['R01.01','R01.01','R05.01']
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


def test_research_accepts_only_requested_topics_and_real_source_urls():
    context=SimpleNamespace(name='Example',website='https://example.org',industry='',country='DE')
    prompts=[]
    def search(prompt):
        prompts.append(prompt)
        return json.dumps({'answers':[
            {'key':'R01.01','value':'Example AG \u2014 gegründet 2010','source_url':'https://example.org/about',
             'sources':['https://example.org/about','https://press.example/story','https://invented.example']},
            {'key':'Q01.02','value':'Private plan','source_url':'https://example.org/about'},
            {'key':'R05.01','value':'Invented','source_url':'https://invented.example'}]}),[('https://press.example/story','Press')]
    fields=[crawler.PUBLIC_FIELDS[0],crawler.PUBLIC_FIELDS[4]]
    answers=crawler.research_batch(context,fields,[{'url':'https://example.org/about','text':'Source'}],search=search)
    assert answers==[dict(key='R01.01',value='Example AG, gegründet 2010',source_url='https://example.org/about',
                          note='Weitere Quellen: https://press.example/story')]
    assert 'Wer ist offiziell vertretungsberechtigt' not in prompts[0]
    assert 'Wann wurde das Unternehmen gegründet' in prompts[0]


def test_a_source_beyond_the_thirtieth_search_hit_still_counts():
    """Claude read 72 pages for Zalando's company size and cited one past the
    thirtieth; the old cap on all citations threw the answer away."""
    context=SimpleNamespace(name='Zalando',website='https://zalando.de',industry='',country='DE')
    hits=[(f'https://site{i}.example/page',f'Hit {i}') for i in range(72)]
    def search(prompt):
        return json.dumps({'answers':[{'key':'R01.01','value':'Gegründet 2008.',
            'source_url':'https://site60.example/page'}]}),hits
    answers=crawler.research_batch(context,[crawler.PUBLIC_FIELDS[0]],[],search=search)
    assert [a['source_url'] for a in answers]==['https://site60.example/page']


def test_research_covers_the_21_topics_one_call_each():
    assert len(crawler.BATCHES)==21 and all(len(b)==1 for b in crawler.BATCHES)
    assert [b[0]['key'] for b in crawler.BATCHES]==[f'R{i:02d}.01' for i in range(1,22)]
    assert all(b[0]['question'] for b in crawler.BATCHES)


def test_research_from_the_old_catalogue_restarts_on_the_topics(setup):
    web,factory=setup
    create(web)
    with factory() as s: claimed=flow.claim(s)
    flow.work(factory,*claimed,crawl=lambda site:[{'url':site,'text':'Public website'}],research=researched)
    with factory() as s:
        job=s.get(CustomerOnboardingJob,1)
        job.checkpoint={k:v for k,v in job.checkpoint.items() if k!='version'};s.commit()
    status=web.get('/client/1/onboarding-workflow').json()
    assert status['status']=='ready' and status['outdated']
    assert web.post('/client/1/onboarding-workflow').status_code==202
    with factory() as s: claimed=flow.claim(s)
    redone=[]
    def again(c,f,p):redone.append(f[0]['key']);return researched(c,f,p)
    flow.work(factory,*claimed,crawl=lambda _:pytest.fail('pages are kept'),research=again)
    assert redone==['R01.01','R05.01']
    status=web.get('/client/1/onboarding-workflow').json()
    assert status['status']=='ready' and not status['outdated']


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


def test_link_available_before_research_and_stable_after_research(setup):
    web,factory=setup
    create(web)
    response=web.post('/client/1/onboarding-workflow/link/ensure')
    assert response.status_code==200,response.text
    path=response.json()['path']
    assert path.endswith('/example-ag')
    assert web.post('/client/1/onboarding-workflow/link/ensure').json()['path']==path
    header={'X-Onboarding-Token':path.split('#')[1].split('/')[0]}
    assert web.get('/api/onboarding',headers=header).status_code==200
    with factory() as s: claimed=flow.claim(s)
    flow.work(factory,*claimed,crawl=lambda _:[],research=researched)
    assert web.get('/client/1/onboarding-workflow').json()['path']==path
    assert len(web.get('/api/onboarding',headers=header).json()['prefill'])==2
    with factory() as s:
        assert len(list(s.scalars(select(CustomerOnboardingInvite))))==1
        s.get(CustomerOnboardingInvite,1).expires_at=dt.datetime.now(dt.UTC)-dt.timedelta(seconds=1)
        s.commit()
    renewed=web.post('/client/1/onboarding-workflow/link/ensure').json()['path']
    assert renewed!=path and renewed.endswith('/example-ag')


def test_customer_name_slug():
    assert flow.customer_link('token','Müller & Söhne GmbH').endswith('/mueller-soehne-gmbh')


def test_backfill_queues_each_mandate_without_topic_research_once(setup):
    web,factory=setup
    with factory() as s:
        s.add_all([Client(name='Never onboarded',website='https://never.example'),
                   Client(name='Old catalogue',website='https://old.example'),
                   Client(name='Done',website='https://done.example'),
                   Client(name='Paused',active=False),
                   Client(name='Rival',is_competitor=True),
                   Client(name='Stalled',website='https://stalled.example')]);s.commit()
        s.add_all([CustomerOnboardingJob(client_id=2,status='ready',checkpoint={'pages':[{'url':'https://old.example','text':'x'}],'next_batch':8}),
                   CustomerOnboardingJob(client_id=3,status='ready',checkpoint={'version':crawler.VERSION,'next_batch':21}),
                   CustomerOnboardingJob(client_id=6,status='failed',checkpoint={'version':crawler.VERSION,'pages':[],'next_batch':1})]);s.commit()
        assert flow.backfill(s)==3
        assert {j.client_id:j.status for j in s.scalars(select(CustomerOnboardingJob))}=={1:'queued',2:'queued',3:'ready',6:'queued'}
        assert s.get(CustomerOnboardingJob,6).checkpoint['next_batch']==1
        assert s.get(CustomerOnboardingJob,2).checkpoint=={'pages':[{'url':'https://old.example','text':'x'}]}
        assert flow.backfill(s)==0


def test_a_new_mandate_gets_its_logo_first_and_a_missing_one_never_blocks(setup,monkeypatch):
    web,factory=setup
    create(web)
    sites=[]
    monkeypatch.setattr(flow,'fetch_logo',lambda site:sites.append(site) or 'data:image/png;base64,iVBORw0KGgo=')
    with factory() as s: claimed=flow.claim(s)
    flow.work(factory,*claimed,crawl=lambda _:[],research=researched)
    with factory() as s:
        assert s.get(Client,1).logo_url=='data:image/png;base64,iVBORw0KGgo='
    assert sites==['https://example.org']
    with factory() as s:
        s.add(Client(name='No mark',website='https://nomark.example'));s.commit()
        flow.enqueue(s,s.get(Client,2));s.commit()
        claimed=flow.claim(s)
    monkeypatch.setattr(flow,'fetch_logo',lambda site:None)
    flow.work(factory,*claimed,crawl=lambda _:[],research=researched)
    assert web.get('/client/2/onboarding-workflow').json()['status']=='ready'
    with factory() as s:
        assert s.get(Client,2).logo_url is None
