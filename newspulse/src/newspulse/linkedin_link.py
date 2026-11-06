"""Each person's own LinkedIn profile, connected to post what RauteOS planned.

LinkedIn's self-serve products are "Sign In with LinkedIn using OpenID Connect"
(who is this) and "Share on LinkedIn" (``w_member_social``: post as this
member). Neither needs LinkedIn's review, and neither issues a refresh token:
an access token lives 60 days, then the person connects again. Comments and
statistics are not part of these products, so nothing here reads them.

One connection per RauteOS sign-in address. The tokens never touch the
database: like Gmail's (``newspulse.gmail_link``) they live in a 0600 file
beside it, so a database copy or an export cannot carry them out. No token
value is ever logged.

Every network call goes through an injected ``fetch``, so the tests never
leave the machine.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config

_log = logging.getLogger(__name__)

_AUTH_ENDPOINT = "https://www.linkedin.com/oauth/v2/authorization"
_TOKEN_ENDPOINT = "https://www.linkedin.com/oauth/v2/accessToken"
_REVOKE_ENDPOINT = "https://www.linkedin.com/oauth/v2/revoke"
_USERINFO_ENDPOINT = "https://api.linkedin.com/v2/userinfo"
_POSTS_ENDPOINT = "https://api.linkedin.com/rest/posts"
_POST_WEB_URL = "https://www.linkedin.com/feed/update/{urn}/"

#: Who this is, and posting as them. Nothing else is asked for.
SCOPES: tuple[str, ...] = ("openid", "profile", "w_member_social")

_TOKEN_FILENAME = "linkedin_tokens.json"
_TOKEN_MODE = 0o600
_TIMEOUT = 20.0
_MAX_ERROR_BYTES = 4096
#: LinkedIn states 60 days; this is only used when an answer omits it.
_DEFAULT_EXPIRES_IN = 60 * 24 * 3600
#: How early the page starts asking for a fresh connection.
RENEW_WARNING = dt.timedelta(days=7)

#: Without a sign-in (basic auth) there is one shared connection.
_SHARED = "team"

_file_lock = threading.Lock()


class LinkedInError(RuntimeError):
    """A LinkedIn call failed; the message is a German sentence for the page."""


#: One call: URL, optional form or JSON body, optional bearer token and extra
#: headers. Returns (status, response headers in lower case, parsed JSON).
Fetch = Callable[..., tuple[int, dict[str, str], dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class Connection:
    """What the page shows about one person's LinkedIn connection."""

    name: str
    person_urn: str
    expires_at: dt.datetime
    connected_at: dt.datetime | None = None
    lost: str = ""

    def usable(self, at: dt.datetime | None = None) -> bool:
        return not self.lost and self.expires_at > (at or _now())

    def expiring(self, at: dt.datetime | None = None) -> bool:
        return self.usable(at) and self.expires_at - (at or _now()) <= RENEW_WARNING


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _key(owner: str) -> str:
    return (owner or "").strip().lower() or _SHARED


# --- The 0600 token file ---------------------------------------------------------


def token_path() -> Path:
    return config.DATABASE_PATH.parent / _TOKEN_FILENAME


def _read() -> dict[str, dict[str, Any]]:
    try:
        stored = json.loads(token_path().read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return stored if isinstance(stored, dict) else {}


def _write(data: dict[str, dict[str, Any]]) -> None:
    """Owner-only, and renamed into place so a reader never sees half a file."""
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(path.name + ".new")
    handle = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _TOKEN_MODE)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream)
        staged.chmod(_TOKEN_MODE)
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def _update(owner: str, record: dict[str, Any] | None) -> None:
    with _file_lock:
        data = _read()
        if record is None:
            data.pop(_key(owner), None)
        else:
            data[_key(owner)] = record
        _write(data)


def _parse_time(raw: object) -> dt.datetime | None:
    try:
        moment = dt.datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=dt.UTC)


def connection(owner: str) -> Connection | None:
    """This person's connection, expired or lost ones included so the page can say so."""
    stored = _read().get(_key(owner))
    if not isinstance(stored, dict) or not stored.get("person_urn"):
        return None
    expires = _parse_time(stored.get("expires_at"))
    if expires is None:
        return None
    return Connection(name=str(stored.get("name") or ""), person_urn=str(stored["person_urn"]),
                      expires_at=expires, connected_at=_parse_time(stored.get("connected_at")),
                      lost=str(stored.get("lost") or ""))


def _access(owner: str) -> tuple[str, str]:
    """The access token and author urn, or the sentence why there are none."""
    stored = _read().get(_key(owner)) or {}
    found = connection(owner)
    if found is None or not stored.get("access_token"):
        raise LinkedInError("Kein LinkedIn-Konto verbunden.")
    if not found.usable():
        raise LinkedInError("Die LinkedIn-Verbindung ist abgelaufen. Bitte neu verbinden.")
    return str(stored["access_token"]), found.person_urn


def _lose(owner: str, reason: str) -> None:
    """LinkedIn refused the token: keep who it was, drop the credential."""
    with _file_lock:
        data = _read()
        record = data.get(_key(owner))
        if isinstance(record, dict):
            record.pop("access_token", None)
            record["lost"] = reason
            _write(data)
    _log.warning("LinkedIn connection ended for one account: %s", reason)


# --- Network ---------------------------------------------------------------------


