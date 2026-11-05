"""The Desk's briefing in RAUTE's words, on request (spec 02 "Offen", spec 09).

The Desk already states its briefing from its own figures. This is the same
briefing written by a model, and it only ever sees those figures: the open
decisions, the due tasks, the open chances, a crisis. It may order and phrase
them; it may not add anything, because a morning briefing that invents a
journalist's call is worse than none.

One call when somebody asks for it, kept for the rest of the day in this
process. A restart or a new day asks again; the figures move during the day,
so "Neu formulieren" asks again on purpose.
"""

from __future__ import annotations

import datetime as dt
import threading

from . import config, prose
from .analyzer import AnalyzerError, invoke_with_fallback

#: The longest briefing the banner shows. A model that writes more has not
#: written a briefing.
MAX_CHARS = 600
_TIMEOUT = 120

_lock = threading.Lock()
_cache: dict[str, tuple[str, dt.datetime]] = {}


def _today() -> str:
    return dt.datetime.now(config.local_zone()).date().isoformat()


def facts(board) -> str:
    """What the model may use, as plain lines. Nothing else reaches it."""
    today = dt.datetime.now(config.local_zone()).date()
    lines = [f"Datum: {today:%d.%m.%Y}",
             f"Aktive Mandanten: {board.clients_active}",
             f"Offene Entscheidungen: {board.decisions_open}",
             f"Offene Chancen: {board.opportunities}",
             f"Offene Aufgaben: {board.tasks_open}"]
    crises = [row.client.name for row in board.rows if row.crisis_open]
    if crises:
        lines.append("Offene Krise bei: " + ", ".join(crises))
    for d in board.decisions[:8]:
        lines.append(f"Entscheidung ({d.kind}) bei {d.client.name}: {d.title}")
    for t in board.tasks:
        due = f", fällig {t.due_on:%d.%m.}" if t.due_on else ""
        late = " (überfällig)" if t.due_on and t.due_on < today else ""
        lines.append(f"Aufgabe ({t.priority}{due}{late}) "
                     f"{'für ' + t.client.name if t.client else 'der Agentur'}: {t.title}")
    for c in board.chances[:6]:
        lines.append(f"Chance bei {c.client.name}: {c.title}")
    waiting = [i for i in board.in_flight if i.state == "raus"]
    if waiting:
        lines.append(f"Verschickt und ohne Antwort: {len(waiting)}")
    return "\n".join(lines)


def prompt(board) -> str:
    return f"""Du schreibst das Morgen-Briefing für das Team einer PR-Agentur.
Schreibe auf Deutsch zwei bis drei kurze Sätze, höchstens 450 Zeichen.
Nenne zuerst, was heute am dringendsten ist, mit Mandantennamen.
Verwende ausschließlich die Angaben unten. Erfinde nichts dazu, keine Zahlen,
keine Personen, keine Termine. Wenn wenig ansteht, sag das in einem Satz.
Keine Anrede, keine Einleitung, keine Aufzählungszeichen, keine Gedankenstriche.

Angaben:
{facts(board)}"""


def cached() -> dict | None:
    """Today's briefing if one was written, with when."""
    with _lock:
        hit = _cache.get(_today())
    return dict(text=hit[0], written_at=hit[1]) if hit else None


def write(board, *, invoke=None) -> dict:
    """Ask the model once and keep the answer for today.

    Raises :class:`AnalyzerError` when the model fails or answers with
    nothing usable; the Desk then keeps its own briefing.
    """
    # Looked up at call time, so a test that replaces the module's function
    # reaches this call too.
    invoke = invoke or invoke_with_fallback
    text = prose.plain(" ".join((invoke(prompt(board), timeout=_TIMEOUT) or "").split()))
    if not text:
        raise AnalyzerError("Das Modell hat kein Briefing geliefert.")
    if len(text) > MAX_CHARS:
        cut = text[:MAX_CHARS]
        text = cut[: cut.rfind(".") + 1] or cut.rsplit(" ", 1)[0] + " …"
    written = dt.datetime.now(dt.UTC)
    with _lock:
        _cache.clear()  # only today matters
        _cache[_today()] = (text, written)
    return dict(text=text, written_at=written)
