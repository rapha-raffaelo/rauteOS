"""Aufgaben, LinkedIn-Beiträge und Sales-CRM-Deals: kept by hand (spec 10).

Three small lists with the same shape: a form posts fields, this module checks
them and writes the row. Everything a person typed is validated here rather
than in the route, so the page and any later integration share one rule.
"""

from __future__ import annotations

import datetime as dt
import threading
from collections.abc import Mapping

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import config, linkedin_link
from .models import (
    DEAL_STAGES, POST_STATES, TASK_PRIORITIES, TASK_STATES,
    Asset, Client, Deal, LinkedInPost, Task, TaskBoard, DismissedTaskSource,
)

#: How the pages name each value. One place, so the Desk says the same words.
TASK_PRIORITY_LABELS = {"urgent": "Urgent", "hoch": "Hoch", "mittel": "Mittel", "niedrig": "Niedrig"}
TASK_STATE_LABELS = {"offen": "Offen", "in_arbeit": "In Arbeit", "review": "Review", "erledigt": "Done"}
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


#: The people who work in RauteOS, as tags on a task. Each has the addresses
#: they sign in with, so "Mir zugewiesen" knows who is looking.
TEAM: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("raphael", "Raphael", ("raphaelmankopf@gmail.com", "r.mankopf@raute-kopf.com")),
    ("lucas", "Lucas", ("lucas.neurauter@gmail.com", "l.neurauter@raute-kopf.com")),
)
TEAM_KEYS = tuple(key for key, _, _ in TEAM)


def member_for(email: str | None) -> str | None:
    """The team key of a signed-in address, or None."""
    address = (email or "").strip().casefold()
    return next((key for key, _, emails in TEAM if address in emails), None)


DEFAULT_BOARDS = (("decisions", "Offene Entscheidungen"), ("rauteos", "rauteOS"))
#: Where a task without a workspace lands, and the board the page opens on.
DEFAULT_BOARD = "rauteos"
#: The board "Allgemein" was retired; its tasks moved to rauteOS.
_RETIRED_BOARD = "general"


def task_boards(session: Session) -> list[TaskBoard]:
    existing = set(session.scalars(select(TaskBoard.system_key)))
    for key, name in DEFAULT_BOARDS:
        if key not in existing:
            session.execute(sqlite_insert(TaskBoard).values(
                name=name, name_key=name.casefold(), system_key=key,
                created_at=_now()).on_conflict_do_nothing())
    rows = list(session.scalars(select(TaskBoard).order_by(TaskBoard.id)))
    home = next(board for board in rows if board.system_key == DEFAULT_BOARD)
    retired = next((board for board in rows if board.system_key == _RETIRED_BOARD), None)
    if retired is not None:
        session.execute(update(Task).where(Task.board_id == retired.id).values(board_id=home.id))
        session.delete(retired)
        session.flush()
        rows = [board for board in rows if board is not retired]
    session.execute(update(Task).where(Task.board_id.is_(None)).values(board_id=home.id))
    return rows


def create_task_board(session: Session, form: Mapping) -> TaskBoard:
    task_boards(session)
    name = _text(form, "workspace_name", 80, required="Bitte einen Namen für den Workspace eingeben")
    board = TaskBoard(name=name, name_key=name.casefold())
    session.add(board)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise Invalid("Ein Workspace mit diesem Namen existiert bereits") from None
    return board


def _task_board(session: Session, form: Mapping, task: Task) -> int:
    boards = task_boards(session)
    raw = form.get("board_id")
    if raw is None or raw == "":
        return task.board_id or next(b.id for b in boards if b.system_key == DEFAULT_BOARD)
    try:
        board_id = int(raw)
    except (ValueError, TypeError, OverflowError):
        raise Invalid("Unbekannter Workspace") from None
    if board_id not in {b.id for b in boards}:
        raise Invalid("Unbekannter Workspace")
    if task.source_key and board_id != task.board_id:
        raise Invalid("Diese Entscheidung gehört zum Workspace Offene Entscheidungen")
    return board_id


def sync_decision_tasks(session: Session, decisions, boards: list[TaskBoard]) -> None:
    """Mirror decision sources without treating a task move as an approval."""
    board_id = next(b.id for b in boards if b.system_key == "decisions")
    by_key = {task.source_key: task for task in session.scalars(
        select(Task).where(Task.source_key.is_not(None)))}
    dismissed = set(session.scalars(select(DismissedTaskSource.source_key)))
    active = set()
    for decision in decisions:
        key = decision.source_key
        if not key or key in dismissed:
            continue
        active.add(key)
        task = by_key.get(key)
        if task is None:
            session.execute(sqlite_insert(Task).values(
                board_id=board_id, source_key=key, source_kind=decision.kind, source_open=True,
                client_id=decision.client.id, title=decision.title[:200], note=decision.detail,
                priority="mittel", status="offen", owner="", assignees=[],
                context_href=decision.href, created_at=_now(),
            ).on_conflict_do_nothing(index_elements=["source_key"]))
        else:
            if task.source_open is False:
                set_task_status(task, "offen")
            task.source_open = True
            task.source_kind = decision.kind
            task.context_href = decision.href
    for key, task in by_key.items():
        if key not in active and task.source_open:
            task.source_open = False
            set_task_status(task, "erledigt")
    session.commit()