def _decode(body: bytes) -> dict[str, Any]:
    text = body.decode("utf-8", "replace").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _fetch(url: str, *, form: dict[str, str] | None = None, json_body: dict[str, Any] | None = None,
           token: str = "", headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], dict[str, Any]]:
    """The one place that reaches LinkedIn. A 4xx comes back, it is not raised:
    the caller branches on it. The error message never carries a body."""
    sent = {"Accept": "application/json", **(headers or {})}
    data: bytes | None = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        sent["Content-Type"] = "application/x-www-form-urlencoded"
    elif json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        sent["Content-Type"] = "application/json"
    if token:
        sent["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=sent,  # noqa: S310 - fixed https endpoints
                                     method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}, _decode(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, _decode(exc.read(_MAX_ERROR_BYTES))
    except urllib.error.URLError as exc:
        raise LinkedInError(f"LinkedIn ist nicht erreichbar: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LinkedInError("LinkedIn antwortet gerade nicht.") from exc


def _error_text(payload: dict[str, Any]) -> str:
    """LinkedIn's own words for a failure: the OAuth pair, or the REST message."""
    code = str(payload.get("error") or "")
    detail = str(payload.get("error_description") or payload.get("message") or "")
    return ": ".join(part for part in (code, detail) if part)[:200]


# --- Connecting ------------------------------------------------------------------


def new_state() -> str:
    return secrets.token_urlsafe(32)


def authorize_url(state: str) -> str:
    if not config.linkedin_configured():
        raise LinkedInError("LinkedIn ist auf dem Server nicht eingerichtet.")
    return f"{_AUTH_ENDPOINT}?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": config.linkedin_client_id(),
        "redirect_uri": config.linkedin_redirect_uri(), "state": state, "scope": " ".join(SCOPES)})


def exchange(owner: str, code: str, *, fetch: Fetch | None = None) -> Connection:
    """Trade the one-time code for a token, ask who it belongs to, store both."""
    call = fetch or _fetch
    status, _, payload = call(_TOKEN_ENDPOINT, form={
        "grant_type": "authorization_code", "code": code, "redirect_uri": config.linkedin_redirect_uri(),
        "client_id": config.linkedin_client_id(), "client_secret": config.linkedin_client_secret()})
    access = str(payload.get("access_token") or "")
    if status >= 400 or not access:
        raise LinkedInError(f"LinkedIn hat die Anmeldung nicht bestätigt ({_error_text(payload) or status}).")
    try:
        lifetime = int(payload.get("expires_in") or _DEFAULT_EXPIRES_IN)
    except (TypeError, ValueError):
        lifetime = _DEFAULT_EXPIRES_IN
    status, _, me = call(_USERINFO_ENDPOINT, token=access)
    person = str(me.get("sub") or "")
    if status >= 400 or not person:
        raise LinkedInError(f"LinkedIn hat das Profil nicht genannt ({_error_text(me) or status}).")
    now = _now()
    name = " ".join(str(me.get("name") or "").split()) or " ".join(
        str(me.get(k) or "") for k in ("given_name", "family_name")).strip()
    record = {"access_token": access, "person_urn": f"urn:li:person:{person}", "name": name[:120],
              "expires_at": (now + dt.timedelta(seconds=lifetime)).isoformat(),
              "connected_at": now.isoformat()}
    _update(owner, record)
    _log.info("LinkedIn connected for one account, valid %d day(s)", lifetime // 86400)
    found = connection(owner)
    assert found is not None
    return found


def disconnect(owner: str, *, fetch: Fetch | None = None) -> None:
    """Forget the token here, and ask LinkedIn to revoke it. Best effort at
    LinkedIn: the local credential is gone either way."""
    access = str((_read().get(_key(owner)) or {}).get("access_token") or "")
    _update(owner, None)
    if access and config.linkedin_configured():
        try:
            (fetch or _fetch)(_REVOKE_ENDPOINT, form={
                "client_id": config.linkedin_client_id(), "client_secret": config.linkedin_client_secret(),
                "token": access})
        except LinkedInError as exc:
            _log.warning("LinkedIn token deleted here but not confirmed revoked: %s", exc)


# --- Posting ---------------------------------------------------------------------

# LinkedIn reads a post's text as "little text": these characters mean markup
# and must be escaped, or the post is cut off or refused. A hashtag stays a
# hashtag only in LinkedIn's own template.
_RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")
_HASHTAG = re.compile(r"(?<![\w#])#(\w+)")


def commentary(text: str) -> str:
    """The text as LinkedIn has to receive it, hashtags kept clickable."""
    out, last = [], 0
    for match in _HASHTAG.finditer(text):
        out.append(_RESERVED.sub(r"\\\1", text[last:match.start()]))
        out.append("{hashtag|\\#|" + _RESERVED.sub(r"\\\1", match.group(1)) + "}")
        last = match.end()
    out.append(_RESERVED.sub(r"\\\1", text[last:]))
    return "".join(out)


def post_url(urn: str) -> str:
    return _POST_WEB_URL.format(urn=urn)


def publish(owner: str, text: str, *, fetch: Fetch | None = None) -> str:
    """Post ``text`` publicly as this person. Returns LinkedIn's urn for it."""
    access, author = _access(owner)
    status, headers, payload = (fetch or _fetch)(_POSTS_ENDPOINT, token=access, headers={
        "LinkedIn-Version": config.linkedin_version(), "X-Restli-Protocol-Version": "2.0.0"}, json_body={
        "author": author, "commentary": commentary(text), "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                         "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False})
    if status == 401:
        _lose(owner, "LinkedIn hat die Verbindung nicht mehr angenommen.")
        raise LinkedInError("LinkedIn hat die Verbindung nicht mehr angenommen. Bitte neu verbinden.")
    urn = headers.get("x-restli-id") or str(payload.get("id") or "")
    if status >= 400 or not urn:
        _log.warning("LinkedIn refused a post: HTTP %s %s", status, _error_text(payload))
        raise LinkedInError(f"LinkedIn hat den Beitrag nicht angenommen ({_error_text(payload) or status}).")
    _log.info("posted to LinkedIn: %s", urn)
    return urn
