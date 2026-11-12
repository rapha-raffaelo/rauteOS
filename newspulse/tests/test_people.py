"""The mandate's phone book, and the media contact RAUTE proposes as a chance's speaker."""
import pytest
from fastapi.testclient import TestClient
from react_render import rendered
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse import activation, people, profile
from newspulse.models import Angle, Base, Client, ClientPerson, OpportunityWorkspace
from newspulse.web.app import create_app, get_db
from newspulse.web.routes import opportunities_api as api


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        session.add_all([Client(name="Qonto"), Client(name="Other")])
        session.flush()
        session.add(Angle(client_id=1, subject="Kreditkosten im Mittelstand", message="Finanzierung wird teurer",
                          context="Zinsen"))
        session.commit()
        yield session
    engine.dispose()


@pytest.fixture
def web(db, monkeypatch):
    monkeypatch.setattr(api, "start_or_release", lambda *args, **kwargs: None)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client


def _add(web, **fields):
    data = dict(name="Anna Berg", position="CFO", phone="+49 30 1234", email="anna@qonto.example",
                linkedin_url="linkedin.com/in/anna-berg", topics="Finanzierung, Kredite", media_contact="1")
    data.update(fields)
    return web.post("/client/1/kontakte", data=data, follow_redirects=False)


def test_a_contact_is_saved_and_shown_on_the_profile(web, db):
    response = web.post("/client/1/kontakte", data=dict(name="Anna Berg", position="CFO",
                        linkedin_url="linkedin.com/in/anna-berg"), follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].startswith("/client/1/twin#kontakt-")
    person = db.scalar(select(ClientPerson))
    assert person.linkedin_url == "https://linkedin.com/in/anna-berg"
    page = rendered(web.get("/client/1/twin"))
    assert "Kontakte &amp; Sprecher" in page and "Anna Berg" in page
    assert 'href="https://linkedin.com/in/anna-berg"' in page


def test_a_link_that_is_not_a_linkedin_profile_is_refused_and_the_entry_kept(web, db):
    page = rendered(_add(web, linkedin_url="https://evil.example/in/anna"))
    assert "führt nicht auf ein Profil" in page and 'value="Anna Berg"' in page
    assert db.scalar(select(ClientPerson)) is None


def test_the_media_switch_writes_the_speakers_into_the_profile(web, db):
    _add(web)
    _add(web, name="Ben Ohne", media_contact="", topics="")
    assert "Anna Berg, CFO (Themen: Finanzierung, Kredite)" == profile.stored(db, 1)["sprecher"].value
    ben = db.scalar(select(ClientPerson).where(ClientPerson.name == "Ben Ohne"))
    web.post(f"/client/1/kontakte/{ben.id}/medien", data={"media_contact": "1"})
    assert "Ben Ohne" in profile.stored(db, 1)["sprecher"].value
    assert web.post("/client/2/kontakte/%d/medien" % ben.id, data={"media_contact": "1"}).status_code == 404


def test_raute_proposes_the_media_contact_whose_topics_fit_and_the_writer_quotes_them(web, db):
    _add(web, name="Carla Produkt", position="CPO", topics="Produkt, App")
    _add(web)
    _add(web, name="Dora Intern", media_contact="", topics="Kredite, Finanzierung, Mittelstand")
    read = web.get("/api/v1/clients/1/opportunities/developed/1").json()
    anna = db.scalar(select(ClientPerson).where(ClientPerson.name == "Anna Berg"))
    assert [p["label"] for p in read["people"]] == ["Anna Berg, CFO", "Carla Produkt, CPO", "Dora Intern, CFO"]
    assert read["speaker_proposal"]["person_id"] == anna.id
    assert read["speaker_proposal"]["reason"] == "Themenverantwortung passt: Finanzierung, Kredite"

    body = dict(revision=0, storyline="Kredite werden teurer", speaker_person_id=anna.id, contact_ids=[])
    saved = web.post("/api/v1/clients/1/opportunities/developed/1/activate", json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["speaker_person_id"] == anna.id and saved.json()["speaker_proposal"] is None
    workspace = db.scalar(select(OpportunityWorkspace))
    context, _ = activation.context_for(db, workspace)
    assert context["speaker"]["value"] == "Anna Berg, CFO"
    assert activation.writing_facts(db, workspace, context)["ceo"].value == "Anna Berg, CFO"


def test_an_internal_profile_contact_is_optional_and_not_a_quotable_speaker(web, db):
    _add(web, name="Dora Intern", media_contact="")
    dora = db.scalar(select(ClientPerson))
    body = dict(revision=0, storyline="x", speaker_person_id=dora.id, contact_ids=[])
    assert web.put("/api/v1/clients/1/opportunities/developed/1", json=body).status_code == 200
    workspace = db.scalar(select(OpportunityWorkspace))
    context, _ = activation.context_for(db, workspace)
    assert context['speaker']['media_contact'] is False
    assert 'ceo' not in activation.writing_facts(db, workspace, context)
    body.update(revision=1, speaker_person_id=None)
    assert web.put("/api/v1/clients/1/opportunities/developed/1", json=body).status_code == 200
    context, _ = activation.context_for(db, workspace)
    assert context['speaker'] is None
