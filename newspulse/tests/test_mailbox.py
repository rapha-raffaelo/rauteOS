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
    found = mailbox.threads("inbox", query="{from:remexian.com}", me="a@x.de")
    row = found["threads"][0]
    assert (row.subject, row.sender, row.snippet, row.count, row.unread) == ("Statement", "Ich, Lena", "Hallo & danke", 2, True)
    assert found["next_page_token"] == "n2"
    assert "labelIds=INBOX" in calls[0] and "q=%7Bfrom%3Aremexian.com%7D" in calls[0]


def test_an_html_mail_keeps_its_layout_but_nothing_that_runs(monkeypatch):
    markup = "<html><style>p{}</style><p>Guten Tag,</p><p>danke &amp; Gruß<script>x()</script></p></html>"
    monkeypatch.setattr(mailbox, "_api", lambda url, **k: {"messages": [{"id": "m1", "payload": {
        "headers": [{"name": "From", "value": "Lena <lena@remexian.com>"}, {"name": "Message-ID", "value": "<id@x>"}],
        "mimeType": "multipart/mixed", "parts": [
            {"mimeType": "text/html", "body": {"data": _b64(markup)}},
            {"mimeType": "application/pdf", "filename": "Briefing.pdf", "partId": "1", "body": {"attachmentId": "a"}}]}}]})
    message = mailbox.thread("t1")[0]
    assert message.body == "Guten Tag,\n\ndanke & Gruß"
    assert "<script" not in message.html and "<p>Guten Tag,</p>" in message.html
    assert [a.name for a in message.attachments] == ["Briefing.pdf"] and message.message_id_header == "<id@x>"


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


def test_clean_html_takes_out_what_could_run_and_keeps_inline_images():
    dirty = ('<div style="color:red" onclick="x()"><a href="javascript:alert(1)">a</a><a href="https://x.de">b</a>'
             '<img src="cid:logo@x"><iframe src="https://evil"></iframe><form action="/x"><input></form>'
             '<img src="data:image/png;base64,AAAA"><svg><script>y()</script></svg></div>')
    clean = mailbox.clean_html(dirty, {"logo@x": "/api/v1/mailbox/messages/m1/parts/2"})
    assert "onclick" not in clean and "javascript" not in clean and "iframe" not in clean and "<form" not in clean
    assert 'href="https://x.de" target="_blank"' in clean and 'src="/api/v1/mailbox/messages/m1/parts/2"' in clean
    assert "data:image/png" in clean and "y()" not in clean and 'style="color:red"' in clean


def test_a_formatted_mail_goes_out_as_html_with_text_and_inline_image():
    raw = mailbox.compose("a@b.de", "Hallo", "", bcc="c@d.de", html_body='<p><b>Fett</b></p><img src="data:image/png;base64,iVBORw0KGgo=">')
    parsed = email.message_from_bytes(base64.urlsafe_b64decode(raw))
    types = [p.get_content_type() for p in parsed.walk()]
    assert "text/plain" in types and "text/html" in types and "image/png" in types and parsed["Bcc"] == "c@d.de"
    html_part = next(p for p in parsed.walk() if p.get_content_type() == "text/html").get_payload(decode=True).decode()
    assert "<b>Fett</b>" in html_part and "cid:" in html_part and "data:" not in html_part


def _manager(monkeypatch, scopes=("https://www.googleapis.com/auth/gmail.modify",)):
    monkeypatch.setattr(gmail_link, "connected", lambda: gmail_link.Link(email="r@raute.de", scopes=scopes))


def test_row_actions_relabel_or_trash_and_need_the_modify_grant(web, monkeypatch):
    calls = []
    monkeypatch.setattr(mailbox, "_api", lambda url, **k: calls.append((url, k.get("json_body"))) or {})
    _manager(monkeypatch)
    assert web.post("/api/v1/mailbox/threads/modify", json={"ids": ["t1", "t2"], "action": "archive"}).json() == {"changed": 2}
    assert calls[0][0].endswith("/threads/t1/modify") and calls[0][1] == {"addLabelIds": [], "removeLabelIds": ["INBOX"]}
    web.post("/api/v1/mailbox/threads/modify", json={"ids": ["t3"], "action": "trash"})
    assert calls[-1][0].endswith("/threads/t3/trash")
    _manager(monkeypatch, scopes=gmail_link.SCOPES[:2])
    assert web.post("/api/v1/mailbox/threads/modify", json={"ids": ["t1"], "action": "read"}).status_code == 409


