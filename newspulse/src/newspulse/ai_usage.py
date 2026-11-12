"""How much of each AI subscription or budget is used, for Einstellungen › KI-Verbindungen.

Each provider tells a different amount, so each is read where it is actually
known, never estimated:

* **Claude (Abo):** every ``claude -p`` call streams a ``rate_limit_event`` with
  the utilisation of the five-hour and the seven-day window and when each
  resets. The last one seen is kept (:func:`record_claude`).
* **OpenAI (ChatGPT-Abo über Codex):** the Codex app server answers
  ``account/rateLimits/read`` without running a model, so it is asked directly
  when the settings are opened, at most every few minutes (:func:`codex`).
* **Gemini (API-Schlüssel):** Google offers no call that says what is left of a
  budget. What RauteOS itself spent is counted instead, per calendar month:
  calls, tokens and Google searches (:func:`record_gemini`). The euro budget
  itself is set and read in Google AI Studio.

Everything is stored in the ``settings`` table under ``ai_usage:<provider>``.
Recording never raises: a counter must not cost the call it counts.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import subprocess

_log = logging.getLogger(__name__)
_PREFIX = "ai_usage:"
_CODEX_MAX_AGE = dt.timedelta(minutes=5)
_CODEX_TIMEOUT = 8.0

#: Where the Gemini budget is set and the bill is read.
GEMINI_BILLING_URL = "https://aistudio.google.com/billing"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _load(session, provider: str) -> dict:
    from .models import Setting

    row = session.get(Setting, _PREFIX + provider)
    try:
        value = json.loads(row.value) if row and row.value else {}
    except json.JSONDecodeError:
        value = {}
    return value if isinstance(value, dict) else {}


def _store(provider: str, update) -> None:
    """Read, change and write one provider's record in its own session."""
    from . import ai_models
    from .models import Setting

    try:
        with ai_models._open() as session:
            if isinstance(session, ai_models._NoSettings):
                return
            record = update(_load(session, provider))
            row = session.get(Setting, _PREFIX + provider)
            text = json.dumps(record)
            if row is None:
                session.add(Setting(key=_PREFIX + provider, value=text))
            else:
                row.value = text
            session.commit()
    except Exception:  # noqa: BLE001 - a counter must never fail the call it counts
        _log.debug("recording %s usage failed", provider, exc_info=True)


def _window(name: str, used: float | None, resets_at, minutes: int | None = None) -> dict:
    return {"name": name, "used_percent": None if used is None else round(float(used), 1),
            "resets_at": int(resets_at) if isinstance(resets_at, (int, float)) else None,
            "minutes": minutes}


# --- Claude ------------------------------------------------------------------------


def record_claude(info: dict) -> None:
    """Keep the windows from one ``rate_limit_event`` of the Claude CLI."""
    if not isinstance(info, dict):
        return
    windows = info.get("unifiedWindows") or {}
    known = {"five_hour": ("5 Stunden", 300), "seven_day": ("7 Tage", 10080)}
    shown = []
    for key, (label, minutes) in known.items():
        w = windows.get(key)
        if isinstance(w, dict) and w.get("utilization") is not None:
            shown.append(_window(label, 100 * float(w["utilization"]), w.get("resetsAt"), minutes))
    if not shown and info.get("resetsAt"):
        shown.append(_window(str(info.get("rateLimitType") or "Kontingent"), None, info.get("resetsAt")))
    record = {"windows": shown, "status": info.get("status"), "seen_at": _now().isoformat()}
    _store("claude", lambda _old: record)


def claude_events(stdout: str) -> None:
    """Record the last ``rate_limit_event`` in a stream of CLI events."""
    last = None
    for line in (stdout or "").splitlines():
        if '"rate_limit_event"' not in line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "rate_limit_event":
            last = event.get("rate_limit_info")
    if last:
        record_claude(last)


# --- OpenAI over Codex -------------------------------------------------------------


def _codex_query(timeout: float = _CODEX_TIMEOUT) -> dict:
    """``account/rateLimits/read`` from a short-lived ``codex app-server``."""
    from . import codex_cli

    requests = [
        {"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "rauteos", "version": "1"}}},
        {"method": "initialized"},
        {"id": 2, "method": "account/rateLimits/read"},
    ]
    stdin = "".join(json.dumps(r) + "\n" for r in requests)
    process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
        ["codex", "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, env=codex_cli.env(),
    )
    try:
        process.stdin.write(stdin)
        process.stdin.flush()
        deadline = _now() + dt.timedelta(seconds=timeout)
        while _now() < deadline:
            line = process.stdout.readline()
            if not line:
                break
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict) and message.get("id") == 2:
                if "error" in message:
                    raise RuntimeError(str((message["error"] or {}).get("message") or "error"))
                return message.get("result") or {}
        raise TimeoutError("codex app-server gave no answer")
    finally:
        process.kill()
        process.wait(timeout=5)


