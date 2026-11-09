"""Each person's LinkedIn profile, connected so RauteOS posts the planned posts."""
from __future__ import annotations

from react_render import rendered

import datetime as dt
import json
import stat
import urllib.parse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse import config, linkedin_link, worklists
from newspulse.models import Base, Client, LinkedInPost
from newspulse.web.app import create_app, get_db


class FakeLinkedIn:
    """Answers like LinkedIn and remembers what it was asked."""

    def __init__(self, *, post_status=201):
        self.calls = []
        self.post_status = post_status

    def __call__(self, url, *, form=None, json_body=None, token="", headers=None):
        self.calls.append(dict(url=url, form=form, json=json_body, token=token, headers=headers or {}))
        if url.endswith("/accessToken"):
            return 200, {}, {"access_token": "tok-1", "expires_in": 5184000, "scope": "openid,profile,w_member_social"}
        if url.endswith("/userinfo"):
            return 200, {}, {"sub": "abc123", "name": "Lucas Neurauter"}
        if url.endswith("/rest/posts"):
            if self.post_status == 201:
                return 201, {"x-restli-id": "urn:li:share:777"}, {}
            return self.post_status, {}, {"message": "Unauthorized"}
        return 200, {}, {}

    def posts(self):
        return [c for c in self.calls if c["url"].endswith("/rest/posts")]


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATABASE_PATH", tmp_path / "newspulse.db")
    monkeypatch.setenv("NEWSPULSE_LINKEDIN_CLIENT_ID", "cid")
    monkeypatch.setenv("NEWSPULSE_LINKEDIN_CLIENT_SECRET", "secret")
    stub = FakeLinkedIn()
    monkeypatch.setattr(linkedin_link, "_fetch", stub)
    return stub


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(factory):
    with factory() as s:
        s.add(Client(id=1, name="Qonto", aliases=[], keywords=[], alert_topics=[]))
        s.add(LinkedInPost(id=5, client_id=1, title="Kreditkosten", status="freigabe",
                           body="Kredite werden teurer (für alle). #Mittelstand"))
        s.commit()
        yield s


@pytest.fixture
def web(factory, session):
    app = create_app()

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def _connect(web):
    start = web.get("/linkedin/connect", follow_redirects=False)
    assert start.status_code == 303
    query = urllib.parse.parse_qs(urllib.parse.urlparse(start.headers["location"]).query)
    assert query["scope"] == ["openid profile w_member_social"]
    assert query["redirect_uri"] == [config.linkedin_redirect_uri()]
    return web.get("/linkedin/callback", params={"code": "c-1", "state": query["state"][0]}, follow_redirects=False)


def test_text_is_escaped_for_linkedin_and_hashtags_stay_hashtags():
    assert linkedin_link.commentary("Kosten (2026) @Bank #Mittelstand_KMU") == (
        r"Kosten \(2026\) \@Bank {hashtag|\#|Mittelstand\_KMU}")


def test_a_person_connects_their_profile_and_the_token_stays_in_a_private_file(web, fake):
    page = rendered(web.get("/linkedin"))
    assert 'href="/linkedin/connect"' in page

    done = _connect(web)
    assert done.headers["location"] == "/linkedin?konto=verbunden"
    stored = json.loads(linkedin_link.token_path().read_text())
    assert stored["team"]["person_urn"] == "urn:li:person:abc123"
    assert stat.S_IMODE(linkedin_link.token_path().stat().st_mode) == 0o600
    page = rendered(web.get("/linkedin?konto=verbunden"))
    assert "Lucas Neurauter" in page and "LinkedIn ist verbunden." in page
    assert 'action="/linkedin/5/publish"' in page


def test_a_callback_without_this_browsers_state_connects_nothing(web, fake):
    web.get("/linkedin/connect", follow_redirects=False)
    refused = web.get("/linkedin/callback", params={"code": "c", "state": "forged"}, follow_redirects=False)
    assert refused.headers["location"] == "/linkedin?konto=fehler"
    assert linkedin_link.connection("") is None


def test_posting_now_publishes_once_as_the_connected_person(web, fake, session):
    _connect(web)
    assert web.post("/linkedin/5/publish", follow_redirects=False).status_code == 303
    session.expire_all()
    post = session.get(LinkedInPost, 5)
    assert (post.status, post.linkedin_urn) == ("veroeffentlicht", "urn:li:share:777")
    assert post.published_url == "https://www.linkedin.com/feed/update/urn:li:share:777/"
    [call] = fake.posts()
    assert call["json"]["author"] == "urn:li:person:abc123"
    assert call["json"]["commentary"].endswith(r"\(für alle\). {hashtag|\#|Mittelstand}")
    assert call["headers"]["LinkedIn-Version"] == config.linkedin_version()
    assert call["token"] == "tok-1"

    again = rendered(web.post("/linkedin/5/publish"))
    assert "schon auf LinkedIn" in again
    assert len(fake.posts()) == 1


def test_a_refused_token_ends_the_connection_and_says_so(web, fake, session):
    _connect(web)
    fake.post_status = 401
    page = rendered(web.post("/linkedin/5/publish"))
    assert "Bitte neu verbinden" in page
    assert not linkedin_link.connection("").usable()
    assert "access_token" not in json.loads(linkedin_link.token_path().read_text())["team"]
    assert session.get(LinkedInPost, 5).linkedin_urn == ""


