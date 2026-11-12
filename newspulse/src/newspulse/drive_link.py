"""Google Drive for the asset export (Spec 12): one shared folder, a folder per client.

Exports land in the shared drive folder "7. Assets"
(:data:`config.DRIVE_ASSETS_FOLDER`), in a sub-folder named after the client,
created on first use. Connected once under Einstellungen, like Gmail, with the
same OAuth client and the same registered callback: the ``state`` of a Drive
consent starts with :data:`STATE_PREFIX`, which is how the shared callback
tells the two apart. Nothing new has to be registered in the Cloud console.

The scope is the full ``drive`` scope, and that is a decision, not a default:
``drive.file`` only reaches files the app created itself, and the asset folder
already exists in the shared drive, so a file could not be put into it. The
token sits beside the database, owner-only, like the Gmail token.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config

_log = logging.getLogger(__name__)

SCOPES: tuple[str, ...] = ("https://www.googleapis.com/auth/drive",)
STATE_PREFIX = "drive."
_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN = "https://oauth2.googleapis.com/token"
_REVOKE = "https://oauth2.googleapis.com/revoke"
_FILES = "https://www.googleapis.com/drive/v3/files"
_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
_ABOUT = "https://www.googleapis.com/drive/v3/about?fields=user(emailAddress)"
_FOLDER = "application/vnd.google-apps.folder"
_TOKEN_FILENAME = "drive_token.json"
_TIMEOUT = 30.0
_SKEW = dt.timedelta(seconds=60)


class DriveError(RuntimeError):
    """Drive could not be reached, refused, or is not connected."""


@dataclass(frozen=True)
class Link:
    email: str
    connected_at: str


def configured() -> bool:
    return config.gmail_configured() and bool(config.DRIVE_ASSETS_FOLDER)


def token_path() -> Path:
    return config.DATABASE_PATH.parent / _TOKEN_FILENAME


def _read() -> dict[str, Any]:
    try:
        stored = json.loads(token_path().read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return stored if isinstance(stored, dict) else {}


def _write(data: dict[str, Any]) -> None:
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(path.name + ".new")
    handle = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream)
        staged.chmod(0o600)
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def connected() -> Link | None:
    stored = _read()
    if not stored.get("refresh_token"):
        return None
    return Link(email=str(stored.get("email") or ""), connected_at=str(stored.get("connected_at") or ""))


def _call(url: str, *, form: dict | None = None, body: bytes | None = None, content_type: str = "",
          method: str = "", token: str = "") -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = body
        headers["Content-Type"] = content_type
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310 - fixed Google endpoints
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()[:4096]
        try:
            payload = json.loads(raw or b"{}")
        except ValueError:
            payload = {}
        if exc.code < 500 and isinstance(payload, dict):
            payload.setdefault("error", {"code": exc.code})
            return payload
        raise DriveError(f"Google Drive antwortete mit HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DriveError("Google Drive ist gerade nicht erreichbar") from exc
    text = raw.decode("utf-8", "replace").strip()
    return json.loads(text) if text else {}


def _error(payload: dict) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or "Fehler")
    return str(payload.get("error_description") or error or "")


def new_state() -> str:
    return STATE_PREFIX + secrets.token_urlsafe(32)


def authorize_url(state: str, *, login_hint: str = "") -> str:
    if not configured():
        raise DriveError("Google ist nicht eingerichtet (NEWSPULSE_GMAIL_CLIENT_ID)")
    params = {"client_id": config.gmail_client_id(), "redirect_uri": config.gmail_redirect_uri(),
              "response_type": "code", "scope": " ".join(SCOPES), "access_type": "offline",
              "prompt": "consent select_account", "state": state}
    if login_hint:
        params["login_hint"] = login_hint
    return f"{_AUTH}?{urllib.parse.urlencode(params)}"


def exchange(code: str, *, call=_call) -> Link:
    payload = call(_TOKEN, form={"code": code, "client_id": config.gmail_client_id(),
                                 "client_secret": config.gmail_client_secret(),
                                 "redirect_uri": config.gmail_redirect_uri(), "grant_type": "authorization_code"})
    access, refresh = str(payload.get("access_token") or ""), str(payload.get("refresh_token") or "")
    if payload.get("error") or not access or not refresh:
        raise DriveError(f"Google lehnte die Drive-Anmeldung ab ({_error(payload) or 'kein Refresh-Token'})")
    about = call(_ABOUT, token=access)
    email = str(((about.get("user") or {}).get("emailAddress")) or "")
    now = dt.datetime.now(dt.UTC)
    _write({"refresh_token": refresh, "access_token": access,
            "expires_at": (now + dt.timedelta(seconds=int(payload.get("expires_in") or 0))).isoformat(),
            "email": email, "connected_at": now.isoformat()})
    _log.info("Google Drive connected as %s", email)
    return Link(email=email, connected_at=now.isoformat())


def token(*, call=_call) -> str:
    stored = _read()
    refresh = str(stored.get("refresh_token") or "")
    if not refresh:
        raise DriveError("Google Drive ist nicht verbunden. Unter Einstellungen verbinden.")
    try:
        expires = dt.datetime.fromisoformat(str(stored.get("expires_at")))
    except ValueError:
        expires = None
    if stored.get("access_token") and expires and dt.datetime.now(dt.UTC) < expires - _SKEW:
        return str(stored["access_token"])
    payload = call(_TOKEN, form={"client_id": config.gmail_client_id(), "client_secret": config.gmail_client_secret(),
                                 "refresh_token": refresh, "grant_type": "refresh_token"})
    if payload.get("error") == "invalid_grant":
        token_path().unlink(missing_ok=True)
        raise DriveError("Die Drive-Anmeldung ist abgelaufen. Unter Einstellungen neu verbinden.")
    access = str(payload.get("access_token") or "")
    if not access:
        raise DriveError(f"Drive-Zugriff nicht erneuerbar ({_error(payload)})")
    stored.update(access_token=access, expires_at=(dt.datetime.now(dt.UTC)
                  + dt.timedelta(seconds=int(payload.get("expires_in") or 0))).isoformat())
    _write(stored)
    return access


def disconnect(*, call=_call) -> None:
    stored = _read()
    if stored.get("refresh_token"):
        try:
            call(_REVOKE, form={"token": stored["refresh_token"]})
        except DriveError:
            _log.warning("Drive token deleted locally but not confirmed revoked")
    token_path().unlink(missing_ok=True)


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def client_folder(name: str, *, access: str, call=_call) -> str:
    """The client's folder under "7. Assets", created when it is missing."""
    root = config.DRIVE_ASSETS_FOLDER
    query = (f"'{_quote(root)}' in parents and name = '{_quote(name)}' and mimeType = '{_FOLDER}' and trashed = false")
    found = call(f"{_FILES}?" + urllib.parse.urlencode({
        "q": query, "fields": "files(id,name)", "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true", "corpora": "allDrives"}), token=access)
    if found.get("error"):
        raise DriveError(f"Ordner „7. Assets“ nicht lesbar ({_error(found)})")
    if found.get("files"):
        return str(found["files"][0]["id"])
    made = call(f"{_FILES}?supportsAllDrives=true", body=json.dumps(
        {"name": name, "mimeType": _FOLDER, "parents": [root]}).encode(), content_type="application/json", token=access)
    if made.get("error") or not made.get("id"):
        raise DriveError(f"Kundenordner nicht anlegbar ({_error(made)})")
    return str(made["id"])


