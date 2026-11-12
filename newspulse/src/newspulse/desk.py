"""The Desk: what the agency owes, what it delivered, and what needs deciding.

"Wenn wir morgens ins System gehen, brauchen wir keinen Newsfeed oder eine
Artikelliste, sondern ein echtes Arbeitsdashboard."

Every other page in RauteOS is about *one* mandate, and the portfolio page is a
list of them. This is the third thing: the agency's own morning. It answers
seven questions in the order they get asked — how many mandates are live, how
much work went out this month against what was promised, where something is
happening, what has been found, what is waiting on a decision, what is in
flight, and whose record has holes in it.

Nothing here is a new fact. Every figure is read from rows another part of the
tool already writes, which is the property that makes a dashboard worth trusting:
a number on the Desk can always be clicked down to the thing it counts. The one
exception is the manual action ledger (:class:`newspulse.models.ClientAction`),
and it exists because the alternative is a wrong number — see below.

Three definitions carry the page, and each was a choice:

* **An action is a delivery, and a delivery is a ``released_at``.** Outreach,
  Asset and Report all carry that column, and it means the same thing on all
  three: a person read it, approved it, and it went out. Not ``generated_at`` —
  the tool drafts far more than the agency sends, and counting drafts would
  report work that never happened.
* **Plus what happened elsewhere.** A background call, a briefing, an editorial
  visit: none of it touches this tool. Counting only released artefacts shows
  the agency doing consistently less than it does, and against a contractual
  figure that is not a neutral error.
* **The Twin is the mandate's record of itself**, and it is three things
  weighted by how hard they are to replace: the profile, the kick-off answers,
  and the communications guide. A machine can research most of a profile. It
  cannot answer what the client will never say in public.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config, profile as profiles
from .models import (
    Analysis,
    Article,
    Asset,
    Client,
    ClientAction,
    Crisis,
    NewsjackOpportunity,
    OpportunityWorkspace,
    Outreach,
    OutreachState,
    ProfileProposal,
    Report,
    visible_coverage,
)

_log = logging.getLogger(__name__)

#: How recently something must have happened for a mandate to read as live.
#: A week, because that is the rhythm the agency works in: a story from twelve
#: days ago is history, and a mandate quiet for six days is not "quiet" — it is
#: between things.
ACTIVE_WINDOW_DAYS = 7

@dataclass(frozen=True, slots=True)
class Actions:
    """Delivered work for one mandate over one span, and where it came from."""

    released: int
    logged: int

    @property
    def total(self) -> int:
        return self.released + self.logged


@dataclass(frozen=True, slots=True)
class Twin:
    """How complete a mandate's record of itself is, and which part is thin."""

    percent: int
    profile_filled: int
    profile_total: int
    has_guide: bool
    required_filled: int | None = None
    required_total: int | None = None
    required_missing: list[str] = field(default_factory=list)
    #: The researched brief (R) and the customer questionnaire (Q), each as
    #: ``{"filled": n, "total": n}``.
    parts: dict = field(default_factory=dict)

    @property
    def gaps(self) -> list[str]:
        """The parts worth naming on a Desk row, thinnest first.

        Named rather than numbered: "Profil unvollständig" tells a consultant
        what to do next, and "72 %" does not.
        """
        if self.required_total is not None:
            return self.required_missing
        missing: list[tuple[float, str]] = []
        if self.profile_total:
            share = self.profile_filled / self.profile_total
            if share < 1:
                missing.append((share, "Profil unvollständig"))
        if not self.has_guide:
            missing.append((0.0, "Kein Kommunikationsguide"))
        return [name for _, name in sorted(missing)]


@dataclass(frozen=True, slots=True)
class MandateRow:
    """One line of the Mandantenüberblick."""

    client: Client
    twin: Twin
    actions_month: Actions
    actions_quarter: Actions
    promised_quarter: int | None
    opportunities: int
    live: bool
    crisis_open: bool

    @property
    def status(self) -> str:
        """The sentence in the status column, and the three states are distinct.

        An open crisis outranks everything: it is the one state where "ruhig"
        would be actively wrong. Otherwise the question is whether the last week
        produced anything at all.
        """
        if self.crisis_open:
            return "krise"
        if self.live:
            return "aktiv"
        return "ruhig"

    @property
    def on_track(self) -> bool | None:
        """Whether the quarter's promise is being kept, or ``None`` if none was made.

        ``None`` rather than ``True``: a mandate nobody has entered a figure for
        is not on track, it is unmeasured, and a green tick against a promise
        that does not exist is the sort of number that gets quoted in a client
        meeting.
        """
        if self.promised_quarter is None:
            return None
        return self.actions_quarter.total >= self.promised_quarter


