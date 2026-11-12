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
    assets_response=web.get('/api/v1/workbench/assets')
    assert assets_response.status_code==200,assets_response.text
    assert assets_response.headers['cache-control']=='no-store'
    assert assets_response.json()['texts'][0]['title']=='Draft'
    assert assets_response.json()['texts'][0]['href']=='/client/1/advice?eintrag=anlass-1#asset-text-1'
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


def test_ask_finds_other_client_profile_from_selected_context(web, db, monkeypatch):
    from newspulse.models import ClientFact
    from newspulse.web.routes import assistant
    from newspulse.streaming import StreamEvent
    db.get(Client, 1).name = 'Remexian'
    db.get(Client, 2).name = 'Zenchef'
    db.add(ClientFact(client_id=2, key='A01.01', value='Zenchef SAS gehört einer Holding.',
                      source_url='https://example.org/zenchef', filled_by='recherche'))
    db.commit()
    def stream(prompt, **kwargs):
        assert 'Zenchef SAS gehört einer Holding.' in prompt
        assert 'https://example.org/zenchef' in prompt
        assert 'SYSTEMWEITE SUCHERGEBNISSE' in prompt
        assert not db.in_transaction()
        yield StreamEvent('text', 'Zenchef gefunden')
        yield StreamEvent('done', '')
    monkeypatch.setattr(assistant, 'stream_assistant', stream)
    result = web.get('/api/assistant/stream', params=dict(q='Wie ist Zenchef strukturiert?', scope='client', client_id=1))
    assert result.status_code == 200 and 'Zenchef gefunden' in result.text


def test_system_search_finds_unselected_tasks_archived_profiles_and_documents(db):
    from newspulse import assistant_search
    from newspulse.models import ClientFact, GuideSource, Task
    db.get(Client, 2).active = False
    db.add_all([ClientFact(client_id=2, key='R05.01', value='Beta baut Spezialroboter.'),
                GuideSource(client_id=2, filename='Positionierung', text='Spezialroboter für Kliniken.'),
                Task(client_id=2, title='Robotik-Pressegespräch vorbereiten')])
    db.commit()
    found = assistant_search.build(db, 'Was wissen wir über Beta?', client_id=1)
    assert found['mentioned_client_ids'] == [2]
    assert {r['type'] for r in found['results']} >= {'client_facts','guide_sources','tasks'}
    assert 'Spezialroboter' in str(found)
    assert assistant_search.build(db, 'Welche Aufgaben sind offen?', client_id=1)['results']


def test_system_search_keeps_followup_client_and_bounds_the_snapshot(db):
    import json
    from newspulse import assistant_search
    from newspulse.models import ClientFact
    db.add_all(ClientFact(client_id=2, key=f'custom-{n}', value='Langer Text ' * 1000) for n in range(80))
    db.commit()
    found = assistant_search.build(db, 'Und wer führt das Unternehmen?', client_id=1,
                                    previous_question='Wie arbeitet Beta?')
    assert found['mentioned_client_ids'] == [2]
    assert len(json.dumps(found, ensure_ascii=False, default=str)) <= assistant_search.MAX_CHARS + 100


def test_system_search_bounds_large_directory_and_prioritizes_named_client(db):
    import json
    from newspulse import assistant_search
    db.add_all(Client(name=f'Company {n} ' + 'x' * 200, legal_name='y' * 200) for n in range(200))
    db.commit()
    found = assistant_search.build(db, 'Beta', client_id=1)
    assert found['clients'][0]['name'] == 'Beta'
    assert len(json.dumps(found, ensure_ascii=False, default=str)) <= assistant_search.MAX_CHARS


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


def test_card_edit_uses_existing_validation_and_keeps_unedited_preferences(web, db):
    db.get(Client, 1).muted_categories = ['boerse']
    db.commit()
    response = web.get('/api/v1/workbench/clients/1/settings')
    assert response.headers['cache-control'] == 'no-store'
    data = response.json()
    body = dict(data['values'], revision=data['revision'], name='Alpha New',
                aliases='Alpha; A', actions_per_quarter='4')
    saved = web.put('/api/v1/workbench/clients/1/settings', json=body)
    assert saved.status_code == 200, saved.text
    assert db.get(Client, 1).name == 'Alpha New'
    assert db.get(Client, 1).aliases == ['Alpha', 'A']
    assert db.get(Client, 1).actions_per_quarter == 4
    assert db.get(Client, 1).muted_categories == ['boerse']
    assert web.put('/api/v1/workbench/clients/1/settings', json=body).status_code == 409
    assert web.get('/api/v1/workbench/clients').json()['clients'][0]['client']['name'] == 'Alpha New'


@pytest.mark.parametrize('field,value', [('name', ''), ('name', 'Beta'), ('country', 'invalid'), ('actions_per_quarter', '-1')])
def test_card_edit_rejects_invalid_values_without_changes(web, db, field, value):
    data = web.get('/api/v1/workbench/clients/1/settings').json()
    body = dict(data['values'], revision=data['revision'])
    body[field] = value
    assert web.put('/api/v1/workbench/clients/1/settings', json=body).status_code == 422
    assert db.get(Client, 1).name == 'Alpha'
    assert db.get(Client, 1).actions_per_quarter is None