def upload(client_name: str, filename: str, mime: str, data: bytes, *, call=_call) -> str:
    """Put one file into the client's folder; returns the link to open it."""
    access = token(call=call)
    folder = client_folder(client_name, access=access, call=call)
    boundary = f"rauteos-{uuid.uuid4().hex}"
    meta = json.dumps({"name": filename, "parents": [folder]}).encode()
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode() + meta
            + f"\r\n--{boundary}\r\nContent-Type: {mime}\r\n\r\n".encode() + data + f"\r\n--{boundary}--".encode())
    made = call(f"{_UPLOAD}?uploadType=multipart&supportsAllDrives=true&fields=id,webViewLink", body=body,
                content_type=f"multipart/related; boundary={boundary}", token=access)
    if made.get("error") or not made.get("id"):
        raise DriveError(f"Datei nicht hochgeladen ({_error(made)})")
    return str(made.get("webViewLink") or f"https://drive.google.com/file/d/{made['id']}/view")


def _bytes(url: str, *, access: str) -> bytes:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {access}"})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310 - fixed Google endpoint
            return response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DriveError("Datei aus Drive nicht ladbar") from exc


#: Google's own formats have no bytes of their own; a mail gets them as these.
_EXPORTS = {"application/vnd.google-apps.document": ("application/pdf", ".pdf"),
            "application/vnd.google-apps.spreadsheet": ("application/pdf", ".pdf"),
            "application/vnd.google-apps.presentation": ("application/pdf", ".pdf")}


def client_files(client_name: str, *, call=_call) -> list[dict]:
    """The files in the client's folder under "7. Assets", newest first."""
    access = token(call=call)
    folder = client_folder(client_name, access=access, call=call)
    found = call(f"{_FILES}?" + urllib.parse.urlencode({
        "q": f"'{_quote(folder)}' in parents and trashed = false and mimeType != '{_FOLDER}'",
        "fields": "files(id,name,mimeType,size,modifiedTime,webViewLink)", "orderBy": "modifiedTime desc",
        "pageSize": "100", "supportsAllDrives": "true", "includeItemsFromAllDrives": "true", "corpora": "allDrives"}),
        token=access)
    if found.get("error"):
        raise DriveError(f"Kundenordner nicht lesbar ({_error(found)})")
    return [dict(id=f["id"], name=f["name"], mime=f.get("mimeType", ""), size=int(f.get("size") or 0),
                 modified=f.get("modifiedTime", ""), url=f.get("webViewLink", "")) for f in found.get("files") or ()]


def download(file_id: str, *, call=_call, fetch=None) -> tuple[str, str, bytes]:
    """``(filename, mime, bytes)`` of one Drive file, Google formats as PDF."""
    access = token(call=call)
    quoted = urllib.parse.quote(file_id, safe="")
    meta = call(f"{_FILES}/{quoted}?fields=name,mimeType&supportsAllDrives=true", token=access)
    if meta.get("error"):
        raise DriveError(f"Datei nicht gefunden ({_error(meta)})")
    name, mime = str(meta.get("name") or "Anhang"), str(meta.get("mimeType") or "application/octet-stream")
    read = fetch or _bytes
    if mime in _EXPORTS:
        target, suffix = _EXPORTS[mime]
        data = read(f"{_FILES}/{quoted}/export?" + urllib.parse.urlencode({"mimeType": target}), access=access)
        return (name if name.endswith(suffix) else name + suffix), target, data
    return name, mime, read(f"{_FILES}/{quoted}?alt=media&supportsAllDrives=true", access=access)
