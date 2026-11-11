"""Date-exact, customer-scoped Google News reloads, independent of sweep watermarks."""
from __future__ import annotations
import datetime as dt
import json
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode
from sqlalchemy import select
from . import config, gnews, job, ingest
from .models import Client, Setting
import xml.etree.ElementTree as ET

KEY = 'media_reload_preferences'
STATUS = 'media_reload_status'


def fetch_search_feed(url, since, *, source, fetched_at, per_entry_source=True, strict=True):
    """Treat valid empty search RSS as no results, and transport/HTML errors as failures."""
    raw = ingest._fetch_raw(url, 20.0)
    root = ET.fromstring(raw)
    if root.tag != 'rss' or root.find('channel') is None:
        raise ValueError('Keine gültige Google-News-Antwort')
    return ingest._parse_items(raw, url=url, since=since, source=source,
                               fetched_at=fetched_at, per_entry_source=per_entry_source,
                               strict=bool(root.findall('./channel/item')))


def read(session, key, default):
    row = session.get(Setting, key)
    try:
        return json.loads(row.value) if row else default
    except (ValueError, TypeError):
        return default


def write(session, key, value):
    session.merge(Setting(key=key, value=json.dumps(value, ensure_ascii=False)))
    session.commit()


def validate(session, dates, choices):
    today = dt.datetime.now(config.local_zone()).date()
    try:
        days = sorted(set(dt.date.fromisoformat(s) for s in dates))
    except (ValueError, TypeError):
        raise ValueError('Bitte gültige Kalendertage auswählen') from None
    if not days or len(days) > 90 or any(day > today for day in days):
        raise ValueError('Bitte 1 bis 90 Tage auswählen, spätestens heute')
    if not isinstance(choices, list) or not choices or len(choices) > 100:
        raise ValueError('Bitte mindestens einen Kunden auswählen')
    active = {str(c.id): c for c in session.scalars(select(Client).where(Client.active.is_(True), Client.is_competitor.is_(False)))}
    result = {}
    for choice in choices:
        if not isinstance(choice, dict) or str(choice.get('id')) not in active:
            raise ValueError('Unbekannter oder inaktiver Kunde')
        client = active[str(choice['id'])]
        keywords = choice.get('keywords', [])
        if not isinstance(keywords, list) or any(not isinstance(k, str) or k not in (client.keywords or []) for k in keywords):
            raise ValueError('Bitte Keywords aus dem Kundenprofil auswählen')
        names = choice.get('company') is True
        if not names and not keywords:
            raise ValueError(f'Bitte für {client.name} Unternehmen oder Keywords auswählen')
        result[client.id] = {'company': names, 'keywords': list(dict.fromkeys(keywords))}
    return days, result


def dated_url(url, day):
    parts = urlsplit(url)
    args = parse_qs(parts.query)
    # Broader provider bounds; exact local-day acceptance below is authoritative.
    args['q'] = [f"({args['q'][0]}) after:{day-dt.timedelta(days=1)} before:{day+dt.timedelta(days=1)}"]
    return urlunsplit(parts._replace(query=urlencode(args, doseq=True)))


def reload_day(session, client, day, choice, *, fetch=fetch_search_feed, analyzer=None):
    start = dt.datetime.combine(day, dt.time.min, tzinfo=config.local_zone())
    end = dt.datetime.combine(day+dt.timedelta(days=1), dt.time.min, tzinfo=config.local_zone())
    now = dt.datetime.now(dt.UTC)
    errors, items, topic_pairs = [], [], []
    queries = []
    lang, country = gnews.edition_for(client)
    if choice['company']:
        queries += [(feed.url, False) for feed in gnews.client_feeds([client])]
    for keyword in choice['keywords']:
        queries.append((gnews.query_url([keyword], lang=lang, country=country), True))
    for url, topic in queries:
        try:
            batch = fetch(dated_url(url, day), start, source='Google News', fetched_at=now, per_entry_source=True, strict=True)
            batch = [item for item in batch if item.published_at is not None and start <= item.published_at < end]
            items.extend(batch)
            if topic:
                topic_pairs.extend(job.Candidate(item=item, client=client) for item in batch)
        except Exception as exc:
            errors.append(f'{client.name}: Suche fehlgeschlagen ({type(exc).__name__})')
    candidates = job._match(items, [client], errors)
    known_urls, known_hashes = job._load_known(session)
    fresh = job.deduplicate(job._distinct_items(candidates + topic_pairs), known_urls=known_urls, known_title_hashes=known_hashes)
    stored = job._persist_articles(session, fresh, now) if fresh else []
    # Existing articles still need linking to this client; global dedup must not discard that association.
    for matched, articles in job._group_pairs(session, job._candidate_pairs(session, candidates)):
        job._analyze_and_persist(session, matched, articles, analyzer or job.get_analyzer(), errors)
    if topic_pairs:
        job._record_topic_hits(session, topic_pairs, now)
    return {'stored': len(stored), 'found': len(items), 'errors': errors}


def execute(session, days, choices, *, fetch=fetch_search_feed, analyzer=None):
    state = {'state':'running', 'days':[day.isoformat() for day in days], 'results':[]}
    write(session, STATUS, state)
    for client_id, choice in choices.items():
        client = session.get(Client, client_id)
        if not client or not client.active:
            continue
        for day in days:
            try:
                result = reload_day(session, client, day, choice, fetch=fetch, analyzer=analyzer)
            except Exception as exc:
                session.rollback()
                result = {'stored':0, 'found':0, 'errors':[f'Nachlauf fehlgeschlagen ({type(exc).__name__})']}
            state['results'].append({'client':client.name, 'day':day.isoformat(), **result})
            write(session, STATUS, state)
    state['state'] = 'partial' if any(r['errors'] for r in state['results']) else 'done'
    write(session, STATUS, state)
