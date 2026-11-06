"""Aufgaben, LinkedIn-Beiträge und Sales-CRM-Deals: kept by hand (spec 10).

Three small lists with the same shape: a form posts fields, this module checks
them and writes the row. Everything a person typed is validated here rather
than in the route, so the page and any later integration share one rule.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    DEAL_STAGES, POST_STATES, TASK_PRIORITIES, TASK_STATES,
    Asset, Client, Deal, LinkedInPost, Task,
)

#: How the pages name each value. One place, so the Desk says the same words.
TASK_PRIORITY_LABELS = {"hoch": "Hoch", "mittel": "Mittel", "niedrig": "Niedrig"}
TASK_STATE_LABELS = {"offen": "Offen", "in_arbeit": "In Arbeit", "erledigt": "Erledigt"}
POST_STATE_LABELS = {"idee": "Idee", "entwurf": "Entwurf", "freigabe": "Freigabe",
                     "geplant": "Geplant", "veroeffentlicht": "Veröffentlicht"}
DEAL_STAGE_LABELS = {"lead": "Lead", "gespraech": "Gespräch", "angebot": "Angebot",
                     "verhandlung": "Verhandlung", "gewonnen": "Gewonnen", "verloren": "Verloren"}
CLOSED_STAGES = ("gewonnen", "verloren")


class Invalid(ValueError):
    """A form value that cannot be stored, said in words for the page."""


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _text(form: Mapping, name: str, limit: int, *, required: str = "") -> str:
    value = " ".join(str(form.get(name) or "").split()) if limit <= 300 else str(form.get(name) or "").strip()
    if required and not value:
        raise Invalid(required)
    if len(value) > limit:
        raise Invalid(f"Höchstens {limit} Zeichen.")
    return value


def _choice(form: Mapping, name: str, allowed: tuple[str, ...], default: str) -> str:
    value = str(form.get(name) or default)
    if value not in allowed:
        raise Invalid("Unbekannter Wert.")
    return value


def _date(form: Mapping, name: str) -> dt.date | None:
    value = str(form.get(name) or "").strip()
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise Invalid("Datum im Format JJJJ-MM-TT.") from None


def _href(form: Mapping, name: str) -> str:
    value = _text(form, name, 300)
    # A path on this site only: a task links to the work it came from.
    if value and (not value.startswith("/") or value.startswith("//") or "\\" in value):
        raise Invalid("Nur ein Link innerhalb von RauteOS.")
    return value


def _mandate(session: Session, form: Mapping, name: str = "client_id", *, required: bool = False) -> int | None:
    raw = str(form.get(name) or "").strip()
    if not raw:
        if required:
            raise Invalid("Bitte einen Mandanten wählen.")
        return None
    try:
        client = session.get(Client, int(raw))
    except (ValueError, OverflowError):
        client = None
    if client is None or client.is_competitor:
        raise Invalid("Unbekannter Mandant.")
    return client.id


def mandates(session: Session) -> list[Client]:
    return list(session.scalars(select(Client).where(
        Client.active.is_(True), Client.is_competitor.is_(False)).order_by(Client.name)))


# --- Aufgaben -------------------------------------------------------------------


def save_task(session: Session, form: Mapping, task: Task | None = None) -> Task:
    task = task or Task()
    task.title = _text(form, "title", 200, required="Was ist zu tun?")
    task.note = _text(form, "note", 5000)
    task.priority = _choice(form, "priority", TASK_PRIORITIES, task.priority or "mittel")
    status = _choice(form, "status", TASK_STATES, task.status or "offen")
    task.due_on = _date(form, "due_on")
    task.owner = _text(form, "owner", 120)
    task.context_href = _href(form, "context_href")
    task.client_id = _mandate(session, form)
    set_task_status(task, status)
    session.add(task)
    session.commit()
    return task


def set_task_status(task: Task, status: str) -> None:
    if status not in TASK_STATES:
        raise Invalid("Unbekannter Wert.")
    if status == "erledigt" and task.status != "erledigt":
        task.done_at = _now()
    elif status != "erledigt":
        task.done_at = None
    task.status = status


def tasks(session: Session, *, status: str = "", client_id: int | None = None) -> list[Task]:
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    if client_id:
        stmt = stmt.where(Task.client_id == client_id)
    rows = list(session.scalars(stmt))
    order = {p: i for i, p in enumerate(TASK_PRIORITIES)}
    far = dt.date.max
    # Open work first, then by date due (none last), then priority.
    rows.sort(key=lambda t: (t.status == "erledigt", t.due_on or far, order[t.priority], -t.id))
    return rows


def open_tasks(session: Session) -> list[Task]:
    return [t for t in tasks(session) if t.status != "erledigt"]


# --- LinkedIn -------------------------------------------------------------------


def save_post(session: Session, form: Mapping, post: LinkedInPost | None = None) -> LinkedInPost:
    post = post or LinkedInPost()
    post.client_id = _mandate(session, form, required=True)
    post.title = _text(form, "title", 200, required="Bitte einen Arbeitstitel.")
    post.author = _text(form, "author", 120)
    post.body = _text(form, "body", 3000)
    post.status = _choice(form, "status", POST_STATES, post.status or "idee")
    post.planned_on = _date(form, "planned_on")
    url = _text(form, "published_url", 500)
    if url and not url.startswith("https://"):
        raise Invalid("Der Link beginnt mit https://.")
    post.published_url = url
    post.updated_at = _now()
    session.add(post)
    session.commit()
    return post


#: How many suggestions of each kind head the LinkedIn page.
SUGGESTIONS_SHOWN = 6


def _first_line(text: str, limit: int = 200) -> str:
    line = next((l.strip() for l in (text or "").splitlines() if l.strip()), "")
    return line if len(line) <= limit else line[:limit].rsplit(" ", 1)[0] + " …"


def suggestions(session: Session) -> dict:
    """What RauteOS already has for LinkedIn and is not on the board yet.

    ``texts`` are the LinkedIn posts written in a chance (format ``linkedin``),
    newest first. ``chances`` are the open chances of the active mandates,
    the Desk's list. Taking one over is a click; nothing lands on the board
    by itself.
    """
    from . import desk

    clients = {c.id: c for c in mandates(session)}
    taken = set(session.scalars(select(LinkedInPost.asset_id).where(LinkedInPost.asset_id.is_not(None))))
    picked = set(session.scalars(select(LinkedInPost.context_href).where(LinkedInPost.context_href != "")))
    texts = []
    if clients:
        rows = session.scalars(select(Asset).where(Asset.kind == "linkedin", Asset.client_id.in_(clients),
                                                   Asset.angle_id.is_not(None))
                               .order_by(Asset.generated_at.desc()).limit(50))
        for a in rows:
            if a.id in taken:
                continue
            texts.append(dict(id=a.id, client=dict(id=a.client_id, name=clients[a.client_id].name),
                              title=a.title or _first_line(a.body), excerpt=_first_line(a.body, 160) if a.title else "",
                              speaker=a.speaker, released=a.released_at is not None, written_at=a.generated_at,
                              href=f"/client/{a.client_id}/advice?eintrag=anlass-{a.angle_id}#asset-{a.id}"))
            if len(texts) == SUGGESTIONS_SHOWN:
                break
    chances = [dict(client=dict(id=c.client.id, name=c.client.name), title=c.title, href=c.href, since=c.since)
               for c in desk._chances(session, clients, limit=SUGGESTIONS_SHOWN + len(picked))
               if c.href not in picked][:SUGGESTIONS_SHOWN]
    return dict(texts=texts, chances=chances)


def post_from_asset(session: Session, asset: Asset) -> LinkedInPost:
    """The board's card for a LinkedIn text RauteOS wrote. Once per text."""
    post = session.scalar(select(LinkedInPost).where(LinkedInPost.asset_id == asset.id))
    if post:
        return post
    post = LinkedInPost(client_id=asset.client_id, asset_id=asset.id, title=(asset.title or _first_line(asset.body))[:200],
                        author=asset.speaker[:120], body=asset.body[:3000],
                        status="freigabe" if asset.released_at else "entwurf", updated_at=_now())
    session.add(post)
    session.commit()
    return post


