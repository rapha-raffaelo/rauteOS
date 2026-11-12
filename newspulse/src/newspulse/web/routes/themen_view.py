"""Themen, Assets and the Agenda: the mandate's flow from a story to a text.

Spec 12. ``Themen`` lists what could become communication, from a starred
article or a proposal by RAUTE; ``Assets`` is where an activated Thema is
written. Both are React pages over the opportunity and activation APIs that
already existed under "Aktivitäten", which now redirects here.
"""
from __future__ import annotations

import datetime as dt
from typing import Literal
from urllib.parse import quote, urlencode

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


# One current, attributable RAUTE proposal, generated off the request thread.
def _suggestion_worker(factory, client_id, lease):
    from ... import topic_suggestions
    with factory() as session:
        topic_suggestions.generate(session, client_id, lease)


@router.get("/api/v1/clients/{client_id}/themen/suggestions")
def suggestion_status(client_id: int, response: Response, session: Session = Depends(get_db)):
    from ... import topic_suggestions
    mandate_or_404(session, client_id)
    response.headers["Cache-Control"] = "no-store"
    return topic_suggestions.state(session, client_id)


@router.post("/api/v1/clients/{client_id}/themen/suggestions")
def ensure_suggestion(client_id: int, session: Session = Depends(get_db)):
    from ... import topic_suggestions
    mandate_or_404(session, client_id)
    lease = topic_suggestions.claim(session, client_id)
    if lease:
        factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
        try:
            start_or_release(_suggestion_worker, args=(factory, client_id, lease), name=f"themen-suggestion-{client_id}",
                release=lambda: topic_suggestions.finish(session, client_id, lease, 'failed', 'Themenvorschlag konnte nicht gestartet werden.'))
        except RuntimeError:
            raise HTTPException(503, 'Themenvorschlag konnte nicht gestartet werden.')
        return lease
    return topic_suggestions.state(session, client_id)


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


# --- Export: Word, PDF and Google Drive (Spec 12, phase 5) ----------------------

_KIND_LABELS = {"kundenmail": "Kundenmail", "pitch": "Pitch", "statement": "Statement",
                "pressemitteilung": "Pressemitteilung", "gastbeitrag": "Gastbeitrag", "custom": "Eigenes Format",
                "qa": "Q&A", "interviewangebot": "Interviewangebot", "linkedin": "LinkedIn-Post"}
Fmt = Literal["docx", "pdf"]


def _text_document(session: Session, client, text_type: str, text_id: int):
    from ... import asset_export
    from ...models import Asset, Outreach

    row = session.get(Asset if text_type == "asset" else Outreach, text_id)
    if row is None or row.client_id != client.id:
        raise HTTPException(404, "Text nicht gefunden.")
    if text_type == "asset":
        kind, title, body = row.kind, row.title or "", row.body or ""
    else:
        kind, title, body = "pitch", row.subject or "", row.message or ""
    label = _KIND_LABELS.get(str(kind), str(kind))
    return asset_export.Document(title=title or label, client=client.name,
                                 sections=[asset_export.Section(heading="", body=body, kicker=label)])


def _thema_document(session: Session, client, kind: str, identity: int):
    from ... import activation, asset_export, workspaces

    detail = workspaces.read(session, client.id, kind, identity)
    if detail is None:
        raise HTTPException(404, "Thema nicht gefunden.")
    pitch = (detail.get("storyline") or (detail.get("storylines") or [""])[0] or "").strip()
    sections = [asset_export.Section("Was ist passiert?", detail.get("situation") or "bitte ergänzen", "Deep Dive"),
                asset_export.Section(f"Warum für {client.name} relevant?", detail.get("relevance") or "bitte ergänzen"),
                asset_export.Section("Pitch", pitch or "bitte ergänzen")]
    stored = workspaces.stored(session, client.id, kind, identity)
    if stored is not None:
        for text in activation.read(session, stored)["texts"]:
            sections.append(asset_export.Section(text["title"] or "", text["body"],
                                                 _KIND_LABELS.get(text["kind"], text["kind"])))
    return asset_export.Document(title=detail["title"], client=client.name, sections=sections)


def _download(document, fmt: str) -> Response:
    from ... import asset_export

    name = asset_export.filename(document, fmt)
    return Response(asset_export.render(document, fmt), media_type=asset_export.MIME[fmt], headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


def _to_drive(document, fmt: str) -> dict:
    from ... import asset_export, drive_link

    try:
        url = drive_link.upload(document.client, asset_export.filename(document, fmt), asset_export.MIME[fmt],
                                asset_export.render(document, fmt))
    except drive_link.DriveError as exc:
        raise HTTPException(409, str(exc)) from exc
    return dict(url=url, folder=f"7. Assets › {document.client}")


class DriveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Fmt = "docx"


@router.get("/api/v1/clients/{client_id}/assets/{text_type}/{text_id}/export.{fmt}")
def export_text(client_id: int, text_type: Literal["asset", "outreach"], text_id: int, fmt: Fmt,
                session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    return _download(_text_document(session, client, text_type, text_id), fmt)


@router.post("/api/v1/clients/{client_id}/assets/{text_type}/{text_id}/drive")
def drive_text(client_id: int, text_type: Literal["asset", "outreach"], text_id: int, body: DriveInput,
               session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    return _to_drive(_text_document(session, client, text_type, text_id), body.format)


@router.get("/api/v1/clients/{client_id}/themen/{kind}/{identity}/export.{fmt}")
def export_thema(client_id: int, kind: Literal["detected", "developed"], identity: int, fmt: Fmt,
                 session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    return _download(_thema_document(session, client, kind, identity), fmt)


@router.post("/api/v1/clients/{client_id}/themen/{kind}/{identity}/drive")
def drive_thema(client_id: int, kind: Literal["detected", "developed"], identity: int, body: DriveInput,
                session: Session = Depends(get_db)):
    client = mandate_or_404(session, client_id)
    return _to_drive(_thema_document(session, client, kind, identity), body.format)
