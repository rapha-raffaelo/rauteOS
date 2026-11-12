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
