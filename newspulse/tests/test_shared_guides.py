import hashlib
import json
import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newspulse import assistant_search, config, shared_guides
from newspulse.models import Base, Client


@pytest.fixture
def package(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", tmp_path / "app.db")
    root = tmp_path / "originals"
    (root / "sources").mkdir(parents=True)
    text = "Allgemeine Einleitung. " * 1000 + "Exklusivitätsfenster mit der Redaktion vereinbaren."
    path = root / "sources" / "manual.md"
    path.write_text(text)
    (root / "import-manifest.json").write_text(json.dumps([dict(
        id="drive-source", path="sources/manual.md", url="https://drive.google.com/file/d/example/view",
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())]))
    return root


def test_full_text_import_is_idempotent_and_preserves_provenance(package):
    first = shared_guides.import_sources(package)
    assert first == shared_guides.import_sources(package)
    with sqlite3.connect(shared_guides.index_path()) as db:
        assert db.execute("SELECT count(*) FROM sources").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM chunks").fetchone()[0] == first["chunks"]
    hits = shared_guides.search(["Exklusivitätsfenster"])
    assert hits and "Exklusivitätsfenster" in hits[0]["fields"]["text"]
    assert hits[0]["metadata"]["source_url"].startswith("https://drive.google.com/")
    assert hits[0]["client_id"] is None
    assert hits[0]["metadata"]["passage"] > 1


def test_corrupt_original_does_not_replace_working_index(package):
    shared_guides.import_sources(package)
    (package / "sources/manual.md").write_text("changed")
    with pytest.raises(ValueError, match="Checksum"):
        shared_guides.import_sources(package)
    assert shared_guides.search(["Exklusivitätsfenster"])


def test_shared_search_is_available_for_every_client_and_no_client(package):
    shared_guides.import_sources(package)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Client(name="Alpha"), Client(name="Beta")])
        session.commit()
        for client_id in [None, 1, 2]:
            result = assistant_search.build(session, "Exklusivitätsfenster", client_id=client_id)
            assert any(r["type"] == "shared_guide_sources" for r in result["results"])
            assert len(json.dumps(result, ensure_ascii=False, default=str)) < assistant_search.MAX_CHARS


def test_missing_index_and_fts_punctuation_are_safe(package):
    assert shared_guides.search(["anything"]) == []
    shared_guides.import_sources(package)
    assert shared_guides.search(['" OR *', '---']) == []


def test_provider_prompt_has_bounded_quoted_sources_and_audit(package, caplog):
    shared_guides.import_sources(package)
    task = "Prüfe das Exklusivitätsfenster. Gib ausschließlich JSON zurück."
    with caplog.at_level("INFO"):
        enriched = shared_guides.enrich_prompt(task, channel="test_job")
    assert enriched.startswith(task)
    assert "<<<ZITAT GEMEINSAME PR-WISSENSQUELLEN" in enriched
    assert "drive-source" in enriched
    assert len(enriched) - len(task) < 11500
    assert "status=attached" in caplog.text
    assert "Prüfe das" not in caplog.text


def test_scheduled_analysis_reaches_cli_with_shared_knowledge(package, monkeypatch):
    from types import SimpleNamespace
    from newspulse import analyzer
    from test_analyzer import make_client, make_article, _cli_stdout, _verdict

    shared_guides.import_sources(package)
    article = make_article(0)
    article.title = "Exklusivitätsfenster"
    captured = []
    def run(*args, **kwargs):
        captured.append(kwargs["input"])
        return SimpleNamespace(returncode=0, stdout=_cli_stdout([_verdict(0)]), stderr="")
    monkeypatch.setattr(analyzer.subprocess, "run", run)
    assert analyzer.ClaudeCodeAnalyzer().analyze(make_client(), [article])
    assert "drive-source" in captured[0]


@pytest.mark.parametrize("method", ["generate", "stream", "search"])
def test_gemini_transports_attach_shared_knowledge(package, monkeypatch, method):
    import io
    from newspulse import gemini

    shared_guides.import_sources(package)
    monkeypatch.setattr(config, "gemini_api_key", lambda: "test")
    monkeypatch.setattr(config, "review_api_key", lambda: "test")
    captured = []
    def open_request(request, **kwargs):
        captured.append(json.loads(request.data))
        payload = json.dumps({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})
        return io.BytesIO(("data: " + payload + "\n\n" if method == "stream" else payload).encode())
    monkeypatch.setattr(gemini.urllib.request, "urlopen", open_request)
    result = getattr(gemini, method)("Exklusivitätsfenster")
    if method == "stream":
        list(result)
    assert "drive-source" in captured[0]["contents"][0]["parts"][0]["text"]


def test_visibility_probes_explicitly_bypass_internal_knowledge(monkeypatch):
    from newspulse import visibility
    calls = []
    def ask(prompt, **kwargs):
        calls.append(kwargs)
        return "ok"
    monkeypatch.setattr(visibility, "invoke_claude_cli", ask)
    monkeypatch.setattr(visibility.gemini, "generate", ask)
    visibility._ask_claude("unbiased question")
    visibility._ask_gemini("unbiased question")
    assert len(calls) == 2
    assert all(call["use_shared_knowledge"] is False for call in calls)


def test_claude_search_and_api_attach_references(package, monkeypatch):
    import sys
    from types import SimpleNamespace
    from newspulse import analyzer

    shared_guides.import_sources(package)
    captured = []
    def run(*args, **kwargs):
        captured.append(kwargs["input"])
        return SimpleNamespace(returncode=0, stdout=json.dumps({"type": "result", "result": "ok", "is_error": False}), stderr="")
    monkeypatch.setattr(analyzer.subprocess, "run", run)
    analyzer.invoke_claude_search("Exklusivitätsfenster")
    def create(**kwargs):
        captured.append(kwargs["messages"][0]["content"])
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="ok")])
    fake = SimpleNamespace(Anthropic=lambda: SimpleNamespace(messages=SimpleNamespace(create=create)), AnthropicError=RuntimeError)
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    analyzer.ClaudeApiAnalyzer()._invoke("Exklusivitätsfenster")
    assert len(captured) == 2
    assert all("drive-source" in prompt for prompt in captured)


def test_claude_stream_attaches_references(package, monkeypatch):
    import io
    from newspulse import streaming

    shared_guides.import_sources(package)
    captured = []
    class Process:
        stdout = io.StringIO(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "ok"}]}}) + "\n" + json.dumps({"type": "result", "is_error": False}) + "\n")
        stderr = io.StringIO("")
        def wait(self, timeout): return 0
        def poll(self): return 0
    def popen(argv, **kwargs):
        captured.append(argv[2])
        return Process()
    monkeypatch.setattr(streaming.subprocess, "Popen", popen)
    assert list(streaming.stream_claude("Exklusivitätsfenster"))[-1].kind == "done"
    assert "drive-source" in captured[0]
