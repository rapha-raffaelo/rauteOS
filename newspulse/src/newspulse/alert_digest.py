"""Read-only, client-scoped bundles of recent alerts about one event."""
import datetime as dt
import hashlib
from types import SimpleNamespace

from sqlalchemy import select
from . import coverage_identity, stories
from .models import Analysis, Angle, Article, Client


def bundles(session, client_id=None, now=None):
    now = now or dt.datetime.now(dt.UTC)
    query = select(Client).where(Client.active.is_(True), Client.is_competitor.is_(False))
    if client_id is not None:
        query = query.where(Client.id == client_id)
    result = []
    for client in session.scalars(query):
        rows = session.execute(select(Article, Analysis).join(Analysis, Analysis.article_id == Article.id).where(
            Analysis.client_id == client.id, Analysis.is_alert.is_(True), Analysis.is_relevant.is_(True),
            Analysis.dismissed_at.is_(None), Article.published_at >= now-dt.timedelta(hours=24),
            Article.published_at <= now).order_by(Analysis.importance_score.desc(), Article.published_at.desc()).limit(200))
        articles = [a for a, _ in coverage_identity.unique(rows)]
        by_id = {a.id: a for a in articles}
        used = set()
        groups = []
        # Source citations in a developed topic already identify a shared event.
        for angle in session.scalars(select(Angle).where(Angle.client_id == client.id,
                Angle.dismissed_at.is_(None)).order_by(Angle.generated_at.desc()).limit(100)):
            members = [by_id[i] for i in (angle.article_ids or []) if i in by_id and i not in used]
            if len(members) >= 2:
                groups.append((f'topic-{angle.id}', members, f'/client/{client.id}/themen?kind=developed&context={angle.id}'))
                used.update(a.id for a in members)
        remaining = [SimpleNamespace(headline=a.title, source=a.source, importance=0, article=a)
                     for a in articles if a.id not in used]
        # Exact meaningful token sets also cover short headlines such as
        # 'Qonto erhält Banklizenz' / 'Qonto erhält die Banklizenz'.
        exact = {}
        for item in remaining:
            tokens = stories._tokens(item.headline, item.source)
            key = tuple(sorted(tokens)) if len(tokens) >= 3 else ('article', item.article.id)
            exact.setdefault(key, []).append(item)
        clustered = stories.cluster([items[0] for items in exact.values()])
        for story in clustered:
            members = [item.article for lead in story.members for items in exact.values()
                       if items[0] is lead for item in items]
            if len(members) >= 2:
                signature = min(a.published_at for a in members).date().isoformat() + '|' + '|'.join(sorted(stories._tokens(story.lead.headline, story.lead.source)))
                groups.append((hashlib.sha256(signature.encode()).hexdigest()[:20], members, f'/client/{client.id}/medien'))
        for key, members, href in groups:
            # A source headline is a factual short label, unlike a speculative pitch.
            lead = min(members, key=lambda a: (len(a.title), a.id))
            latest = max(a.published_at for a in members)
            result.append(dict(id=f'{client.id}:{key}', client_id=client.id, client_name=client.name,
                title=lead.title, count=len(members), latest=latest.isoformat(), href=href,
                link_label='Zum Thema' if '?kind=' in href else 'Zu den Medien',
                sources=[dict(id=a.id, title=a.title, source=a.source, url=a.url) for a in members]))
    return sorted(result, key=lambda item: item['latest'], reverse=True)[:10]
