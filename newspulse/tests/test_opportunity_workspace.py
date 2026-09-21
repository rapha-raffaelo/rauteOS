"""Developed ideas remain hypotheses; activation retains sources and explicit choices."""
import datetime as dt
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,func,select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from newspulse import opportunity_development as development
from newspulse.models import (Angle,Article,Base,Client,ClientAction,ClientFact,Contact,NewsjackOpportunity,
    OpportunityDevelopment,OpportunityEvent,OpportunityWorkspace,Standing)
from newspulse.web.app import create_app,get_db
from newspulse.web.routes import opportunities_api as api


@pytest.fixture
def db():
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine,expire_on_commit=False)() as session:
        session.add_all([Client(name='Mandate'),Client(name='Other'),Client(name='Benchmark',is_competitor=True)])
        session.flush()
        session.add(Angle(client_id=1,subject='Existing idea',message='Business relevance',context='Context'))
        session.add(ClientFact(client_id=1,key='ceo',value='Anna CEO',evidence_type='Client Statement',
                               external_use='Allowed',confidentiality='Public'))
        session.add(Contact(name='Journalist Example',outlet='Newspaper'))
        session.commit();yield session
    engine.dispose()


@pytest.fixture
def web(db,monkeypatch):
    monkeypatch.setattr(api,'start_or_release',lambda *args,**kwargs:None)
    app=create_app();app.dependency_overrides[get_db]=lambda:db
    with TestClient(app) as client:yield client


def base(client=1):return f'/api/v1/clients/{client}/opportunities'

def choice(**values):return dict(revision=0,storyline='A new regulatory perspective',speaker_statement_id=1,contact_ids=[1],**values)


def idea(**extra):
    return dict(title='New data story',situation='We can develop a study',relevance='It concerns the business',
        why_now='Planning opportunity, verify timing',window_days=None,thesis='A testable hypothesis',
        storylines=['Publish a study','Offer an interview'],recommended_actions=['kundenmail','pitch'],
        risks=['Client statement, not independently confirmed'],source_ids=[],proof_statement_ids=[1],**extra)


def launch(web):
    response=web.post(base()+'/develop',json={'focus':'BioLNG transport'})
    assert response.status_code==202,response.text
    return response.json()['id']


def test_get_is_read_only_and_is_scoped(web,db):
    response = web.get(base()+'/developed/1')
    assert response.status_code==200
    assert response.json()['angle_id']==1
    assert db.scalar(select(func.count()).select_from(OpportunityWorkspace))==0
    assert web.get(base(2)+'/developed/1').status_code==404
    assert web.get(base(3)).status_code==404
    assert web.get(base()+'/developed/1').headers['cache-control']=='no-store'
    assert web.get('/client/1/opportunities').status_code==200


def test_activation_persists_choices_without_counting_delivery(web,db):
    response=web.post(base()+'/developed/1/activate',json=choice())
    assert response.status_code==200,response.text
    result=response.json()
    assert result['status']=='active' and result['speaker_statement_id']==1 and result['contact_ids']==[1]
    assert len(result['events'])==1 and result['events'][0]['kind']=='activated'
    assert db.scalar(select(func.count()).select_from(ClientAction))==0
    assert web.post(base()+'/developed/1/activate',json=choice()).status_code==409
    fresh=choice();fresh['revision']=result['revision']
    res=web.post(base()+'/developed/1/activate',json=fresh)
    assert res.status_code==200 and res.json()['revision']>result['revision']
    assert db.scalar(select(func.count()).select_from(OpportunityEvent).where(OpportunityEvent.kind=='activated'))==1


def test_selection_rejects_foreign_or_restricted_speaker_and_unknown_contact(web,db):
    body=choice();body['speaker_statement_id']=999
    assert web.put(base()+'/developed/1',json=body).status_code==422
    db.get(ClientFact,1).confidentiality='Client Confidential';db.commit()
    assert web.put(base()+'/developed/1',json=choice()).status_code==422
    body=choice();body['speaker_statement_id']=None;body['contact_ids']=[999]
    assert web.put(base()+'/developed/1',json=body).status_code==422
    assert db.scalar(select(func.count()).select_from(OpportunityWorkspace))==0


