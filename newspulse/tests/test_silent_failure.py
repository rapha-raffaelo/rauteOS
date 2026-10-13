"""A broken tool must not look like a quiet news day.

These come from an independent review of the running product. Each is a case
where the interface stayed calm while something underneath had stopped working —
the failure mode the job's own module docstring says it exists to survive:
"silently stopping in week three".
"""

from __future__ import annotations

import datetime as dt
import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from newspulse import job
from newspulse.analyzer import BackendError, _BaseClaudeAnalyzer
from newspulse.db import make_engine
from newspulse.models import (
    Analysis,
    Article,
    Base,
    Category,
    Client,
    RunStatus,
    TopicHit,
)


@pytest.fixture
def session():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as sess:
        yield sess


class _DeadBackend(_BaseClaudeAnalyzer):
    """The `claude` CLI is gone: not on PATH, or its session expired.

    Not a quota error, so the Gemini fallback never engages — this is the outage
    the deployment is actually exposed to, since the CLI's login lives on a
    volume that cannot be recreated from a laptop.
    """

    def _invoke(self, prompt: str) -> str:
        raise BackendError("claude: command not found")


def _article(session, title="Eine Meldung") -> Article:
    article = Article(
        title=title,
        url=f"https://ex.de/{abs(hash(title)) % 10**6}",
        source="Handelsblatt",
        published_at=dt.datetime.now(dt.UTC),
        fetched_at=dt.datetime.now(dt.UTC),
        summary_text=None,
        language="de",
        title_hash=str(abs(hash(title)) % 10**8),
    )
    session.add(article)
    session.commit()
    return article


def test_a_dead_analysis_backend_is_reported_rather_than_swallowed(session):
    """The contract says analyze() must never raise. It was implemented as
    "never tell anyone": every batch was dropped, no error was recorded, and the
    run was written OK — so the dashboard showed a healthy header over an empty
    day, indistinguishable from a quiet one."""
    client = Client(name="Zalando", aliases=[], keywords=[], alert_topics=[])
    session.add(client)
    session.commit()
    article = _article(session)
    errors: list[str] = []

    written = job._analyze_and_persist(
        session, client, [article], _DeadBackend(), errors
    )

    assert written == 0
    assert errors, "a backend that produced nothing must say so"
    assert "command not found" in errors[0]
    # And an error in the list is what stops the run being recorded as OK, which
    # is what the header reads to decide between "Lauf ok" and a fault.
    assert job._final_status(errors) is RunStatus.PARTIAL


def test_a_working_backend_records_no_error(session):
    """The counter must attribute failures to the client that caused them, not
    carry an earlier client's outage into a healthy one."""

    class _Fine(_BaseClaudeAnalyzer):
        def _invoke(self, prompt: str) -> str:
            return json.dumps(
                [
                    {
                        "id": 0,
                        "is_relevant": True,
                        "summary": "Ein Satz.",
                        "category": "produkt",
                        "relevance_score": 6,
                        "importance_score": 4,
                        "is_alert": False,
                        "reasoning": "Direkt über das Unternehmen.",
                    }
                ]
            )

    client = Client(name="Zalando", aliases=[], keywords=[], alert_topics=[])
    session.add(client)
    session.commit()
    errors: list[str] = []

    job._analyze_and_persist(session, client, [_article(session)], _Fine(), errors)

    assert errors == []


def test_a_dismissed_article_leaves_the_outlet_ranking(session):
    """Dismissing takes a story out of "Heute, the archive, the counts, the share
    of voice, the digest, the exports and every prompt" — the outlet and
    journalist rankings on the Marktumfeld page were reading around that gate, so
    a publication kept credit for coverage the user had already rejected."""
    from newspulse.web.routes.client import _nominations

    client = Client(name="Zalando", aliases=[], keywords=[], alert_topics=[])
    session.add(client)
    session.flush()
    article = _article(session, "Eine Verwechslung")
    analysis = Analysis(is_relevant=True, 
        article_id=article.id,
        client_id=client.id,
        summary="s",
        category=Category.SONSTIGES,
        relevance_score=5,
        importance_score=4,
        is_alert=False,
    )
    session.add(analysis)
    session.commit()

    before = _nominations(session, client.id, days=90)
    assert any(o.name == "Handelsblatt" for o in before["own_outlets"])

    analysis.dismissed_at = dt.datetime.now(dt.UTC)
    session.commit()

    after = _nominations(session, client.id, days=90)
    assert not any(o.name == "Handelsblatt" for o in after["own_outlets"])


