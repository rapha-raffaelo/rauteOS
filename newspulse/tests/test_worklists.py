"""Spec 10: Aufgaben, LinkedIn and Sales CRM, kept by hand."""
from __future__ import annotations

from react_render import rendered

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse import desk, worklists
from newspulse.models import Angle, Base, Client, Deal, LinkedInPost, Outreach, OutreachState, Task, TaskBoard
from newspulse.web.app import create_app, get_db


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(factory):
    with factory() as s:
        s.add_all([Client(id=1, name="Qonto", aliases=[], keywords=[], alert_topics=[]),
                   Client(id=2, name="Rival", is_competitor=True, aliases=[], keywords=[], alert_topics=[])])
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


# --- Aufgaben -------------------------------------------------------------------


def test_a_task_is_created_from_the_form_and_listed(web, session):
    response = web.post("/aufgaben", data={"title": "EZB-Statement finalisieren", "client_id": "1",
                                           "priority": "hoch", "due_on": "2026-11-05"}, follow_redirects=False)
    assert response.status_code == 303
    task = session.scalar(select(Task))
    assert (task.title, task.client_id, task.priority, task.status) == ("EZB-Statement finalisieren", 1, "hoch", "offen")
    assert task.due_on == dt.date(2026, 11, 5)
    assert "EZB-Statement finalisieren" in rendered(web.get("/aufgaben"))


def test_an_agency_task_needs_no_mandate(web, session):
    web.post("/aufgaben", data={"title": "Medienliste aktualisieren"})
    assert session.scalar(select(Task)).client_id is None


@pytest.mark.parametrize("form,reason", [
    ({"title": ""}, "Was ist zu tun?"),
    ({"title": "x", "priority": "dringend"}, "Unbekannter Wert."),
    ({"title": "x", "due_on": "morgen"}, "Datum im Format"),
    ({"title": "x", "client_id": "2"}, "Unbekannter Mandant."),
    ({"title": "x", "context_href": "https://evil.example"}, "innerhalb von RauteOS"),
])
def test_an_invalid_task_is_refused_with_the_reason_and_nothing_stored(web, session, form, reason):
    body = rendered(web.post("/aufgaben", data=form))
    assert reason in body
    assert session.scalar(select(Task)) is None


def test_finishing_a_task_stamps_it_and_reopening_clears_the_stamp(web, session):
    web.post("/aufgaben", data={"title": "Pitch schreiben"})
    task = session.scalar(select(Task))
    web.post(f"/aufgaben/{task.id}", data={"status": "erledigt"})
    session.refresh(task)
    assert task.status == "erledigt" and task.done_at is not None
    web.post(f"/aufgaben/{task.id}", data={"status": "offen"})
    session.refresh(task)
    assert task.status == "offen" and task.done_at is None


def test_open_work_comes_first_then_by_date_due(session):
    for title, due, status in [("später", "2026-12-01", "offen"), ("ohne Datum", "", "offen"),
                               ("bald", "2026-11-06", "offen"), ("fertig", "2026-11-01", "erledigt")]:
        worklists.save_task(session, {"title": title, "due_on": due, "status": status})
    assert [t.title for t in worklists.tasks(session)] == ["bald", "später", "ohne Datum", "fertig"]


def test_a_task_can_be_deleted_and_a_missing_one_is_a_404(web, session):
    web.post("/aufgaben", data={"title": "weg"})
    task = session.scalar(select(Task))
    assert web.post(f"/aufgaben/{task.id}/delete", follow_redirects=False).status_code == 303
    assert session.scalar(select(Task)) is None
    assert web.post("/aufgaben/999/delete").status_code == 404


def test_the_desk_counts_open_tasks_and_lists_them_before_decisions(session):
    worklists.save_task(session, {"title": "heute", "due_on": "2026-11-05", "client_id": "1"})
    worklists.save_task(session, {"title": "erledigt", "status": "erledigt"})
    board = desk.build(session)
    assert board.tasks_open == 1
    assert [t.title for t in board.tasks] == ["heute"]
    assert board.tasks[0].href.startswith("/aufgaben?aufgabe=")