def test_card_delete_only_removes_selected_mandate_from_active_roster(web, db):
    response = web.request('DELETE', '/api/v1/workbench/clients/1', json={'name': 'Wrong name'})
    assert response.status_code == 409
    assert db.get(Client, 1).active is True
    for _ in range(2):
        response = web.request('DELETE', '/api/v1/workbench/clients/1', json={'name': 'Alpha'})
        assert response.status_code == 200
    assert db.get(Client, 1).active is False
    assert db.get(Client, 2).active is True
    assert db.get(Asset, 1).body == 'Client statement, not verified'
    assert db.get(Angle, 1) is not None
    from newspulse.web.navigation import clients_for_nav
    assert [c.id for c in clients_for_nav(db)] == [2]
    assert [r['client']['id'] for r in web.get('/api/v1/workbench/clients').json()['clients']] == [2]
    web.post('/settings/clients/1/reactivate', follow_redirects=False)
    assert db.get(Client, 1).active is True


@pytest.mark.parametrize('identity', [3, 999])
def test_card_management_rejects_competitors_and_unknown_ids(web, identity):
    assert web.get(f'/api/v1/workbench/clients/{identity}/settings').status_code == 404
    assert web.request('DELETE', f'/api/v1/workbench/clients/{identity}', json={'name': 'Rival'}).status_code == 404


def test_the_overview_names_the_company_its_goal_and_its_next_steps(web, db):
    """Spec 09: "Das Unternehmen" reads the researched description (R05.01)
    and the client's own goal (Q01.02); "Nächste Schritte" are this mandate's
    open decisions from the Desk."""
    from newspulse.models import ClientFact
    long = 'Alpha baut Roboterarme für Operationssäle. ' * 12
    db.add_all([ClientFact(client_id=1, key='R05.01', value=long, is_primary=True),
                ClientFact(client_id=1, key='Q01.02', value='Marktführer in DACH werden.', is_primary=True)])
    db.commit()
    data = web.get('/api/v1/workbench/clients/1').json()
    assert data['company']['description'].startswith('Alpha baut Roboterarme')
    assert len(data['company']['description']) <= 280
    assert data['company']['goal'] == 'Marktführer in DACH werden.'
    assert isinstance(data['next_steps'], list)
    assert web.get('/api/v1/workbench/clients/2').json()['company']['description'] == ''


def test_stories_and_content_leads_with_the_running_stories(web, db):
    """Spec 09: the story cards are each mandate's open opportunities."""
    data = web.get('/api/v1/workbench/assets').json()
    assert [s['title'] for s in data['stories']] == ['Hypothesis']
    assert data['stories'][0]['client']['name'] == 'Alpha'
    assert data['stories'][0]['href'].startswith('/client/1/themen#thema-developed-')


def test_social_monitoring_scopes_published_posts(web, db):
    from newspulse.models import LinkedInPost
    db.add_all([LinkedInPost(client_id=1,title='Published',status='veroeffentlicht'),LinkedInPost(client_id=1,title='Draft',status='entwurf'),LinkedInPost(client_id=2,title='Other',status='veroeffentlicht')]);db.commit()
    result=web.get('/api/v1/workbench/clients/1/monitoring/social')
    assert result.status_code==200
    assert [p['title'] for p in result.json()['posts']]==['Published']
    assert result.json()['metrics_connected'] is False
    assert web.get('/api/v1/workbench/clients/3/monitoring/social').status_code==404


def test_today_news_local_day_and_client_scope(db):
    from newspulse.models import Article, Analysis, Category
    from newspulse.web.routes.workbench import today_news
    now=dt.datetime(2026,11,6,12,tzinfo=dt.timezone.utc)
    cases=[('today',1,now,True),('other',2,now,True),('irrelevant',1,now,False),('yesterday',1,now-dt.timedelta(days=1),True),('midnight',1,dt.datetime(2026,11,5,23,tzinfo=dt.timezone.utc),True),('tomorrow',1,dt.datetime(2026,11,6,23,tzinfo=dt.timezone.utc),True)]
    for i,(title,cid,published,relevant) in enumerate(cases):
        article=Article(title=title,url=f'https://example.org/{i}',source='Paper',title_hash=str(i),published_at=published)
        db.add(article);db.flush()
        db.add(Analysis(article_id=article.id,client_id=cid,is_relevant=relevant,category=next(iter(Category)),relevance_score=5,importance_score=3))
    db.commit()
    result=today_news(db,1,now=now)
    assert result['total']==2
    assert [r['title'] for r in result['items']]==['today','midnight']
    # A quiet morning still shows the latest coverage: the archive's rows before today.
    assert [r['title'] for r in result['earlier']]==['yesterday']
    assert result['earlier'][0]['importance']==3 and result['earlier'][0]['analysis_id']


def test_today_redirect_and_kpi_placeholder(web):
    response = web.get('/client/1/heute', follow_redirects=False)
    assert response.headers['location'] == '/client/1/overview'
    response = web.get('/client/1/monitoring/kpis')
    assert response.status_code == 200
    assert 'monitoring_kpis' in response.text
    assert web.get('/client/999/monitoring/kpis').status_code == 404


def test_daily_overview_includes_more_than_eight_news(db):
    from newspulse.models import Article, Analysis, Category
    from newspulse.web.routes.workbench import today_news
    now = dt.datetime(2026, 11, 9, 12, tzinfo=dt.timezone.utc)
    for i in range(12):
        article = Article(title=f'News {i}', url=f'https://example.org/daily/{i}', source='Paper', title_hash=f'daily{i}', published_at=now)
        db.add(article)
        db.flush()
        db.add(Analysis(article_id=article.id, client_id=1, is_relevant=True, category=next(iter(Category)), relevance_score=5, importance_score=3))
    db.commit()
    result = today_news(db, 1, now=now)
    assert result['total'] == len(result['items']) == 12
