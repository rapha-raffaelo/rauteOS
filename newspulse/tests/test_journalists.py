"""Profiles stay attributable; fresh research never pretends the archive is complete."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse import journalists
from newspulse.ingest import FeedItem
from newspulse.models import Angle, Article, Base, Client, Contact, JournalistEvidence, JournalistProfile, JournalistResearch
from newspulse.web.app import create_app, get_db
from newspulse.web.routes import journalists_api as api


@pytest.fixture
def db():
    engine=create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        session.add_all([Client(name='Mandate'),Client(name='Other'),Client(name='Benchmark',is_competitor=True)])
        session.flush()
        session.add(Angle(client_id=1,subject='BioLNG im Schwerlastverkehr',message='Test',context='Transport'))
        session.commit()
        yield session
    engine.dispose()


@pytest.fixture
def web(db,monkeypatch):
    monkeypatch.setattr(api,'start_or_release',lambda *args,**kwargs:None)
    app=create_app();app.dependency_overrides[get_db]=lambda:db
    with TestClient(app) as client: yield client


def create(web,**extra):
    res=web.post('/api/v1/journalists',json={'name':'Anna Beispiel','outlet':'Handelsblatt',**extra})
    assert res.status_code==201,res.text
    return res.json()


def payload(data,**extra):
    return dict(contact={key:value for key,value in data['contact'].items() if key not in {'id','updated_at'}},
        profile={key:value for key,value in data['profile'].items() if key!='revision'},
        revision=data['profile']['revision'],contact_updated_at=data['contact']['updated_at'],**extra)


def article(db, *, days=1, author='Anna Beispiel', source='Handelsblatt', title='BioLNG im Transport', url=None):
    row=Article(title=title,author=author,source=source,url=url or f'https://example.org/{days}/{author}/{source}',
        published_at=dt.datetime.now(dt.UTC)-dt.timedelta(days=days),title_hash=str(days))
    db.add(row);db.commit();return row


def research(web,client=1):
    return web.post(f'/api/v1/clients/{client}/journalist-research',json={
        'context_kind':'developed','context_id':1,'query':'BioLNG Transport'})


def test_profile_roundtrip_and_legacy_contact_are_one_record(web,db):
    data=create(web,email='anna@example.org');body=payload(data)
    body['profile'].update(topics=['BioLNG'],story_types=['Interview'],relationship_status='Im Kontakt',
                           preferences='Kurze Datenangebote',last_interaction_at='2026-08-01T12:00:00Z')
    res=web.put('/api/v1/journalists/1',json=body)
    assert res.status_code==200,res.text
    assert res.json()['profile']['topics']==['BioLNG']
    assert res.json()['relationship']['last_interaction_at']=='2026-08-01T12:00:00+00:00'
    assert db.get(Contact,1).email=='anna@example.org'
    assert db.get(JournalistProfile,1).preferences=='Kurze Datenangebote'
    assert web.get('/api/v1/journalists/1').headers['cache-control']=='no-store'
    assert web.get('/journalists').status_code==200


def test_stale_profile_and_legacy_edits_do_not_overwrite(web,db):
    data=create(web);body=payload(data);body['profile']['topics']=['Transport']
    assert web.put('/api/v1/journalists/1',json=body).status_code==200
    assert web.put('/api/v1/journalists/1',json=body).status_code==409
    fresh=payload(web.get('/api/v1/journalists/1').json())
    db.get(Contact,1).notes='Legacy correction';db.commit()
    assert web.put('/api/v1/journalists/1',json=fresh).status_code==409
    assert db.get(Contact,1).notes=='Legacy correction'


def test_invalid_profile_changes_no_contact_fields(web,db):
    data=create(web);body=payload(data);body['contact']['email']='wrong@example.org'
    body['profile']['relationship_status']='Guessed'
    assert web.put('/api/v1/journalists/1',json=body).status_code==422
    assert db.get(Contact,1).email==''
    assert web.post('/api/v1/journalists',json={'name':'  '}).status_code==422
    assert web.post('/api/v1/journalists',json={'name':'Anna Beispiel','outlet':'Handelsblatt'}).status_code==409


def test_article_history_requires_both_name_and_outlet_with_explicit_aliases(web,db):
    data=create(web)
    article(db);article(db,source='Another outlet');article(db,source='handelsblatt.com');article(db,author='Other Person')
    body=payload(data);body['profile']['source_aliases']=['handelsblatt.com']
    res=web.put('/api/v1/journalists/1',json=body).json()
    assert {a['source'] for a in res['articles']}=={'Handelsblatt','handelsblatt.com'}
    assert res['contact']['email']==''


def test_rank_uses_recent_attributable_articles_and_excludes_do_not_contact(web,db):
    create(web);article(db,days=1);article(db,days=2);article(db,days=43);article(db,days=-1)
    article(db,days=3,author='dpa');article(db,days=4,author='Other Person',title='Football results')
    values,capped=journalists.rank(db,'BioLNG Transport',now=dt.datetime.now(dt.UTC))
    assert len(values)==1 and values[0]['article_count']==2
    assert values[0]['contact_id']==1 and values[0]['fit']=='Belegter Themenbezug'
    assert all(row['published_at'] and row['url'] for row in values[0]['evidence'])
    db.add(JournalistProfile(contact_id=1,relationship_status='Nicht kontaktieren'));db.commit()
    assert journalists.rank(db,'BioLNG',now=dt.datetime.now(dt.UTC))[0]==[]


def test_research_is_scoped_read_only_until_requested_and_deduplicates_running(web,db):
    url='/api/v1/clients/1/journalist-research?context_kind=developed&context_id=1'
    assert web.get(url).json()['research'] is None
    assert db.scalar(select(func.count()).select_from(JournalistResearch))==0
    assert research(web,2).status_code==404
    assert research(web,3).status_code==404
    assert research(web).status_code==202
    assert research(web).status_code==409
    assert web.get(url).json()['research']['status']=='running'
    assert web.get(url.replace('/clients/1/','/clients/2/')).status_code==404


def test_interrupted_research_can_be_retried_and_old_worker_cannot_publish(web,db):
    research(web);old=db.get(JournalistResearch,1)
    old.started_at=dt.datetime.now(dt.UTC)-dt.timedelta(minutes=11);db.commit()
    assert research(web).status_code==202
    db.refresh(old);assert old.status=='failed'
    journalists.run(db,1,providers=[])
    assert old.status=='failed'


def test_provider_failure_is_visible_and_only_metadata_enters_research(web,db):
    research(web);now=dt.datetime.now(dt.UTC)
    item=FeedItem(title='BioLNG Transport',link='https://example.org/fresh',source='Handelsblatt',
        author='Anna Beispiel',published_at=now-dt.timedelta(days=2),summary='x'*3000,language='de')
    def failed(): raise RuntimeError('SECRET_KEY should never be returned')
    journalists.run(db,1,providers=[('Good',True,lambda:[item,item]),('Bad',True,failed),('Disabled',False,failed)])
    row=db.get(JournalistResearch,1)
    assert row.status=='complete' and row.providers['Bad']['status']=='failed'
    assert row.providers['Good']['articles']==1
    assert 'SECRET' not in str(row.providers)+row.note
    assert row.results[0]['name']=='Anna Beispiel'
    assert db.scalar(select(func.count()).select_from(Article))==0
    evidence=db.scalar(select(JournalistEvidence));assert len(evidence.snippet)==1000
    assert db.scalar(select(func.count()).select_from(JournalistEvidence))==1
    assert 'Fehlende Treffer beweisen nicht' in row.note


def test_archive_only_is_distinct_from_fresh_zero_results(web,db):
    article(db);research(web)
    journalists.run(db,1,providers=[])
    assert db.get(JournalistResearch,1).status=='archive_only'
    assert len(db.get(JournalistResearch,1).results)==1
    research(web);journalists.run(db,2,providers=[('Live',True,lambda:[])])
    assert db.get(JournalistResearch,2).status=='complete'
    assert db.get(JournalistResearch,2).providers['Live']['articles']==0


def test_worker_failure_releases_persistent_running_lock(web,db,monkeypatch):
    research(web)
    def fail(*args):raise ValueError('private')
    monkeypatch.setattr(journalists,'run',fail)
    api.worker(sessionmaker(bind=db.get_bind()),1)
    db.expire_all();assert db.get(JournalistResearch,1).status=='failed'
    assert research(web).status_code==202


@pytest.mark.parametrize('url',['javascript:alert(1)','https://[invalid','https://user:password@example.org','https://','x'*2049])
def test_invalid_article_urls_are_not_published(url):
    assert not journalists.public_url(url)


def test_replaced_attempt_cannot_finish_after_its_network_call(web,db):
    research(web)
    def replace():
        record=db.get(JournalistResearch,1)
        record.status='failed'
        db.commit()
        return []
    journalists.run(db,1,providers=[('Slow',True,replace)])
    assert db.get(JournalistResearch,1).status=='failed'
    assert db.get(JournalistResearch,1).providers=={}


def test_thread_start_failure_leaves_retryable_job(web,db,monkeypatch):
    def unavailable(*args,release,**kwargs):
        release()
        raise RuntimeError('Cannot start thread')
    monkeypatch.setattr(api,'start_or_release',unavailable)
    assert research(web).status_code==503
    db.expire_all()
    assert db.get(JournalistResearch,1).status=='failed'