def _assignees(form: Mapping) -> list[str]:
    raw = form.get("assignees", [])
    values = raw if isinstance(raw, (list, tuple)) else [raw]
    picked = [str(v).strip() for v in values if str(v).strip()]
    if any(v not in TEAM_KEYS for v in picked):
        raise Invalid("Unbekannte Person.")
    return list(dict.fromkeys(picked))


#: The fields a one-click change may carry: ticking off and the star. Anything
#: else is the full form, which rewrites every field it holds.
QUICK_FIELDS = frozenset({"status", "priority", "favorite"})


def quick_update(session: Session, task: Task, form: Mapping) -> Task:
    """Change only what the click carried, leaving every other field alone."""
    if "favorite" in form:
        value = str(form["favorite"])
        if value not in {"0", "1"}:
            raise Invalid("Ungültiger Favoritenstatus")
        task.favorite = value == "1"
    if "priority" in form:
        task.priority = _choice(form, "priority", TASK_PRIORITIES, task.priority)
    if "status" in form:
        set_task_status(task, str(form.get("status", "")))
    session.commit()
    return task


def save_task(session: Session, form: Mapping, task: Task | None = None) -> Task:
    task = task or Task()
    task.board_id = _task_board(session, form, task)
    task.assignees = _assignees(form)
    task.title = _text(form, "title", 200, required="Was ist zu tun?")
    task.note = _text(form, "note", 5000)
    task.priority = _choice(form, "priority", TASK_PRIORITIES, task.priority or "mittel")
    status = _choice(form, "status", TASK_STATES, task.status or "offen")
    task.due_on = _date(form, "due_on")
    task.owner = _text(form, "owner", 120)
    if not task.source_key:
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


def task_archived(task: Task, *, now: dt.datetime | None = None) -> bool:
    """Ten full days after completion, retained in the archive until reopened."""
    return bool(task.status == "erledigt" and task.done_at is not None
                and task.done_at <= (now or _now()) - dt.timedelta(days=10))


def tasks(session: Session, *, status: str = "", client_id: int | None = None, include_archived: bool = False) -> list[Task]:
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    if client_id:
        stmt = stmt.where(Task.client_id == client_id)
    rows = [task for task in session.scalars(stmt) if include_archived or not task_archived(task)]
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
    status = _choice(form, "status", POST_STATES, post.status or "idee")
    # An idea with its text written is a draft: the board's next column.
    set_post_status(post, "entwurf" if status == "idee" and post.body else status)
    post.planned_on = _date(form, "planned_on") if post.post_at is None else post.planned_on
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


def first_line(text: str, limit: int = 200) -> str:
    line = next((l.strip() for l in (text or "").splitlines() if l.strip()), "")
    return line if len(line) <= limit else line[:limit].rsplit(" ", 1)[0] + " …"


