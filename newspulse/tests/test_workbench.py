"""Primary read models and Ask RAUTE ownership; no model calls or sends."""
import datetime as dt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from newspulse import assistant_context
from newspulse.models import Base, Client, Angle, Asset, ClientAction
from newspulse.web.app import create_app, get_db

@pytest.fixture
def db():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine,expire_on_commit=False)() as session:
        session.add_all([Client(id=1,name='Alpha',aliases=[],keywords=[],alert_topics=[]),
            Client(id=2,name='Beta',aliases=[],keywords=[],alert_topics=[]),
            Client(id=3,name='Rival',is_competitor=True,aliases=[],keywords=[],alert_topics=[])])
        session.flush()
        angle=Angle(client_id=1,subject='Hypothesis',message='Proposal',context='Unverified idea',article_ids=[])
        session.add(angle);session.flush()
        session.add(Asset(id=1,client_id=1,angle_id=angle.id,kind='kundenmail',title='Draft',body='Client statement, not verified'))
        session.commit();yield session
    engine.dispose()

@pytest.fixture
def web(db):
    app=create_app();app.dependency_overrides[get_db]=lambda:db
    with TestClient(app) as client:yield client


def test_primary_reads_are_scoped_and_drafts_are_not_delivery(web,db):
    result=web.get('/api/v1/workbench/clients');assert result.status_code==200,result.text
    assert {r['client']['name'] for r in result.json()['clients']}=={'Alpha','Beta'}
    data=web.get('/api/v1/workbench/clients/1').json()
    assert data['summary']['actions_quarter']['total']==0
    assert data['texts'][0]['title']=='Draft' and not data['texts'][0]['released_at']
    assert not web.get('/api/v1/workbench/clients/2').json()['texts']
    assert web.get('/api/v1/workbench/clients/3').status_code==404
    assert web.get('/api/v1/workbench/assets').headers['cache-control']=='no-store'
    assert db.scalar(select(func.count()).select_from(ClientAction))==0


def test_ask_scope_validates_before_streaming(web):
    for params in [dict(scope='asset',client_id=2,asset_type='asset',asset_id=1),
        dict(scope='client',client_id=3),dict(scope='client',client_id=999),
        dict(scope='opportunity',client_id=2,opportunity_kind='developed',opportunity_id=1)]:
        assert web.get('/api/assistant/stream',params={'q':'Question',**params}).status_code==404
    assert web.get('/api/assistant/stream',params={'q':'Question','scope':'global','client_id':1}).status_code==422


def test_ask_uses_saved_text_and_global_delivery_gaps(db):
    scope,text=assistant_context.build(db,scope='asset',client_id=1,asset_type='asset',asset_id=1)
    assert scope=='asset' and 'Client statement, not verified' in text
    assert 'Beta' not in text
    _,global_text=assistant_context.build(db,scope='global')
    assert 'delivered_quarter' in global_text and 'promised_quarter' in global_text


def test_ask_stream_has_context_and_releases_transaction(web,db,monkeypatch):
    from newspulse.web.routes import assistant
    from newspulse.streaming import StreamEvent
    def stream(prompt,**kwargs):
        assert 'Client statement, not verified' in prompt
        assert not db.in_transaction()
        yield StreamEvent('text','Read-only answer')
        yield StreamEvent('done','')
    monkeypatch.setattr(assistant,'stream_assistant',stream)
    response=web.get('/api/assistant/stream',params=dict(q='Improve?',scope='asset',client_id=1,asset_type='asset',asset_id=1))
    assert response.status_code==200 and 'Read-only answer' in response.text
    assert db.get(Asset,1).body=='Client statement, not verified'


def test_opportunity_chat_carries_dated_journalist_research(db):
    from newspulse.models import JournalistResearch
    db.add(JournalistResearch(client_id=1,context_kind='developed',context_id=1,
        query='Data reporting',status='archive_only',providers={'demo':{'status':'not_configured'}},
        results=[{'journalist':'Reporter Example','articles':[{'url':'https://example.org/story','title':'Data story'}]}],
        note='Archive only; no live lookup'))
    db.commit()
    _,text=assistant_context.build(db,scope='opportunity',client_id=1,
        opportunity_kind='developed',opportunity_id=1)
    assert 'Reporter Example' in text and 'https://example.org/story' in text
    assert 'archive_only' in text and 'not_configured' in text


def test_developed_opportunities_and_activity_are_visible_without_inflating_delivery(web,db):
    from newspulse.models import OpportunityWorkspace, OpportunityEvent
    workspace=OpportunityWorkspace(client_id=1,context_kind='developed',context_id=1,angle_id=1,status='active')
    db.add(workspace);db.flush()
    db.add(OpportunityEvent(workspace_id=workspace.id,kind='activated',actor='Consultant',detail={'contact_ids':[7,8]}))
    db.commit()
    data=web.get('/api/v1/workbench/clients/1').json()
    assert data['summary']['opportunities']==1
    assert data['summary']['actions_quarter']['total']==0
    assert data['activity'][0]['kind']=='activated'
    assert data['activity'][0]['selected_journalists']==2
    assert web.get('/api/v1/workbench/clients/2').json()['activity']==[]
    workspace.status='closed';db.commit()
    assert web.get('/api/v1/workbench/clients/1').json()['summary']['opportunities']==0


def test_detected_angle_is_not_counted_twice_and_dismissed_ideas_are_excluded(db):
    from newspulse import desk
    from newspulse.models import Article, NewsjackOpportunity, Standing
    now=dt.datetime.now(dt.UTC)
    article=Article(title='News',url='https://example.org/test-count',source='Paper',published_at=now,title_hash='test-count')
    db.add(article);db.flush()
    detected=NewsjackOpportunity(client_id=1,article_id=article.id,standing=Standing.BELEGT,reason='Fits',window_ends_at=now+dt.timedelta(days=1))
    db.add(detected);db.flush()
    db.add(Angle(client_id=1,newsjack_id=detected.id,subject='Detected angle',message='Proposal',context='News'))
    db.get(Angle,1).dismissed_at=now;db.commit()
    assert desk._opportunity_counts(db,now)[1]==1
