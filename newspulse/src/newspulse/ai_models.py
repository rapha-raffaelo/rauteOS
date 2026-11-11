"""KI-Modelle: which provider answers in which role, and the keys to reach them.

Three providers (Claude, OpenAI, Gemini) and three roles:

* **Designer** writes: drafts, impulses, research answers. Every call that went
  through :func:`newspulse.analyzer.invoke_with_fallback` is the designer's.
* **Reviewer** reads a finished text against sources and profile. Never the
  designer's first model: a self-check reliably answers "looks good".
* **Lektor** smooths language and style of a finished text without changing
  what it says. Off until a provider is assigned.

Each role holds an order of providers. The first connected one answers; the next
steps in when it is out of quota, unreachable or refuses the key. A broken prompt
still fails loudly rather than being re-run on another metered account.

Keys entered in the settings are stored encrypted in the ``settings`` table. The
encryption key is derived from ``NEWSPULSE_SESSION_SECRET`` and never stored, so
a copy of the database alone does not hand out the keys. Without that secret no
key can be stored. Keys from the environment keep working as before.

OpenAI takes no key at all: it runs over the ChatGPT subscription through the
Codex CLI (:mod:`newspulse.codex_cli`), logged in once on the server with
``codex login --device-auth``. No path here sends a prompt to the metered
OpenAI API.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from pathlib import Path
import shutil
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass

from . import config

_log = logging.getLogger(__name__)

PROVIDERS: dict[str, dict[str, str]] = {
    "claude": {"label": "Claude", "vendor": "Anthropic", "model": "claude-sonnet-5"},
    "openai": {"label": "OpenAI", "vendor": "ChatGPT-Abo", "model": ""},
    "gemini": {"label": "Gemini", "vendor": "Google", "model": ""},
}

ROLES: dict[str, tuple[str, str]] = {
    "designer": ("Designer", "Schreibt Entwürfe, Impulse und Recherche-Antworten."),
    "reviewer": ("Reviewer", "Prüft fertige Texte gegen Quellen und Profil. Nie das erste Modell des Designers."),
    "lektor": ("Lektor", "Glättet Sprache und Stil fertiger Texte, ohne Inhalte zu ändern."),
}

#: What the tool did before this page existed: Claude writes and Gemini steps
#: in, Gemini cross-reads, nobody polishes.
DEFAULT_ORDER: dict[str, list[str]] = {
    "designer": ["claude", "gemini"],
    "reviewer": ["gemini"],
    "lektor": [],
}

_KEY_PREFIX = "ai_key:"
_MODEL_PREFIX = "ai_model:"
_ROLES_KEY = "ai_roles"
_ENV_KEYS = {
    "claude": ("NEWSPULSE_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
    "gemini": ("NEWSPULSE_GEMINI_API_KEY", "GEMINI_API_KEY"),
}


#: Providers reached only through a subscription CLI login, never with a key.
SUBSCRIPTION_ONLY = frozenset({"openai"})

#: How to log in, shown in the settings for a provider without a key field.
LOGIN_COMMAND = {"openai": "docker compose exec app codex login --device-auth"}


class NotConnected(Exception):
    """The provider has neither a key nor (for Claude) a subscription login."""


class NoSecret(Exception):
    """``NEWSPULSE_SESSION_SECRET`` is unset, so a key cannot be stored safely."""


# --- Keys --------------------------------------------------------------------------


def _fernet():
    secret = config.session_secret()
    if not secret:
        raise NoSecret("NEWSPULSE_SESSION_SECRET ist nicht gesetzt; ohne ihn wird kein Schlüssel gespeichert.")
    from cryptography.fernet import Fernet

    digest = hashlib.sha256(b"rauteos-ai-keys:" + secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


class _SettingsUnreadable(Exception):
    """The settings table could not be read; fall back to defaults."""


class _NoSettings:
    """Stands in for a session when there is no database to read."""

    def get(self, *_args):
        return None


@contextmanager
def _open():
    """The one place this module opens the database (tests replace it)."""
    from .db import get_session

    with get_session() as session:
        yield session


def _setting(session, key: str) -> str:
    from .models import Setting

    try:
        row = session.get(Setting, key)
    except Exception as exc:  # noqa: BLE001 - a missing table is "nothing set"
        raise _SettingsUnreadable() from exc
    return (row.value or "") if row else ""


def _put(session, key: str, value: str | None) -> None:
    from .models import Setting

    row = session.get(Setting, key)
    if value is None:
        if row is not None:
            session.delete(row)
    elif row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value


def stored_key(session, provider: str) -> str:
    """The key entered in the settings, decrypted, or "" when none (or unreadable)."""
    if provider in SUBSCRIPTION_ONLY:
        return ""
    token = _setting(session, _KEY_PREFIX + provider)
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except Exception:  # noqa: BLE001 - a rotated secret makes the key unreadable, not the app
        _log.warning("stored %s key cannot be decrypted (secret changed?)", provider)
        return ""


def env_key(provider: str, role: str | None = None) -> str:
    """A key from the server's environment.

    The bare ``GEMINI_API_KEY`` only counts for the reviewer. Writing or
    polishing with Gemini sends client coverage to Google, which needs the
    explicitly named ``NEWSPULSE_GEMINI_API_KEY`` (or a key entered in the
    settings): two different things to consent to, see ``config.review_api_key``.
    """
    if provider in SUBSCRIPTION_ONLY:
        return ""
    if provider == "gemini":
        if role == "reviewer":
            return config.review_api_key() if config.review_configured() else ""
        return config.gemini_api_key()
    names = _ENV_KEYS[provider]
    return next((os.environ[n].strip() for n in names if os.environ.get(n, "").strip()), "")


def api_key(session, provider: str, role: str | None = None) -> str:
    """The key to call ``provider`` with: the settings' one first, then the environment."""
    return stored_key(session, provider) or env_key(provider, role)


