"""Google web search per mandate and sweep slot, through Gemini's grounding."""
import datetime as dt
import json
import sqlite3
from types import SimpleNamespace

from newspulse import google_web_search as google

MORNING = dt.datetime(2026, 11, 11, 7, 5, tzinfo=dt.UTC)   # 08:05 in Berlin
AFTERNOON = dt.datetime(2026, 11, 11, 15, 5, tzinfo=dt.UTC)  # 16:05 in Berlin
REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc"
PAGE = "https://www.fachblatt.example.de/acme-neues-werk"


def client(id=1, **extra):
    return SimpleNamespace(id=id, name="Acme GmbH", aliases=["Acme"], industry="Maschinenbau",
                           keywords=["Industrie 4.0"], alert_topics=[], active=True,
                           is_competitor=False, **extra)


def answer(now, url=REDIRECT):
    return json.dumps({"articles": [{"url": url, "title": "Acme baut neues Werk",
                                     "published_at": (now - dt.timedelta(hours=1)).isoformat(),
                                     "summary": "Acme investiert."}]})


def resolve(url):
    return PAGE if url == REDIRECT else url


def test_the_slot_is_the_last_sweep_time_in_berlin():
    assert google.slot(MORNING) == "2026-11-11 08:00"
    assert google.slot(AFTERNOON) == "2026-11-11 16:00"
    assert google.slot(dt.datetime(2026, 11, 11, 5, 0, tzinfo=dt.UTC)) == "2026-11-11 00:00"


def test_each_mandate_is_searched_by_name_and_keywords_once_per_slot(tmp_path):
    prompts = []

    def search(prompt):
        prompts.append(prompt)
        now = AFTERNOON if len(prompts) > 1 else MORNING
        return answer(now), [(REDIRECT, "fachblatt.example.de")]

    args = dict(search=search, resolve=resolve, ledger_path=tmp_path / "news.db")
    items, errors = google.harvest([client()], MORNING - dt.timedelta(days=1), fetched_at=MORNING, **args)
    assert not errors and [i.link for i in items] == [PAGE]
    assert items[0].title == "Acme baut neues Werk" and items[0].source == "www.fachblatt.example.de"
    assert "Acme GmbH" in prompts[0] and "Industrie 4.0" in prompts[0] and "Google-Suche" in prompts[0]

    google.harvest([client()], MORNING - dt.timedelta(days=1), fetched_at=MORNING, **args)
    assert len(prompts) == 1, "a second sweep in the same slot spends no second search"
    google.harvest([client()], MORNING, fetched_at=AFTERNOON, **args)
    assert len(prompts) == 2, "the 16:00 sweep searches again"
    with sqlite3.connect(tmp_path / "news.db") as conn:
        assert PAGE in conn.execute("SELECT sources FROM google_search LIMIT 1").fetchone()[0]


def test_a_page_google_did_not_return_is_dropped(tmp_path):
    def search(prompt):
        return answer(MORNING, url="https://erfunden.example.org/x"), [(REDIRECT, "fachblatt.example.de")]

    items, errors = google.harvest([client()], MORNING - dt.timedelta(days=1), fetched_at=MORNING,
                                   search=search, resolve=resolve, ledger_path=tmp_path / "news.db")
    assert items == [] and errors == []


def test_competitors_and_inactive_mandates_are_not_searched(tmp_path):
    a, b = client(1), client(2)
    a.active, b.is_competitor = False, True

    def unexpected(prompt):
        raise AssertionError("should not search")

    assert google.harvest([a, b], MORNING, fetched_at=MORNING, search=unexpected, resolve=resolve,
                          ledger_path=tmp_path / "news.db") == ([], [])


def test_a_spent_quota_stops_the_search_for_everyone(tmp_path):
    from newspulse.analyzer import BackendError

    calls = []

    def search(prompt):
        calls.append(prompt)
        raise BackendError("Gemini HTTP 429: RESOURCE_EXHAUSTED")

    items, errors = google.harvest([client(1), client(2)], MORNING, fetched_at=MORNING, search=search,
                                   resolve=resolve, ledger_path=tmp_path / "news.db")
    assert items == [] and len(calls) == 1 and any("quota" in e for e in errors)


def test_on_with_a_gemini_key_unless_switched_off(monkeypatch):
    from newspulse import config

    monkeypatch.setattr(config, "review_api_key", lambda: "key")
    monkeypatch.delenv("NEWSPULSE_GOOGLE_WEB_SEARCH")
    assert google.enabled()
    monkeypatch.setenv("NEWSPULSE_GOOGLE_WEB_SEARCH", "0")
    assert not google.enabled()
    monkeypatch.delenv("NEWSPULSE_GOOGLE_WEB_SEARCH")
    monkeypatch.setattr(config, "review_api_key", lambda: "")
    assert not google.enabled()


def test_the_sweep_takes_google_hits_into_matching(monkeypatch):
    from newspulse import job

    called = {}
    monkeypatch.setattr(google, "enabled", lambda: True)

    def harvest(clients, since, *, fetched_at):
        called["clients"] = [c.name for c in clients]
        return [], ["Google web search for client 1: BackendError"]

    monkeypatch.setattr(google, "harvest", harvest)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from newspulse.models import Base, Client

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add(Client(name="Alpha AG", aliases=[], keywords=[], alert_topics=[]))
        session.commit()
        report = job.run(session, feeds=[], fetch=lambda feed: [], analyzer=None,
                         now=lambda: MORNING)
    assert called["clients"] == ["Alpha AG"]
    assert report.status.value != "ok"
