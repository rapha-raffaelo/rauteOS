"""Einen Text ändern, löschen oder archivieren — und die Grenze dazwischen.

"auch fehlt das Papierkorb oder Bearbeiten Button."

Die Grenze verläuft an der Freigabe, und sie ist der eigentliche Inhalt dieser
Datei. Ein Entwurf hat nie jemand ausser uns gesehen: er darf bearbeitet und
gelöscht werden. Ein freigegebener Text ist raus — ihn zu ändern hiesse,
nachträglich umzuschreiben, was ein Kunde gesehen und freigegeben hat; ihn zu
löschen hiesse, es verschwinden zu lassen. Beides ist keine Aufräumarbeit,
sondern das Verfälschen einer Akte.

``assets_view`` sagt das seit je in Worten ("Released texts stay final"). Hier
steht es als etwas, das fällt, wenn jemand es aufweicht.
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse import asset_edit
from newspulse.models import Angle, Asset, AssetKind, Base, Client
from newspulse.web.app import create_app, get_db

_NOW = dt.datetime(2026, 10, 13, 9, 0, tzinfo=dt.UTC)


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
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
def client(session):
    row = Client(name="Qonto", aliases=[], keywords=[], alert_topics=[])
    session.add(row)
    session.commit()
    return row


def _asset(session, client, *, released=False, archived=False) -> Asset:
    # Ein Asset braucht einen Anker (ck_assets_anchor): einen Impuls oder eine
    # Krise. Es gibt keinen Text ohne Anlass, und das Schema hält das fest.
    angle = Angle(
        client_id=client.id, generated_at=_NOW - dt.timedelta(days=4),
        subject="Anlass", message="m", context="k",
    )
    session.add(angle)
    session.commit()
    row = Asset(
        client_id=client.id,
        angle_id=angle.id,
        kind=AssetKind.PRESSEMITTEILUNG,
        title="Ein Titel",
        body="Ein Rumpf.",
        generated_at=_NOW - dt.timedelta(days=3),
        released_at=_NOW - dt.timedelta(days=1) if released else None,
        archived_at=_NOW if archived else None,
    )
    session.add(row)
    session.commit()
    return row


# --- Der Entwurf -------------------------------------------------------------------


def test_a_draft_can_be_edited(session, client):
    row = _asset(session, client)

    asset_edit.edit(session, row, title="Neuer Titel", body="Neuer Rumpf.")

    assert (row.title, row.body) == ("Neuer Titel", "Neuer Rumpf.")
    assert row.edited_at is not None, "die Seite unterscheidet erzeugt von überarbeitet"


def test_a_draft_can_be_deleted(session, client):
    row = _asset(session, client)

    asset_edit.delete(session, row)

    assert session.scalar(select(func.count()).select_from(Asset)) == 0


def test_an_empty_body_is_refused_rather_than_stored(session, client):
    """Ein Text ohne Inhalt ist kein Text, und wer ihn loswerden will, hat den
    Papierkorb."""
    row = _asset(session, client)

    with pytest.raises(asset_edit.Refused):
        asset_edit.edit(session, row, title="Titel", body="   ")

    assert row.body == "Ein Rumpf."


# --- Der freigegebene Text ---------------------------------------------------------


def test_a_released_text_cannot_be_edited(session, client):
    """Was freigegeben wurde, hat der Kunde so gesehen."""
    row = _asset(session, client, released=True)

    with pytest.raises(asset_edit.Refused, match="nicht mehr ändern"):
        asset_edit.edit(session, row, title="Anders", body="Anders.")

    assert row.title == "Ein Titel"


def test_a_released_text_cannot_be_deleted(session, client):
    """Die Zeile, die diese ganze Datei schützt."""
    row = _asset(session, client, released=True)

    with pytest.raises(asset_edit.Refused, match="archivieren"):
        asset_edit.delete(session, row)

    assert session.scalar(select(func.count()).select_from(Asset)) == 1


def test_a_released_text_can_be_archived(session, client):
    row = _asset(session, client, released=True)

    asset_edit.archive(session, row)

    assert row.archived_at is not None
    assert session.scalar(select(func.count()).select_from(Asset)) == 1, "nicht gelöscht"


def test_archiving_twice_does_not_move_the_stamp(session, client):
    """Das erste Mal ist die Handlung. Ein zweiter Klick auf eine veraltete
    Liste darf nicht so aussehen, als wäre heute etwas geschehen."""
    row = _asset(session, client, released=True)
    asset_edit.archive(session, row)
    first = row.archived_at

    asset_edit.archive(session, row)

    assert row.archived_at == first


def test_what_was_archived_comes_back(session, client):
    """Ohne diesen Weg wäre Archivieren ein Löschen mit besserem Namen."""
    row = _asset(session, client, released=True, archived=True)

    asset_edit.restore(session, row)

    assert row.archived_at is None


# --- Die Liste ---------------------------------------------------------------------


def test_an_archived_text_leaves_the_list_but_not_the_database(web, session, client):
    _asset(session, client, released=True, archived=True)
    _asset(session, client)

    body = web.get("/api/v1/workbench/assets").json()

    assert len(body["texts"]) == 1
    assert session.scalar(select(func.count()).select_from(Asset)) == 2


def test_the_list_says_which_texts_may_be_edited(web, session, client):
    """Die Oberfläche soll die Regel nicht aus dem Freigabedatum nachbauen."""
    _asset(session, client)
    _asset(session, client, released=True)

    rows = web.get("/api/v1/workbench/assets").json()["texts"]

    assert sorted(r["editable"] for r in rows) == [False, True]


# --- Über HTTP ---------------------------------------------------------------------


def test_the_endpoint_refuses_to_delete_a_released_text(web, session, client):
    row = _asset(session, client, released=True)

    response = web.delete(f"/api/v1/workbench/assets/{row.id}")

    # 409 und nicht 403: es fehlt keine Berechtigung, der Text ist in einem
    # Zustand, in dem die Handlung nicht vorgesehen ist.
    assert response.status_code == 409
    assert "archivieren" in response.json()["detail"]
    assert session.scalar(select(func.count()).select_from(Asset)) == 1


def test_the_endpoint_deletes_a_draft(web, session, client):
    row = _asset(session, client)

    assert web.delete(f"/api/v1/workbench/assets/{row.id}").status_code == 200
    assert session.scalar(select(func.count()).select_from(Asset)) == 0


def test_the_endpoint_edits_a_draft(web, session, client):
    row = _asset(session, client)

    response = web.put(
        f"/api/v1/workbench/assets/{row.id}",
        json={"title": "Geändert", "body": "Neuer Rumpf."},
    )

    assert response.status_code == 200
    session.expire_all()
    assert session.get(Asset, row.id).title == "Geändert"


def test_an_unknown_text_is_a_404(web):
    assert web.delete("/api/v1/workbench/assets/9999").status_code == 404