def _client_letter(session, subject="Was beim Wechsel zum Depot nicht mitwandert"):
    angle = Angle(client_id=1, generated_at=dt.datetime(2026, 9, 4, tzinfo=dt.UTC),
                  subject="Impuls", message="m", context="k")
    session.add(angle)
    session.flush()
    session.add(Outreach(angle_id=angle.id, client_id=1, subject=subject, message="x",
                         generated_at=dt.datetime(2026, 9, 4, tzinfo=dt.UTC), state=OutreachState.ENTWURF))
    session.commit()


def test_the_desks_open_decisions_are_listed_on_the_tasks_page(web, session):
    """"Entscheidungen offen" on the Desk has a page: the same rows, each linked."""
    _client_letter(session)
    board = desk.build(session)
    assert board.decisions_open == len(desk.open_decisions(session))
    body = rendered(web.get("/aufgaben?workspace=decisions"))
    assert "Offene Entscheidungen" in body
    assert "Was beim Wechsel zum Depot nicht mitwandert" in body
    assert "Kundenfreigabe" in body
    for decision in board.decisions:
        assert decision.href.replace("&", "&amp;") in body or decision.href in body


def test_the_decisions_follow_the_mandate_filter(web, session):
    _client_letter(session)
    assert len(desk.open_decisions(session, 1)) == len(desk.open_decisions(session))
    assert desk.open_decisions(session, 999) == []


def test_ticking_a_task_on_the_desk_goes_back_to_the_desk(web, session):
    web.post("/aufgaben", data={"title": "abhaken"})
    task = session.scalar(select(Task))
    response = web.post(f"/aufgaben/{task.id}", data={"status": "erledigt", "redirect_to": "/desk"},
                        follow_redirects=False)
    assert response.headers["location"] == "/desk"
    session.refresh(task)
    assert task.status == "erledigt"
    off_site = web.post(f"/aufgaben/{task.id}", data={"status": "offen", "redirect_to": "//evil.example"},
                        follow_redirects=False)
    assert off_site.headers["location"] == "/aufgaben"


# --- LinkedIn -------------------------------------------------------------------


def test_a_post_belongs_to_a_mandate_and_moves_through_its_states(web, session):
    assert "Bitte einen Mandanten wählen." in rendered(web.post("/linkedin", data={"title": "Kreditkosten"}))
    web.post("/linkedin", data={"title": "Kreditkosten", "client_id": "1", "author": "CEO"})
    post = session.scalar(select(LinkedInPost))
    assert post.status == "idee"
    web.post(f"/linkedin/{post.id}", data={"status": "entwurf"})
    session.refresh(post)
    assert post.status == "entwurf"
    assert "Kreditkosten" in rendered(web.get("/linkedin"))


def test_a_published_link_must_be_https(web, session):
    body = rendered(web.post("/linkedin", data={"title": "x", "client_id": "1", "published_url": "javascript:alert(1)"}))
    assert "https://" in body
    assert session.scalar(select(LinkedInPost)) is None


# --- Sales CRM ------------------------------------------------------------------


def test_a_deal_is_created_and_the_pipeline_sums_its_value(web, session):
    web.post("/sales", data={"company": "Fountainhead Digital", "value_eur": "4.900", "stage": "angebot"})
    deal = session.scalar(select(Deal))
    assert deal.value_eur == 4900
    columns = {c["stage"]: c for c in worklists.pipeline(worklists.deals(session))}
    assert columns["angebot"]["value"] == 4900 and columns["lead"]["value"] == 0
    assert "Fountainhead Digital" in rendered(web.get("/sales"))


def test_a_closed_deal_is_stamped_and_reopening_clears_it(web, session):
    web.post("/sales", data={"company": "Zenchef"})
    deal = session.scalar(select(Deal))
    web.post(f"/sales/{deal.id}", data={"stage": "gewonnen"})
    session.refresh(deal)
    assert deal.closed_at is not None
    web.post(f"/sales/{deal.id}", data={"stage": "verhandlung"})
    session.refresh(deal)
    assert deal.closed_at is None
    # Winning a deal does not create a mandate.
    assert session.scalar(select(Client).where(Client.name == "Zenchef")) is None


