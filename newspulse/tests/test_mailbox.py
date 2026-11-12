"""Gmail inside RauteOS: read live, filtered by client, sent with Drive assets."""
from __future__ import annotations

import base64
import email

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse import drive_link, gmail_link, mailbox
from newspulse.models import Base, Client, ClientPerson
from newspulse.web.app import create_app, get_db


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(factory):
    with factory() as s:
        yield s


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


@pytest.fixture
def client_row(session):
    row = Client(name="Remexian Pharma GmbH", aliases=["Remexian"], website="https://www.remexian.com")
    session.add(row)
    session.flush()
    session.add(ClientPerson(client_id=row.id, name="Anna Beispiel", email="anna@agentur-extern.de"))
    session.commit()
    return row


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def test_a_client_filter_searches_its_domain_people_and_name(session, client_row):
    query = mailbox.client_query(session, client_row)
    for part in ("from:remexian.com", "to:remexian.com", "from:anna@agentur-extern.de", '"Remexian Pharma GmbH"', '"Remexian"'):
        assert part in query
    assert query.startswith("{") and query.endswith("}")


def test_threads_are_listed_with_sender_subject_and_unread(monkeypatch):
    calls = []

    def api(url, **kwargs):
        calls.append(url)
        if "threads?" in url:
            return {"threads": [{"id": "t1", "snippet": "Hallo &amp; danke"}], "nextPageToken": "n2"}
        return {"messages": [
            {"labelIds": ["INBOX"], "payload": {"headers": [{"name": "Subject", "value": "Statement"},
                                                             {"name": "From", "value": "A <a@x.de>"},
                                                             {"name": "Date", "value": "Thu, 12 Nov 2026 09:00:00 +0100"}]}},
            {"labelIds": ["INBOX", "UNREAD"], "payload": {"headers": [{"name": "From", "value": "Lena Muster <lena@remexian.com>"},
                                                                       {"name": "Date", "value": "Thu, 12 Nov 2026 10:00:00 +0100"}]}}]}

    monkeypatch.setattr(mailbox, "_api", api)
    found = mailbox.threads("inbox", query="{from:remexian.com}")
    row = found["threads"][0]
    assert (row.subject, row.sender, row.snippet, row.count, row.unread) == ("Statement", "Lena Muster", "Hallo & danke", 2, True)
    assert found["next_page_token"] == "n2"
    assert "labelIds=INBOX" in calls[0] and "q=%7Bfrom%3Aremexian.com%7D" in calls[0]


def test_an_html_only_mail_is_read_as_text_never_as_markup(monkeypatch):
    markup = "<html><style>p{}</style><p>Guten Tag,</p><p>danke &amp; Gruß<script>x()</script></p></html>"
    monkeypatch.setattr(mailbox, "_api", lambda url, **k: {"messages": [{"id": "m1", "payload": {
        "headers": [{"name": "From", "value": "Lena <lena@remexian.com>"}, {"name": "Message-ID", "value": "<id@x>"}],
        "mimeType": "multipart/mixed", "parts": [
            {"mimeType": "text/html", "body": {"data": _b64(markup)}},
            {"mimeType": "application/pdf", "filename": "Briefing.pdf", "body": {"attachmentId": "a"}}]}}]})
    message = mailbox.thread("t1")[0]
    assert message.body == "Guten Tag,\n\ndanke & Gruß"
    assert message.attachments == ["Briefing.pdf"] and message.message_id_header == "<id@x>"


def test_a_reply_carries_its_thread_and_the_drive_assets(web, monkeypatch, client_row):
    monkeypatch.setattr(gmail_link, "connected", lambda: type("L", (), {"email": "raphael@raute-kopf.com", "may_send": True})())
    monkeypatch.setattr(drive_link, "download", lambda file_id: ("Statement.pdf", "application/pdf", b"%PDF-1.4 test"))
    sent = {}

    def fake_api(url, *, json_body=None, what="", **kwargs):
        sent["payload"] = json_body
        return {"id": "d1"}

    monkeypatch.setattr(gmail_link, "_api", fake_api)
    monkeypatch.setattr(gmail_link, "send", lambda draft_id: type("S", (), {"message_id": "m9", "thread_id": "t1"})())
    answer = web.post("/api/v1/mailbox/send", json={"to": "lena@remexian.com", "subject": "Re: Statement", "body": "Anbei.",
                                                     "thread_id": "t1", "reply_to": "<id@x>", "drive_files": ["f1"]})
    assert answer.status_code == 200 and answer.json() == {"message_id": "m9", "thread_id": "t1"}
    assert sent["payload"]["message"]["threadId"] == "t1"
    raw = base64.urlsafe_b64decode(sent["payload"]["message"]["raw"])
    parsed = email.message_from_bytes(raw)
    assert parsed["In-Reply-To"] == "<id@x>" and parsed["To"] == "lena@remexian.com"
    assert [p.get_filename() for p in parsed.walk() if p.get_filename()] == ["Statement.pdf"]


def test_a_mailbox_without_send_rights_does_not_send(web, monkeypatch):
    monkeypatch.setattr(gmail_link, "connected", lambda: type("L", (), {"email": "x", "may_send": False})())
    refused = web.post("/api/v1/mailbox/send", json={"to": "a@b.de", "subject": "x", "body": "y"})
    assert refused.status_code == 409


def test_bad_recipients_are_refused_before_gmail():
    with pytest.raises(ValueError):
        mailbox.compose("kein-empfaenger", "x", "y")


def test_the_page_and_the_status_render(web, client_row, monkeypatch):
    monkeypatch.setattr(gmail_link, "connected", lambda: None)
    assert web.get("/gmail").status_code == 200
    status = web.get("/api/v1/mailbox").json()
    assert status["connected"] is False and status["clients"] == [{"id": client_row.id, "name": "Remexian Pharma GmbH"}]
