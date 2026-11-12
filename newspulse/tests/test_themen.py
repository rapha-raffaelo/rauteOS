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


# --- Export: Word, PDF and Drive -------------------------------------------------

import io
import zipfile

from newspulse import asset_export, drive_link
from newspulse.models import Asset


def _asset(session, mandate, angle_id, body="Erster Absatz.\n\nZweiter Absatz."):
    asset = Asset(client_id=mandate.id, angle_id=angle_id, kind="statement", title="Statement zur Verschreibung",
                  body=body)
    session.add(asset)
    session.commit()
    return asset


def test_an_asset_downloads_as_word_and_pdf(web, session, mandate):
    article = _article(session, "Bundestag schränkt Medizinalcannabis ein", "https://ex.de/radar-007", radar=mandate)
    row = themen.star(session, mandate, article)
    asset = _asset(session, mandate, row.context_id)

    word = web.get(f"/api/v1/clients/{mandate.id}/assets/asset/{asset.id}/export.docx")
    assert word.status_code == 200 and word.headers["content-type"] == asset_export.DOCX
    assert "Remexian" in word.headers["content-disposition"]
    text = zipfile.ZipFile(io.BytesIO(word.content)).read("word/document.xml").decode()
    assert "Zweiter Absatz." in text and "Statement zur Verschreibung" in text

    pdf = web.get(f"/api/v1/clients/{mandate.id}/assets/asset/{asset.id}/export.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert web.get(f"/api/v1/clients/{mandate.id}/assets/asset/{asset.id}/export.txt").status_code == 422


def test_a_thema_exports_with_its_deep_dive(web, session, mandate):
    article = _article(session, "Bundestag schränkt Medizinalcannabis ein", "https://ex.de/radar-008", radar=mandate)
    row = themen.star(session, mandate, article)
    word = web.get(f"/api/v1/clients/{mandate.id}/themen/developed/{row.context_id}/export.docx")
    text = zipfile.ZipFile(io.BytesIO(word.content)).read("word/document.xml").decode()
    assert "Was ist passiert?" in text and "Warum für Remexian Pharma GmbH relevant?" in text and "bitte ergänzen" in text


def test_drive_puts_the_file_into_the_clients_folder_under_7_assets(tmp_path, monkeypatch):
    from newspulse import config

    monkeypatch.setattr(config, "DATABASE_PATH", tmp_path / "db.sqlite")
    monkeypatch.setattr(config, "DRIVE_ASSETS_FOLDER", "root-folder")
    drive_link._write({"refresh_token": "r", "access_token": "a", "expires_at": "2999-01-01T00:00:00+00:00"})
    calls = []

    def call(url, **kwargs):
        calls.append((url, kwargs))
        if "files?q=" in url:
            return {"files": []}
        if "upload" in url:
            return {"id": "f1", "webViewLink": "https://drive.google.com/file/d/f1/view"}
        return {"id": "folder-1"}

    url = drive_link.upload("Remexian Pharma GmbH", "a.docx", asset_export.DOCX, b"bytes", call=call)
    assert url == "https://drive.google.com/file/d/f1/view"
    made = json.loads(calls[1][1]["body"])
    assert made == {"name": "Remexian Pharma GmbH", "mimeType": "application/vnd.google-apps.folder", "parents": ["root-folder"]}
    assert b'"parents": ["folder-1"]' in calls[2][1]["body"] and "supportsAllDrives=true" in calls[2][0]


def test_without_a_drive_connection_the_export_says_so(web, session, mandate, tmp_path, monkeypatch):
    from newspulse import config

    monkeypatch.setattr(config, "DATABASE_PATH", tmp_path / "db.sqlite")
    article = _article(session, "Bundestag schränkt Medizinalcannabis ein", "https://ex.de/radar-009", radar=mandate)
    asset = _asset(session, mandate, themen.star(session, mandate, article).context_id)
    refused = web.post(f"/api/v1/clients/{mandate.id}/assets/asset/{asset.id}/drive", json={"format": "pdf"})
    assert refused.status_code == 409 and "nicht verbunden" in refused.json()["detail"]


def test_drive_connects_through_the_gmail_callback_by_its_state(web, monkeypatch):
    from newspulse import config

    monkeypatch.setattr(config, "gmail_configured", lambda: True)
    monkeypatch.setattr(config, "gmail_client_id", lambda: "client-id")
    exchanged = []
    monkeypatch.setattr(drive_link, "exchange", lambda code: exchanged.append(code))

    start = web.get("/settings/drive/start", follow_redirects=False)
    assert start.status_code == 303 and "auth%2Fdrive" in start.headers["location"]
    state = web.cookies.get("newspulse_gmail_state")
    assert state.startswith(drive_link.STATE_PREFIX)

    back = web.get(f"/settings/gmail/callback?code=abc&state={state}", follow_redirects=False)
    assert back.headers["location"] == "/settings?drive=verbunden#drive"
    assert exchanged == ["abc"]


def test_suggestions_use_recent_client_news_once_and_keep_sources(session, mandate):
    from newspulse import topic_suggestions
    recent = _article(session, 'Neue Versorgungsstudie', 'https://ex.de/new-study', radar=mandate)
    old = _article(session, 'Alte Studie', 'https://ex.de/old-study', radar=mandate)
    old.published_at = dt.datetime.now(dt.UTC) - dt.timedelta(days=60)
    session.commit()
    calls = []
    def invoke(prompt, **kwargs):
        calls.append(prompt)
        assert 'Neue Versorgungsstudie' in prompt
        assert 'Alte Studie' not in prompt
        return json.dumps(dict(worth_sending=True, subject='Versorgung einordnen', message='Ein Vorschlag',
                               evidence=[0], context='Die neue Studie', credibility='Versorgung', thesis='These'))
    lease = topic_suggestions.claim(session, mandate.id)
    assert lease and topic_suggestions.claim(session, mandate.id) is None
    topic_suggestions.generate(session, mandate.id, lease, invoke=invoke)
    assert topic_suggestions.state(session, mandate.id)['status'] == 'ready'
    angle = session.query(Angle).filter_by(client_id=mandate.id).one()
    assert angle.article_ids == [recent.id]
    assert len(calls) == 1
    # An archived suggestion must not be regenerated from the same news.
    angle.dismissed_at = dt.datetime.now(dt.UTC)
    session.commit()
    next_lease = topic_suggestions.claim(session, mandate.id, now=dt.datetime.now(dt.UTC)+dt.timedelta(hours=7))
    topic_suggestions.generate(session, mandate.id, next_lease, invoke=invoke)
    assert len(calls) == 1
    assert topic_suggestions.state(session, mandate.id)['status'] == 'empty'


def test_suggestions_do_not_invent_news_and_report_model_failure(session, mandate):
    from newspulse import topic_suggestions
    lease = topic_suggestions.claim(session, mandate.id)
    topic_suggestions.generate(session, mandate.id, lease, invoke=lambda *a, **kw: pytest.fail('No news: no model call'))
    assert topic_suggestions.state(session, mandate.id)['status'] == 'empty'
    _article(session, 'Neue Studie', 'https://ex.de/new-study', radar=mandate)
    next_lease = topic_suggestions.claim(session, mandate.id, now=dt.datetime.now(dt.UTC)+dt.timedelta(hours=7))
    def fail(*args, **kwargs):
        raise RuntimeError('Provider unavailable')
    topic_suggestions.generate(session, mandate.id, next_lease, invoke=fail)
    assert topic_suggestions.state(session, mandate.id)['status'] == 'failed'
    assert session.query(Angle).count() == 0