@pytest.mark.parametrize("form,reason", [
    ({"company": ""}, "Bitte das Unternehmen nennen."),
    ({"company": "x", "contact_email": "keine-mail"}, "Keine gültige E-Mail-Adresse."),
    ({"company": "x", "value_eur": "viel"}, "ganze Zahl in Euro"),
])
def test_an_invalid_deal_is_refused(web, session, form, reason):
    assert reason in rendered(web.post("/sales", data=form))
    assert session.scalar(select(Deal)) is None


# --- Navigation -----------------------------------------------------------------


def test_the_sidebar_carries_the_three_new_areas(web):
    side = rendered(web.get("/aufgaben")).split('<aside class="side">', 1)[1].split("</aside>", 1)[0]
    for href in ("/aufgaben", "/linkedin", "/sales"):
        assert f'href="{href}" class="side__row' in side
    assert "Wachstum" in side


# --- LinkedIn: what RauteOS already has -----------------------------------------


def _linkedin_text(session, *, released=False):
    from newspulse.models import Angle, Asset
    angle = Angle(client_id=1, subject="Kreditkosten im Mittelstand", message="m", context="c", thesis="t", statements=[])
    session.add(angle)
    session.flush()
    asset = Asset(client_id=1, angle_id=angle.id, kind="linkedin", title="",
                  body="Kredite werden teurer.\n\nWas das für Gründer heißt.", speaker="Alexandre Prot",
                  released_at=dt.datetime.now(dt.UTC) if released else None)
    session.add(asset)
    session.commit()
    return asset


def test_a_linkedin_text_rauteos_wrote_is_suggested_and_taken_over_once(web, session):
    asset = _linkedin_text(session, released=True)
    texts = worklists.suggestions(session)["texts"]
    assert [(t["id"], t["title"], t["speaker"]) for t in texts] == [(asset.id, "Kredite werden teurer.", "Alexandre Prot")]
    assert "Kredite werden teurer." in rendered(web.get("/linkedin"))

    for _ in range(2):
        assert web.post(f"/linkedin/from-text/{asset.id}", follow_redirects=False).status_code == 303
    post = session.scalar(select(LinkedInPost))
    assert (post.client_id, post.asset_id, post.status, post.author) == (1, asset.id, "freigabe", "Alexandre Prot")
    assert post.body.startswith("Kredite werden teurer.")
    assert len(session.scalars(select(LinkedInPost)).all()) == 1
    assert worklists.suggestions(session)["texts"] == []


def test_an_unreleased_text_starts_as_a_draft_and_another_format_is_a_404(web, session):
    from newspulse.models import Asset
    asset = _linkedin_text(session)
    web.post(f"/linkedin/from-text/{asset.id}")
    assert session.scalar(select(LinkedInPost)).status == "entwurf"
    other = Asset(client_id=1, angle_id=asset.angle_id, kind="statement", title="x", body="y")
    session.add(other)
    session.commit()
    assert web.post(f"/linkedin/from-text/{other.id}").status_code == 404


def test_an_open_chance_becomes_an_idea_once(web, session, monkeypatch):
    href = "/client/1/opportunities?kind=developed&context=7"
    chance = desk.Chance(client=session.get(Client, 1), kind="developed", title="Kreditkosten", status="draft",
                         since=None, href=href)
    monkeypatch.setattr(desk, "_chances", lambda s, clients, limit=6: [chance])
    assert [c["href"] for c in worklists.suggestions(session)["chances"]] == [href]
    form = {"client_id": "1", "title": "Kreditkosten", "context_href": href}
    web.post("/linkedin/from-chance", data=form)
    web.post("/linkedin/from-chance", data=form)
    post = session.scalar(select(LinkedInPost))
    assert (post.status, post.context_href, post.title) == ("idee", href, "Kreditkosten")
    assert len(session.scalars(select(LinkedInPost)).all()) == 1
    assert worklists.suggestions(session)["chances"] == []
    assert f'href="{href}"' in rendered(web.get("/linkedin")).replace("&amp;", "&")


def test_a_chance_from_outside_rauteos_is_refused(web, session):
    body = rendered(web.post("/linkedin/from-chance", data={"client_id": "1", "title": "x", "context_href": "https://evil.example"}))
    assert "innerhalb von RauteOS" in body
    assert session.scalar(select(LinkedInPost)) is None


