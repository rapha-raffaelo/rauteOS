"""Journalist intelligence from explicit profiles and attributable article metadata."""
from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from dataclasses import asdict
from urllib.parse import urlsplit

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from . import config, newsapis, outreach
from .models import Angle, Article, Contact, JournalistEvidence, JournalistProfile, JournalistResearch, NewsjackOpportunity, Standing

WINDOW_DAYS = 42
RELATIONSHIPS = ['Unbekannt', 'Neu', 'Im Kontakt', 'Gute Beziehung', 'Ruhend', 'Nicht kontaktieren']
LIST_FIELDS = ('topics','specialties','story_types','companies','source_aliases')
STOP = set('aber auch auf aus bei das dass dem den der des die ein eine einer eines eine für im in ist mit nach oder sich sind über und vom von vor wie wird zum zur'.split())


def normalized(value):
    return ' '.join((value or '').casefold().split())


def source_name(value):
    return normalized(value).removeprefix('https://').removeprefix('http://').removeprefix('www.').rstrip('/')


def public_url(value):
    try:
        parsed = urlsplit(value)
        return len(value) <= 2048 and parsed.scheme in {'http', 'https'} and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def is_person(name):
    return bool(name and len(name.strip()) > 3 and normalized(name) not in {'redaktion','dpa','reuters','afp','presseportal'})


def matches(contact: Contact, item: dict, profile: JournalistProfile | None = None):
    # A shared name alone does not identify a journalist at a different outlet.
    sources = [contact.outlet, *((profile.source_aliases or []) if profile else [])]
    return normalized(contact.name) == normalized(item['author']) and bool(contact.outlet) and any(
        source_name(source) == source_name(item['source']) for source in sources)


def article_dict(row, provider='Archiv'):
    return dict(id=row.id, title=row.title, url=row.url, source=row.source, author=row.author,
                published_at=row.published_at.isoformat(), provider=getattr(row,'provider',provider),
                snippet=(getattr(row,'snippet',None) or getattr(row,'summary_text',None) or '')[:1000])


def corpus(session: Session, *, since: dt.datetime | None = None, until: dt.datetime | None = None):
    items = {}
    capped = False
    for model in (Article, JournalistEvidence):
        stmt = select(model).where(model.author.is_not(None), model.author != '')
        if since: stmt = stmt.where(model.published_at >= since)
        if until: stmt = stmt.where(model.published_at <= until)
        rows = list(session.scalars(stmt.order_by(model.published_at.desc()).limit(2001)))
        capped |= len(rows) > 2000
        for row in rows[:2000]:
            if is_person(row.author) and public_url(row.url):
                items.setdefault(row.url, article_dict(row))
    return sorted(items.values(),key=lambda i:i['published_at'],reverse=True), capped


def relationship(session: Session, contact: Contact, profile: JournalistProfile | None):
    history = outreach.history_for_contact(session, contact.id)
    timeline = outreach.timeline(history)
    dates = [event.at for event in timeline]
    if profile and profile.last_interaction_at: dates.append(profile.last_interaction_at)
    return dict(tally=asdict(outreach.tally(history)), last_interaction_at=max(dates).isoformat() if dates else None,
                capped=len(history) >= outreach.MAX_HISTORY,
                timeline=[dict(at=event.at.isoformat(),kind=event.kind.value,subject=event.letter.subject,
                               mandate=event.mandate,state=event.letter.state.value,
                               href=f'/client/{event.letter.client_id}/advice#outreach-{event.letter.id}') for event in timeline])


def profile_data(session: Session, contact: Contact):
    profile = session.get(JournalistProfile,contact.id)
    articles,capped = corpus(session)
    return dict(contact={key:getattr(contact,key) for key in ('id','name','first_name','last_name','outlet','email','phone','beat','position','notes','updated_at')},
                profile={**{name: getattr(profile,name) if profile else [] for name in LIST_FIELDS},
                         'preferences':profile.preferences if profile else '',
                         'relationship_status':profile.relationship_status if profile else 'Unbekannt',
                         'last_interaction_at':profile.last_interaction_at if profile else None,
                         'revision':profile.revision if profile else 0},
                articles=[item for item in articles if matches(contact,item,profile)], corpus_capped=capped,
                relationship=relationship(session,contact,profile),relationship_options=RELATIONSHIPS)


def context(session: Session, client_id: int, kind: str, identity: int):
    if kind == 'detected':
        row = session.get(NewsjackOpportunity,identity)
        if row is None or row.client_id != client_id or row.standing not in {Standing.BELEGT}: return None
        article = session.get(Article,row.article_id)
        return dict(title=article.title if article else row.reason, description=row.reason)
    if kind == 'developed':
        row = session.get(Angle,identity)
        if row is None or row.client_id != client_id: return None
        return dict(title=row.subject,description=row.context)
    return None


def terms(query: str):
    return list(dict.fromkeys(word for word in re.findall(r'[\w-]+',query.casefold()) if len(word)>=3 and word not in STOP))[:16]