def save_key(session, provider: str, key: str, model: str = "") -> None:
    if provider not in PROVIDERS:
        raise ValueError("Unbekannter Anbieter.")
    model = validate_model(model)
    key = key.strip()
    if key and provider in SUBSCRIPTION_ONLY:
        raise ValueError(f"{PROVIDERS[provider]['label']} wird über das Abo angemeldet, nicht mit einem Schlüssel.")
    if key:
        _put(session, _KEY_PREFIX + provider, _fernet().encrypt(key.encode()).decode())
    _put(session, _MODEL_PREFIX + provider, model.strip() or None)
    session.commit()


def forget_key(session, provider: str) -> None:
    _put(session, _KEY_PREFIX + provider, None)
    session.commit()


def model_for(session, provider: str, role: str | None = None) -> str:
    stored = role_models(session).get(role, {}).get(provider, "") if role else ""
    stored = stored or _setting(session, _MODEL_PREFIX + provider)
    if stored:
        return stored
    if provider == "gemini":
        return config.review_model() if role == "reviewer" else config.GEMINI_MODEL
    return PROVIDERS[provider]["model"]


def validate_model(model: str) -> str:
    model = model.strip()
    if model and (len(model) > 100 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/\[\]-]*", model)):
        raise ValueError("Bitte eine gültige Modell-ID auswählen oder eingeben.")
    return model


def role_models(session) -> dict:
    try:
        value = json.loads(_setting(session, "ai_role_models") or "{}")
    except json.JSONDecodeError:
        return {}
    return {r: {p: m for p, m in v.items() if p in PROVIDERS and isinstance(m, str)}
            for r, v in value.items() if r in ROLES and isinstance(v, dict)} if isinstance(value, dict) else {}


def model_options(session, provider: str) -> list[str]:
    """Offer configured IDs and local CLI catalogue entries, not a guessed model list."""
    options = [model_for(session, provider), PROVIDERS[provider]["model"]]
    options.extend(model_for(session, provider, role) for role in ROLES)
    if provider == "claude" and not api_key(session, provider):
        options.extend(["sonnet", "opus", "haiku"])
    if provider == "gemini":
        options.extend([config.GEMINI_MODEL, config.review_model()])
    if provider == "openai":
        try:
            cache = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "models_cache.json"
            data = json.loads(cache.read_text())
            options.extend(m.get("slug", "") for m in data.get("models", []) if isinstance(m, dict))
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    return list(dict.fromkeys(x for x in options if x))


def _claude_cli() -> bool:
    return shutil.which("claude") is not None


def _codex_login() -> bool:
    from . import codex_cli

    return codex_cli.logged_in()


