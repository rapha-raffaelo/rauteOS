"""Einstellungen › KI-Verbindungen: what is left of each subscription or budget."""
import datetime as dt
import json
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse import ai_models, ai_usage
from newspulse.models import Base


@pytest.fixture
def factory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    make = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _open():
        with make() as s:
            yield s

    monkeypatch.setattr(ai_models, "_open", _open)
    return make


EVENT = {"type": "rate_limit_event", "rate_limit_info": {
    "status": "allowed", "resetsAt": 1794487200, "rateLimitType": "five_hour",
    "unifiedWindows": {"five_hour": {"utilization": 0.02, "resetsAt": 1794487200},
                       "seven_day": {"utilization": 0.21, "resetsAt": 1794571200}}}}


def test_claude_windows_come_from_the_cli_event_stream(factory):
    stdout = "\n".join([json.dumps({"type": "system"}), json.dumps(EVENT),
                        json.dumps({"type": "result", "result": "ok"})])
    ai_usage.claude_events(stdout)
    with factory() as s:
        windows = ai_usage.overview(s)["claude"]["windows"]
    assert [(w["name"], w["used_percent"], w["resets_at"]) for w in windows] == [
        ("5 Stunden", 2.0, 1794487200), ("7 Tage", 21.0, 1794571200)]


def test_the_cli_result_is_read_from_the_stream():
    from newspulse.analyzer import _result_line

    stream = "\n".join([json.dumps(EVENT), json.dumps({"type": "result", "result": "ok"})])
    assert json.loads(_result_line(stream))["result"] == "ok"
    assert _result_line('{"type": "result", "result": "x"}') == '{"type": "result", "result": "x"}'


def test_chatgpt_limits_are_asked_from_codex_and_kept_for_a_while(factory, monkeypatch):
    from newspulse import codex_cli

    monkeypatch.setenv("NEWSPULSE_AI_USAGE_QUERY", "1")
    monkeypatch.setattr(codex_cli, "logged_in", lambda: True)
    asked = []

    def query():
        asked.append(1)
        return {"rateLimits": {"planType": "plus",
                               "primary": {"usedPercent": 35, "windowDurationMins": 300, "resetsAt": 1794480000},
                               "secondary": {"usedPercent": 80, "windowDurationMins": 10080, "resetsAt": 1795000000}},
                "ordinaryUsageAllowed": True}

    with factory() as s:
        record = ai_usage.codex(s, query=query)
        assert [(w["name"], w["used_percent"]) for w in record["windows"]] == [("5 Stunden", 35.0), ("7 Tage", 80.0)]
        assert record["plan"] == "plus" and not record["blocked"]
    with factory() as s:
        ai_usage.codex(s, query=query)
    assert len(asked) == 1, "a second look within minutes reuses the answer"


def test_a_failed_codex_read_keeps_the_last_state_and_says_so(factory, monkeypatch):
    from newspulse import codex_cli

    monkeypatch.setenv("NEWSPULSE_AI_USAGE_QUERY", "1")
    monkeypatch.setattr(codex_cli, "logged_in", lambda: True)

    def broken():
        raise RuntimeError("codex account authentication required")

    with factory() as s:
        assert "nicht gelesen" in ai_usage.codex(s, query=broken)["error"]


def test_gemini_counts_calls_tokens_and_searches_per_month(factory):
    payload = {"usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 200, "thoughtsTokenCount": 50},
               "candidates": [{"groundingMetadata": {"webSearchQueries": ["Acme", "Acme Werk"]}}]}
    ai_usage.record_gemini(payload)
    ai_usage.record_gemini(payload, searched=True)
    ai_usage.record_gemini_refusal("RESOURCE_EXHAUSTED")
    with factory() as s:
        g = ai_usage.overview(s)["gemini"]
    assert (g["calls"], g["input_tokens"], g["output_tokens"], g["searches"]) == (2, 2000, 500, 2)
    assert g["month"] == dt.datetime.now(dt.UTC).strftime("%Y-%m") and g["refused_at"]
    assert g["billing_url"].startswith("https://aistudio.google.com")


def test_recording_without_a_database_is_silent():
    ai_usage.record_gemini({"usageMetadata": {"promptTokenCount": 1}})
    ai_usage.claude_events(json.dumps(EVENT))

def test_manual_cash_is_independent_of_monthly_usage(factory, monkeypatch):
    with factory() as s:
        saved=ai_usage.save_gemini_cash(s,'123,45','EUR')
        assert saved['amount']=='123.45' and saved['updated_at']
    ai_usage.record_gemini({'usageMetadata':{'promptTokenCount':12}})
    monkeypatch.setattr(ai_usage,'_now',lambda:dt.datetime(2030,1,1,tzinfo=dt.UTC))
    with factory() as s:
        assert ai_usage._load(s, 'gemini_cash')==saved
        for amount,currency in [('NaN','EUR'),('1.234','EUR'),('12','BAD')]:
            with pytest.raises(ValueError): ai_usage.save_gemini_cash(s,amount,currency)
        assert ai_usage._load(s, 'gemini_cash')==saved
        assert ai_usage.save_gemini_cash(s,'0','USD')['amount']=='0.00'

def test_claude_extra_credits_do_not_hide_available_subscription(factory):
    ai_usage.record_claude({**EVENT['rate_limit_info'],'overageDisabledReason':'out_of_credits'})
    with factory() as s:
        data=ai_usage.overview(s)['claude']
        assert data['extra_usage_exhausted'] is True
        assert len(data['windows'])==2
    ai_usage.record_claude(EVENT['rate_limit_info'])
    with factory() as s:
        assert ai_usage.overview(s)['claude']['extra_usage_exhausted'] is False
