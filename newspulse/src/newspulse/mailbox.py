"""The Gmail mailbox inside RauteOS: read, sort, write, as Gmail itself does.

This widens DEC-6. Until now RauteOS read only the conversations it had started
itself. At Raphael's request (12.11.2026) the connected mailbox is shown as a
whole, so the agency can work its mail beside the clients. What it still does
not do is *store* any of it: every list and every message is read from Gmail
when the page asks and handed to the browser, never written to the database.
The Kontakte sync (:mod:`newspulse.mailsync`) keeps its narrower rule. The one
thing kept is the signature, which the agency writes itself.

It also widens DEC-4 by ``gmail.modify`` (see :data:`gmail_link.SCOPES`): the
row actions Gmail has (archive, delete, read and unread, star, spam) relabel a
conversation. Delete means Gmail's Papierkorb, never the permanent delete.
A mailbox connected before that asks to be connected again, and until then
:func:`may_manage` is false and the page hides those actions.

Sending goes the same two steps as a letter, a draft and then that draft, so a
retried click cannot send twice.

Mail HTML is someone else's markup. :func:`clean_html` takes out everything
that could run (scripts, frames, forms, event attributes, ``javascript:``
links) and the page shows the rest in a sandboxed frame that runs no script.
Attachments are served as downloads, and only plain images inline, so a mail
cannot put a page of its own on RauteOS's origin.

A client filter is a Gmail search over what identifies the client's mail: the
domain of its website, the addresses in its Kontakte & Sprecher, and its name.
"""
from __future__ import annotations

import base64
import binascii
import html
import re
import threading
import time
import urllib.parse
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import getaddresses, make_msgid, parseaddr, parsedate_to_datetime
from html.parser import HTMLParser

from sqlalchemy import select
from sqlalchemy.orm import Session

from contextvars import copy_context
from . import gmail_link, mail_identity
from .models import Client, Setting

FOLDERS = {"inbox": "INBOX", "starred": "STARRED", "sent": "SENT", "drafts": "DRAFT",
           "all": "", "spam": "SPAM", "trash": "TRASH"}
PAGE_SIZE = 25
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
SIGNATURE_KEY = "mailbox.signature"
_API = gmail_link._API_ROOT
# Images a browser shows without running anything. SVG is an image that can carry script.
INLINE_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"})

# What a row action does to the conversation's labels.
ACTIONS: dict[str, tuple[list[str], list[str]]] = {
    "archive": ([], ["INBOX"]),
    "inbox": (["INBOX"], ["SPAM", "TRASH"]),
    "read": ([], ["UNREAD"]),
    "unread": (["UNREAD"], []),
    "star": (["STARRED"], []),
    "unstar": ([], ["STARRED"]),
    "spam": (["SPAM"], ["INBOX"]),
    "notspam": (["INBOX"], ["SPAM"]),
}


@dataclass(frozen=True)
class Attachment:
    name: str
    mime: str
    size: int
    part_id: str
    message_id: str


@dataclass(frozen=True)
class Summary:
    id: str
    subject: str
    sender: str
    snippet: str
    date: str
    count: int
    unread: bool
    starred: bool = False
    labels: list[str] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    history_id: str = ""


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
    html: str = ""
    references: str = ""
    unread: bool = False
    starred: bool = False
    snippet: str = ""
    attachments: list[Attachment] = field(default_factory=list)


def _api(url: str, **kwargs) -> dict:
    return gmail_link._api(url, what=kwargs.pop("what", "Gmail ist gerade nicht lesbar"), **kwargs)


def _quote(value: str) -> str:
    return urllib.parse.quote(str(value), safe="")


def may_manage(link: gmail_link.Link | None) -> bool:
    """Whether the grant covers relabelling: archive, delete, read, star."""
    return bool(link and link.may_manage)


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


def _walk(part: dict):
    yield part
    for nested in part.get("parts") or ():
        yield from _walk(nested)


def _attachments(payload: dict, message_id: str) -> list[Attachment]:
    found = []
    for part in _walk(payload):
        name = str(part.get("filename") or "")
        if not name or not part.get("partId"):
            continue
        disposition = _header(part.get("headers"), "Content-Disposition").casefold()
        if _header(part.get("headers"), "Content-ID") and not disposition.startswith("attachment"):
            continue  # an image drawn in the mail, not a file beside it
        found.append(Attachment(name=name, mime=str(part.get("mimeType") or "application/octet-stream"),
                                size=int((part.get("body") or {}).get("size") or 0),
                                part_id=str(part["partId"]), message_id=message_id))
    return found


