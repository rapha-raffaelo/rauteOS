"""Research on the open web: Claude first, Gemini when Claude cannot answer.

Claude is the default because it runs on the subscription the rest of the tool
already uses and reads pages itself before it writes. Gemini stays as the
fallback for the day the CLI login has lapsed or the subscription is spent,
which is exactly when a mandate's research would otherwise stop.

A timeout is not a reason to switch: the onboarding queue retries it, and a
second provider asked the same slow question doubles the wait.
"""

from __future__ import annotations

import logging

from . import analyzer, config, gemini

_log = logging.getLogger(__name__)


def search(prompt: str) -> tuple[str, list[tuple[str, str]]]:
    """``(text, [(url, title), ...])`` for one research prompt."""
    try:
        return analyzer.invoke_claude_search(prompt)
    except analyzer.BackendError as exc:
        if "timed out" in str(exc) or not config.review_configured():
            raise
        _log.warning("Claude web research failed, asking Gemini instead: %s", exc)
    return gemini.search(prompt)
