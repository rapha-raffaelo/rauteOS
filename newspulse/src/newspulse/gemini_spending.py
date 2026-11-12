"""Read actual reported Gemini costs from a scoped Cloud Billing BigQuery export.

No model token-price estimates, prepaid balances, or implicit conversion of old
manual balances into top-ups. Credentials stay in server-side Google ADC.
"""
import datetime as dt
import json
import re
import threading
from decimal import Decimal
from zoneinfo import ZoneInfo

from .models import Setting

LOCK = threading.Lock()
PREFIX = 'gemini_spending:'


def now():
    return dt.datetime.now(dt.UTC)


def load(session, key):
    row = session.get(Setting, PREFIX + key)
    try:
        data = json.loads(row.value) if row else {}
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def store(session, key, value):
    row = session.get(Setting, PREFIX + key)
    if row is None:
        session.add(Setting(key=PREFIX + key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    session.commit()


def save_config(session, table, project, services, location):
    table, project, location = table.strip(), project.strip(), location.strip()
    ids = sorted(set(s.strip() for s in services.split(',') if s.strip()))
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,61}[a-z0-9]\.[A-Za-z_][A-Za-z0-9_]{0,1023}\.[A-Za-z0-9_]{1,1024}', table):
        raise ValueError('Export-Tabelle als projekt.dataset.tabelle angeben')
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,61}[a-z0-9]', project):
        raise ValueError('Bitte die Google-Cloud-Projekt-ID für Gemini angeben')
    if not ids or len(ids) > 20 or any(not re.fullmatch(r'[A-Za-z0-9-]{1,100}', s) for s in ids):
        raise ValueError('Gemini-Service-IDs aus dem Billing-Export angeben, durch Kommas getrennt')
    if not re.fullmatch(r'[A-Za-z0-9-]{2,40}', location):
        raise ValueError('BigQuery-Region angeben, beispielsweise EU')
    config = {'table':table, 'project':project, 'services':ids, 'location':location}
    with LOCK:
        store(session, 'config', config)
        store(session, 'cache', {})
    return view(session)


def period():
    local = now().astimezone(ZoneInfo('Europe/Zurich'))
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start.strftime('%Y-%m'), start.astimezone(dt.UTC)


def view(session):
    config, cache = load(session, 'config'), load(session, 'cache')
    month, _ = period()
    if cache.get('month') != month or cache.get('config') != config:
        cache = {}
    return {'config':config, 'month':month, 'state':cache.get('state', 'pending' if config else 'not_configured'),
            **{k:v for k,v in cache.items() if k != 'config'}}


def query(config, start, end):
    from google.cloud import bigquery
    # Identifier validated when saved; all values use query parameters.
    sql = f'''SELECT currency, COUNT(*) AS entries,
      SUM(CAST(cost AS NUMERIC)) AS gross,
      SUM(IFNULL((SELECT SUM(CAST(c.amount AS NUMERIC)) FROM UNNEST(credits) c), 0)) AS credits,
      MAX(export_time) AS exported_at
      FROM `{config['table']}`
      WHERE usage_start_time >= @start AND usage_start_time < @end
        AND project.id = @project AND service.id IN UNNEST(@services)
      GROUP BY currency'''
    client = bigquery.Client(project=config['table'].split('.')[0])
    job = None
    try:
        job = client.query(sql, location=config['location'], timeout=10, retry=None, job_retry=None,
            job_config=bigquery.QueryJobConfig(use_legacy_sql=False, maximum_bytes_billed=1_000_000_000,
                job_timeout_ms=20000, query_parameters=[
                    bigquery.ScalarQueryParameter('start', 'TIMESTAMP', start),
                    bigquery.ScalarQueryParameter('end', 'TIMESTAMP', end),
                    bigquery.ScalarQueryParameter('project', 'STRING', config['project']),
                    bigquery.ArrayQueryParameter('services', 'STRING', config['services'])]))
        return [dict(row) for row in job.result(timeout=25, retry=None, job_retry=None)]
    except Exception:
        if job is not None:
            try: job.cancel(timeout=3)
            except Exception: pass
        raise
    finally:
        client.close()


def refresh(session, fetch=query):
    with LOCK:
        session.expire_all()
        config = load(session, 'config')
        if not config:
            return view(session)
        month, start = period()
        old = load(session, 'cache')
        stamp = now()
        if old.get('month') == month and old.get('config') == config:
            try:
                if (stamp-dt.datetime.fromisoformat(old['attempted_at'])).total_seconds() < 900:
                    return view(session)
            except (KeyError, ValueError, TypeError): pass
        else:
            old = {}
        record = {**old, 'month':month, 'config':config, 'attempted_at':stamp.isoformat()}
        try:
            rows = fetch(config, start, stamp)
            if len(rows) > 1:
                raise ValueError('mixed currencies')
            record = {k:v for k,v in record.items() if k in {'month','config','attempted_at'}}
            record.update(checked_at=stamp.isoformat(), state='no_data')
            if rows:
                row = rows[0]
                gross, credits = Decimal(str(row['gross'])), Decimal(str(row['credits']))
                if not gross.is_finite() or not credits.is_finite() or not re.fullmatch('[A-Z]{3}', row['currency']):
                    raise ValueError('invalid costs')
                record.update(state='ready', gross=str(gross), credits=str(credits), net=str(gross+credits),
                              currency=row['currency'], exported_at=row['exported_at'].isoformat() if row.get('exported_at') else None)
        except Exception as exc:
            # Never expose credential paths, SQL, or provider internals to the UI.
            record.update(state='error', error='Billing-Daten konnten nicht geladen werden. Export, Filter und Serverzugriff prüfen.')
            if exc.__class__.__name__ == 'DefaultCredentialsError':
                record['error'] = 'Google-Cloud-Zugang für BigQuery fehlt auf dem Server'
            elif isinstance(exc, ValueError):
                record['error'] = 'Der Export liefert uneinheitliche Währungen oder ungültige Kosten'
        store(session, 'cache', record)
        return view(session)