@dataclass(frozen=True)
class Status:
    provider: str
    connected: bool
    how: str  # "Schlüssel aus den Einstellungen", "Server-Konfiguration", "Claude-Abo (CLI)", "ChatGPT-Abo (Codex CLI)", ""
    hint: str  # the last four characters of a stored key, never more
    model: str


def status(session, provider: str, role: str | None = None) -> Status:
    stored, env = stored_key(session, provider), env_key(provider, role)
    if stored:
        how, hint = "Schlüssel aus den Einstellungen", stored[-4:]
    elif env:
        how, hint = "Server-Konfiguration", ""
    elif provider == "claude" and _claude_cli():
        how, hint = "Claude-Abo (CLI)", ""
    elif provider == "openai" and _codex_login():
        how, hint = "ChatGPT-Abo (Codex CLI)", ""
    else:
        how, hint = "", ""
    return Status(provider, bool(how), how, hint, model_for(session, provider, role))


# --- Roles -------------------------------------------------------------------------


def order(session) -> dict[str, list[str]]:
    """Each role's providers, first choice first. Unknown names are dropped."""
    raw = _setting(session, _ROLES_KEY)
    try:
        saved = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        saved = {}
    result = {}
    for role, default in DEFAULT_ORDER.items():
        chosen = saved.get(role, default) if isinstance(saved, dict) else default
        result[role] = [p for p in dict.fromkeys(chosen if isinstance(chosen, list) else []) if p in PROVIDERS]
    return result


def save_order(session, roles: dict[str, list[str]], models: dict | None = None) -> None:
    """Store the order; the reviewer may not start with the designer's first model."""
    if any(len([p for p in roles.get(r, []) if p]) != len(set(p for p in roles.get(r, []) if p)) for r in ROLES):
        raise ValueError("Bitte jeden Anbieter pro Rolle nur einmal auswählen.")
    clean = {role: [p for p in dict.fromkeys(roles.get(role, [])) if p in PROVIDERS] for role in ROLES}
    if clean["designer"] and clean["reviewer"] and clean["designer"][0] == clean["reviewer"][0]:
        raise ValueError("Der Reviewer braucht ein anderes erstes Modell als der Designer, sonst prüft ein Modell sich selbst.")
    if models is not None:
        checked = {r: {p: validate_model(m) for p, m in models.get(r, {}).items()
                       if p in clean[r]} for r in ROLES}
        _put(session, "ai_role_models", json.dumps(checked))
    _put(session, _ROLES_KEY, json.dumps(clean))
    session.commit()


# --- Calling -----------------------------------------------------------------------