@dataclass(frozen=True, slots=True)
class Decision:
    """One thing waiting on a person, with what it is about and how urgent."""

    client: Client
    kind: str
    title: str
    detail: str
    since: dt.datetime | None
    href: str
    source_key: str = ""


@dataclass(frozen=True, slots=True)
class InFlight:
    """One piece of work between drafted and delivered."""

    client: Client
    title: str
    state: str
    since: dt.datetime
    href: str


@dataclass(frozen=True, slots=True)
class Chance:
    """One open Thema, for the Desk's "Themen" list."""

    client: Client
    kind: str
    title: str
    status: str
    since: dt.datetime | None
    href: str


@dataclass(frozen=True, slots=True)
class TaskItem:
    """One open task for the Desk (spec 10). ``client`` is None for agency work."""

    id: int
    client: Client | None
    title: str
    priority: str
    due_on: dt.date | None
    href: str
    #: Who does it, as team member names ("Lucas").
    assignees: tuple[str, ...] = ()
    status: str = "offen"


@dataclass(frozen=True, slots=True)
class Desk:
    """Everything the morning page states, assembled once."""

    rows: list[MandateRow] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    in_flight: list[InFlight] = field(default_factory=list)
    chances: list[Chance] = field(default_factory=list)
    tasks: list[TaskItem] = field(default_factory=list)
    tasks_open: int = 0
    #: Of those, due today or overdue. Counted over all of them, not the five shown.
    tasks_due: int = 0
    #: Every open task, for the mandate pages that filter by client.
    all_tasks: list[TaskItem] = field(default_factory=list)
    generated_at: dt.datetime | None = None

    @property
    def clients_active(self) -> int:
        return len(self.rows)

    @property
    def actions_month(self) -> int:
        return sum(row.actions_month.total for row in self.rows)

    @property
    def opportunities(self) -> int:
        return sum(row.opportunities for row in self.rows)

    @property
    def decisions_open(self) -> int:
        return len(self.decisions)

    @property
    def twins_with_gaps(self) -> int:
        return sum(1 for row in self.rows if row.twin.gaps)

    @property
    def twin_average(self) -> int:
        """The portfolio's own completeness, for the footer figure."""
        if not self.rows:
            return 0
        return round(sum(row.twin.percent for row in self.rows) / len(self.rows))


# --- Spans -----------------------------------------------------------------------


