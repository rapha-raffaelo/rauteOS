import datetime as dt
import json
import sqlite3
from types import SimpleNamespace

import pytest
from newspulse import daily_news_search as news

NOW = dt.datetime(2026, 11, 6, 8, 10, tzinfo=dt.UTC)
URL = 'https://news.example.org/acme'

def client(id=1, **extra):
    return SimpleNamespace(id=id,name='Acme GmbH',aliases=['Acme'],industry='Finanzen',keywords=['Broker'],alert_topics=[],country='DE',active=True,is_competitor=False,**extra)

def answer(**overrides):
    return json.dumps({'articles':[dict(url=URL,title='Acme wächst',published_at=(NOW-dt.timedelta(hours=2)).isoformat(),summary='Neue Meldung über Acme.',**overrides)]})

def test_claude_web_research_cached_once_per_day_and_filters_new_watermark(tmp_path):
    calls=[]
    def search(prompt):
        calls.append(prompt)
        assert 'WebSearch' in prompt and 'Acme GmbH' in prompt
        return answer(),[(URL,'Titel aus dem Suchwerkzeug')]
    args=dict(fetched_at=NOW,search=search,ledger_path=tmp_path/'news.db')
    items,errors=news.harvest([client()],NOW-dt.timedelta(days=1),**args)
    assert not errors and len(items)==1
    assert items[0].title=='Titel aus dem Suchwerkzeug'
    assert items[0].source=='news.example.org'
    news.harvest([client()],NOW-dt.timedelta(days=1),**args)
    assert len(calls)==1
    assert news.harvest([client()],NOW-dt.timedelta(hours=1),**args)==([],[])
    args['fetched_at']=NOW+dt.timedelta(days=1)
    news.harvest([client()],NOW,**args)
    assert len(calls)==2
    with sqlite3.connect(args['ledger_path']) as conn:
        assert URL in conn.execute('SELECT sources FROM web_research LIMIT 1').fetchone()[0]


def test_failure_is_durable_and_other_mandates_still_run(tmp_path):
    calls=[]
    def search(prompt):
        calls.append(prompt)
        if len(calls)==1:raise RuntimeError('secret-token')
        return '{"articles":[]}',[]
    args=dict(fetched_at=NOW,search=search,ledger_path=tmp_path/'news.db')
    items, errors=news.harvest([client(1),client(2)],NOW-dt.timedelta(days=1),**args)
    assert len(errors)==1 and 'secret' not in errors[0] and len(calls)==2
    news.harvest([client(1)],NOW-dt.timedelta(days=1),**args)
    assert len(calls)==2


def test_ignores_inactive_competitors_and_archived_clients(tmp_path):
    a,b,c=client(1),client(2),client(3,archived_at=NOW)
    a.active=False;b.is_competitor=True
    def unexpected(*args): raise AssertionError('should not call')
    assert news.harvest([a,b,c],NOW,fetched_at=NOW,search=unexpected,ledger_path=tmp_path/'news.db')==([],[])


@pytest.mark.parametrize('change',[
    {'url':'https://invented.example.org/story'},
    {'url':'http://127.0.0.1/private'},
    {'published_at':(NOW+dt.timedelta(days=1)).isoformat()},
    {'published_at':(NOW-dt.timedelta(days=3)).isoformat()},
    {'published_at':'2026-11-06'},
    {'published_at':None},
])
def test_rejects_unobserved_private_undated_old_and_future_articles(change):
    row=json.loads(answer())['articles'][0];row.update(change)
    items,rejected=news._parse(json.dumps({'articles':[row]}),[(URL,'Title'),('http://127.0.0.1/private','Private')],since=NOW-dt.timedelta(days=1),now=NOW)
    assert items==[] and rejected==1


def test_empty_results_are_valid_but_wrong_schema_fails():
    assert news._parse('{"articles":[]}',[],since=NOW,now=NOW)==([],0)
    with pytest.raises(ValueError):news._parse('{"queries":[]}',[],since=NOW,now=NOW)


def test_local_day_boundary_uses_berlin_date(tmp_path):
    early=dt.datetime(2026,11,5,23,30,tzinfo=dt.UTC)
    path=tmp_path/'news.db'
    news.harvest([client()],early-dt.timedelta(days=1),fetched_at=early,search=lambda p:('{"articles":[]}',[]),ledger_path=path)
    with sqlite3.connect(path) as conn:assert conn.execute('SELECT day FROM web_research').fetchone()[0]=='2026-11-06'