# --- Links and counts that must agree (review 2026-11-06) ------------------------


def test_every_open_task_counts_as_due_not_just_the_five_shown(session):
    for i in range(7):
        worklists.save_task(session, {"title": f"t{i}", "due_on": "2026-01-01"})
    board = desk.build(session)
    assert (len(board.tasks), board.tasks_open, board.tasks_due) == (5, 7, 7)


def test_the_task_manager_lists_by_person_client_and_internal(web, session):
    worklists.save_task(session, {"title": "Pitch Qonto", "client_id": "1", "assignees": ["lucas"]})
    worklists.save_task(session, {"title": "Medienliste", "assignees": ["raphael", "lucas"]})
    worklists.save_task(session, {"title": "fertig", "status": "erledigt"})
    body = rendered(web.get("/aufgaben"))
    for option in ('value="heute"', 'value="lucas"', 'value="raphael"',
                   'value="intern"', 'value="kunde"', 'value="1"'):
        assert option in body
    assert 'title="Lucas"' in body and 'title="Raphael"' in body
    assert "Pitch Qonto" in body and "Medienliste" in body


def test_tags_are_saved_and_an_unknown_person_is_refused(web, session):
    web.post("/aufgaben", data={"title": "Zwei Leute", "assignees": ["raphael", "lucas"]})
    assert session.scalar(select(Task)).assignees == ["raphael", "lucas"]
    assert "Unbekannte Person." in rendered(web.post("/aufgaben", data={"title": "x", "assignees": "eve"}))


def test_a_task_added_in_a_list_lands_in_it_and_comes_back_there(web, session):
    response = web.post("/aufgaben", data={"title": "Für Qonto", "client_id": "1",
                                           "redirect_to": "/aufgaben?liste=kunde%3A1"}, follow_redirects=False)
    assert response.headers["location"] == "/aufgaben?liste=kunde%3A1"
    assert session.scalar(select(Task)).client_id == 1


def test_the_star_changes_only_the_priority(web, session):
    worklists.save_task(session, {"title": "Behalten", "client_id": "1", "note": "Notiz",
                                  "due_on": "2026-12-01", "assignees": ["lucas"]})
    task = session.scalar(select(Task))
    web.post(f"/aufgaben/{task.id}", data={"priority": "hoch", "redirect_to": "/aufgaben?liste=wichtig"})
    session.refresh(task)
    assert (task.priority, task.client_id, task.note, task.assignees) == ("hoch", 1, "Notiz", ["lucas"])
    assert task.due_on == dt.date(2026, 12, 1)


def test_the_signed_in_person_is_known_by_either_address():
    assert worklists.member_for("L.Neurauter@raute-kopf.com") == "lucas"
    assert worklists.member_for("raphaelmankopf@gmail.com") == "raphael"
    assert worklists.member_for("someone@else.example") is None


def test_a_mandates_next_steps_start_with_its_tasks(web, session):
    worklists.save_task(session, {"title": "Statement abstimmen", "client_id": "1", "due_on": "2026-11-09"})
    worklists.save_task(session, {"title": "Agenturarbeit"})
    steps = web.get("/api/v1/workbench/clients/1").json()["next_steps"]
    assert [(s["kind"], s["title"], s["detail"]) for s in steps] == [("aufgabe", "Statement abstimmen", "fällig 09.11.2026")]


def test_a_text_link_names_its_occasion_and_an_anchor_that_exists(session):
    from newspulse import workspaces
    asset = _linkedin_text(session)
    href = workspaces.text_href(session, asset)
    assert href == f"/client/1/advice?eintrag=anlass-{asset.angle_id}#asset-text-{asset.id}"
    from pathlib import Path
    template = Path(workspaces.__file__).parent / "web/templates/advice.html"
    assert 'id="asset-text-{{ asset.id }}"' in template.read_text()
    assert 'id="letter-text-{{ msg.id }}"' in template.read_text()