def _post(url: str, body: dict, headers: dict, timeout: float, name: str) -> dict:
    from .analyzer import BackendError

    request = urllib.request.Request(  # noqa: S310 - fixed https endpoints below
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace")[:500]
        except Exception:  # noqa: BLE001
            detail = ""
        raise BackendError(f"{name} HTTP {exc.code}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise BackendError(f"{name} unreachable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise BackendError(f"{name} timed out after {timeout}s") from exc
    except json.JSONDecodeError as exc:
        raise BackendError(f"{name} did not return JSON: {exc}") from exc


def call(session, provider: str, prompt: str, *, timeout: float, role: str | None = None) -> str:
    """One prompt to one provider. Raises :class:`NotConnected` or ``BackendError``."""
    from . import shared_guides
    from .analyzer import BackendError

    key = api_key(session, provider, role)
    model = model_for(session, provider, role)
    if provider == "gemini":
        # Without a key of its own, the configured fallback resolves its key
        # inside gemini.generate, as it did before roles existed.
        if not key and (role == "reviewer" or not config.gemini_configured()):
            raise NotConnected("Gemini ist nicht verbunden.")
        from . import gemini

        return gemini.generate(prompt, timeout=timeout, model=model, api_key=key or None)
    if provider == "claude" and not key:
        # The subscription, exactly as before this page existed.
        from . import analyzer

        return analyzer.invoke_claude_cli(prompt, timeout=timeout, model=model)
    if provider == "openai":
        # The ChatGPT subscription through the Codex CLI; never an API key.
        from . import codex_cli

        if not codex_cli.logged_in():
            raise NotConnected("OpenAI ist nicht angemeldet: auf dem Server codex login --device-auth ausführen.")
        return codex_cli.run(shared_guides.enrich_prompt(prompt, channel="openai_codex"),
                             timeout=timeout, model=model)
    if not key:
        raise NotConnected(f"{PROVIDERS[provider]['label']} ist nicht verbunden.")
    prompt = shared_guides.enrich_prompt(prompt, channel=f"{provider}_api")
    payload = _post("https://api.anthropic.com/v1/messages",
                    {"model": model, "max_tokens": 8192, "messages": [{"role": "user", "content": prompt}]},
                    {"x-api-key": key, "anthropic-version": "2023-06-01"}, timeout, "Claude")
    text = "".join(b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")
    if not text.strip():
        raise BackendError(f"{PROVIDERS[provider]['label']} returned no text")
    return text


def _steps_aside(exc: Exception) -> bool:
    """Whether the next provider in the order should try: out of quota, not
    connected, or the key refused. Anything else is the prompt's fault."""
    from .quota import is_quota_error

    if isinstance(exc, NotConnected) or is_quota_error(exc):
        return True
    text = str(exc)
    # "401 Unauthorized" is how the Codex CLI reports an expired login.
    return (any(f"HTTP {code}" in text for code in (401, 403)) or "unreachable" in text
            or "401 Unauthorized" in text)


def ask(role: str, prompt: str, *, timeout: float, session=None, providers: list[str] | None = None) -> str:
    """The role's answer: its providers in order until one answers."""
    from .analyzer import BackendError

    if session is None:
        try:
            with _open() as own:
                return ask(role, prompt, timeout=timeout, session=own, providers=providers)
        except _SettingsUnreadable:
            # No settings table to read (a fresh CLI, a test): the defaults and
            # the environment's keys, which is what the tool did before.
            return ask(role, prompt, timeout=timeout, session=_NoSettings(), providers=providers)
    try:
        chain = providers if providers is not None else order(session)[role]
    except Exception as exc:  # noqa: BLE001 - only the read is guarded, never the call
        if isinstance(session, _NoSettings):
            raise
        raise _SettingsUnreadable() from exc
    if not chain:
        raise NotConnected(f"Für die Rolle {ROLES[role][0]} ist kein Modell eingestellt.")
    failures: list[Exception] = []
    for provider in chain:
        try:
            return call(session, provider, prompt, timeout=timeout, role=role)
        except (NotConnected, BackendError) as exc:
            if not _steps_aside(exc):
                raise
            _log.warning("%s: %s steps aside (%s)", role, provider, exc)
            failures.append(exc)
    # The first real failure says the most (the quota of the model that was
    # meant to answer); a provider that is merely not connected says least.
    real = [f for f in failures if not isinstance(f, NotConnected)]
    if real:
        raise real[0]
    raise BackendError(str(failures[0])) from failures[0]


def caller(role: str):
    """``ask`` bound to a role, in the shape the existing callers take: ``(prompt, timeout=...)``."""
    def _call(prompt: str, *, timeout: float = 600.0, **_ignored) -> str:
        return ask(role, prompt, timeout=timeout)
    return _call


def has_role(role: str) -> bool:
    """Whether any provider of ``role`` is connected. Unreadable settings mean
    the defaults, read against the environment."""
    try:
        with _open() as session:
            return any(status(session, p, role).connected for p in order(session)[role])
    except Exception:  # noqa: BLE001 - no settings table is "nothing configured"
        none = _NoSettings()
        return any(status(none, p, role).connected for p in DEFAULT_ORDER[role])


def reviewer_model() -> str:
    """The model a cross-check is filed under: the reviewer's first connected one."""
    try:
        with _open() as session:
            return _first_connected(session, "reviewer")
    except Exception:  # noqa: BLE001
        return _first_connected(_NoSettings(), "reviewer")


def _first_connected(session, role: str) -> str:
    for provider in order(session)[role]:
        state = status(session, provider, role)
        if state.connected:
            return state.model or PROVIDERS[provider]["label"]
    return config.review_model()


def test(session, provider: str) -> str:
    """A minimal call that says whether the connection works."""
    reply = call(session, provider, "Antworte nur mit dem Wort: ok", timeout=60)
    return reply.strip()[:40]
