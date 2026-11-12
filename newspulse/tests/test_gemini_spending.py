import datetime as dt
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from newspulse.models import Base
from newspulse import gemini_spending as spending

@pytest.fixture
def session():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as s: yield s

def setup(session):
    return spending.save_config(session,'billing-project.costs.export_table','gemini-project','ABC-DEF','EU')

def row(currency='EUR'):
    return {'currency':currency,'entries':2,'gross':Decimal('12.34'),'credits':Decimal('-2.34'),'exported_at':dt.datetime(2026,11,12,tzinfo=dt.UTC)}

def test_missing_export_never_means_zero(session):
    assert spending.refresh(session,fetch=lambda *a:pytest.fail())['state']=='not_configured'
    setup(session)
    result=spending.refresh(session,fetch=lambda *a:[])
    assert result['state']=='no_data' and 'net' not in result

def test_costs_credits_cache_and_config_scope(session):
    setup(session)
    result=spending.refresh(session,fetch=lambda *a:[row()])
    assert result['net']=='10.00' and result['credits']=='-2.34'
    assert spending.refresh(session,fetch=lambda *a:pytest.fail())['net']=='10.00'
    spending.save_config(session,'billing-project.costs.export_table','another-project','ABC-DEF','EU')
    assert 'net' not in spending.view(session)

def test_month_rollover_and_failed_refresh_preserves_only_current_data(session,monkeypatch):
    moment=dt.datetime(2026,11,12,tzinfo=dt.UTC)
    monkeypatch.setattr(spending,'now',lambda:moment)
    setup(session)
    spending.refresh(session,fetch=lambda *a:[row()])
    moment+=dt.timedelta(minutes=16)
    def fail(*a): raise RuntimeError('secret provider details')
    data=spending.refresh(session,fetch=fail)
    assert data['state']=='error' and data['net']=='10.00'
    assert 'secret' not in data['error']
    moment=dt.datetime(2026,12,1,tzinfo=dt.UTC)
    data=spending.refresh(session,fetch=fail)
    assert 'net' not in data

def test_mixed_currencies_refused(session):
    setup(session)
    data=spending.refresh(session,fetch=lambda *a:[row(),row('USD')])
    assert data['state']=='error' and 'net' not in data

def test_identifier_injection_rejected(session):
    with pytest.raises(ValueError):
        spending.save_config(session,'project.dataset.table`; DROP TABLE x','gemini-project','ABC','EU')
    assert not spending.view(session)['config']

def test_query_uses_scoped_parameters_and_bounded_read_only_sql(monkeypatch):
    from google.cloud import bigquery
    seen={}
    class Job:
        def result(self, **kwargs):
            seen['result']=kwargs
            return [row()]
    class Client:
        def __init__(self, **kwargs): seen['client']=kwargs
        def query(self, sql, **kwargs): seen.update(sql=sql,options=kwargs);return Job()
        def close(self): seen['closed']=True
    monkeypatch.setattr(bigquery,'Client',Client)
    config={'table':'billing-project.costs.export_table','project':'gemini-project','services':['ABC'],'location':'EU'}
    spending.query(config,dt.datetime(2026,11,1,tzinfo=dt.UTC),dt.datetime(2026,11,12,tzinfo=dt.UTC))
    assert 'project.id = @project' in seen['sql'] and 'service.id IN UNNEST(@services)' in seen['sql']
    assert 'UNNEST(credits)' in seen['sql']
    assert 'gemini-project' not in seen['sql']
    options=seen['options']['job_config']
    assert options.maximum_bytes_billed==1_000_000_000
    assert {p.name:p.value for p in options.query_parameters if hasattr(p,'value')}['project']=='gemini-project'
    assert seen['closed'] and seen['result']['timeout']==25
