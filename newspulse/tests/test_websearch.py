"""Web research: Claude reads the web by default, Gemini only when Claude cannot."""

from __future__ import annotations

import json
import subprocess

import pytest

from newspulse import analyzer, config, gemini, websearch


def _stream(*events) -> str:
    return "\n".join(json.dumps(e) for e in events)


def _completed(stdout: str, returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


_SEARCH = {
    "type": "user",
    "tool_use_result": {
        "query": "Zalando Gründung",
        "results": [
            {"content": [
                {"title": "Zehn Jahre Zalando", "url": "https://fashionunited.de/zalando"},
                {"title": "Gründer", "url": "https://gruender.de/zalando"},
            ]},
            "a summary string the CLI also puts in this list",
        ],
    },
}
_FETCH = {"type": "user", "tool_use_result": {"url": "https://corporate.zalando.com/", "code": 200}}
_DEAD = {"type": "user", "tool_use_result": {"url": "https://gone.example/", "code": 404}}


def test_the_pages_come_from_the_tool_results_not_from_the_answer(monkeypatch):
    """A source the model names but never opened must not count as one, so the
    list is read from what WebSearch and WebFetch returned."""
    result = {"type": "result", "is_error": False,
              "result": 'Hier ist das JSON:\n{"answers": []}\nViel Erfolg.'}
    seen = {}

    def run(argv, **kwargs):
        seen["argv"] = argv
        return _completed(_stream(_SEARCH, _FETCH, _DEAD, result))

    monkeypatch.setattr(subprocess, "run", run)

    text, pages = analyzer.invoke_claude_search("frage")

    assert text == '{"answers": []}'
    assert pages == [
        ("https://fashionunited.de/zalando", "Zehn Jahre Zalando"),
        ("https://gruender.de/zalando", "Gründer"),
        ("https://corporate.zalando.com/", ""),
    ]
    # Page text from the open web is in the prompt: nothing that runs commands.
    assert seen["argv"][seen["argv"].index("--tools") + 1] == "WebSearch,WebFetch"


def test_a_failed_claude_call_is_a_backend_error(monkeypatch):
    result = {"type": "result", "is_error": True, "result": "Not logged in · Please run /login"}
    monkeypatch.setattr(subprocess, "run", lambda argv, **k: _completed(_stream(result), 1))

    with pytest.raises(analyzer.BackendError, match="Not logged in"):
        analyzer.invoke_claude_search("frage")


def test_claude_is_asked_first(monkeypatch):
    monkeypatch.setattr(analyzer, "invoke_claude_search", lambda p: ("{}", [("https://a.de", "")]))
    monkeypatch.setattr(gemini, "search", lambda p: pytest.fail("Gemini was asked"))

    assert websearch.search("frage") == ("{}", [("https://a.de", "")])


def test_gemini_answers_when_claude_cannot(monkeypatch):
    def broken(prompt):
        raise analyzer.BackendError("claude -p exited 1: OAuth session expired")

    monkeypatch.setattr(analyzer, "invoke_claude_search", broken)
    monkeypatch.setattr(config, "review_configured", lambda: True)
    monkeypatch.setattr(gemini, "search", lambda p: ("{}", []))

    assert websearch.search("frage") == ("{}", [])


def test_a_slow_claude_is_retried_by_the_queue_rather_than_handed_to_gemini(monkeypatch):
    def slow(prompt):
        raise analyzer.BackendError("claude -p timed out after 300s")

    monkeypatch.setattr(analyzer, "invoke_claude_search", slow)
    monkeypatch.setattr(config, "review_configured", lambda: True)
    monkeypatch.setattr(gemini, "search", lambda p: pytest.fail("Gemini was asked"))

    with pytest.raises(analyzer.BackendError, match="timed out"):
        websearch.search("frage")
