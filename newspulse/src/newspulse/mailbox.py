"""The Gmail mailbox inside RauteOS: read, filter by client, write with Drive assets.

This widens DEC-6. Until now RauteOS read only the conversations it had started
itself. At Raphael's request (12.11.2026) the connected mailbox is shown as a
whole, so the agency can work its mail beside the clients. What it still does
not do is *store* any of it: every list and every message is read from Gmail
when the page asks and handed to the browser, never written to the database.
The Kontakte sync (:mod:`newspulse.mailsync`) keeps its narrower rule.

It uses the scopes the mailbox is already connected with (``gmail.readonly``
and ``gmail.compose``): reading and sending, no deleting or relabelling. Sending
goes the same two steps as a letter, a draft and then that draft, so a retried
click cannot send twice.

A client filter is a Gmail search over what identifies the client's mail: the
domain of its website, the addresses in its Kontakte & Sprecher, and its name.
"""
from __future__ import annotations

import base64
import html
import re
import urllib.parse
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr, parsedate_to_datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import gmail_link
from .models import Client

FOLDERS = {"inbox": "INBOX", "sent": "SENT", "drafts": "DRAFT", "starred": "STARRED"}
PAGE_SIZE = 20
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class Summary:
    id: str
    subject: str
    sender: str
    snippet: str
    date: str
    count: int
    unread: bool


@dataclass(frozen=True)
class Message:
    id: str
    sender: str
    sender_email: str
    to: str
    cc: str
    date: str
    subject: str
    body: str
    message_id_header: str
    attachments: list[str] = field(default_factory=list)


def _api(url: str, **kwargs) -> dict:
    return gmail_link._api(url, what="Gmail ist gerade nicht lesbar", **kwargs)


def _header(headers: list, name: str) -> str:
    wanted = name.casefold()
    return next((str(h.get("value") or "") for h in headers or () if str(h.get("name", "")).casefold() == wanted), "")


def _date(raw: str) -> str:
    try:
        return parsedate_to_datetime(raw).isoformat()
    except (TypeError, ValueError):
        return ""


# --- The client filter --------------------------------------------------------------


def _domain(website: str | None) -> str:
    host = urllib.parse.urlsplit(website if "://" in (website or "") else f"https://{website or ''}").hostname or ""
    return host[4:] if host.startswith("www.") else host


def client_query(session: Session, client: Client) -> str:
    """The Gmail search that finds this client's mail."""
    from .models import ClientPerson

    terms = []
    domain = _domain(client.website)
    if domain:
        terms += [f"from:{domain}", f"to:{domain}", f"cc:{domain}"]
    emails = session.scalars(select(ClientPerson.email).where(ClientPerson.client_id == client.id, ClientPerson.email != ""))
    for email in dict.fromkeys(e.strip() for e in emails if e and "@" in e):
        terms += [f"from:{email}", f"to:{email}"]
    for name in dict.fromkeys(n.strip() for n in [client.name, *(client.aliases or [])] if n and n.strip()):
        terms.append('"' + name.replace('"', "") + '"')
    return "{" + " ".join(terms) + "}" if terms else ""


# --- Reading ------------------------------------------------------------------------


def threads(folder: str = "inbox", *, query: str = "", page_token: str = "") -> dict:
    """One page of conversations, newest first, as Gmail lists them."""
    params = [("maxResults", str(PAGE_SIZE))]
    if folder in FOLDERS:
        params.append(("labelIds", FOLDERS[folder]))
    if query:
        params.append(("q", query))
    if page_token:
        params.append(("pageToken", page_token))
    listing = _api(f"{gmail_link._THREADS_ENDPOINT}?{urllib.parse.urlencode(params)}")
    rows = []
    for item in listing.get("threads") or ():
        detail = _api(f"{gmail_link._THREADS_ENDPOINT}/{urllib.parse.quote(str(item['id']), safe='')}"
                      "?format=metadata&metadataHeaders=Subject&metadataHeaders=From&metadataHeaders=Date")
        messages = detail.get("messages") or [{}]
        first, last = messages[0].get("payload") or {}, messages[-1].get("payload") or {}
        name, address = parseaddr(_header(last.get("headers"), "From"))
        rows.append(Summary(
            id=str(item["id"]), subject=_header(first.get("headers"), "Subject") or "(ohne Betreff)",
            sender=name or address, snippet=html.unescape(str(item.get("snippet") or "")),
            date=_date(_header(last.get("headers"), "Date")), count=len(messages),
            unread=any("UNREAD" in (m.get("labelIds") or ()) for m in messages)))
    return dict(threads=rows, next_page_token=listing.get("nextPageToken") or "")


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


