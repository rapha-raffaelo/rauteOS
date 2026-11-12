"""Gmail inside RauteOS: the page and its API (see :mod:`newspulse.mailbox`).

Every answer here is read from Gmail on request and handed on; nothing of the
mailbox is written to the database.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import drive_link, gmail_link, mailbox
from ...models import Client
from .. import frontend
from ..app import get_db, templates
from ..mandates import mandate_or_404
from .today import _fetch_last_run, _local_tz

router = APIRouter()


@router.get("/gmail")
def mailbox_page(request: Request, session: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "mailbox_react.html", dict(
        frontend=frontend.page_assets("mailbox"), last_run=_fetch_last_run(session),
        header_date=dt.datetime.now(_local_tz()).date()))


def _guarded(work):
    try:
        return work()
    except gmail_link.GmailError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/api/v1/mailbox")
def status(response: Response, session: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    link = gmail_link.connected()
    clients = session.scalars(select(Client).where(Client.active.is_(True), Client.is_competitor.is_(False))
                              .order_by(Client.name))
    return dict(connected=link is not None, email=link.email if link else "",
                may_send=bool(link and link.may_send), drive=drive_link.connected() is not None,
                clients=[dict(id=c.id, name=c.name) for c in clients])


@router.get("/api/v1/mailbox/threads")
def threads(response: Response, folder: str = "inbox", client: int | None = None, q: str = "",
            page_token: str = "", session: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    parts = [q.strip()[:300]]
    if client:
        query = mailbox.client_query(session, mandate_or_404(session, client))
        if not query:
            return dict(threads=[], next_page_token="", note="Für diesen Kunden ist keine Website und keine Kontakt-E-Mail hinterlegt.")
        parts.append(query)
    found = _guarded(lambda: mailbox.threads(folder, query=" ".join(p for p in parts if p), page_token=page_token))
    return dict(threads=[asdict(t) for t in found["threads"]], next_page_token=found["next_page_token"])


@router.get("/api/v1/mailbox/threads/{thread_id}")
def thread(thread_id: str, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return dict(messages=[asdict(m) for m in _guarded(lambda: mailbox.thread(thread_id))])


@router.get("/api/v1/mailbox/assets")
def assets(client: int, response: Response, session: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    row = mandate_or_404(session, client)
    try:
        return dict(files=drive_link.client_files(row.name), folder=f"7. Assets › {row.name}")
    except drive_link.DriveError as exc:
        raise HTTPException(409, str(exc)) from exc


class SendInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    to: str = Field(min_length=3, max_length=2000)
    cc: str = Field(default="", max_length=2000)
    subject: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=100000)
    thread_id: str = Field(default="", max_length=100)
    reply_to: str = Field(default="", max_length=500)
    drive_files: list[str] = Field(default_factory=list, max_length=10)


@router.post("/api/v1/mailbox/send")
def send(body: SendInput):
    link = gmail_link.connected()
    if link is None or not link.may_send:
        raise HTTPException(409, "Das Postfach darf nicht senden. Unter Einstellungen mit Senderechten verbinden.")
    try:
        files = [drive_link.download(file_id) for file_id in body.drive_files]
        raw = mailbox.compose(body.to, body.subject, body.body, cc=body.cc, reply_to_id=body.reply_to,
                              attachments=files)
    except drive_link.DriveError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _guarded(lambda: mailbox.send(raw, thread_id=body.thread_id))