def suggestions(session: Session) -> dict:
    """What RauteOS already has for LinkedIn and is not on the board yet.

    ``texts`` are the LinkedIn posts written in a chance (format ``linkedin``),
    newest first. ``chances`` are the open chances of the active mandates,
    the Desk's list. Taking one over is a click; nothing lands on the board
    by itself.
    """
    from . import desk, workspaces

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
                              title=a.title or first_line(a.body), excerpt=first_line(a.body, 160) if a.title else "",
                              speaker=a.speaker, released=a.released_at is not None, written_at=a.generated_at,
                              href=workspaces.text_href(session, a)))
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
    post = LinkedInPost(client_id=asset.client_id, asset_id=asset.id, title=(asset.title or first_line(asset.body))[:200],
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


def set_post_status(post: LinkedInPost, status: str) -> None:
    """A post moved off "geplant" is no longer the scheduler's to send."""
    post.status = status
    if status != "geplant":
        post.post_at = None


# --- Posting to LinkedIn ----------------------------------------------------------

#: One post goes out at a time in this process, so a double click or the
#: scheduler racing a button cannot post the same text twice.
_posting = threading.Lock()


def publish_post(session: Session, post: LinkedInPost, owner: str, *, fetch=None) -> LinkedInPost:
    """Post the text now through ``owner``'s LinkedIn account."""
    with _posting:
        session.refresh(post)
        if post.linkedin_urn:
            raise Invalid("Dieser Beitrag ist schon auf LinkedIn.")
        if not post.body.strip():
            raise Invalid("Ohne Text kann nichts auf LinkedIn erscheinen.")
        try:
            urn = linkedin_link.publish(owner, post.body, fetch=fetch)
        except linkedin_link.LinkedInError as exc:
            post.post_error = str(exc)[:300]
            session.commit()
            raise Invalid(str(exc)) from exc
        post.linkedin_urn = urn[:120]
        post.published_url = linkedin_link.post_url(urn)[:500]
        post.status, post.post_at, post.post_as, post.post_error = "veroeffentlicht", None, owner, ""
        post.planned_on = dt.datetime.now(config.local_zone()).date()
        post.updated_at = _now()
        session.commit()
        return post


def schedule_post(session: Session, post: LinkedInPost, owner: str, form: Mapping) -> LinkedInPost:
    """Let the scheduler post it at the given local time, through ``owner``'s account."""
    if post.linkedin_urn:
        raise Invalid("Dieser Beitrag ist schon auf LinkedIn.")
    if not post.body.strip():
        raise Invalid("Ohne Text kann nichts auf LinkedIn erscheinen.")
    raw = str(form.get("post_at") or "").strip()
    try:
        local = dt.datetime.fromisoformat(raw)
    except ValueError:
        raise Invalid("Bitte Datum und Uhrzeit angeben.") from None
    zone = config.local_zone()
    moment = (local if local.tzinfo else local.replace(tzinfo=zone)).astimezone(dt.UTC)
    if moment < _now() - dt.timedelta(minutes=1):
        raise Invalid("Der Zeitpunkt liegt in der Vergangenheit.")
    linked = linkedin_link.connection(owner)
    if linked is None or not linked.usable():
        raise Invalid("Erst LinkedIn verbinden.")
    if not linked.usable(moment):
        raise Invalid(f"Deine LinkedIn-Verbindung läuft am {linked.expires_at.astimezone(zone):%d.%m.%Y} ab, "
                      "vor diesem Termin. Bitte zuerst neu verbinden.")
    post.post_at, post.post_as, post.post_error, post.status = moment, owner, "", "geplant"
    post.planned_on = moment.astimezone(zone).date()
    post.updated_at = _now()
    session.commit()
    return post


#: Where a post someone published by hand lives.
_LINKEDIN_HOSTS = ("https://www.linkedin.com/", "https://linkedin.com/", "https://lnkd.in/")


def mark_published(session: Session, post: LinkedInPost, form: Mapping) -> LinkedInPost:
    """A person posted it on LinkedIn themselves and brings back the link."""
    url = _text(form, "published_url", 500, required="Bitte den Link zum Beitrag einfügen.")
    if not url.startswith(_LINKEDIN_HOSTS):
        raise Invalid("Das ist kein Link zu LinkedIn.")
    post.published_url, post.status, post.post_at = url, "veroeffentlicht", None
    post.planned_on = post.planned_on or dt.datetime.now(config.local_zone()).date()
    post.updated_at = _now()
    session.commit()
    return post


def unschedule_post(session: Session, post: LinkedInPost) -> None:
    post.post_at = None
    post.updated_at = _now()
    session.commit()


def publish_due(session: Session, now: dt.datetime | None = None, *, fetch=None) -> int:
    """Post every scheduled post whose time has come. Returns how many went out.

    Each is unscheduled before it is tried: a failure is written on the card
    for a person to see, never retried by itself into a second post.
    """
    now = now or _now()
    due = list(session.scalars(select(LinkedInPost).where(
        LinkedInPost.post_at.is_not(None), LinkedInPost.post_at <= now, LinkedInPost.linkedin_urn == "")))
    sent = 0
    for post in due:
        owner = post.post_as
        post.post_at = None
        session.commit()
        try:
            publish_post(session, post, owner, fetch=fetch)
            sent += 1
        except Invalid as exc:
            post.post_error = f"Geplanter Beitrag ging nicht raus: {exc}"[:300]
            session.commit()
    return sent


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


def overdue_for(session, member, *, today=None):
    """Only assigned, unfinished tasks, from the calendar day after their deadline."""
    import datetime as dt
    from zoneinfo import ZoneInfo
    if member not in TEAM_KEYS:
        return []
    today = today or dt.datetime.now(ZoneInfo('Europe/Zurich')).date()
    return [task for task in open_tasks(session)
            if member in (task.assignees or []) and task.due_on and task.due_on < today
            and task.source_open is not False]
