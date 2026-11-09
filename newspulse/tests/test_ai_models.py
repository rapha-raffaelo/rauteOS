"""KI-Modelle: keys stored encrypted, each role answered in its order."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from react_render import rendered
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse import ai_models, config
from newspulse.analyzer import BackendError
from newspulse.models import Base, Setting
from newspulse.web.app import create_app, get_db


@pytest.fixture
def factory(monkeypatch):
    monkeypatch.setenv("NEWSPULSE_SESSION_SECRET", "test-secret")
    for name in ("NEWSPULSE_OPENAI_API_KEY", "OPENAI_API_KEY", "NEWSPULSE_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(factory):
    with factory() as s:
        yield s


def test_a_key_is_stored_encrypted_and_shown_only_by_its_last_four(session):
    ai_models.save_key(session, "openai", "sk-test-1234567890abcd")
    raw = session.get(Setting, "ai_key:openai").value
    assert "sk-test" not in raw
    assert ai_models.stored_key(session, "openai") == "sk-test-1234567890abcd"
    state = ai_models.status(session, "openai")
    assert state.connected and state.hint == "abcd" and state.how == "Schlüssel aus den Einstellungen"
    ai_models.forget_key(session, "openai")
    assert not ai_models.status(session, "openai").connected


def test_without_the_server_secret_no_key_is_stored(session, monkeypatch):
    monkeypatch.setenv("NEWSPULSE_SESSION_SECRET", "")
    monkeypatch.setattr(config, "SESSION_SECRET", "")
    with pytest.raises(ai_models.NoSecret):
        ai_models.save_key(session, "openai", "sk-x")


def test_the_reviewer_may_not_start_with_the_designers_model(session):
    with pytest.raises(ValueError, match="anderes erstes Modell"):
        ai_models.save_order(session, {"designer": ["openai"], "reviewer": ["openai", "gemini"], "lektor": []})
    ai_models.save_order(session, {"designer": ["openai", "claude"], "reviewer": ["gemini"], "lektor": ["claude"]})
    assert ai_models.order(session) == {"designer": ["openai", "claude"], "reviewer": ["gemini"], "lektor": ["claude"]}


def test_a_role_asks_its_providers_in_order_and_the_next_steps_in(session, monkeypatch):
    asked = []

    def fake(session_, provider, prompt, *, timeout, role=None):
        asked.append(provider)
        if provider == "openai":
            raise BackendError("OpenAI HTTP 429: rate limit")
        return f"{provider}: {prompt}"

    monkeypatch.setattr(ai_models, "call", fake)
    ai_models.save_order(session, {"designer": ["openai", "claude"], "reviewer": ["gemini"], "lektor": []})
    assert ai_models.ask("designer", "hallo", timeout=5, session=session) == "claude: hallo"
    assert asked == ["openai", "claude"]


def test_a_broken_prompt_is_not_rerun_elsewhere(session, monkeypatch):
    def fake(session_, provider, prompt, *, timeout, role=None):
        raise BackendError("OpenAI HTTP 400: bad request")

    monkeypatch.setattr(ai_models, "call", fake)
    ai_models.save_order(session, {"designer": ["openai", "claude"], "reviewer": [], "lektor": []})
    with pytest.raises(BackendError, match="400"):
        ai_models.ask("designer", "x", timeout=5, session=session)


def test_the_bare_gemini_key_only_counts_for_the_reviewer(monkeypatch):
    """Writing with Gemini sends coverage to Google; that needs the named key."""
    monkeypatch.delenv("NEWSPULSE_GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "bare")
    assert ai_models.env_key("gemini", "designer") == ""
    assert ai_models.env_key("gemini", "reviewer") == "bare"


def test_openai_is_called_with_the_stored_key(session, monkeypatch):
    seen = {}

    def post(url, body, headers, timeout, name):
        seen.update(url=url, auth=headers["Authorization"], model=body["model"])
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(ai_models, "_post", post)
    monkeypatch.setattr("newspulse.shared_guides.enrich_prompt", lambda prompt, channel: prompt)
    ai_models.save_key(session, "openai", "sk-abc", "gpt-test")
    assert ai_models.call(session, "openai", "hi", timeout=5) == "ok"
    assert seen == {"url": "https://api.openai.com/v1/chat/completions", "auth": "Bearer sk-abc", "model": "gpt-test"}


# --- The Lektor ---------------------------------------------------------------------


def test_the_lektor_polishes_language_but_never_a_quote(monkeypatch):
    from newspulse import assets
    from newspulse.schemas import AssetDraft

    fmt = type("F", (), {"key": "statement"})()
    draft = AssetDraft(title="Titel", body='Der Satz ist holprig. „Wir wachsen“, sagt sie.')
    monkeypatch.setattr(ai_models, "has_role", lambda role: role == "lektor")
    monkeypatch.setattr(assets, "validate", lambda fmt, d, given: [])

    monkeypatch.setattr(ai_models, "ask", lambda role, prompt, timeout: json.dumps(
        {"title": "Titel", "body": 'Der Satz ist flüssig. „Wir wachsen“, sagt sie.'}))
    assert assets._proofread(fmt, draft, None).body.startswith("Der Satz ist flüssig.")

    monkeypatch.setattr(ai_models, "ask", lambda role, prompt, timeout: json.dumps(
        {"title": "Titel", "body": 'Der Satz ist flüssig. „Wir wachsen stark“, sagt sie.'}))
    assert assets._proofread(fmt, draft, None) is draft


def test_without_a_lektor_the_draft_is_untouched(monkeypatch):
    from newspulse import assets
    from newspulse.schemas import AssetDraft

    draft = AssetDraft(title="T", body="Text.")
    monkeypatch.setattr(ai_models, "ask", lambda *a, **k: pytest.fail("no Lektor is set up"))
    assert assets._proofread(type("F", (), {"key": "x"})(), draft, None) is draft


# --- The settings panel ----------------------------------------------------------------


@pytest.fixture
def web(factory):
    app = create_app()

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def test_the_settings_connect_a_provider_and_order_the_roles(web, factory):
    body = rendered(web.get("/settings"))
    assert 'id="ki-modelle"' in body and "Designer" in body and "Lektor" in body
    assert "KI-Ausweichmodell" not in body

    assert web.post("/settings/ai/key", data={"provider": "openai", "api_key": "sk-zzzz9876"},
                    follow_redirects=False).status_code == 303
    body = rendered(web.get("/settings"))
    assert "…9876" in body and "sk-zzzz9876" not in body

    refused = rendered(web.post("/settings/ai/order", data={"designer_1": "openai", "reviewer_1": "openai"}))
    assert "anderes erstes Modell" in refused
    web.post("/settings/ai/order", data={"designer_1": "openai", "designer_2": "claude", "reviewer_1": "gemini",
                                         "lektor_1": "claude"}, follow_redirects=False)
    with factory() as s:
        assert ai_models.order(s)["designer"] == ["openai", "claude"]
        assert ai_models.order(s)["lektor"] == ["claude"]
