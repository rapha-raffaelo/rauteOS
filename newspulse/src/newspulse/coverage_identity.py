"""Recognise a publisher's identical article under multiple section URLs.

Do not merge reporting by different publishers, or later articles with the
same headline. Archive rows and their provenance remain intact.
"""
from urllib.parse import urlsplit
from sqlalchemy import select
from .matching import canonical_url, normalize_title
from .models import Article, Analysis


def identity(article):
    host=(urlsplit(article.url).hostname or '').lower().removeprefix('www.')
    title=normalize_title(article.title, article.source)
    # Redirect aggregators host unrelated publishers; use URL identity there.
    if not title or not host or host in {'news.google.com','news.google.de'}:
        return ('url',canonical_url(article.url))
    return ('publisher',host,title,article.published_at)


def unique(rows, *, limit=None):
    """Article/Analysis pairs, deduplicated per mandate before the limit."""
    seen=set(); result=[]
    for article,analysis in rows:
        key=(analysis.client_id,identity(article))
        if key in seen:continue
        seen.add(key);result.append((article,analysis))
        if limit is not None and len(result)>=limit:break
    return result


def equivalents(session, analysis):
    article=session.get(Article,analysis.article_id)
    key=identity(article)
    rows=session.execute(select(Article,Analysis).join(Analysis,Analysis.article_id==Article.id)
        .where(Analysis.client_id==analysis.client_id,Article.published_at==article.published_at))
    return [value for candidate,value in rows if identity(candidate)==key]
