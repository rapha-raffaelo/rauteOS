"""Gmail inside RauteOS: the page and its API (see :mod:`newspulse.mailbox`).

Every answer here is read from Gmail on request and handed on; nothing of the
mailbox is written to the database. The signature is the one thing kept.
"""
from __future__ import annotations

import base64
import binascii
import datetime as dt
import urllib.parse
from dataclasses import asdict
from typing import Literal

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
    except gmail_link.GmailMissing as exc:
        raise HTTPException(404, str(exc)) from exc
    except gmail_link.GmailError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/api/v1/mailbox")
def status(response: Response, session: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    link = gmail_link.connected()
    clients = session.scalars(select(Client).where(Client.active.is_(True), Client.is_competitor.is_(False))
                              .order_by(Client.name))
    return dict(connected=link is not None, email=link.email if link else "",
                may_send=bool(link and link.may_send), may_manage=mailbox.may_manage(link),
                drive=drive_link.connected() is not None, signature=mailbox.signature(session),
                clients=[dict(id=c.id, name=c.name) for c in clients])


@router.get("/api/v1/mailbox/threads")
def threads(response: Response, folder: str = "inbox", client: int | None = None, q: str = "",
            page_token: str = "", session: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    parts = [q.strip()[:300]]
    if client:
        query = mailbox.client_query(session, mandate_or_404(session, client))
        if not query:
            return dict(threads=[], next_page_token="", total=0, unread_inbox=None,
                        note="Für diesen Kunden ist keine Website und keine Kontakt-E-Mail hinterlegt.")
        parts.append(query)
    link = gmail_link.connected()
    found = _guarded(lambda: mailbox.threads(folder, query=" ".join(p for p in parts if p), page_token=page_token,
                                             me=link.email if link else ""))
    return dict(found, threads=[asdict(t) for t in found["threads"]])


@router.get("/api/v1/mailbox/threads/{thread_id}")
def thread(thread_id: str, response: Response, h: str = ""):
    response.headers["Cache-Control"] = "no-store"
    return dict(messages=[asdict(m) for m in _guarded(lambda: mailbox.thread(thread_id, history_id=h[:40]))])


class ModifyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[str] = Field(min_length=1, max_length=100)
    action: Literal["archive", "inbox", "read", "unread", "star", "unstar", "spam", "notspam", "trash", "untrash"]


@router.post("/api/v1/mailbox/threads/modify")
def modify(body: ModifyInput):
    if not mailbox.may_manage(gmail_link.connected()):
        raise HTTPException(409, "Das Postfach ist ohne Verwaltungsrechte verbunden. Unter Einstellungen einmal neu verbinden.")
    return dict(changed=_guarded(lambda: mailbox.modify(body.ids, body.action)))


@router.get("/api/v1/mailbox/messages/{message_id}/parts/{part_id}")
def attachment(message_id: str, part_id: str, download: bool = False):
    name, mime, data = _guarded(lambda: mailbox.part(message_id, part_id))
    inline = mime.casefold() in mailbox.INLINE_TYPES and not download
    quoted = urllib.parse.quote(name)
    return Response(data, media_type=mime if inline else "application/octet-stream", headers={
        "Content-Disposition": f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quoted}",
        "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'",
        "Cache-Control": "private, max-age=3600"})


@router.get("/api/v1/mailbox/assets")
def assets(client: int, response: Response, session: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    row = mandate_or_404(session, client)
    try:
        return dict(files=drive_link.client_files(row.name), folder=f"7. Assets › {row.name}")
    except drive_link.DriveError as exc:
        raise HTTPException(409, str(exc)) from exc


class SignatureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    html: str = Field(default="", max_length=2_000_000)


@router.get("/api/v1/mailbox/signature")
def get_signature(session: Session = Depends(get_db)):
    return dict(html=mailbox.signature(session))


@router.put("/api/v1/mailbox/signature")
def put_signature(body: SignatureInput, session: Session = Depends(get_db)):
    return dict(html=mailbox.save_signature(session, body.html))


class Upload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=300)
    mime: str = Field(default="application/octet-stream", max_length=200)
    data: str = Field(max_length=30_000_000)  # base64


class Forwarded(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(max_length=100)
    part_id: str = Field(max_length=50)


class SendInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    to: str = Field(default="", max_length=2000)
    cc: str = Field(default="", max_length=2000)
    bcc: str = Field(default="", max_length=2000)
    subject: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=100000)
    html: str = Field(default="", max_length=25_000_000)
    thread_id: str = Field(default="", max_length=100)
    reply_to: str = Field(default="", max_length=500)
    references: str = Field(default="", max_length=5000)
    drive_files: list[str] = Field(default_factory=list, max_length=10)
    uploads: list[Upload] = Field(default_factory=list, max_length=20)
    forwarded: list[Forwarded] = Field(default_factory=list, max_length=20)


def _raw(body: SendInput, *, draft: bool = False) -> str:
    try:
        files = [drive_link.download(file_id) for file_id in body.drive_files]
        for upload in body.uploads:
            try:
                files.append((upload.name, upload.mime, base64.b64decode(upload.data, validate=True)))
            except (binascii.Error, ValueError) as exc:
                raise ValueError(f"Die Datei {upload.name} ließ sich nicht lesen.") from exc
        files += [_guarded(lambda f=f: mailbox.part(f.message_id, f.part_id)) for f in body.forwarded]
        return mailbox.compose(body.to, body.subject, body.body, draft=draft,
                               cc=body.cc, bcc=body.bcc, reply_to_id=body.reply_to, references=body.references,
                               html_body=body.html, attachments=files)
    except drive_link.DriveError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _may_send():
    link = gmail_link.connected()
    if link is None or not link.may_send:
        raise HTTPException(409, "Das Postfach darf nicht senden. Unter Einstellungen mit Senderechten verbinden.")


@router.post("/api/v1/mailbox/send")
def send(body: SendInput):
    _may_send()
    if not body.to:
        raise HTTPException(422, "Bitte mindestens eine:n Empfänger:in angeben.")
    raw = _raw(body)
    return _guarded(lambda: mailbox.send(raw, thread_id=body.thread_id))


@router.post("/api/v1/mailbox/draft")
def draft(body: SendInput):
    _may_send()
    raw = _raw(body, draft=True)
    return _guarded(lambda: mailbox.save_draft(raw, thread_id=body.thread_id))
