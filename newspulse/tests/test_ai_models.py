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


def test_a_key_is_stored_encrypted_and_shown_only_by_its_last_four(session, monkeypatch):
    monkeypatch.setattr(ai_models, "_claude_cli", lambda: False)
    ai_models.save_key(session, "claude", "sk-ant-test-1234567890abcd")
    raw = session.get(Setting, "ai_key:claude").value
    assert "sk-ant" not in raw
    assert ai_models.stored_key(session, "claude") == "sk-ant-test-1234567890abcd"
    state = ai_models.status(session, "claude")
    assert state.connected and state.hint == "abcd" and state.how == "Schlüssel aus den Einstellungen"
    ai_models.forget_key(session, "claude")
    assert not ai_models.status(session, "claude").connected


def test_without_the_server_secret_no_key_is_stored(session, monkeypatch):
    monkeypatch.setenv("NEWSPULSE_SESSION_SECRET", "")
    monkeypatch.setattr(config, "SESSION_SECRET", "")
    with pytest.raises(ai_models.NoSecret):
        ai_models.save_key(session, "claude", "sk-x")


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


# --- OpenAI over the ChatGPT subscription ------------------------------------------


def _codex_home(tmp_path, monkeypatch, auth):
    from newspulse import codex_cli

    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setattr(codex_cli, "installed", lambda: True)
    if auth is not None:
        (tmp_path / "auth.json").write_text(json.dumps(auth))
    return codex_cli