def _first_names(messages: list[dict], me: str) -> str:
    """Who wrote in a conversation, as Gmail's row says it: "Debtist, Ich"."""
    names: list[str] = []
    for raw in messages:
        name, address = parseaddr(_header((raw.get("payload") or {}).get("headers"), "From"))
        label = "Ich" if me and address.casefold() == me.casefold() else (name or address)
        if label and label not in names:
            names.append(label)
    if len(names) == 1:
        return names[0]
    return ", ".join(n if n == "Ich" else n.split()[0] for n in names[-3:])


def _label_count(label: str, key: str) -> int | None:
    held = _counts.get((label, key))
    if held and time.monotonic() - held[0] < _COUNT_SECONDS:
        return held[1]
    try:
        value = int(_api(f"{_API}/labels/{_quote(label)}").get(key) or 0)
    except gmail_link.GmailError:
        return None
    _counts[(label, key)] = (time.monotonic(), value)
    return value


# --- The cache ----------------------------------------------------------------------
#
# Gmail is slow at one thing: a page of 25 conversations is one list call and
# then one call per conversation. A conversation only changes when its
# ``historyId`` does, and the list call names that id, so a conversation read
# once is not read again until something happened in it. Held in this process's
# memory only, never on disk or in the database (DEC-6), bounded, and gone with
# a restart. Keyed by the connected address, so a reconnected other mailbox
# never sees the first one's mail.

_SUMMARIES = 3000
_THREADS = 150
_COUNT_SECONDS = 20.0
_lock = threading.Lock()
_summaries: OrderedDict[tuple, Summary] = OrderedDict()
_threads: OrderedDict[tuple, list] = OrderedDict()
_counts: dict[tuple, tuple[float, int | None]] = {}
_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="gmail")


def _account() -> str:
    link = gmail_link.connected()
    return f"{mail_identity.owner.get()}:{link.email}" if link else ""


def _remember(store: OrderedDict, key: tuple, value, limit: int):
    with _lock:
        store[key] = value
        store.move_to_end(key)
        while len(store) > limit:
            store.popitem(last=False)
    return value


def _recall(store: OrderedDict, key: tuple):
    with _lock:
        value = store.get(key)
        if value is not None:
            store.move_to_end(key)
        return value


def forget(thread_ids=None) -> None:
    """Drop what is held: for some conversations after a change, or all of it."""
    with _lock:
        if thread_ids is None:
            _summaries.clear()
            _threads.clear()
        else:
            wanted = set(thread_ids)
            for store in (_summaries, _threads):
                for key in [k for k in store if k[1] in wanted]:
                    del store[key]
        _counts.clear()


def threads(folder: str = "inbox", *, query: str = "", page_token: str = "", me: str = "") -> dict:
    """One page of conversations, newest first, as Gmail lists them."""
    params = [("maxResults", str(PAGE_SIZE))]
    label = FOLDERS.get(folder, "INBOX")
    if label:
        params.append(("labelIds", label))
    if folder in ("spam", "trash"):
        params.append(("includeSpamTrash", "true"))
    if query:
        params.append(("q", query))
    if page_token:
        params.append(("pageToken", page_token))
    listing = _api(f"{gmail_link._THREADS_ENDPOINT}?{urllib.parse.urlencode(params)}")
    fields = ("messages(id,labelIds,payload(headers,partId,filename,mimeType,body/size,"
              "parts(partId,filename,mimeType,headers,body/size,parts(partId,filename,mimeType,headers,body/size,"
              "parts(partId,filename,mimeType,headers,body/size)))))")
    account = _account()

    def summary(item: dict) -> Summary:
        key = (account, str(item["id"]), str(item.get("historyId") or ""), me)
        if key[2] and (held := _recall(_summaries, key)) is not None:
            return held
        detail = _api(f"{gmail_link._THREADS_ENDPOINT}/{_quote(item['id'])}?format=full&fields={_quote(fields)}")
        messages = detail.get("messages") or [{}]
        first, last = messages[0].get("payload") or {}, messages[-1].get("payload") or {}
        labels = sorted({lab for m in messages for lab in (m.get("labelIds") or ())})
        row = Summary(
            id=str(item["id"]), subject=_header(first.get("headers"), "Subject") or "(kein Betreff)",
            sender=_first_names(messages, me), snippet=html.unescape(str(item.get("snippet") or "")),
            date=_date(_header(last.get("headers"), "Date")), count=len(messages),
            unread="UNREAD" in labels, starred="STARRED" in labels,
            labels=[lab for lab in labels if lab in ("INBOX", "SPAM", "TRASH", "SENT", "DRAFT", "IMPORTANT")],
            attachments=[a for m in messages for a in _attachments(m.get("payload") or {}, str(m.get("id") or ""))],
            history_id=key[2])
        return _remember(_summaries, key, row, _SUMMARIES) if key[2] else row

    items = list(listing.get("threads") or ())
    # The conversations not held yet are read side by side, not one after another.
    jobs = [_pool.submit(copy_context().run, summary, item) for item in items]
    rows = [job.result() for job in jobs]
    count_total = _pool.submit(copy_context().run, _label_count, label, "threadsTotal") if label and not query else None
    unread = _label_count("INBOX", "threadsUnread")
    total = count_total.result() if count_total else None
    return dict(threads=rows, next_page_token=listing.get("nextPageToken") or "",
                total=total if total is not None else int(listing.get("resultSizeEstimate") or len(rows)),
                unread_inbox=unread)