def test_an_attachment_is_a_download_unless_it_is_a_plain_image(web, monkeypatch):
    monkeypatch.setattr(mailbox, "part", lambda m, p: ("seite.html", "text/html", b"<script>x()</script>"))
    page = web.get("/api/v1/mailbox/messages/m1/parts/2")
    assert page.headers["content-type"] == "application/octet-stream" and page.headers["content-disposition"].startswith("attachment")
    monkeypatch.setattr(mailbox, "part", lambda m, p: ("logo.png", "image/png", b"PNG"))
    image = web.get("/api/v1/mailbox/messages/m1/parts/2")
    assert image.headers["content-type"] == "image/png" and image.headers["content-disposition"].startswith("inline")


def test_the_signature_is_kept_and_cleaned(web):
    saved = web.put("/api/v1/mailbox/signature", json={"html": '<p onclick="x()">Raphael<br>raute+kopf</p>'}).json()
    assert saved["html"] == "<p>Raphael<br>raute+kopf</p>"
    assert web.get("/api/v1/mailbox/signature").json()["html"] == saved["html"]


def test_closing_the_window_keeps_a_draft_without_recipient(web, monkeypatch):
    _manager(monkeypatch, scopes=gmail_link.SCOPES)
    kept = {}
    monkeypatch.setattr(gmail_link, "_api", lambda url, *, json_body=None, what="", **k: kept.update(body=json_body) or {"id": "d7"})
    assert web.post("/api/v1/mailbox/draft", json={"subject": "Halb fertig", "html": "<p>Idee</p>"}).json() == {"draft_id": "d7"}
    parsed = email.message_from_bytes(base64.urlsafe_b64decode(kept["body"]["message"]["raw"]))
    assert parsed["To"] is None and parsed["Subject"] == "Halb fertig"


def test_a_conversation_read_once_is_not_read_again_until_it_changes(monkeypatch):
    mailbox.forget()
    calls = []

    def api(url, **kwargs):
        calls.append(url)
        if "threads?" in url:
            return {"threads": [{"id": "t1", "historyId": history[0], "snippet": "x"}, {"id": "t2", "historyId": "5", "snippet": "y"}]}
        if "/labels/" in url:
            return {"threadsTotal": 2, "threadsUnread": 1}
        return {"historyId": history[0], "messages": [{"id": "m", "labelIds": ["INBOX"], "payload": {"headers": [{"name": "Subject", "value": "S"}]}}]}

    history = ["9"]
    monkeypatch.setattr(mailbox, "_api", api)
    first = mailbox.threads("inbox")
    assert [r.history_id for r in first["threads"]] == ["9", "5"]
    reads = sum("/threads/t" in c for c in calls)
    mailbox.threads("inbox")
    assert sum("/threads/t" in c for c in calls) == reads, "unchanged conversations come from memory"
    history[0] = "10"
    mailbox.threads("inbox")
    assert sum("/threads/t1" in c for c in calls) == 2, "a changed one is read again"
    mailbox.thread("t1")
    before = len(calls)
    mailbox.thread("t1", history_id="10")
    assert len(calls) == before
    mailbox.forget()