def month_start(now: dt.datetime) -> dt.datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def quarter_start(now: dt.datetime) -> dt.datetime:
    """The first instant of the calendar quarter ``now`` falls in.

    Calendar quarters, not a rolling ninety days: the promise is contractual and
    a contract's quarter is January, April, July, October. A rolling window would
    show a mandate slipping out of compliance on a Tuesday because a delivery
    from ninety-one days ago fell off the back.
    """
    first_month = 3 * ((now.month - 1) // 3) + 1
    return now.replace(
        month=first_month, day=1, hour=0, minute=0, second=0, microsecond=0
    )


# --- Counting --------------------------------------------------------------------


def _released_counts(session: Session, since: dt.datetime) -> dict[int, int]:
    """Released artefacts per client since ``since``, across all three kinds.

    One query per table rather than a union: they are three different tables with
    three different meanings, and a union would need every one of them to keep
    the same column names forever to stay correct.
    """
    counts: dict[int, int] = {}
    for model in (Outreach, Asset, Report):
        rows = session.execute(
            select(model.client_id, func.count())
            .where(model.released_at.is_not(None), model.released_at >= since)
            .group_by(model.client_id)
        ).all()
        for client_id, count in rows:
            counts[client_id] = counts.get(client_id, 0) + count
    return counts


def _logged_counts(session: Session, since: dt.datetime) -> dict[int, int]:
    """Hand-logged actions per client since ``since``.

    By ``happened_at``, never ``logged_at``: an action belongs in the quarter it
    happened in, not the quarter somebody remembered to write it down.
    """
    rows = session.execute(
        select(ClientAction.client_id, func.count())
        .where(ClientAction.happened_at >= since)
        .group_by(ClientAction.client_id)
    ).all()
    return {client_id: count for client_id, count in rows}


def _actions(
    client_id: int, released: dict[int, int], logged: dict[int, int]
) -> Actions:
    return Actions(
        released=released.get(client_id, 0), logged=logged.get(client_id, 0)
    )


def _twin(session: Session, client: Client) -> Twin:
    """The mandate's record of itself, as one figure and its parts."""
    facts = profiles.stored(session, client.id)
    has_guide = bool((client.comms_guide or "").strip())
    from . import twin
    progress = twin.completeness(facts.statements)
    return Twin(
        percent=progress["percent"],
        profile_filled=sum(f.key in facts for f in profiles.FIELDS),
        profile_total=profiles.FILLABLE,
        has_guide=has_guide,
        required_filled=progress["required_filled"],
        required_total=progress["required_total"],
        required_missing=([f"{len(progress['missing'])} Fragen unbeantwortet"]
                          if progress["missing"] else []),
        parts=progress["parts"],
    )


def _live_clients(session: Session, since: dt.datetime) -> set[int]:
    """Mandates with visible coverage in the window.

    :func:`newspulse.models.visible_coverage` and not merely "an analysis exists":
    the same predicate the rest of the tool uses for "this counts as coverage",
    so the Desk cannot disagree with the page a reader clicks through to.
    """
    rows = session.execute(
        select(Analysis.client_id)
        .join(Article, Article.id == Analysis.article_id)
        .where(visible_coverage(), Article.published_at >= since)
        .group_by(Analysis.client_id)
    ).all()
    return {client_id for (client_id,) in rows}


def _open_crises(session: Session) -> set[int]:
    rows = session.execute(
        select(Crisis.client_id).where(Crisis.closed_at.is_(None))
    ).all()
    return {client_id for (client_id,) in rows}


def _open_listings(session: Session, clients) -> dict[int, list[dict]]:
    """Each mandate's open chances, exactly as its own opportunity list has them
    (:func:`workspaces.listings`): evidenced, not dismissed, window open, not
    closed. The count and the lists read this, so they cannot disagree."""
    from . import workspaces

    return {cid: [r for r in workspaces.listings(session, cid) if r["status"] != "closed"] for cid in clients}


def _opportunity_counts(session: Session, now: dt.datetime, listed: dict[int, list[dict]] | None = None) -> dict[int, int]:
    """Opportunities still open, per mandate: the length of its open list.

    A closed window is not an opportunity any more, and drawing it as one is how
    a dashboard teaches people to ignore its numbers.
    """
    if listed is None:
        listed = _open_listings(session, [c.id for c in session.scalars(select(Client).where(
            Client.active.is_(True), Client.is_competitor.is_(False)))])
    return {cid: len(rows) for cid, rows in listed.items() if rows}


def _decisions(session: Session, clients: dict[int, Client], *, hide_settled: bool = True) -> list[Decision]:
    """Everything standing still until somebody decides, newest need first.

    Three kinds, and they are three because each has a different answer:

    * a letter written and not yet signed off by the client — the gate OUT-05
      put in front of every journalist;
    * a letter signed off and not yet released — the agency's own last look;
    * a profile value the research contradicts, which only a person can settle.

    Not included: an impulse RAUTE proposed. It is already an open chance
    (a developed one) in "Relevante Chancen" and in the count beside it, and
    listing it here too made one proposal read as two kinds of work.
    Nor anything the tool can decide itself. A dashboard that lists
    work it could have done is a dashboard nobody finishes reading.
    """
    from . import workspaces

    pending: list[Decision] = []

    letters = session.scalars(
        select(Outreach).where(
            Outreach.state == OutreachState.ENTWURF,
            Outreach.client_id.in_(clients),
        )
    ).all()
    for letter in letters:
        signed_off = letter.client_ok_at is not None
        pending.append(
            Decision(
                client=clients[letter.client_id],
                kind="freigabe" if signed_off else "kundenfreigabe",
                title=letter.subject or "Anschreiben ohne Betreff",
                detail=(
                    "Vom Kunden abgestimmt, wartet auf die Freigabe der Agentur."
                    if signed_off
                    else "Wartet auf die Abstimmung mit dem Kunden."
                ),
                since=letter.generated_at,
                href=workspaces.text_href(session, letter, "outreach"),
                source_key=f"outreach:{letter.id}",
            )
        )

    contradictions = session.scalars(
        select(ProfileProposal).where(
            ProfileProposal.discarded_at.is_(None),
            ProfileProposal.client_id.in_(clients),
        )
    ).all()
    for row in contradictions:
        pending.append(
            Decision(
                client=clients[row.client_id],
                kind="profil",
                title=f"Profilfeld „{row.key}“",
                detail="Die Recherche widerspricht dem, was im Profil steht.",
                since=row.proposed_at,
                href=f"/client/{row.client_id}/profil",
                source_key=f"profile-proposal:{row.id}",
            )
        )

    # The Desk counts what the board "Offene Entscheidungen" shows: a decision
    # whose task was deleted there, or moved to Erledigt, is settled for the
    # team even though the letter itself is still waiting. Counting it anyway
    # left a "1 offene Entscheidung" nobody could find.
    from .models import DismissedTaskSource, Task

    keys = [d.source_key for d in pending if d.source_key]
    if keys and hide_settled:
        settled = set(session.scalars(
            select(DismissedTaskSource.source_key).where(DismissedTaskSource.source_key.in_(keys))))
        settled |= set(session.scalars(
            select(Task.source_key).where(Task.source_key.in_(keys), Task.status == "erledigt")))
        pending = [d for d in pending if d.source_key not in settled]

    # Oldest first: a decision that has been waiting three weeks is more urgent
    # than one raised this morning, and a list sorted the other way buries it.
    pending.sort(key=lambda d: (d.since is None, d.since))
    return pending


def open_decisions(session: Session, client_id: int | None = None, *, hide_settled: bool = True) -> list[Decision]:
    """The Desk's open decisions, for pages other than the Desk.

    The same rows "Entscheidungen offen" counts, so the Aufgaben page lists
    exactly what the Desk's figure promises. ``client_id`` narrows to one mandate.
    """
    query = select(Client).where(Client.active.is_(True), Client.is_competitor.is_(False))
    if client_id is not None:
        query = query.where(Client.id == client_id)
    by_id = {client.id: client for client in session.scalars(query)}
    return _decisions(session, by_id, hide_settled=hide_settled) if by_id else []


def _in_flight(session: Session, clients: dict[int, Client]) -> list[InFlight]:
    """Work between drafted and delivered: letters out, texts not yet released."""
    from . import workspaces
    running: list[InFlight] = []

    sent = session.scalars(
        select(Outreach).where(
            Outreach.state == OutreachState.RAUS, Outreach.client_id.in_(clients)
        )
    ).all()
    for letter in sent:
        running.append(
            InFlight(
                client=clients[letter.client_id],
                title=letter.subject or "Anschreiben",
                state="raus",
                since=letter.released_at or letter.generated_at,
                href=workspaces.text_href(session, letter, "outreach"),
            )
        )

    drafts = session.scalars(
        select(Asset).where(
            Asset.released_at.is_(None), Asset.client_id.in_(clients)
        )
    ).all()
    for asset in drafts:
        running.append(
            InFlight(
                client=clients[asset.client_id],
                title=asset.title or str(asset.kind),
                state="entwurf",
                since=asset.edited_at or asset.generated_at,
                href=workspaces.text_href(session, asset),
            )
        )

    running.sort(key=lambda row: row.since, reverse=True)
    return running


# --- The page ----------------------------------------------------------------------


def build(session: Session, *, now: dt.datetime | None = None, member: str | None = None) -> Desk:
    """Assemble the whole morning page in one pass.

    Mandates only. A competitor is tracked so a mandate can be compared against
    it; nobody owes it actions, nobody writes it letters, and a yardstick in the
    Mandantenüberblick would be counted in every total on the page.
    """
    moment = now or dt.datetime.now(dt.UTC)
    since_month = month_start(moment)
    since_quarter = quarter_start(moment)
    since_week = moment - dt.timedelta(days=ACTIVE_WINDOW_DAYS)

    mandates = session.scalars(
        select(Client)
        .where(Client.active.is_(True), Client.is_competitor.is_(False))
        .order_by(Client.name)
    ).all()
    by_id = {client.id: client for client in mandates}
    open_tasks = _open_tasks(session, member=member)
    if not by_id:
        return Desk(generated_at=moment, tasks=open_tasks[:TASKS_SHOWN], tasks_open=len(open_tasks),
                    tasks_due=_due(open_tasks, moment), all_tasks=open_tasks)

    released_month = _released_counts(session, since_month)
    logged_month = _logged_counts(session, since_month)
    released_quarter = _released_counts(session, since_quarter)
    logged_quarter = _logged_counts(session, since_quarter)
    live = _live_clients(session, since_week)
    crises = _open_crises(session)
    listed = _open_listings(session, by_id)
    opportunities = _opportunity_counts(session, moment, listed)

    rows = [
        MandateRow(
            client=client,
            twin=_twin(session, client),
            actions_month=_actions(client.id, released_month, logged_month),
            actions_quarter=_actions(client.id, released_quarter, logged_quarter),
            promised_quarter=client.actions_per_quarter,
            opportunities=opportunities.get(client.id, 0),
            live=client.id in live,
            crisis_open=client.id in crises,
        )
        for client in mandates
    ]
    return Desk(
        rows=rows,
        decisions=_personal_decisions(session, _decisions(session, by_id), member),
        in_flight=_in_flight(session, by_id),
        chances=_chances(session, by_id, listed=listed),
        tasks=open_tasks[:TASKS_SHOWN],
        tasks_open=len(open_tasks),
        tasks_due=_due(open_tasks, moment),
        all_tasks=open_tasks,
        generated_at=moment,
    )


#: How many open tasks "Heute priorisiert" carries before the decisions.
TASKS_SHOWN = 5


def _due(tasks: list["TaskItem"], moment: dt.datetime) -> int:
    today = moment.astimezone(config.local_zone()).date()
    return sum(1 for t in tasks if t.due_on and t.due_on <= today)


def _open_tasks(session: Session, *, member: str | None = None) -> list[TaskItem]:
    """Open tasks, due first (spec 10): the same order as the Aufgaben page."""
    from . import worklists

    names = {key: name for key, name, _ in worklists.TEAM}
    return [TaskItem(id=t.id, client=t.client, title=t.title, priority=t.priority, due_on=t.due_on, status=t.status,
                     href=t.context_href or f"/aufgaben?aufgabe={t.id}",
                     assignees=tuple(names.get(a, a) for a in (t.assignees or [])))
            for t in worklists.open_tasks(session) if not t.source_key
            and (member is None or member in (t.assignees or []))]


def _personal_decisions(session, decisions, member):
    if member is None:
        return decisions
    from .models import Task
    assigned_elsewhere = {t.source_key for t in session.scalars(select(Task).where(Task.source_key.is_not(None)))
                          if t.assignees and member not in t.assignees}
    return [d for d in decisions if d.source_key not in assigned_elsewhere]


#: How many open opportunities the Desk lists. The count beside it is the
#: whole number; the list is where to start.
CHANCES_SHOWN = 6


def _chances(session: Session, clients: dict[int, Client], limit: int = CHANCES_SHOWN, *,
             listed: dict[int, list[dict]] | None = None, kind: str | None = None) -> list[Chance]:
    """The newest open opportunities across every mandate.

    The same rows each mandate's own opportunity list shows
    (:func:`workspaces.listings`), so the Desk cannot name a chance the
    mandate's page does not have. Closed ones are left out; ``kind`` keeps
    only detected or developed ones, before the cut to ``limit``.
    """
    listed = listed if listed is not None else _open_listings(session, clients)
    found = [
        Chance(
            client=client,
            kind=row["context_kind"],
            title=row["title"],
            status=row["status"],
            since=row["created_at"],
            # Spec 12: an activated Thema is worked on under Assets; an open one
            # is read on the Themen, at its own card.
            href=(f"/client/{client.id}/assets?kind={row['context_kind']}&context={row['context_id']}"
                  if row["status"] == "active" else
                  f"/client/{client.id}/themen#thema-{row['context_kind']}-{row['context_id']}"),
        )
        for client in clients.values()
        for row in listed.get(client.id, [])
        if kind is None or row["context_kind"] == kind
    ]
    epoch = dt.datetime.min.replace(tzinfo=dt.UTC)
    found.sort(key=lambda c: _aware(c.since) if c.since else epoch, reverse=True)
    return found[:limit]


def _aware(moment: dt.datetime) -> dt.datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=dt.UTC)