def post_from_chance(session: Session, form: Mapping) -> LinkedInPost:
    """An idea on the board for one of the open chances. Once per chance."""
    href = _href(form, "context_href")
    if not href:
        raise Invalid("Nur ein Link innerhalb von RauteOS.")
    post = session.scalar(select(LinkedInPost).where(LinkedInPost.context_href == href))
    if post:
        return post
    post = LinkedInPost(client_id=_mandate(session, form, required=True), context_href=href,
                        title=_text(form, "title", 200, required="Bitte einen Arbeitstitel."),
                        status="idee", updated_at=_now())
    session.add(post)
    session.commit()
    return post


def posts(session: Session, *, client_id: int | None = None) -> list[LinkedInPost]:
    stmt = select(LinkedInPost)
    if client_id:
        stmt = stmt.where(LinkedInPost.client_id == client_id)
    rows = list(session.scalars(stmt))
    far = dt.date.max
    rows.sort(key=lambda p: (p.planned_on or far, -p.id))
    return rows


# --- Sales CRM ------------------------------------------------------------------


def save_deal(session: Session, form: Mapping, deal: Deal | None = None) -> Deal:
    deal = deal or Deal()
    deal.company = _text(form, "company", 200, required="Bitte das Unternehmen nennen.")
    deal.contact_name = _text(form, "contact_name", 120)
    email = _text(form, "contact_email", 200)
    if email and ("@" not in email or " " in email):
        raise Invalid("Keine gültige E-Mail-Adresse.")
    deal.contact_email = email
    stage = _choice(form, "stage", DEAL_STAGES, deal.stage or "lead")
    raw = str(form.get("value_eur") or "").replace(".", "").replace(" ", "").strip()
    try:
        deal.value_eur = int(raw) if raw else None
    except ValueError:
        raise Invalid("Potenzial als ganze Zahl in Euro.") from None
    if deal.value_eur is not None and not 0 <= deal.value_eur <= 10_000_000:
        raise Invalid("Potenzial als ganze Zahl in Euro.")
    deal.owner = _text(form, "owner", 120)
    deal.next_step = _text(form, "next_step", 300)
    deal.next_step_on = _date(form, "next_step_on")
    deal.note = _text(form, "note", 5000)
    set_deal_stage(deal, stage)
    session.add(deal)
    session.commit()
    return deal


def set_deal_stage(deal: Deal, stage: str) -> None:
    if stage not in DEAL_STAGES:
        raise Invalid("Unbekannter Wert.")
    if stage in CLOSED_STAGES and deal.stage not in CLOSED_STAGES:
        deal.closed_at = _now()
    elif stage not in CLOSED_STAGES:
        deal.closed_at = None
    deal.stage = stage
    deal.updated_at = _now()


def deals(session: Session) -> list[Deal]:
    rows = list(session.scalars(select(Deal)))
    far = dt.date.max
    rows.sort(key=lambda d: (d.next_step_on or far, -d.id))
    return rows


def pipeline(rows: list[Deal]) -> list[dict]:
    """The pipeline as columns: each stage, its deals and their summed value."""
    return [dict(stage=s, label=DEAL_STAGE_LABELS[s],
                 deals=[d for d in rows if d.stage == s],
                 value=sum(d.value_eur or 0 for d in rows if d.stage == s))
            for s in DEAL_STAGES]
