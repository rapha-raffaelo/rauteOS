import datetime as dt
from urllib.parse import parse_qs, urlsplit
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from newspulse import media_reload as reload, config
from newspulse.db import make_engine
from newspulse.models import Base, Client, Article, Analysis, TopicHit, Run
from newspulse.ingest import FeedItem
from test_job import _FakeAnalyzer

@pytest.fixture
def session():
    engine=make_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def customer(session,name):
    c=Client(name=name,keywords=['Solar'],active=True,aliases=[])
    session.add(c);session.commit();return c

def test_exact_local_days_dedup_and_client_isolation(session):
    alpha=customer(session,'Alpha AG'); other=customer(session,'Beta AG')
    day=dt.date(2026,7,10)
    start=dt.datetime.combine(day,dt.time.min,tzinfo=config.local_zone())
    def item(title,time):
        return FeedItem(title,'https://example.org/'+str(time.timestamp()),'Example',time,None,'de')
    batch=[item('Alpha AG Solar Mitteilung',start),item('Alpha AG zu alt',start-dt.timedelta(seconds=1)),item('Alpha AG morgen',start+dt.timedelta(days=1))]
    calls=[]
    def fetch(url,*args,**kwargs): calls.append(url);return batch
    analyzer=_FakeAnalyzer()
    for _ in range(2):
        reload.execute(session,[day],{alpha.id:{'company':True,'keywords':['Solar']}},fetch=fetch,analyzer=analyzer)
    assert session.scalar(select(func.count()).select_from(Article))==1
    assert session.scalar(select(func.count()).select_from(Analysis))==1
    assert session.scalar(select(Analysis)).client_id==alpha.id
    assert session.scalar(select(func.count()).select_from(TopicHit))==1
    assert session.scalar(select(func.count()).select_from(Run))==0
    assert all('before:2026-07-11' in parse_qs(urlsplit(url).query)['q'][0] for url in calls)
    assert reload.read(session,reload.STATUS,{})['state']=='done'

def test_existing_article_gets_a_second_customer_link(session):
    a=customer(session,'Alpha AG');b=customer(session,'Beta AG')
    day=dt.date(2026,7,10)
    item=FeedItem('Alpha AG und Beta AG kooperieren','https://example.org/shared','Example',dt.datetime(2026,7,10,12,tzinfo=dt.UTC),None,'de')
    reload.execute(session,[day],{a.id:{'company':True,'keywords':[]},b.id:{'company':True,'keywords':[]}},fetch=lambda *a,**k:[item],analyzer=_FakeAnalyzer())
    assert session.scalar(select(func.count()).select_from(Article))==1
    assert set(session.scalars(select(Analysis.client_id)))=={a.id,b.id}

def test_invalid_dates_customers_and_keywords_are_rejected(session):
    c=customer(session,'Alpha AG')
    for days,choices in [([],[]),(['9999-01-01'],[{'id':c.id,'company':True}]),(['bad'],[]),(['2026-01-01'],[{'id':999,'company':True}]),(['2026-01-01'],[{'id':c.id,'keywords':['unknown']}])]:
        with pytest.raises(ValueError):reload.validate(session,days,choices)

def test_failed_search_is_visible_and_does_not_write_watermark(session):
    c=customer(session,'Alpha AG')
    def fail(*a,**k):raise TimeoutError()
    reload.execute(session,[dt.date(2026,7,10)],{c.id:{'company':True,'keywords':[]}},fetch=fail)
    state=reload.read(session,reload.STATUS,{})
    assert state['state']=='partial' and state['results'][0]['errors']
    assert session.scalar(select(func.count()).select_from(Run))==0


def test_valid_empty_google_feed_is_distinct_from_provider_failure(monkeypatch):
    day=dt.datetime(2026,1,1,tzinfo=dt.UTC)
    monkeypatch.setattr(reload.ingest,'_fetch_raw',lambda *a:b'<rss version="2.0"><channel><title>Google News</title></channel></rss>')
    assert reload.fetch_search_feed('https://news.google.com/rss/search',day,source='Google News',fetched_at=day)==[]
    monkeypatch.setattr(reload.ingest,'_fetch_raw',lambda *a:b'<html><body>Unavailable</body></html>')
    with pytest.raises(ValueError):reload.fetch_search_feed('https://news.google.com/rss/search',day,source='Google News',fetched_at=day)