def test_openai_takes_no_api_key(session, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    with pytest.raises(ValueError, match="Abo"):
        ai_models.save_key(session, "openai", "sk-abc")
    assert ai_models.env_key("openai") == ""
    session.add(Setting(key="ai_key:openai", value="left over"))
    assert ai_models.stored_key(session, "openai") == ""


def test_openai_counts_as_connected_only_with_a_chatgpt_login(session, tmp_path, monkeypatch):
    _codex_home(tmp_path, monkeypatch, None)
    assert not ai_models.status(session, "openai").connected
    _codex_home(tmp_path, monkeypatch, {"OPENAI_API_KEY": "sk-key-login", "tokens": None})
    assert not ai_models.status(session, "openai").connected
    _codex_home(tmp_path, monkeypatch, {"OPENAI_API_KEY": None, "tokens": {"access_token": "x"}})
    state = ai_models.status(session, "openai")
    assert state.connected and state.how == "ChatGPT-Abo (Codex CLI)"


def test_openai_runs_codex_read_only_without_any_api_key(session, tmp_path, monkeypatch):
    import subprocess

    codex_cli = _codex_home(tmp_path, monkeypatch, {"tokens": {"access_token": "x"}})
    monkeypatch.setenv("OPENAI_API_KEY", "sk-must-not-leak")
    monkeypatch.setattr("newspulse.shared_guides.enrich_prompt", lambda prompt, channel: prompt)
    seen = {}

    def fake_run(argv, *, input, env, **kwargs):
        seen.update(argv=argv, prompt=input, env=env)
        instructions = next(a for a in argv if a.startswith("model_instructions_file="))
        seen["instructions"] = open(json.loads(instructions.split("=", 1)[1]), encoding="utf-8").read()
        out = argv[argv.index("--output-last-message") + 1]
        with open(out, "w", encoding="utf-8") as handle:
            handle.write("ok\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(codex_cli.subprocess, "run", fake_run)
    assert ai_models.call(session, "openai", "hallo", timeout=5) == "ok"
    argv = seen["argv"]
    assert argv[:2] == ["codex", "exec"] and argv[-1] == "-" and seen["prompt"] == "hallo"
    assert argv[argv.index("--sandbox") + 1] == "read-only" and "--ephemeral" in argv
    assert 'forced_login_method="chatgpt"' in argv
    # A text job, not an agent: own short instructions, no tools, no skills list.
    assert "RauteOS" in seen["instructions"]
    for option in ("--ignore-user-config", 'web_search="disabled"', "features.shell_tool=false",
                   "skills.include_instructions=false"):
        assert option in argv
    assert "OPENAI_API_KEY" not in seen["env"] and seen["env"]["CODEX_HOME"] == str(tmp_path)


def test_an_expired_codex_login_hands_over_to_the_next_model(session, monkeypatch):
    def fake(session_, provider, prompt, *, timeout, role=None):
        if provider == "openai":
            raise BackendError("codex exec failed (1): ERROR: unexpected status 401 Unauthorized")
        return "claude"

    monkeypatch.setattr(ai_models, "call", fake)
    ai_models.save_order(session, {"designer": ["openai", "claude"], "reviewer": ["gemini"], "lektor": []})
    assert ai_models.ask("designer", "x", timeout=5, session=session) == "claude"


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


def test_the_settings_connect_a_provider_and_order_the_roles(web, factory, monkeypatch):
    from newspulse import codex_cli

    monkeypatch.setattr(codex_cli, "logged_in", lambda: False)
    body = rendered(web.get("/settings"))
    assert 'id="ki-modelle"' in body and "Designer" in body and "Lektor" in body
    assert "KI-Ausweichmodell" not in body

    assert "codex login --device-auth" in body
    assert web.post("/settings/ai/key", data={"provider": "claude", "api_key": "sk-zzzz9876"},
                    follow_redirects=False).status_code == 303
    body = rendered(web.get("/settings"))
    assert "…9876" in body and "sk-zzzz9876" not in body
    assert "über das Abo angemeldet" in rendered(
        web.post("/settings/ai/key", data={"provider": "openai", "api_key": "sk-x"}))

    refused = rendered(web.post("/settings/ai/order", data={"designer_1": "openai", "reviewer_1": "openai"}))
    assert "anderes erstes Modell" in refused
    web.post("/settings/ai/order", data={"designer_1": "openai", "designer_2": "claude", "reviewer_1": "gemini",
                                         "lektor_1": "claude"}, follow_redirects=False)
    with factory() as s:
        assert ai_models.order(s)["designer"] == ["openai", "claude"]
        assert ai_models.order(s)["lektor"] == ["claude"]


def test_role_models_are_persisted_and_used_independently(session, monkeypatch):
    from newspulse import codex_cli
    ai_models.save_order(session, {'designer': ['openai'], 'reviewer': ['gemini'], 'lektor': []},
                         models={'designer': {'openai': 'test-model'}, 'reviewer': {'gemini': 'review-model'}})
    assert ai_models.model_for(session, 'openai', 'designer') == 'test-model'
    assert ai_models.model_for(session, 'openai') == ''
    monkeypatch.setattr(codex_cli, 'logged_in', lambda: True)
    calls = []
    monkeypatch.setattr(codex_cli, 'run', lambda prompt, **kw: calls.append(kw) or 'ok')
    assert ai_models.ask('designer', 'test', timeout=1, session=session) == 'ok'
    assert calls[0]['model'] == 'test-model'


def test_claude_subscription_receives_the_selected_model(session, monkeypatch):
    from newspulse import analyzer
    monkeypatch.setattr(ai_models, 'api_key', lambda *a: '')
    ai_models.save_key(session, 'claude', '', 'opus')
    calls = []
    monkeypatch.setattr(analyzer, 'invoke_claude_cli', lambda prompt, **kw: calls.append(kw) or 'ok')
    ai_models.call(session, 'claude', 'test', timeout=1)
    assert calls[0]['model'] == 'opus'


def test_invalid_model_and_duplicate_provider_leave_settings_unchanged(session):
    before = ai_models.order(session)
    with pytest.raises(ValueError):
        ai_models.save_order(session, before, models={'designer': {'claude': '--bad flag'}})
    assert ai_models.order(session) == before
    with pytest.raises(ValueError):
        ai_models.save_order(session, {'designer': ['claude', 'claude']})


def test_inline_connection_check_reports_success_and_sanitized_errors(web, monkeypatch):
    monkeypatch.setattr(ai_models, 'test', lambda *a: 'ok')
    result = web.post('/settings/ai/test?inline=1', data={'provider': 'claude'})
    assert result.status_code == 200 and result.json()['ok']
    def fail(*a): raise BackendError('HTTP 401 private-secret')
    monkeypatch.setattr(ai_models, 'test', fail)
    result = web.post('/settings/ai/test?inline=1', data={'provider': 'claude'})
    assert result.status_code == 422 and not result.json()['ok']
    assert 'private-secret' not in result.text
    assert 'Anmeldung' in result.json()['message']


def test_role_model_form_reaches_storage(web, factory):
    result = web.post('/settings/ai/order', data={'designer_1': 'openai', 'designer_model_1': 'selected-model',
                                                  'reviewer_1': 'gemini'}, follow_redirects=False)
    assert result.status_code == 303
    with factory() as session:
        assert ai_models.model_for(session, 'openai', 'designer') == 'selected-model'


def test_expired_claude_login_uses_configured_fallback(session, monkeypatch):
    calls = []
    def fake(session, provider, prompt, **kwargs):
        calls.append(provider)
        if provider == 'claude':
            raise BackendError('Failed to authenticate: this login reached its time limit and cannot be renewed')
        return 'ok'
    monkeypatch.setattr(ai_models, 'call', fake)
    assert ai_models.ask('designer', 'test', timeout=1, session=session) == 'ok'
    assert calls == ['claude', 'gemini']
