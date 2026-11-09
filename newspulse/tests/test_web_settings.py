"""Route tests for the Settings view (NP-09).

These drive the settings routes through FastAPI's TestClient against a seeded
in-memory SQLite database — interface-level, not the whole app stack. The
``get_db`` dependency is overridden to hand each request a session bound to the
fixture engine (StaticPool keeps them all on one connection), so no real database
file, daily job, or ``claude`` subprocess is ever involved.

Covered: adding, editing, archiving and purging mandates, feeds and runs.
"""

from __future__ import annotations

from react_render import rendered

import datetime as dt
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse import config
from newspulse.feeds import load_feeds
from newspulse.models import (
    Analysis,
    Article,
    Base,
    Category,
    Client,
    Run,
    RunStatus,
    Setting,
)
from newspulse.web.app import create_app, get_db
from newspulse.web.routes.settings import get_active_feed_names, set_active_feed_names

_ALERT_THRESHOLD_KEY = "alert_threshold"


@pytest.fixture
def factory():
    """A sessionmaker bound to a fresh in-memory database with the schema built.

    StaticPool keeps every session on the same single connection so a POST's write
    is visible to the follow-up GET's session — a plain ``:memory:`` engine would
    give each connection its own empty database.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def client(factory):
    """A TestClient whose route session is bound to the fixture database."""
    app = create_app()

    def _override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def _utc(day: int = 20, hour: int = 6) -> dt.datetime:
    return dt.datetime(2026, 7, day, hour, 0, tzinfo=dt.UTC)


def _seed_analysis(session, *, importance: int, is_alert: bool) -> int:
    """Seed one client + article + analysis, returning the analysis id."""
    client_obj = Client(name="Alpha AG")
    session.add(client_obj)
    session.flush()
    article = Article(
        title="Alpha meldet etwas",
        url="https://ex.de/alpha",
        source="FAZ",
        published_at=_utc(),
        fetched_at=_utc(),
        summary_text="Snippet.",
        language="de",
        title_hash="hash-alpha",
    )
    session.add(article)
    session.flush()
    analysis = Analysis(
        article_id=article.id,
        client_id=client_obj.id,
        category=Category.PRODUKT,
        is_relevant=importance >= 1, relevance_score=importance,
        importance_score=importance,
        is_alert=is_alert,
    )
    session.add(analysis)
    session.commit()
    return analysis.id


# --- The page renders ----------------------------------------------------------


def test_settings_page_renders_with_empty_database(client):
    """A fresh install renders the settings page (no clients, feeds from config)."""
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert "Einstellungen" in rendered(resp)
    # The registered feeds are listed even before anything is configured.
    assert "Spiegel" in rendered(resp)


# --- Client CRUD ---------------------------------------------------------------


def test_adding_a_client_creates_it_through_the_service(factory, client):
    """Posting the add form creates a client and it appears in the reloaded list."""
    resp = client.post(
        "/settings/clients",
        data={
            "name": "Neu AG",
            "industry": "Automotive",
            "aliases": "Neu, Neu Gruppe",
            "alert_topics": "Rückruf; Insolvenz",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Neu AG" in rendered(resp)

    with factory() as session:
        created = session.query(Client).filter(Client.name == "Neu AG").one()
        assert created.active is True
        assert created.aliases == ["Neu", "Neu Gruppe"]
        assert created.alert_topics == ["Rückruf", "Insolvenz"]


def test_adding_a_client_without_name_shows_inline_error(factory, client):
    """A blank name is rejected inline and nothing is written."""
    resp = client.post("/settings/clients", data={"name": "  "})
    assert resp.status_code == 200
    assert "Name ist erforderlich" in rendered(resp)
    with factory() as session:
        assert session.query(Client).count() == 0


def test_duplicate_active_client_name_shows_inline_error(factory, client):
    """A duplicate active name (NP-02 guard) surfaces as an inline error."""
    client.post("/settings/clients", data={"name": "Doppel AG"}, follow_redirects=True)
    resp = client.post("/settings/clients", data={"name": "doppel ag"})
    assert resp.status_code == 200
    assert "already exists" in rendered(resp)
    with factory() as session:
        assert session.query(Client).count() == 1


def test_editing_a_client_updates_fields(factory, client):
    """The per-client edit form updates fields through the CRUD service."""
    with factory() as session:
        obj = Client(name="Alt AG", industry="Alt")
        session.add(obj)
        session.commit()
        client_id = obj.id

    client.post(
        f"/settings/clients/{client_id}",
        data={"name": "Alt AG", "industry": "Neu", "keywords": "x, y"},
        follow_redirects=True,
    )

    with factory() as session:
        reloaded = session.get(Client, client_id)
        assert reloaded.industry == "Neu"
        assert reloaded.keywords == ["x", "y"]


def test_deactivating_a_client_is_soft(factory, client):
    """Deactivate flips active=False; the client row still exists (soft delete)."""
    with factory() as session:
        obj = Client(name="Ruhend AG")
        session.add(obj)
        session.commit()
        client_id = obj.id

    client.post(f"/settings/clients/{client_id}/deactivate", follow_redirects=True)

    with factory() as session:
        assert session.get(Client, client_id).active is False


def test_reactivating_a_client_flips_active_back(factory, client):
    """A deactivated client can be reactivated through the edit service."""
    with factory() as session:
        obj = Client(name="Wieder AG", active=False)
        session.add(obj)
        session.commit()
        client_id = obj.id

    client.post(f"/settings/clients/{client_id}/reactivate", follow_redirects=True)

    with factory() as session:
        assert session.get(Client, client_id).active is True


def test_reactivate_into_duplicate_name_shows_inline_error(factory, client):
    """Reactivating into a name a live client already holds is refused inline, so an
    operator cannot create two active same-name clients that would break import
    dedup (the QA-reported bypass through the reactivate route)."""
    client.post("/settings/clients", data={"name": "Alpha AG"}, follow_redirects=True)
    with factory() as session:
        first_id = session.query(Client).filter_by(name="Alpha AG").one().id
    client.post(f"/settings/clients/{first_id}/deactivate", follow_redirects=True)
    client.post("/settings/clients", data={"name": "Alpha AG"}, follow_redirects=True)

    resp = client.post(f"/settings/clients/{first_id}/reactivate")
    assert resp.status_code == 200
    assert "already exists" in rendered(resp)
    with factory() as session:
        assert session.query(Client).filter_by(name="Alpha AG", active=True).count() == 1


# --- Feeds ---------------------------------------------------------------------


def test_saving_active_feeds_persists_the_checked_subset(factory, client):
    """Saving the feed form persists exactly the checked feed names to settings."""
    client.post(
        "/settings/feeds", data={"feed": ["Spiegel", "Zeit"]}, follow_redirects=True
    )
    feeds = load_feeds()
    with factory() as session:
        assert get_active_feed_names(session, feeds) == {"Spiegel", "Zeit"}


def test_feed_added_after_save_defaults_active(factory):
    """A feed added to the registry after a save is active by default (deny-list).

    The operator saved with only "A" checked out of {A, B}; a later-registered feed
    "C" was never deselected, so it must come back active — not silently dropped.
    """
    registry_v1 = [SimpleNamespace(name="A"), SimpleNamespace(name="B")]
    with factory() as session:
        set_active_feed_names(session, ["A"], [f.name for f in registry_v1])

    registry_v2 = registry_v1 + [SimpleNamespace(name="C")]
    with factory() as session:
        active = get_active_feed_names(session, registry_v2)
    assert active == {"A", "C"}  # B stays off (deselected); C defaults on


# --- Run history ---------------------------------------------------------------


def test_run_history_shows_status_articles_and_errors(factory, client):
    """The run-history table surfaces status, articles_found, and any errors."""
    with factory() as session:
        session.add(
            Run(
                started_at=_utc(hour=6),
                finished_at=_utc(hour=6),
                status=RunStatus.PARTIAL,
                articles_found=87,
                errors=["Feed Spiegel timed out"],
            )
        )
        session.commit()

    body = rendered(client.get("/settings"))
    assert "partial" in body
    assert "87" in body
    assert "Feed Spiegel timed out" in body


# --- Run trigger + backfill ----------------------------------------------------


def test_run_trigger_rejects_a_window_not_offered(client):
    """Only the offered backfill windows are accepted; anything else is refused
    without starting a sweep."""
    resp = client.post("/settings/run", data={"since_days": "999"})
    assert resp.status_code == 200  # re-rendered with an inline error, no redirect
    assert "Ungültiger Zeitraum" in rendered(resp)


def test_run_trigger_rejects_non_numeric_window(client):
    resp = client.post("/settings/run", data={"since_days": "dreissig"})
    assert resp.status_code == 200
    assert "Ungültiger Zeitraum" in rendered(resp)


def test_backfill_offers_an_onboarding_window(client):
    """A newly added mandate needs its history, not just "since the last run".

    30 days was the widest window on offer, and a client added after its launch
    coverage had aged past that showed an empty archive with nothing to reach for.
    """
    from newspulse.web.routes.settings import BACKFILL_DAYS

    assert 90 in BACKFILL_DAYS
    body = rendered(client.get("/settings"))
    assert 'value="90"' in body


def test_run_trigger_refuses_a_second_concurrent_run(client, monkeypatch):
    """A sweep already in flight is reported, never queued: two concurrent runs
    would double-fetch every feed and race on the same articles."""
    from newspulse.web.routes import settings as settings_routes

    # Hold the guard as an in-flight run would, without starting a real sweep.
    assert settings_routes._run_guard.acquire(blocking=False)
    try:
        resp = client.post("/settings/run", data={"since_days": ""})
        assert resp.status_code == 200
        assert "Es läuft bereits ein Lauf" in rendered(resp)
    finally:
        settings_routes._run_guard.release()


def test_run_trigger_starts_a_sweep_with_the_requested_window(client, monkeypatch):
    """A valid request starts the sweep off-thread and redirects; the chosen
    window reaches job.run as an explicit `since`."""
    import datetime as dt

    from newspulse.web.routes import settings as settings_routes

    captured: dict[str, object] = {}

    def _fake_execute(since_days):
        captured["since_days"] = since_days
        settings_routes._run_guard.release()

    class _ImmediateThread:
        def __init__(self, target, args, daemon=None, name=None):
            self._target, self._args = target, args

        def start(self):
            self._target(*self._args)

    monkeypatch.setattr(settings_routes, "_execute_run", _fake_execute)
    monkeypatch.setattr(settings_routes.threading, "Thread", _ImmediateThread)

    resp = client.post(
        "/settings/run", data={"since_days": "30"}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/settings?started=30"
    assert captured["since_days"] == 30
    # The guard is free again for the next run.
    assert settings_routes._run_guard.acquire(blocking=False)
    settings_routes._run_guard.release()


def test_lookback_since_matches_the_requested_window():
    """The CLI's --since-days and the dashboard's control share one definition."""
    import datetime as dt

    from newspulse import job

    fixed = dt.datetime(2026, 7, 27, 12, 0, tzinfo=dt.UTC)
    assert job.lookback_since(30, now=lambda: fixed) == fixed - dt.timedelta(days=30)
    assert job.lookback_since(1, now=lambda: fixed) == fixed - dt.timedelta(days=1)
    with pytest.raises(ValueError):
        job.lookback_since(0)


def test_the_run_button_returns_to_where_it_was_clicked(client, monkeypatch):
    """The refresh lives in the header on every page; bouncing the reader to
    Settings would lose their place."""
    from newspulse.web.routes import settings as settings_routes

    class _Immediate:
        def __init__(self, target, args, daemon=None, name=None):
            self._t, self._a = target, args

        def start(self):
            settings_routes._run_guard.release()

    monkeypatch.setattr(settings_routes.threading, "Thread", _Immediate)
    resp = client.post(
        "/settings/run",
        data={"since_days": "", "redirect_to": "/archive?month=2026-07"},
        follow_redirects=False,
    )
    assert resp.headers["location"] == "/archive?month=2026-07"


def test_an_offsite_run_redirect_is_refused(client, monkeypatch):
    from newspulse.web.routes import settings as settings_routes

    class _Immediate:
        def __init__(self, target, args, daemon=None, name=None):
            pass

        def start(self):
            settings_routes._run_guard.release()

    monkeypatch.setattr(settings_routes.threading, "Thread", _Immediate)
    resp = client.post(
        "/settings/run",
        data={"since_days": "", "redirect_to": "https://evil.example/"},
        follow_redirects=False,
    )
    assert resp.headers["location"].startswith("/settings")


# --- Mandates and yardsticks are different kinds of thing ------------------------


# --- Mandates only; the archive can be emptied ----------------------------------


def test_settings_list_mandates_compactly_and_keep_competitors_out(factory, client):
    """Competitors are managed per mandate under Strategie, not in the settings."""
    with factory() as session:
        mandate = Client(name="Zalando", aliases=[], industry="Modehandel", keywords=[], alert_topics=[])
        rival = Client(name="H&M", aliases=[], keywords=[], alert_topics=[], is_competitor=True)
        session.add_all([mandate, rival])
        session.flush()
        mandate.competitors.append(rival)
        session.commit()
        mandate_id = mandate.id

    body = rendered(client.get("/settings"))
    assert "Mandanten gesamt" in body and "Zalando" in body
    assert "H&amp;M" not in body and "H&M" not in body
    assert "Maßstab für" not in body
    assert f'aria-label="Bearbeiten: Zalando"' in body
    assert "Deaktivieren" not in body  # only behind the edit icon
    opened = rendered(client.get(f"/settings?edit={mandate_id}"))
    assert f'action="/settings/clients/{mandate_id}/deactivate"' in opened
    assert f'href="/client/{mandate_id}/wettbewerb"' in opened


def test_all_archived_mandates_can_be_deleted_at_once(factory, client):
    with factory() as session:
        live = Client(name="Live", aliases=[], keywords=[], alert_topics=[])
        gone = Client(name="Gone", aliases=[], keywords=[], alert_topics=[], active=False)
        rival = Client(name="Rival", aliases=[], keywords=[], alert_topics=[], active=False, is_competitor=True)
        session.add_all([live, gone, rival])
        session.commit()

    page = rendered(client.get("/settings"))
    assert 'action="/settings/archive/purge"' in page and "Alle löschen" in page
    resp = client.post("/settings/archive/purge", follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/settings"
    with factory() as session:
        names = {c.name for c in session.scalars(select(Client))}
    assert names == {"Live", "Rival"}