def test_detected_activation_reuses_the_existing_angle_and_refuses_closed_window(web,db):
    now=dt.datetime.now(dt.UTC)
    article=Article(title='A regulation',url='https://example.org/regulation',source='Paper',published_at=now,title_hash='regulation')
    db.add(article);db.flush()
    opp=NewsjackOpportunity(client_id=1,article_id=article.id,standing=Standing.BELEGT,reason='Relevant',
                           window_ends_at=now+dt.timedelta(days=1))
    db.add(opp);db.commit()
    path=base()+f'/detected/{opp.id}/activate'
    first=web.post(path,json=choice());assert first.status_code==200,first.text
    body=choice();body['revision']=first.json()['revision']
    assert web.post(path,json=body).status_code==200
    assert db.scalar(select(func.count()).select_from(Angle).where(Angle.newsjack_id==opp.id))==1
    opp.window_ends_at=now-dt.timedelta(days=1);db.commit()
    assert web.post(path,json=body).status_code==409
    assert web.get(base()+f'/detected/{opp.id}').json()['status']=='closed'


def test_develops_without_any_news_and_preserves_twin_provenance(web,db,monkeypatch):
    identity=launch(web);prompts=[]
    from newspulse import default_content
    drafted=[]
    def default(session, client, angle):
        assert session.get(OpportunityDevelopment,identity).status == 'running'
        drafted.append(angle.id)
    monkeypatch.setattr(default_content,'press_release',default)
    def invoke(prompt,**kwargs):
        prompts.append(prompt)
        return json.dumps({'ideas':[idea()],'note':'No fresh sources; research required.'})
    development.develop(db,identity,providers=[],invoke=invoke)
    row=db.get(OpportunityDevelopment,identity)
    assert row.status=='complete' and len(row.workspace_ids)==1
    assert len(drafted)==1
    workspace=db.get(OpportunityWorkspace,row.workspace_ids[0])
    assert workspace.data['evidence_type']=='RAUTE Hypothesis'
    assert workspace.data['statement_snapshots'][0]['evidence_type']=='Client Statement'
    assert workspace.data['sources']==[]
    assert db.get(Angle,workspace.angle_id).article_ids==[]
    assert 'nicht unabhängig bestätigt' in prompts[0]
    assert 'Existing idea' in prompts[0]
    assert len(row.queries)==5
    assert db.scalar(select(func.count()).select_from(ClientAction))==0


def test_invented_citations_are_rejected_and_research_survives_model_failure(web,db):
    identity=launch(web)
    invalid=idea();invalid['source_ids']=[999]
    with pytest.raises(ValueError):
        development.develop(db,identity,providers=[],invoke=lambda *args,**kwargs:json.dumps({'ideas':[invalid],'note':'Test'}))
    assert db.scalar(select(func.count()).select_from(OpportunityWorkspace))==0
    assert len(db.get(OpportunityDevelopment,identity).queries)==5


def test_no_idea_and_duplicate_idea_are_honest_empty_results(web,db):
    identity=launch(web)
    development.develop(db,identity,providers=[],invoke=lambda *args,**kwargs:json.dumps({'ideas':[],'note':'Not enough evidence'}))
    assert db.get(OpportunityDevelopment,identity).status=='no_opportunity'
    identity=launch(web);duplicate=idea();duplicate['title']='Existing idea'
    development.develop(db,identity,providers=[],invoke=lambda *args,**kwargs:json.dumps({'ideas':[duplicate],'note':'Test'}))
    assert db.get(OpportunityDevelopment,identity).status=='no_opportunity'
    assert db.scalar(select(func.count()).select_from(Angle))==1


def test_only_one_development_runs_per_mandate_and_failures_are_retryable(web,db,monkeypatch):
    identity=launch(web)
    assert web.post(base()+'/develop',json={'focus':'Another theme'}).status_code==409
    def fail(*args):raise ValueError('private')
    monkeypatch.setattr(development,'develop',fail)
    api.worker(sessionmaker(bind=db.get_bind()),identity)
    db.expire_all();assert db.get(OpportunityDevelopment,identity).status=='failed'
    launch(web)


def test_each_research_area_keeps_provider_failures_visible():
    called=[]
    def failed(term):called.append(term);raise ValueError('SECRET')
    queries,sources=development.collect('BioLNG',['Competitor'],[],now=dt.datetime.now(dt.UTC),
        providers=[('Failure',True,failed),('Missing',False,failed)])
    assert len(called)==5 and 'Competitor' in called[1]
    assert all(q['providers']['Failure']['status']=='failed' for q in queries)
    assert 'SECRET' not in str(queries) and sources==[]


def test_default_content_does_not_revive_an_expired_development(web,db,monkeypatch):
    from newspulse import default_content
    identity=launch(web)
    def expire(session,client,angle):
        row=session.get(OpportunityDevelopment,identity)
        row.status='failed'
        session.commit()
    monkeypatch.setattr(default_content,'press_release',expire)
    development.develop(db,identity,providers=[],invoke=lambda *a,**k:json.dumps({'ideas':[idea()],'note':'Test'}))
    db.expire_all()
    assert db.get(OpportunityDevelopment,identity).status=='failed'