def test_accounts_are_isolated_through_authenticated_requests(web, monkeypatch, tmp_path):
    import json
    from newspulse import config, mail_identity
    from newspulse.web import google_auth
    monkeypatch.setattr(config, 'DATABASE_PATH', tmp_path / 'test.db')
    monkeypatch.setattr(google_auth, 'is_configured', lambda: True)
    monkeypatch.setattr(google_auth, 'read_session', lambda cookie: {'r':'r.mankopf@raute-kopf.com','l':'l.neurauter@raute-kopf.com'}.get(cookie))
    monkeypatch.setattr(google_auth, 'session_name', lambda _: '')
    for owner, email in [('raphael','r.mankopf@raute-kopf.com'),('lucas','l.neurauter@raute-kopf.com')]:
        token=mail_identity.owner.set(owner)
        try:
            gmail_link._write({'email':email,'refresh_token':'test-'+owner,'scopes':list(gmail_link.SCOPES),'connected_at':'2026-11-13T00:00:00+00:00'})
        finally:
            mail_identity.owner.reset(token)
    for cookie,email in [('r','r.mankopf@raute-kopf.com'),('l','l.neurauter@raute-kopf.com')]:
        web.cookies.set(google_auth.SESSION_COOKIE,cookie)
        assert web.get('/api/v1/mailbox').json()['email']==email
        assert web.put('/api/v1/mailbox/signature',json={'html':email}).status_code==200
    web.cookies.set(google_auth.SESSION_COOKIE,'r')
    assert 'r.mankopf' in web.get('/api/v1/mailbox/signature').json()['html']
    assert mail_identity.owner.get()==''
    assert gmail_link.connected() is None, 'unscoped jobs cannot use personal credentials'
    # A callback started in Lucas's session cannot connect into Raphael's session.
    web.cookies.set('newspulse_gmail_state','lucas.test')
    exchange=__import__('unittest.mock',fromlist=['Mock']).Mock()
    monkeypatch.setattr(gmail_link,'exchange',exchange)
    web.get('/settings/gmail/callback?state=lucas.test&code=test',follow_redirects=False)
    exchange.assert_not_called()


def test_mail_worker_threads_keep_the_request_owner(monkeypatch):
    from newspulse import mail_identity
    from contextvars import copy_context
    from concurrent.futures import ThreadPoolExecutor
    def listing(owner):
        token=mail_identity.owner.set(owner)
        try:
            return mailbox.threads('inbox')
        finally:
            mail_identity.owner.reset(token)
    def api(url, **kwargs):
        owner=mail_identity.owner.get()
        assert owner in {'raphael','lucas'}
        if '/threads?' in url:
            return {'threads':[{'id':'1'},{'id':'2'}]}
        if '/threads/' in url:
            return {'messages':[{'payload':{'headers':[{'name':'Subject','value':owner}]}}]}
        return {'threadsTotal':2,'threadsUnread':0}
    monkeypatch.setattr(mailbox,'_api',api)
    monkeypatch.setattr(mailbox,'_account',lambda:mail_identity.owner.get())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(listing,['raphael','lucas']))
    assert [r['threads'][0].subject for r in results]==['raphael','lucas']


def test_token_use_disconnect_and_wrong_account_consent_are_scoped(monkeypatch, tmp_path):
    from newspulse import config, mail_identity
    import datetime as dt
    monkeypatch.setattr(config, 'DATABASE_PATH', tmp_path / 'test.db')
    for name,address in [('raphael','r.mankopf@raute-kopf.com'),('lucas','l.neurauter@raute-kopf.com')]:
        token=mail_identity.owner.set(name)
        try:
            gmail_link._write({'email':address,'refresh_token':'refresh-'+name,'access_token':'access-'+name,
                'expires_at':(dt.datetime.now(dt.UTC)+dt.timedelta(hours=1)).isoformat()})
            observed=[]
            gmail_link._api('https://gmail.googleapis.com/test',what='test',fetch=lambda url,**kw: observed.append(kw['token']) or {})
            assert observed == ['access-'+name]
        finally:
            mail_identity.owner.reset(token)
    token=mail_identity.owner.set('raphael')
    try:
        def wrong_google(url,**kw):
            if url==gmail_link._TOKEN_ENDPOINT:
                return {'access_token':'new','refresh_token':'new'}
            return {'emailAddress':'l.neurauter@raute-kopf.com'}
        with pytest.raises(gmail_link.GmailError,match='eigene Google-Konto'):
            gmail_link.exchange('code',fetch=wrong_google)
        assert gmail_link._read()['access_token']=='access-raphael'
        gmail_link.disconnect(fetch=lambda *a,**k:{})
        assert gmail_link.connected() is None
        assert (tmp_path/'gmail_token_lucas.json').exists()
    finally:
        mail_identity.owner.reset(token)
