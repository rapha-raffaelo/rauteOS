"""The mandate file around the retired kick-off: guide tab, old addresses, research offers."""
from __future__ import annotations

from react_render import rendered

import datetime as dt
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse import guide
from newspulse import profile as profiles
from newspulse.models import (
    Base,
    Client,
    ClientFact,
    OnboardingAnswer,
    ProfileProposal,
)
from newspulse.web import app as web_app
from newspulse.web.app import create_app, get_db


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(factory):
    return factory()


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


def _client(session) -> Client:
    c = Client(name="Vermont Robotics", aliases=[], industry="Medizintechnik",
               country="DE", keywords=[], alert_topics=[])
    session.add(c)
    session.commit()
    return c




def test_a_sourceless_research_proposal_is_not_called_the_clients_statement(factory, web):
    """The grounding API does come back without a source. "Angabe des Mandanten"
    is the strongest provenance the page can print, and putting it under a machine
    guess nobody can check is the exact inversion of what it means."""
    with factory() as session:
        client = _client(session)
        client_id = client.id
        session.add(ProfileProposal(
            client_id=client_id, key="geschaeftsfeld",
            value="Zulieferer für OP-Technik.",
            source_url="", source_title="",
            previous_value="", proposed_at=dt.datetime.now(dt.UTC),
            proposed_by="gemini-2.5-flash",
        ))
        session.commit()

    body = rendered(web.get(f"/client/{client_id}/profil"))

    # Not merely unlabelled: not offered. A value the reader cannot check is not
    # a decision anybody should be asked to make, so the page drops it — which
    # settles the provenance question this test was written about, because there
    # is nothing left to mislabel.
    assert "Zulieferer für OP-Technik." not in body
    assert "Angabe des Mandanten" not in body


def test_the_profile_page_carries_the_guide(web, session):
    """The guide has its own tab in the mandate's file again."""
    client = _client(session)
    guide.save(session, client, "Nie ohne Zahl. Nie im Konjunktiv.")

    body = rendered(web.get(f"/client/{client.id}/guide"))

    assert "Nie ohne Zahl. Nie im Konjunktiv." in body
    assert f'action="/client/{client.id}/guide"' in body, "the guide is editable here"


def test_a_guide_error_is_still_shown_after_the_move(web, session, monkeypatch):
    """The reason the guide's routes pass their answers through rather than
    redirecting: a distillation that failed has something to say, and a redirect
    would drop it. Every key the guide page used to build has a default on the
    profile page, so a missing one renders as empty rather than raising."""
    from newspulse.web.routes import guide_routes

    client = _client(session)

    def _boom(*args, **kwargs):
        raise guide_routes.AnalyzerError("das Modell ist nicht erreichbar")

    monkeypatch.setattr(guide_routes.guide, "distill", _boom)

    body = rendered(web.post(
        f"/client/{client.id}/guide/distill", data={}, follow_redirects=False
    ))

    assert "das Modell ist nicht erreichbar" in body


def test_the_old_kickoff_address_leads_to_the_profile(web, session):
    """The 20-question kick-off is retired; a bookmark lands on the profile,
    where the 22 customer questions now live."""
    client = _client(session)

    kickoff = web.get(f"/client/{client.id}/kickoff", follow_redirects=False)
    guide_page = web.get(f"/client/{client.id}/guide", follow_redirects=False)

    assert kickoff.headers["location"] == f"/client/{client.id}/twin"
    assert guide_page.status_code == 200, "the guide is a tab of its own"


def test_the_strip_has_no_kickoff_tab(web, session):
    client = _client(session)

    strip = rendered(web.get(f"/client/{client.id}/profil"))

    assert f'href="/client/{client.id}/twin"' in strip
    assert f'href="/client/{client.id}/kickoff"' not in strip
    assert f'href="/client/{client.id}/guide"' in strip


def test_the_guide_offers_no_draft_from_the_retired_kickoff(web, session):
    client = _client(session)

    body = rendered(web.get(f"/client/{client.id}/guide"))

    assert "/guide/kickoff" not in body
    assert "Kickoff" not in body
    assert f'action="/client/{client.id}/guide/vorschlag"' in body
    assert web.post(f"/client/{client.id}/guide/kickoff").status_code in (404, 405)
