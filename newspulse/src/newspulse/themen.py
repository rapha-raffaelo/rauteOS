"""Themen from Medien: a starred article becomes a Thema (Spec 12).

A Thema is not a new kind of record. Starring an article opens the same pair
every developed opportunity has: an :class:`Angle` that carries the article as
its occasion, and an :class:`OpportunityWorkspace` whose ``data`` says it came
from Medien and who starred it. From there the Deep Dive, "Thema aktivieren"
and every asset kind work exactly as for a proposal by RAUTE.

The Deep Dive of a starred article is written in the background by the
designer model (:func:`deep_dive`): what happened, why it matters to this
mandate, a pitch and up to three storylines. Until it arrives the Thema shows
the article itself, and a failed Deep Dive leaves the Thema usable.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from importlib import resources
from string import Template

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import brain, prose, quoting
from .models import Angle, Article, Client, OpportunityEvent, OpportunityWorkspace

_log = logging.getLogger(__name__)
ORIGIN = "medien"
_PROMPT = "prompts/themen_deep_dive.txt"
_TIMEOUT = 300.0


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _starred(session: Session, client_id: int) -> list[OpportunityWorkspace]:
    rows = session.scalars(select(OpportunityWorkspace).where(
        OpportunityWorkspace.client_id == client_id, OpportunityWorkspace.context_kind == "developed"))
    return [row for row in rows if (row.data or {}).get("origin") == ORIGIN]


def starred(session: Session, client_id: int) -> dict[int, dict]:
    """Article id → its Thema, for the stars in Medien. Dismissed ones are not starred."""
    result = {}
    for row in _starred(session, client_id):
        angle = session.get(Angle, row.context_id)
        if angle is None or angle.dismissed_at is not None:
            continue
        result[int(row.data["article_id"])] = dict(
            kind="developed", context=row.context_id, status=row.status,
            starred_by=row.data.get("starred_by", ""))
    return result


def _find(session: Session, client_id: int, article_id: int) -> OpportunityWorkspace | None:
    return next((row for row in _starred(session, client_id)
                 if int((row.data or {}).get("article_id", 0)) == article_id), None)


def star(session: Session, client: Client, article: Article, *, by: str = "") -> OpportunityWorkspace:
    """Make ``article`` a Thema of ``client``; starring it twice is one Thema."""
    row = _find(session, client.id, article.id)
    if row is not None:
        angle = session.get(Angle, row.context_id)
        if angle is not None and angle.dismissed_at is not None:
            angle.dismissed_at = None
            row.revision += 1
            session.commit()
        return row
    angle = Angle(client_id=client.id, subject=article.title[:500], message="",
                  context=(article.summary_text or article.title or "")[:4000],
                  article_ids=[article.id])
    session.add(angle)
    session.flush()
    row = OpportunityWorkspace(client_id=client.id, context_kind="developed", context_id=angle.id,
                               angle_id=angle.id, status="draft",
                               data=dict(origin=ORIGIN, article_id=article.id, starred_by=by,
                                         situation=article.title, deep_dive="pending"))
    session.add(row)
    session.flush()
    session.add(OpportunityEvent(workspace_id=row.id, kind="starred", actor=by or "mensch",
                                 detail=dict(article_id=article.id)))
    session.commit()
    return row


def unstar(session: Session, client_id: int, article_id: int) -> bool:
    """Take the star back. An activated Thema stays: work has started on it."""
    row = _find(session, client_id, article_id)
    if row is None:
        return False
    if row.status == "active":
        raise ValueError("Dieses Thema ist schon aktiviert und bleibt unter Assets.")
    angle = session.get(Angle, row.context_id)
    if angle is not None:
        angle.dismissed_at = _now()
    session.commit()
    return True


def _profile(client: Client) -> str:
    from .angles import _client_profile

    return _client_profile(client)


def _prompt(client: Client, article: Article) -> str:
    text = resources.files("newspulse").joinpath(_PROMPT).read_text("utf-8")
    body = "\n".join(part for part in (
        f"Titel: {article.title}", f"Medium: {article.source}",
        f"Veröffentlicht: {article.published_at:%d.%m.%Y}" if article.published_at else "",
        article.summary_text or "") if part)
    return Template(brain.compose(text)).safe_substitute(
        client_profile=_profile(client), article=quoting.fence(body, label="ARTIKEL"))


def _parse(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    payload = json.loads(text[start:end + 1] if 0 <= start < end else text)
    if not isinstance(payload, dict):
        raise ValueError("Deep Dive is not an object")
    clean = lambda value: prose.plain(str(value or "")).strip()[:2000]
    storylines = payload.get("storylines") or []
    return dict(situation=clean(payload.get("situation")), relevance=clean(payload.get("relevance")),
                pitch=clean(payload.get("pitch")),
                storylines=[clean(s) for s in storylines if isinstance(s, str) and s.strip()][:3])


def deep_dive(session: Session, workspace_id: int, *, invoke=None) -> None:
    """Write the Deep Dive of a starred article into its Thema."""
    from .analyzer import invoke_with_fallback

    row = session.get(OpportunityWorkspace, workspace_id)
    if row is None:
        return
    angle = session.get(Angle, row.context_id)
    client = session.get(Client, row.client_id)
    article = session.get(Article, int(row.data["article_id"]))
    if angle is None or client is None or article is None:
        return
    try:
        found = _parse((invoke or invoke_with_fallback)(_prompt(client, article), timeout=_TIMEOUT))
    except Exception as exc:  # noqa: BLE001 - the Thema stays usable without it
        _log.warning("Deep Dive for Thema %s failed: %s", row.id, exc)
        row.data = {**row.data, "deep_dive": "failed"}
        session.commit()
        return
    row.data = {**row.data, "deep_dive": "ready", "situation": found["situation"] or article.title,
                "relevance": found["relevance"], "storylines": [s for s in [found["pitch"], *found["storylines"]] if s]}
    angle.message = found["pitch"]
    angle.thesis = found["pitch"]
    angle.credibility = found["relevance"]
    angle.statements = [s for s in [found["pitch"], *found["storylines"]] if s]
    session.commit()