_TAGS = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)
_LINES = re.compile(r"<\s*(br|/li|/tr)\s*/?>", re.I)
_PARAGRAPHS = re.compile(r"<\s*(/p|/div|/h\d|/table)\s*>", re.I)


def _html_text(markup: str) -> str:
    """HTML mail as readable text. Never rendered as HTML: a mail's markup is
    someone else's code, and the reading pane shows words, not their page."""
    text = _TAGS.sub("", _LINES.sub("\n", _PARAGRAPHS.sub("\n\n", markup)))
    text = "\n".join(line.strip() for line in html.unescape(text).splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _body(part: dict) -> tuple[str, str]:
    """``(plain, html)`` of a payload, walking multipart."""
    mime = str(part.get("mimeType") or "")
    data = str((part.get("body") or {}).get("data") or "")
    if mime.startswith("text/plain") and data and not part.get("filename"):
        return _decode(data), ""
    if mime.startswith("text/html") and data and not part.get("filename"):
        return "", _decode(data)
    plain, markup = "", ""
    for nested in part.get("parts") or ():
        p, h = _body(nested)
        plain, markup = plain or p, markup or h
    return plain, markup


def _attachments(part: dict) -> list[str]:
    found = [str(part["filename"])] if part.get("filename") else []
    for nested in part.get("parts") or ():
        found += _attachments(nested)
    return found


def thread(thread_id: str) -> list[Message]:
    answer = _api(f"{gmail_link._THREADS_ENDPOINT}/{urllib.parse.quote(thread_id, safe='')}?format=full")
    result = []
    for raw in answer.get("messages") or ():
        payload = raw.get("payload") or {}
        headers = payload.get("headers")
        name, address = parseaddr(_header(headers, "From"))
        plain, markup = _body(payload)
        result.append(Message(
            id=str(raw.get("id") or ""), sender=name or address, sender_email=address,
            to=_header(headers, "To"), cc=_header(headers, "Cc"), date=_date(_header(headers, "Date")),
            subject=_header(headers, "Subject"), body=(plain or _html_text(markup)).replace("\r\n", "\n").strip(),
            message_id_header=_header(headers, "Message-ID"), attachments=_attachments(payload)))
    return result


# --- Writing ------------------------------------------------------------------------


def _addresses(raw: str) -> list[str]:
    found = [address for _, address in getaddresses([raw or ""]) if "@" in address]
    if raw.strip() and not found:
        raise ValueError("Bitte gültige E-Mail-Adressen angeben.")
    return found


def compose(to: str, subject: str, body: str, *, cc: str = "", reply_to_id: str = "",
            attachments: list[tuple[str, str, bytes]] = ()) -> str:
    """The message as Gmail's base64url ``raw``."""
    recipients = _addresses(to)
    if not recipients:
        raise ValueError("Bitte mindestens eine:n Empfänger:in angeben.")
    message = EmailMessage()
    message["To"] = ", ".join(recipients)
    if cc.strip():
        message["Cc"] = ", ".join(_addresses(cc))
    message["Subject"] = subject.strip()
    if reply_to_id:
        message["In-Reply-To"] = reply_to_id
        message["References"] = reply_to_id
    message.set_content(body)
    total = 0
    for name, mime, data in attachments:
        total += len(data)
        if total > MAX_ATTACHMENT_BYTES:
            raise ValueError("Die Anhänge sind zusammen größer als 20 MB.")
        main, _, sub = (mime or "application/octet-stream").partition("/")
        message.add_attachment(data, maintype=main, subtype=sub or "octet-stream", filename=name)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def send(raw: str, *, thread_id: str = "") -> dict:
    """Draft, then send that draft: a retried click sends once."""
    payload: dict = {"message": {"raw": raw}}
    if thread_id:
        payload["message"]["threadId"] = thread_id
    draft = gmail_link._api(gmail_link._DRAFTS_ENDPOINT, json_body=payload, what="Gmail-Entwurf nicht anlegbar")
    if not draft.get("id"):
        raise gmail_link.GmailError("Gmail nannte keinen Entwurf")
    sent = gmail_link.send(str(draft["id"]))
    return dict(message_id=sent.message_id, thread_id=sent.thread_id)