def test_an_irrelevant_match_never_counts_towards_an_outlet(session):
    """Relevance zero means the analyzer decided the story is not about this
    client. It must not shape who to pitch."""
    from newspulse.web.routes.client import _nominations

    client = Client(name="Zalando", aliases=[], keywords=[], alert_topics=[])
    session.add(client)
    session.flush()
    article = _article(session, "Ein Namensvetter")
    session.add(
        Analysis(
            article_id=article.id,
            client_id=client.id,
            summary="s",
            category=Category.SONSTIGES,
            relevance_score=0,
            importance_score=1,
            is_alert=False,
        )
    )
    session.commit()

    assert _nominations(session, client.id, days=90)["own_outlets"] == []


def test_the_market_ranking_still_counts_what_the_radar_found(session):
    """The gate belongs on coverage *of* the client only: a radar hit has no
    analysis at all, and filtering it the same way would empty the page it is
    the whole point of."""
    from newspulse.web.routes.client import _nominations

    client = Client(name="Zalando", aliases=[], keywords=["Mode"], alert_topics=[])
    session.add(client)
    session.flush()
    article = _article(session, "Modebranche diskutiert Retouren")
    session.add(
        TopicHit(
            article_id=article.id, client_id=client.id, found_at=dt.datetime.now(dt.UTC)
        )
    )
    session.commit()

    assert any(
        o.name == "Handelsblatt"
        for o in _nominations(session, client.id, days=90)["market_outlets"]
    )


# --- Die abgelaufene Anmeldung ---------------------------------------------------
#
# Am 13.10.2026 an der Produktion gemessen: vierzehn Läufe in Folge gescheitert,
# seit dem 30. September, 3154 Artikel unanalysiert, 685 davon aus den letzten
# sieben Tagen. In der Kopfzeile stand die ganze Zeit "11 Fehler im
# Nachrichtenlauf" mit dem Hinweis "Details im Log" — und elf Fehler lesen sich
# wie elf Feed-Schluckaufe an einem schlechten Morgen.
#
# Es war ein einziger Fehler, elfmal wiederholt, und er legt jede modellgestützte
# Funktion zugleich still: Analyse, Impulse, Chancen, Profile, Sichtbarkeit.

_OAUTH = (
    "analysis 'Zalando': 25 batch(es) dropped: claude -p exited 1: "
    "Failed to authenticate: OAuth session expired and could not be refreshed"
)


@pytest.fixture
def web():
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from newspulse.web.app import create_app, get_db

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def _override():
        open_session = factory()
        try:
            yield open_session
        finally:
            open_session.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app), factory


def _run_with(factory, errors, *, found=91):
    from newspulse.models import Run

    now = dt.datetime.now(dt.UTC)
    with factory() as session:
        session.add(
            Run(
                started_at=now,
                finished_at=now,
                status=RunStatus.PARTIAL,
                articles_found=found,
                errors=list(errors),
            )
        )
        session.commit()


def test_an_expired_sign_in_is_named_rather_than_counted(web):
    """Die Zeile, um die es geht. Elf gleiche Fehler sind keine elf Fehler."""
    from react_render import rendered

    client, factory = web
    _run_with(factory, [_OAUTH] * 11)

    body = rendered(client.get("/today"))

    assert "Anmeldung abgelaufen" in body
    assert "11 Fehler im Nachrichtenlauf" not in body


def test_the_header_says_that_nothing_is_being_analysed(web):
    """Nicht nur "Fehler", sondern die Folge: Artikel kommen weiter herein, und
    kein einziger wird ausgewertet. Ohne diesen Halbsatz liest sich die Meldung
    wie ein technisches Detail statt wie ein stillgelegtes Werkzeug."""
    from react_render import rendered

    client, factory = web
    _run_with(factory, [_OAUTH])

    body = rendered(client.get("/today"))

    assert "nichts wird analysiert" in body


def test_an_ordinary_run_still_reads_as_ok(web):
    """Der teure Irrtum in die andere Richtung."""
    from react_render import rendered

    client, factory = web
    _run_with(factory, [])

    assert "Anmeldung abgelaufen" not in rendered(client.get("/today"))


def test_a_feed_failure_is_not_turned_into_a_sign_in_alarm(web):
    """Es schickte sonst jemanden zum Neuanmelden statt zum Feed."""
    from react_render import rendered

    client, factory = web
    _run_with(factory, ["feed 'Handelsblatt': timed out"])

    body = rendered(client.get("/today"))

    assert "Anmeldung abgelaufen" not in body
    assert "Fehler im Nachrichtenlauf" in body


def test_a_broken_feed_beside_the_dead_sign_in_is_still_counted(web):
    """Sonst verdeckt der eine Ausfall den anderen — und der Feed bleibt auch
    nach dem Neuanmelden kaputt, ohne dass es jemand gesehen hätte."""
    from react_render import rendered

    client, factory = web
    _run_with(factory, [_OAUTH, _OAUTH, "feed 'Handelsblatt': timed out"])

    body = rendered(client.get("/today"))

    assert "Anmeldung abgelaufen" in body
    assert "1" in body and "weitere Fehler" in body
