"""Read-only, bounded retrieval across the workspace, independent of the open tab."""
from __future__ import annotations

import json
import re
from sqlalchemy import String, cast, or_, select
from . import guide, models as m
from .matching import terms_matcher

_STOP = set('wie was wer welche welcher welchen welches ist sind das die der den dem des ein eine einer einen einem und oder für von mit zum zur im in am an auf zu mir bitte über kann kannst du wir uns the a an of in is are what how who about please'.split())
MAX_CHARS = 65000


def _bounded(items, budget):
    result = []
    for item in items:
        size = len(json.dumps(item, ensure_ascii=False, default=str)) + 2
        if size > budget: continue
        result.append(item)
        budget -= size
    return result


def mentioned_clients(session, question):
    result = []
    for client in session.scalars(select(m.Client).order_by(m.Client.id)):
        matcher = terms_matcher([n for n in [client.name, client.legal_name, *(client.aliases or [])] if n])
        if matcher and matcher.search(question.casefold()): result.append(client)
    return result


def _excerpt(value, terms, limit=1800):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    hits = [text.casefold().find(term) for term in terms if term in text.casefold()]
    start = max(0, min(hits) - 200) if hits and len(text) > limit else 0
    return ('…' if start else '') + text[start:start+limit] + ('…' if len(text) > start+limit else '')


def build(session, question, *, client_id=None, previous_question=''):
    terms = list(dict.fromkeys(t for t in re.findall(r'[\w-]+', question.casefold())
                              if len(t) >= 3 and t not in _STOP))[:16]
    if any(t.startswith(('struktur', 'aufgebaut', 'gehört', 'eigent')) for t in terms):
        terms += ['eigentümer', 'gesellschafter', 'muttergesellschaft', 'tochtergesellschaft', 'rechtsform', 'geschäftsführung']
    clients = list(session.scalars(select(m.Client).order_by(m.Client.id)))
    named = mentioned_clients(session, question)
    if not named and previous_question:
        named = mentioned_clients(session, previous_question)
    focus = [c.id for c in named] or ([client_id] if client_id else [])
    names = {c.id: c.name for c in clients}
    data = dict(search_scope='Gesamtes System',
        note='Arbeitskontext ist nur Fokus, keine Suchgrenze. Treffer sind eine begrenzte Auswahl, kein vollständiger Datenbestand. Fehlende Treffer beweisen nicht, dass keine Daten existieren.',
        mentioned_client_ids=[c.id for c in named],
        clients=_bounded((dict(id=c.id, name=c.name, legal_name=c.legal_name, active=c.active,
                      competitor=c.is_competitor, website=c.website)
                      for c in sorted(clients, key=lambda c: c.id not in focus)), 10000),
        guides=_bounded((dict(client_id=c.id, name=c.name, text=guide.for_prompt(c)[:4000])
                for c in clients if c.id in focus), 12000), results=[])
    budget = MAX_CHARS - len(json.dumps(data, ensure_ascii=False, default=str))
    # Search all these stores, including archived clients. No database writes,
    # settings, credentials or external lookup are involved.
    stores = [
        (m.ClientFact, ('key','value','source_title'), ('source_url','filled_by','evidence_type','confidence','fact_status','is_primary'), {'profil','profile','unternehmen','struktur','eigentuemer','eigentümer'}, 100),
        (m.GuideSource, ('filename','text'), ('uploaded_at',), {'dokument','dokumente','guide'}, 8),
        (m.Task, ('title','note','owner'), ('status','due_on','priority'), {'aufgaben','aufgabe','tasks'}, 15),
        (m.OpportunityWorkspace, ('storyline','data'), ('status','context_kind','context_id'), {'chancen','opportunities','story'}, 12),
        (m.Angle, ('subject','message','context'), ('generated_at','dismissed_at'), {'ideen','impulse'}, 12),
        (m.Asset, ('title','body'), ('kind','released_at'), {'texte','entwürfe','texts'}, 12),
        (m.Outreach, ('subject','message','journalist','outlet'), ('state','released_at'), {'pitch','pitches','ansprache'}, 12),
        (m.MarketSignal, ('title','summary','publisher'), ('url','kind','effective_at','deadline_at'), {'markt','marktsignale'}, 12),
        (m.PlanHook, ('title','reason'), ('month','day','state'), {'redaktionsplan','termine'}, 12),
        (m.Issue, ('title','description'), ('status','owner'), {'issues','risiken','krisen'}, 12),
        (m.ClientAction, ('title','note'), ('happened_at',), {'leistungen','aktivitäten'}, 12),
        (m.LinkedInPost, ('title','body','author'), ('status','published_url','planned_on'), {'linkedin'}, 12),
        (m.Contact, ('name','outlet','beat','notes'), ('position',), {'journalisten','kontakte','medien'}, 12),
        (m.Deal, ('company','contact_name','next_step','note'), ('stage','value_eur','owner'), {'sales','deals','crm'}, 12),
        (m.Article, ('title','summary_text','source'), ('url','published_at'), {'artikel','archiv','meldungen','berichterstattung'}, 15),
    ]
    for model, fields, metadata, category_terms, cap in stores:
        store_budget = min(budget, 20000 if model is m.ClientFact else 6000)
        columns = [cast(getattr(model, field), String) for field in fields]
        conditions = [column.icontains(term, autoescape=True) for column in columns for term in terms]
        if focus and hasattr(model, 'client_id'):
            conditions.append(model.client_id.in_(focus))
        if category_terms.intersection(terms): conditions.append(True)
        if not conditions: continue
        query = select(model).where(or_(*conditions))
        if focus and hasattr(model, 'client_id'):
            query = query.order_by(model.client_id.in_(focus).desc())
        rows = session.scalars(query.order_by(model.id.desc()).limit(cap * 4)).all()
        def rank(row):
            text = ' '.join(str(getattr(row, f) or '') for f in fields).casefold()
            return (getattr(row, 'client_id', None) in focus, sum(t in text for t in terms), row.id)
        rows.sort(key=rank, reverse=True)
        for row in rows[:cap]:
            identity = getattr(row, 'client_id', None)
            result = dict(type=model.__tablename__, id=row.id, client_id=identity,
                          client=names.get(identity),
                          fields={f:_excerpt(getattr(row,f) or '',terms) for f in fields},
                          metadata={f:getattr(row,f) for f in metadata})
            size = len(json.dumps(result, ensure_ascii=False, default=str)) + 2
            if size > store_budget: continue
            data['results'].append(result)
            budget -= size
            store_budget -= size
    data['selection_limited'] = True
    return data
