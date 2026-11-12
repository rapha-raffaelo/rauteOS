"""Spec 12: Medien → Themen → Assets, and the Agenda beside the Themen."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from react_render import rendered
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse.models import Base, Client
from newspulse.web.app import create_app, get_db


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(factory):
    with factory() as open_session:
        yield open_session


@pytest.fixture
def web(factory):
    app = create_app()

    def _override():
        open_session = factory()
        try:
            yield open_session
        finally:
            open_session.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


@pytest.fixture
def mandate(session) -> Client:
    client = Client(name="Remexian Pharma GmbH", aliases=["Remexian"], industry="Pharma",
                    keywords=["Medizinalcannabis"])
    session.add(client)
    session.commit()
    return client


@pytest.mark.parametrize("page,title", [("themen", "Themen"), ("assets", "Assets")])
def test_themen_and_assets_are_pages_under_their_own_tab(web, mandate, page, title):
    body = rendered(web.get(f"/client/{mandate.id}/{page}"))
    assert f'id="react-{page}"' in body
    strip = body.split('class="subtabs"', 1)[1].split("</nav>", 1)[0]
    assert f'href="/client/{mandate.id}/{page}" class="active"' in strip


def test_a_competitor_has_neither_page(web, session):
    rival = Client(name="Zolar", is_competitor=True)
    session.add(rival)
    session.commit()
    assert web.get(f"/client/{rival.id}/themen").status_code == 404
    assert web.get(f"/api/v1/clients/{rival.id}/agenda").status_code == 404


def test_an_empty_agenda_is_an_empty_list(web, mandate):
    assert web.get(f"/api/v1/clients/{mandate.id}/agenda").json()["items"] == []


# --- Medien: both halves and the star -------------------------------------------

import datetime as dt
import json

from newspulse import themen
from newspulse.models import Analysis, Angle, Article, Category, OpportunityWorkspace, TopicHit


def _article(session, title, url, *, about=None, radar=None, summary="Feed-Snippet."):
    at = dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)
    article = Article(title=title, url=url, source="Ärzte Zeitung", published_at=at, fetched_at=at,
                      summary_text=summary, language="de", title_hash=url[-16:])
    session.add(article)
    session.flush()
    if about:
        session.add(Analysis(article_id=article.id, client_id=about.id, summary="Über den Kunden.",
                             category=Category.PRODUKT, is_relevant=True, relevance_score=5,
                             importance_score=5, is_alert=False))
    if radar:
        session.add(TopicHit(article_id=article.id, client_id=radar.id, found_at=at))
    session.commit()
    return article


def test_medien_lists_the_keyword_hits_beside_the_coverage(web, session, mandate):
    _article(session, "Remexian erweitert Lieferprogramm", "https://ex.de/own-0001", about=mandate)
    _article(session, "Bundestag schränkt Medizinalcannabis ein", "https://ex.de/radar-001", radar=mandate)
    _article(session, "Etwas anderes im Feld", "https://ex.de/radar-002", radar=mandate)

    own = rendered(web.get(f"/client/{mandate.id}/medien"))
    assert "Remexian erweitert Lieferprogramm" in own and "Bundestag schränkt" not in own
    assert "Zu den Keywords · 2" in own

    radar = rendered(web.get(f"/client/{mandate.id}/medien?quelle=keywords"))
    assert "Bundestag schränkt Medizinalcannabis ein" in radar and "Remexian erweitert" not in radar
    assert "„Medizinalcannabis“" in radar

    one = rendered(web.get(f"/client/{mandate.id}/medien?quelle=keywords&keyword=Medizinalcannabis"))
    assert "Bundestag schränkt" in one and "Etwas anderes im Feld" not in one


def test_the_star_makes_one_thema_and_takes_it_back(web, session, mandate, monkeypatch):
    from newspulse.web.routes import themen_view

    started = []
    monkeypatch.setattr(themen_view, "start_or_release", lambda *a, **k: started.append(k["name"]))
    article = _article(session, "Bundestag schränkt Medizinalcannabis ein", "https://ex.de/radar-003", radar=mandate)

    first = web.post(f"/api/v1/clients/{mandate.id}/themen", json={"article_id": article.id})
    again = web.post(f"/api/v1/clients/{mandate.id}/themen", json={"article_id": article.id})
    assert first.status_code == again.status_code == 201
    assert first.json()["context"] == again.json()["context"]
    assert len(started) == 1, "the Deep Dive is written once"

    row = next(r for r in web.get(f"/api/v1/clients/{mandate.id}/opportunities").json()["opportunities"]
               if r["context_id"] == first.json()["context"])
    assert row["origin"] == "medien" and row["title"] == article.title
    assert web.get(f"/api/v1/clients/{mandate.id}/themen/starred").json()[str(article.id)]["context"] == row["context_id"]

    assert web.delete(f"/api/v1/clients/{mandate.id}/themen/{article.id}").status_code == 200
    assert web.get(f"/api/v1/clients/{mandate.id}/themen/starred").json() == {}
    open_rows = [r for r in web.get(f"/api/v1/clients/{mandate.id}/opportunities").json()["opportunities"]
                 if r["status"] != "closed"]
    assert open_rows == []


def test_only_an_article_medien_shows_can_be_starred(web, session, mandate):
    stranger = _article(session, "Fremd", "https://ex.de/strange-01")
    assert web.post(f"/api/v1/clients/{mandate.id}/themen", json={"article_id": stranger.id}).status_code == 404


def test_the_deep_dive_fills_the_thema_without_inventing_people(session, mandate):
    article = _article(session, "Bundestag schränkt Medizinalcannabis ein", "https://ex.de/radar-004", radar=mandate)
    row = themen.star(session, mandate, article, by="lucas")
    seen = {}

    def invoke(prompt, timeout):
        seen["prompt"] = prompt
        return json.dumps({"situation": "Der Bundestag hat beschlossen.", "relevance": "Remexian beliefert Apotheken.",
                           "pitch": "Versorgung vor Debatte.", "storylines": ["Übergangsfrist fordern"]})

    themen.deep_dive(session, row.id, invoke=invoke)
    assert "Medizinalcannabis" in seen["prompt"] and "Remexian Pharma GmbH" in seen["prompt"]
    session.refresh(row)
    angle = session.get(Angle, row.context_id)
    assert row.data["deep_dive"] == "ready" and row.data["situation"] == "Der Bundestag hat beschlossen."
    assert angle.message == "Versorgung vor Debatte." and angle.statements[0] == "Versorgung vor Debatte."


def test_a_failed_deep_dive_leaves_the_thema_usable(session, mandate):
    article = _article(session, "Bundestag schränkt Medizinalcannabis ein", "https://ex.de/radar-005", radar=mandate)
    row = themen.star(session, mandate, article)

    def invoke(prompt, timeout):
        raise RuntimeError("quota")

    themen.deep_dive(session, row.id, invoke=invoke)
    session.refresh(row)
    assert row.data["deep_dive"] == "failed" and row.data["situation"] == article.title


def test_an_activated_thema_keeps_its_star(web, session, mandate):
    article = _article(session, "Bundestag schränkt Medizinalcannabis ein", "https://ex.de/radar-006", radar=mandate)
    row = themen.star(session, mandate, article)
    row.status = "active"
    session.commit()
    assert web.delete(f"/api/v1/clients/{mandate.id}/themen/{article.id}").status_code == 409