def _decode(data: str) -> str:
    return _bytes(data).decode("utf-8", "replace")


def _bytes(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


_TAGS = re.compile(r"<(script|style|head)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)
_LINES = re.compile(r"<\s*(br|/li|/tr)\s*/?>", re.I)
_PARAGRAPHS = re.compile(r"<\s*(/p|/div|/h\d|/table|/blockquote)\s*>", re.I)


def html_text(markup: str) -> str:
    """HTML as readable text: the plain part of a sent mail, a quote, a search."""
    text = _TAGS.sub("", _LINES.sub("\n", _PARAGRAPHS.sub("\n\n", markup)))
    text = "\n".join(line.strip() for line in html.unescape(text).splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


_html_text = html_text

_DROP_WITH_CONTENT = {"script", "iframe", "frame", "frameset", "object", "embed", "applet", "noscript", "template", "title"}
_DROP_TAG = {"form", "input", "button", "select", "textarea", "base", "link", "meta", "html", "head", "body", "svg", "math"}
_URL_ATTRS = {"href", "src", "background", "action", "poster", "srcset", "xlink:href", "formaction"}
_SAFE_SCHEMES = ("http:", "https:", "mailto:", "tel:", "cid:", "#")


class _Cleaner(HTMLParser):
    def __init__(self, cid: dict[str, str]):
        super().__init__(convert_charrefs=False)
        self.out: list[str] = []
        self.skip = 0
        self.cid = cid

    def _attrs(self, attrs) -> str:
        kept = []
        for name, value in attrs:
            name = name.casefold()
            if name.startswith("on") or name in ("srcdoc", "formaction", "http-equiv"):
                continue
            value = value or ""
            if name in _URL_ATTRS:
                target = re.sub(r"[\s\x00-\x1f]", "", html.unescape(value)).casefold()
                image = name == "src" and re.match(r"^data:image/(png|jpeg|gif|webp);", target)
                if name == "srcset" or not (image or target.startswith(_SAFE_SCHEMES)
                                            or not re.match(r"^[a-z][a-z0-9+.-]*:", target)):
                    continue
                if target.startswith("cid:"):
                    value = self.cid.get(html.unescape(value).strip()[4:].strip("<>"), "")
                    if not value:
                        continue
            if name == "style" and re.search(r"expression\s*\(|javascript:|behavior\s*:|-moz-binding", value, re.I):
                continue
            kept.append(f' {name}="{html.escape(value, quote=True)}"')
        return "".join(kept)

    def handle_starttag(self, tag, attrs):
        tag = tag.casefold()
        if tag in _DROP_WITH_CONTENT:
            self.skip += 1
            return
        if self.skip or tag in _DROP_TAG:
            return
        extra = ' target="_blank" rel="noopener noreferrer"' if tag == "a" else ""
        self.out.append(f"<{tag}{self._attrs(attrs)}{extra}>")

    def handle_startendtag(self, tag, attrs):
        if tag.casefold() not in _DROP_WITH_CONTENT:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.casefold()
        if tag in _DROP_WITH_CONTENT:
            self.skip = max(0, self.skip - 1)
            return
        if not self.skip and tag not in _DROP_TAG:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(html.escape(data, quote=False))

    def handle_entityref(self, name):
        if not self.skip:
            self.out.append(f"&{name};")

    def handle_charref(self, name):
        if not self.skip:
            self.out.append(f"&#{name};")


def clean_html(markup: str, cid: dict[str, str] | None = None) -> str:
    """Mail HTML without anything that could run. ``cid`` maps inline image ids to URLs."""
    cleaner = _Cleaner(cid or {})
    cleaner.feed(re.sub(r"<!--.*?-->", "", markup or "", flags=re.S))
    cleaner.close()
    return "".join(cleaner.out)


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


def part_url(message_id: str, part_id: str) -> str:
    return f"/api/v1/mailbox/messages/{_quote(message_id)}/parts/{_quote(part_id)}"


def thread(thread_id: str, *, history_id: str = "") -> list[Message]:
    """A whole conversation. With the ``history_id`` the list named, one read
    before and unchanged since is answered from memory."""
    account = _account()
    if history_id and (held := _recall(_threads, (account, thread_id, history_id))) is not None:
        return held
    answer = _api(f"{gmail_link._THREADS_ENDPOINT}/{_quote(thread_id)}?format=full")
    messages = _messages(answer)
    if answer.get("historyId"):
        _remember(_threads, (account, thread_id, str(answer["historyId"])), messages, _THREADS)
    return messages


def _messages(answer: dict) -> list[Message]:
    result = []
    for raw in answer.get("messages") or ():
        payload = raw.get("payload") or {}
        headers = payload.get("headers")
        message_id = str(raw.get("id") or "")
        name, address = parseaddr(_header(headers, "From"))
        plain, markup = _body(payload)
        cid = {_header(p.get("headers"), "Content-ID").strip("<> "): part_url(message_id, str(p["partId"]))
               for p in _walk(payload) if p.get("partId") and _header(p.get("headers"), "Content-ID")}
        labels = raw.get("labelIds") or ()
        result.append(Message(
            id=message_id, sender=name or address, sender_email=address,
            to=_header(headers, "To"), cc=_header(headers, "Cc"), date=_date(_header(headers, "Date")),
            subject=_header(headers, "Subject"), body=(plain or html_text(markup)).replace("\r\n", "\n").strip(),
            html=clean_html(markup, cid) if markup else "",
            message_id_header=_header(headers, "Message-ID"),
            references=" ".join(v for v in (_header(headers, "References"), _header(headers, "Message-ID")) if v),
            unread="UNREAD" in labels, starred="STARRED" in labels,
            snippet=html.unescape(str(raw.get("snippet") or "")),
            attachments=_attachments(payload, message_id)))
    return result


def part(message_id: str, part_id: str) -> tuple[str, str, bytes]:
    """One attachment as ``(name, mime, bytes)``, found by its part.

    By part and not by Gmail's attachment id, because that id changes from one
    read to the next while the part number stays.
    """
    message = _api(f"{gmail_link._MESSAGES_ENDPOINT}/{_quote(message_id)}?format=full")
    found = next((p for p in _walk(message.get("payload") or {}) if str(p.get("partId")) == part_id), None)
    if found is None:
        raise gmail_link.GmailMissing("Anhang nicht gefunden")
    body = found.get("body") or {}
    if body.get("attachmentId"):
        body = _api(f"{gmail_link._MESSAGES_ENDPOINT}/{_quote(message_id)}/attachments/{_quote(body['attachmentId'])}")
    return (str(found.get("filename") or "anhang"), str(found.get("mimeType") or "application/octet-stream"),
            _bytes(str(body.get("data") or "")))


def modify(thread_ids: list[str], action: str) -> int:
    """Archive, delete, mark or star conversations, as Gmail's buttons do."""
    for thread_id in thread_ids:
        base = f"{gmail_link._THREADS_ENDPOINT}/{_quote(thread_id)}"
        if action == "trash":
            _api(f"{base}/trash", json_body={}, what="Gmail hat die E-Mail nicht gelöscht")
        elif action == "untrash":
            _api(f"{base}/untrash", json_body={}, what="Gmail hat die E-Mail nicht wiederhergestellt")
        else:
            add, remove = ACTIONS[action]
            _api(f"{base}/modify", json_body={"addLabelIds": add, "removeLabelIds": remove},
                 what="Gmail hat die E-Mail nicht geändert")
    forget(thread_ids)
    return len(thread_ids)


# --- The signature ------------------------------------------------------------------


def _signature_key() -> str:
    owner = mail_identity.owner.get()
    return f"{SIGNATURE_KEY}:{owner}" if owner else SIGNATURE_KEY


def signature(session: Session) -> str:
    row = session.get(Setting, _signature_key())
    return (row.value or "") if row else ""


def save_signature(session: Session, markup: str) -> str:
    cleaned = clean_html(markup).strip()
    row = session.get(Setting, _signature_key())
    if row is None:
        session.add(Setting(key=_signature_key(), value=cleaned))
    else:
        row.value = cleaned
    session.commit()
    return cleaned


# --- Writing ------------------------------------------------------------------------


def _addresses(raw: str) -> list[str]:
    found = [address for _, address in getaddresses([raw or ""]) if "@" in address]
    if (raw or "").strip() and not found:
        raise ValueError("Bitte gültige E-Mail-Adressen angeben.")
    return found


_DATA_IMAGE = re.compile(r"""src=(["'])data:(image/(?:png|jpeg|gif|webp));base64,([A-Za-z0-9+/=\s]+)\1""", re.I)


def compose(to: str, subject: str, body: str, *, cc: str = "", bcc: str = "", reply_to_id: str = "",
            references: str = "", html_body: str = "", draft: bool = False,
            attachments: list[tuple[str, str, bytes]] = ()) -> str:
    """The message as Gmail's base64url ``raw``.

    With ``html_body`` it is sent as Gmail sends a formatted mail: the HTML and a
    plain-text copy of it, images pasted into the text as inline parts.
    """
    recipients = _addresses(to)
    if not recipients and not draft:
        raise ValueError("Bitte mindestens eine:n Empfänger:in angeben.")
    message = EmailMessage()
    if recipients:
        message["To"] = ", ".join(recipients)
    if cc.strip():
        message["Cc"] = ", ".join(_addresses(cc))
    if bcc.strip():
        message["Bcc"] = ", ".join(_addresses(bcc))
    message["Subject"] = subject.strip()
    if reply_to_id:
        message["In-Reply-To"] = reply_to_id
        message["References"] = references or reply_to_id
    total = 0

    def _count(size: int):
        nonlocal total
        total += size
        if total > MAX_ATTACHMENT_BYTES:
            raise ValueError("Die Anhänge sind zusammen größer als 20 MB.")

    if html_body.strip():
        inline: list[tuple[str, str, bytes]] = []

        def _cid(match: re.Match) -> str:
            try:
                data = base64.b64decode(re.sub(r"\s", "", match.group(3)), validate=True)
            except (binascii.Error, ValueError):
                return 'src=""'
            _count(len(data))
            cid = make_msgid(domain="raute-os")
            inline.append((cid, match.group(2).lower(), data))
            return f'src="cid:{cid[1:-1]}"'

        markup = _DATA_IMAGE.sub(_cid, html_body)
        message.set_content(body.strip() or html_text(markup))
        message.add_alternative(f'<div dir="ltr">{markup}</div>', subtype="html")
        if inline:
            html_part = message.get_payload()[1]
            for cid, mime, data in inline:
                html_part.add_related(data, maintype="image", subtype=mime.split("/", 1)[1], cid=cid)
    else:
        message.set_content(body)
    for name, mime, data in attachments:
        _count(len(data))
        main, _, sub = (mime or "application/octet-stream").partition("/")
        message.add_attachment(data, maintype=main, subtype=sub or "octet-stream", filename=name)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def _draft_payload(raw: str, thread_id: str) -> dict:
    payload: dict = {"message": {"raw": raw}}
    if thread_id:
        payload["message"]["threadId"] = thread_id
    return payload


def save_draft(raw: str, *, thread_id: str = "") -> dict:
    """Keep an unsent mail in Gmail's Entwürfe, as closing Gmail's window does."""
    draft = gmail_link._api(gmail_link._DRAFTS_ENDPOINT, json_body=_draft_payload(raw, thread_id),
                            what="Gmail-Entwurf nicht anlegbar")
    return dict(draft_id=str(draft.get("id") or ""))


def send(raw: str, *, thread_id: str = "") -> dict:
    """Draft, then send that draft: a retried click sends once."""
    draft = gmail_link._api(gmail_link._DRAFTS_ENDPOINT, json_body=_draft_payload(raw, thread_id),
                            what="Gmail-Entwurf nicht anlegbar")
    if not draft.get("id"):
        raise gmail_link.GmailError("Gmail nannte keinen Entwurf")
    sent = gmail_link.send(str(draft["id"]))
    return dict(message_id=sent.message_id, thread_id=sent.thread_id)