def _codex_record(result: dict) -> dict:
    limits = result.get("rateLimits") or {}
    shown = []
    for key in ("primary", "secondary"):
        w = limits.get(key)
        if isinstance(w, dict) and w.get("usedPercent") is not None:
            minutes = w.get("windowDurationMins")
            label = _span(minutes) if minutes else ("Kurzfristig" if key == "primary" else "Wöchentlich")
            shown.append(_window(label, w["usedPercent"], w.get("resetsAt"), minutes))
    return {"windows": shown, "plan": limits.get("planType"),
            "blocked": result.get("ordinaryUsageAllowed") is False, "seen_at": _now().isoformat()}


def _span(minutes: int) -> str:
    if minutes % 1440 == 0:
        days = minutes // 1440
        return "1 Tag" if days == 1 else f"{days} Tage"
    if minutes % 60 == 0:
        hours = minutes // 60
        return "1 Stunde" if hours == 1 else f"{hours} Stunden"
    return f"{minutes} Minuten"


def codex(session, *, query=None) -> dict:
    """The ChatGPT subscription's windows, asked fresh when the last answer is old."""
    from . import codex_cli

    record = _load(session, "openai")
    seen = record.get("seen_at")
    fresh = seen and _now() - dt.datetime.fromisoformat(seen) < _CODEX_MAX_AGE
    if fresh or disabled() or not codex_cli.logged_in():
        return record
    try:
        record = _codex_record((query or _codex_query)())
    except Exception as exc:  # noqa: BLE001 - the page shows the last known state
        _log.warning("reading the ChatGPT rate limits failed: %s", exc)
        return {**record, "error": "Kontingent konnte gerade nicht gelesen werden."}
    _store("openai", lambda _old: record)
    return record


# --- Gemini ------------------------------------------------------------------------


def record_gemini(payload: dict, *, searched: bool = False) -> None:
    """Add one ``generateContent`` answer to this month's count."""
    meta = (payload or {}).get("usageMetadata") or {}
    month = _now().strftime("%Y-%m")
    queries = 0
    if searched:
        grounding = ((payload.get("candidates") or [{}])[0] or {}).get("groundingMetadata") or {}
        queries = len(grounding.get("webSearchQueries") or []) or 1

    def update(old: dict) -> dict:
        current = old if old.get("month") == month else {"month": month}
        return {
            **current,
            "month": month,
            "calls": int(current.get("calls", 0)) + 1,
            "input_tokens": int(current.get("input_tokens", 0)) + int(meta.get("promptTokenCount") or 0),
            "output_tokens": int(current.get("output_tokens", 0)) + int(meta.get("candidatesTokenCount") or 0)
            + int(meta.get("thoughtsTokenCount") or 0),
            "searches": int(current.get("searches", 0)) + queries,
            "seen_at": _now().isoformat(),
        }

    _store("gemini", update)


def record_gemini_refusal(message: str) -> None:
    """Remember that Google refused for quota or budget, and when."""
    _store("gemini", lambda old: {**old, "refused_at": _now().isoformat(), "refusal": message[:200]})


# --- For the page ------------------------------------------------------------------


def overview(session) -> dict[str, dict]:
    """Per provider what the settings show: windows, or this month's count."""
    gemini = _load(session, "gemini")
    month = _now().strftime("%Y-%m")
    if gemini.get("month") != month:
        gemini = {"month": month, "refused_at": gemini.get("refused_at"), "refusal": gemini.get("refusal")}
    try:
        openai = codex(session)
    except Exception:  # noqa: BLE001
        openai = _load(session, "openai")
    return {
        "claude": {"kind": "windows", **_load(session, "claude")},
        "openai": {"kind": "windows", **openai},
        "gemini": {"kind": "budget", "billing_url": GEMINI_BILLING_URL, **gemini, "cash": _load(session, "gemini_cash")},
    }


def disabled() -> bool:
    """Tests and a developer without the CLIs can switch the live Codex query off."""
    return os.environ.get("NEWSPULSE_AI_USAGE_QUERY", "").lower() in {"0", "false", "off", "no"}


def save_gemini_cash(session, amount: str, currency: str) -> dict:
    """A manually copied balance, independent of usage counters and monthly reset."""
    from decimal import Decimal
    import re
    from .models import Setting
    text = amount.strip().replace(',', '.')
    if not re.fullmatch(r'-?\d{1,9}(?:\.\d{1,2})?', text):
        raise ValueError('Bitte einen Betrag mit maximal zwei Nachkommastellen eingeben')
    if currency not in {'EUR', 'USD', 'CHF'}:
        raise ValueError('Bitte EUR, USD oder CHF auswählen')
    record = {'amount': format(Decimal(text), '.2f'), 'currency': currency, 'updated_at': _now().isoformat()}
    key = _PREFIX + 'gemini_cash'
    row = session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=json.dumps(record)))
    else:
        row.value = json.dumps(record)
    session.commit()
    return record