def test_a_scheduled_post_goes_out_when_due_and_a_failure_is_not_retried(web, fake, session, monkeypatch):
    _connect(web)
    when = dt.datetime.now(config.local_zone()).replace(second=0, microsecond=0) + dt.timedelta(days=1)
    web.post("/linkedin/5/schedule", data={"post_at": when.strftime("%Y-%m-%dT%H:%M")})
    session.expire_all()
    post = session.get(LinkedInPost, 5)
    assert post.status == "geplant" and post.post_at == when.astimezone(dt.UTC)
    assert "Geht am" in rendered(web.get("/linkedin"))

    assert worklists.publish_due(session, when.astimezone(dt.UTC) - dt.timedelta(minutes=1)) == 0
    fake.post_status = 500
    assert worklists.publish_due(session, when.astimezone(dt.UTC)) == 0
    session.expire_all()
    post = session.get(LinkedInPost, 5)
    assert post.post_at is None and post.post_error.startswith("Geplanter Beitrag ging nicht raus")
    assert worklists.publish_due(session, when.astimezone(dt.UTC) + dt.timedelta(hours=1)) == 0
    assert len(fake.posts()) == 1

    fake.post_status = 201
    web.post("/linkedin/5/schedule", data={"post_at": when.strftime("%Y-%m-%dT%H:%M")})
    assert worklists.publish_due(session, when.astimezone(dt.UTC)) == 1
    session.expire_all()
    assert session.get(LinkedInPost, 5).status == "veroeffentlicht"


def test_scheduling_past_the_connections_expiry_is_refused(web, fake, session):
    _connect(web)
    far = dt.datetime.now() + dt.timedelta(days=90)
    page = rendered(web.post("/linkedin/5/schedule", data={"post_at": far.strftime("%Y-%m-%dT%H:%M")}))
    assert "vor diesem Termin" in page
    session.expire_all()
    assert session.get(LinkedInPost, 5).post_at is None


def test_moving_a_scheduled_post_off_geplant_unschedules_it(web, fake, session):
    _connect(web)
    soon = dt.datetime.now() + dt.timedelta(days=1)
    web.post("/linkedin/5/schedule", data={"post_at": soon.strftime("%Y-%m-%dT%H:%M")})
    web.post("/linkedin/5", data={"status": "freigabe"})
    session.expire_all()
    assert session.get(LinkedInPost, 5).post_at is None


def test_disconnecting_forgets_the_token_and_asks_linkedin_to_revoke_it(web, fake):
    _connect(web)
    assert web.post("/linkedin/disconnect", follow_redirects=False).headers["location"] == "/linkedin?konto=getrennt"
    assert linkedin_link.connection("") is None
    assert any(c["url"].endswith("/revoke") and c["form"]["token"] == "tok-1" for c in fake.calls)


def test_without_an_app_the_page_says_so_and_offers_no_connection(web, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATABASE_PATH", tmp_path / "newspulse.db")
    monkeypatch.delenv("NEWSPULSE_LINKEDIN_CLIENT_ID", raising=False)
    page = rendered(web.get("/linkedin"))
    assert "In LinkedIn öffnen" in page and "/linkedin/connect" not in page


def test_a_post_published_by_hand_takes_its_linkedin_link(web, session):
    url = "https://www.linkedin.com/posts/lucas_kreditkosten-activity-1"
    assert web.post("/linkedin/5/published", data={"published_url": url}, follow_redirects=False).status_code == 303
    session.expire_all()
    post = session.get(LinkedInPost, 5)
    assert (post.status, post.published_url) == ("veroeffentlicht", url)
    assert post.planned_on is not None


def test_a_link_elsewhere_is_not_taken_as_the_post(web, session):
    page = rendered(web.post("/linkedin/5/published", data={"published_url": "https://evil.example/x"}))
    assert "kein Link zu LinkedIn" in page
    session.expire_all()
    assert session.get(LinkedInPost, 5).status == "freigabe"


def test_an_idea_from_a_chance_gets_its_text_and_goes_out_by_hand(web, session):
    """The whole board flow without an app: chance, idea, text, LinkedIn, link."""
    made = web.post("/linkedin/from-chance", data={"client_id": "1", "title": "Neue Wettbewerber",
                                                   "context_href": "/client/1/opportunities?kind=detected&context=9"},
                    follow_redirects=False)
    assert made.status_code == 303
    idea = session.scalar(select(LinkedInPost).where(LinkedInPost.title == "Neue Wettbewerber"))
    page = rendered(web.get("/linkedin"))
    assert "Text schreiben" in page and f'action="/linkedin/{idea.id}/published"' not in page

    web.post(f"/linkedin/{idea.id}", data={"title": idea.title, "client_id": "1", "status": "idee",
                                           "body": "Der Engpass ist der Betrieb nach dem Start."})
    session.expire_all()
    assert session.get(LinkedInPost, idea.id).status == "entwurf"
    assert "In LinkedIn öffnen" in rendered(web.get("/linkedin"))

    url = "https://www.linkedin.com/posts/lucas_activity-2"
    web.post(f"/linkedin/{idea.id}/published", data={"published_url": url})
    session.expire_all()
    assert session.get(LinkedInPost, idea.id).status == "veroeffentlicht"