def test_dragging_a_task_to_review_keeps_its_details(web, session):
    web.post("/aufgaben", data={"title": "Review pitch", "assignees": ["raphael", "lucas"],
        "priority": "hoch", "due_on": "2026-11-12", "client_id": "1", "note": "Keep this"})
    task = session.scalar(select(Task))
    response = web.post(f"/aufgaben/{task.id}", data={"status": "review"},
                        headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert response.json() == {"id": task.id, "status": "review"}
    session.refresh(task)
    assert task.assignees == ["raphael", "lucas"]
    assert (task.note, task.priority, task.client_id, task.done_at) == ("Keep this", "hoch", 1, None)
    assert task.due_on == dt.date(2026, 11, 12)
    response = web.post(f"/aufgaben/{task.id}", data={"status": "unknown"},
                        headers={"Accept": "application/json"})
    assert response.status_code == 422
    session.refresh(task)
    assert task.status == "review"


def test_workspaces_keep_tasks_separate_and_can_be_created_and_changed(web, session):
    response = web.post("/aufgaben/boards", data={"workspace_name": "Operations"}, follow_redirects=False)
    assert response.status_code == 303
    board = session.scalar(select(TaskBoard).where(TaskBoard.name == "Operations"))
    assert response.headers["location"] == f"/aufgaben?board={board.id}"
    response = web.post("/aufgaben/boards", data={"workspace_name": " operations "})
    assert "existiert bereits" in response.text
    web.post("/aufgaben", data={"title": "Only Operations", "board_id": str(board.id), "status": "review"})
    task = session.scalar(select(Task).where(Task.title == "Only Operations"))
    assert task.board_id == board.id
    assert "Only Operations" in rendered(web.get(f"/aufgaben?board={board.id}"))
    assert "Only Operations" not in rendered(web.get("/aufgaben"))
    assert "Only Operations" in rendered(web.get("/aufgaben?board=all"))
    other = session.scalar(select(TaskBoard).where(TaskBoard.system_key == "rauteos"))
    web.post(f"/aufgaben/{task.id}", data={"title": task.title, "board_id": str(other.id), "status": "review"})
    session.refresh(task)
    assert task.board_id == other.id
    assert "Only Operations" in rendered(web.get(f"/aufgaben?board={other.id}"))
    assert "Only Operations" not in rendered(web.get(f"/aufgaben?board={board.id}"))
    response = web.post("/aufgaben", data={"title": "Invalid", "board_id": "999999"})
    assert "Unbekannter Workspace" in response.text


def test_decision_board_is_idempotent_and_status_does_not_approve_source(web, session):
    _client_letter(session)
    web.get("/aufgaben?workspace=decisions")
    task = session.scalar(select(Task).where(Task.source_key.is_not(None)))
    letter = session.scalar(select(Outreach))
    board = session.scalar(select(TaskBoard).where(TaskBoard.system_key == "decisions"))
    assert task.board_id == board.id and task.status == "offen"
    assert task.source_key == f"outreach:{letter.id}"
    web.post(f"/aufgaben/{task.id}", data={"status": "review"})
    web.get("/aufgaben?workspace=decisions")
    session.refresh(task)
    assert task.status == "review"
    web.post(f"/aufgaben/{task.id}", data={"status": "erledigt"})
    web.get("/aufgaben?workspace=decisions")
    session.refresh(letter)
    assert letter.state == OutreachState.ENTWURF and letter.client_ok_at is None
    assert len(list(session.scalars(select(Task).where(Task.source_key.is_not(None))))) == 1
    assert web.post(f"/aufgaben/{task.id}/delete").status_code == 400
    # Advancing the source gate must reuse the same card, not create another.
    letter.client_ok_at = dt.datetime.now(dt.UTC)
    session.commit()
    web.get("/aufgaben?workspace=decisions")
    session.refresh(task)
    assert task.source_kind == "freigabe" and task.status == "erledigt"
    letter.state = OutreachState.RAUS
    session.commit()
    web.get("/aufgaben?workspace=decisions")
    session.refresh(task)
    assert task.source_open is False and task.status == "erledigt"
    letter.state = OutreachState.ENTWURF
    session.commit()
    web.get("/aufgaben?workspace=decisions")
    session.refresh(task)
    assert task.source_open is True and task.status == "offen"
