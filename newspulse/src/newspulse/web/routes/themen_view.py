"""Themen, Assets and the Agenda: the mandate's flow from a story to a text.

Spec 12. ``Themen`` lists what could become communication, from a starred
article or a proposal by RAUTE; ``Assets`` is where an activated Thema is
written. Both are React pages over the opportunity and activation APIs that
already existed under "Aktivitäten", which now redirects here.
"""
from __future__ import annotations

import datetime as dt
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ... import plan, themen, worklists
from ...models import Analysis, Article, HookState, TopicHit
from ..spawn import start_or_release
from .. import frontend
from ..app import get_db, templates
from ..mandates import mandate_or_404
from .today import _fetch_last_run, _local_tz

router = APIRouter()
_SEE_OTHER = 303

#: How far ahead the Agenda beside the Themen reaches.
AGENDA_ITEMS = 8


def _page(request: Request, session: Session, client, page: str, active: str, title: str):
    return templates.TemplateResponse(request, "client_flow_react.html", dict(
        client=client, page=page, active=active, page_title=title,
        frontend=frontend.page_assets(page), last_run=_fetch_last_run(session),
        header_date=dt.datetime.now(_local_tz()).date()))


@router.get("/client/{client_id}/themen")
def themen_page(client_id: int, request: Request, session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    return _page(request, session, client, "themen", "themen", "Themen")


@router.get("/client/{client_id}/assets")
def assets_page(client_id: int, request: Request, session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    return _page(request, session, client, "assets", "assets", "Assets")


@router.get("/client/{client_id}/opportunities")
def opportunities_moved(client_id: int, request: Request, session: Session = Depends(get_db)):
    """Aktivitäten became Themen and Assets. A link to one opportunity opens it
    under Assets, every other link lands on the Themen."""
    mandate_or_404(session, client_id)
    query = dict(request.query_params)
    if query.get("context"):
        return RedirectResponse(f"/client/{client_id}/assets?{urlencode(query)}", status_code=_SEE_OTHER)
    return RedirectResponse(f"/client/{client_id}/themen", status_code=_SEE_OTHER)


@router.get("/api/v1/clients/{client_id}/agenda")
def agenda(client_id: int, response: Response, session: Session = Depends(get_db)):
    """The next dates of the Agenda (formerly Redaktionsplan), oldest first."""
    client = mandate_or_404(session, client_id)
    response.headers["Cache-Control"] = "no-store"
    now = dt.datetime.now(dt.UTC)
    current = plan.month_key(now)
    items = []
    for month, hooks in plan.read(session, client, now=now):
        for hook in hooks:
            if hook.state == HookState.VERWORFEN:
                continue
            if month == current and hook.day and hook.day < now.astimezone(_local_tz()).day:
                continue
            items.append(dict(
                id=hook.id, title=hook.title, reason=hook.reason, month=month, day=hook.day,
                format=str(hook.format or ""), state=hook.state.value,
                href=f"/client/{client_id}/plan#monat-{month}"))
    items.sort(key=lambda item: (item["month"], item["day"] or 99))
    return dict(items=items[:AGENDA_ITEMS], total=len(items), href=f"/client/{client_id}/plan")


# --- The star in Medien --------------------------------------------------------


class StarInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    article_id: int = Field(gt=0)


def _article_of(session: Session, client_id: int, article_id: int) -> Article:
    """Only an article Medien shows for this mandate can become its Thema."""
    article = session.get(Article, article_id)
    shown = article is not None and (
        session.scalar(select(Analysis.id).where(Analysis.client_id == client_id, Analysis.article_id == article_id).limit(1))
        or session.scalar(select(TopicHit.id).where(TopicHit.client_id == client_id, TopicHit.article_id == article_id).limit(1)))
    if not shown:
        raise HTTPException(404, "Artikel nicht gefunden.")
    return article


def _deep_dive_worker(factory, workspace_id: int) -> None:
    with factory() as session:
        themen.deep_dive(session, workspace_id)


@router.get("/api/v1/clients/{client_id}/themen/starred")
def starred(client_id: int, response: Response, session: Session = Depends(get_db)):
    mandate_or_404(session, client_id)
    response.headers["Cache-Control"] = "no-store"
    return {str(article_id): row for article_id, row in themen.starred(session, client_id).items()}


@router.post("/api/v1/clients/{client_id}/themen", status_code=201)
def star(client_id: int, body: StarInput, request: Request, session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    article = _article_of(session, client_id, body.article_id)
    fresh = themen._find(session, client_id, article.id) is None
    row = themen.star(session, client, article, by=worklists.member_for(request.scope.get("user_email")) or "")
    if fresh:
        factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
        try:
            start_or_release(_deep_dive_worker, args=(factory, row.id), name=f"themen-deep-dive-{row.id}",
                             release=lambda: None)
        except RuntimeError:
            pass  # the Thema stands without its Deep Dive; the page says so
    return dict(kind="developed", context=row.context_id, status=row.status,
                href=f"/client/{client_id}/themen")


@router.delete("/api/v1/clients/{client_id}/themen/{article_id}")
def unstar(client_id: int, article_id: int, session: Session = Depends(get_db)):
    mandate_or_404(session, client_id)
    try:
        if not themen.unstar(session, client_id, article_id):
            raise HTTPException(404, "Kein Thema zu diesem Artikel.")
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return dict(ok=True)