def rank(session: Session, query: str, *, now: dt.datetime):
    words = terms(query)
    items,capped = corpus(session,since=now-dt.timedelta(days=WINDOW_DAYS),until=now)
    contacts = list(session.scalars(select(Contact)))
    profiles = {p.contact_id:p for p in session.scalars(select(JournalistProfile))}
    grouped = defaultdict(list)
    for item in items:
        text = normalized(item['title']+' '+item['snippet'])
        matched = [word for word in words if re.search(r'(?<!\w)'+re.escape(word)+r'(?!\w)',text)]
        if matched:
            grouped[(normalized(item['author']),source_name(item['source']))].append({**item,'matched_terms':matched})
    results=[]
    for rows in grouped.values():
        head = rows[0]
        contact = next((c for c in contacts if matches(c,head,profiles.get(c.id))),None)
        profile = profiles.get(contact.id) if contact else None
        if profile and profile.relationship_status == 'Nicht kontaktieren': continue
        covered = sorted({term for row in rows for term in row['matched_terms']})
        relation = relationship(session,contact,profile) if contact else None
        results.append(dict(name=head['author'],outlet=head['source'],contact_id=contact.id if contact else None,
                            fit='Belegter Themenbezug' if len(rows)>1 else 'Möglicher Fit',
                            reason=f"{len(rows)} belegte Artikel in den letzten {WINDOW_DAYS} Tagen zu: {', '.join(covered)}.",
                            approach=(profile.preferences if profile and profile.preferences else
                                      'An einen der belegten Artikel anknüpfen; bevorzugtes Format ist nicht hinterlegt.'),
                            evidence=rows[:8],article_count=len(rows),relationship=relation))
    results.sort(key=lambda r:(r['article_count'],r['evidence'][0]['published_at']),reverse=True)
    return results[:20],capped


def run(session: Session, research_id: int, *, providers=None):
    """Bounded provider calls; errors cannot masquerade as a complete live search."""
    record=session.get(JournalistResearch,research_id)
    if record is None or record.status != 'running': return
    now=dt.datetime.now(dt.UTC); since=now-dt.timedelta(days=WINDOW_DAYS)
    query=record.query
    providers = providers if providers is not None else [
        ('Perigon',bool(config.PERIGON_API_KEY),lambda:newsapis.perigon(query,since,fetched_at=now)),
        ('Event Registry',bool(config.EVENT_REGISTRY_API_KEY),lambda:newsapis.event_registry(query,since,fetched_at=now)),
        ('mediastack',bool(config.MEDIASTACK_API_KEY),lambda:newsapis.mediastack(since,fetched_at=now))]
    states={}
    fetched={}
    session.commit()  # No database transaction is held during network calls.
    for name,enabled,fetch in providers:
        if not enabled:
            states[name]={'status':'not_configured','articles':0};continue
        try:
            fetched[name]=fetch()
        except Exception:
            # Provider errors may contain credentials; never expose them.
            states[name]={'status':'failed','articles':0}
            continue
    # A timed-out attempt may have been replaced while providers were running.
    claimed=session.execute(update(JournalistResearch).where(JournalistResearch.id==research_id,
        JournalistResearch.status=='running').values(status='running')).rowcount
    if claimed != 1:
        session.rollback()
        return
    for name,items in fetched.items():
        accepted=set()
        for item in items[:100]:
            if (not is_person(item.author) or not item.published_at or not item.published_at.tzinfo
                    or not since <= item.published_at <= now or not public_url(item.link)):
                continue
            # Savepoints isolate URL races between independent research jobs.
            from sqlalchemy.exc import IntegrityError
            try:
                with session.begin_nested():
                    existing=session.scalar(select(JournalistEvidence).where(JournalistEvidence.url==item.link))
                    if existing is None:
                        session.add(JournalistEvidence(url=item.link,title=item.title[:2000],source=item.source[:255],
                                    author=item.author[:255],published_at=item.published_at,fetched_at=now,
                                    snippet=(item.summary or '')[:1000],provider=name))
                        session.flush()
            except IntegrityError:
                if session.scalar(select(JournalistEvidence.id).where(JournalistEvidence.url==item.link)) is None:
                    raise
            accepted.add(item.link)
        states[name]={'status':'ok','articles':len(accepted)}
    results,capped=rank(session,record.query,now=now)
    live=any(state['status']=='ok' for state in states.values())
    record.providers=states;record.results=results;record.finished_at=dt.datetime.now(dt.UTC)
    record.status='complete' if live else 'archive_only'
    record.note=('Recherche in konfigurierten Quellen und Archiv. ' if live else 'Keine frische Quelle verfügbar; nur Archivbelege. ')+(
        'Die Quellen sind unvollständig. Fehlende Treffer beweisen nicht, dass jemand nichts veröffentlicht hat. '
        'Format und Beziehungsangaben stammen aus dem Kontaktbuch, nicht aus einer Vermutung.')
    if capped: record.note+=' Der Korpus wurde auf die neuesten 2.000 Artikel je Quelle begrenzt.'
    session.commit()
