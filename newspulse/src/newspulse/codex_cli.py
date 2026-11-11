"""OpenAI through the ChatGPT subscription: one ``codex exec`` call per prompt.

The counterpart of :func:`newspulse.analyzer.invoke_claude_cli`. No API key is
ever used here: the Codex CLI reads its ChatGPT login from ``$CODEX_HOME``
(``/data/codex`` on the server, on the volume beside the database), so the
consumption runs over the subscription of whoever logged in with
``codex login --device-auth``.

Two guards keep it that way:

* ``OPENAI_API_KEY`` and ``CODEX_API_KEY`` are removed from the subprocess's
  environment, and the login method is forced to ChatGPT, so a key lying around
  on the server can never turn this into metered API spend.
* A login made with an API key (``codex login --with-api-key``) does not count as
  connected: :func:`logged_in` only accepts the ChatGPT tokens.

Codex is an agent. It runs in a read-only sandbox, in an empty temporary
directory, without persisting a session, so a prompt can make it think but not
change anything on the server.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

_TIMEOUT_SECONDS = 600.0
_SCRUBBED = ("OPENAI_API_KEY", "CODEX_API_KEY", "NEWSPULSE_OPENAI_API_KEY")


def home() -> Path:
    """Where the CLI keeps its login: ``$CODEX_HOME``, else ``~/.codex``."""
    return Path(os.environ.get("CODEX_HOME") or "~/.codex").expanduser()


def installed() -> bool:
    return shutil.which("codex") is not None


def logged_in() -> bool:
    """Whether the CLI is installed and holds a ChatGPT login (not an API key)."""
    if not installed():
        return False
    try:
        auth = json.loads((home() / "auth.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(auth, dict) and bool(auth.get("tokens")) and not auth.get("OPENAI_API_KEY")


def env() -> dict[str, str]:
    environment = {k: v for k, v in os.environ.items() if k not in _SCRUBBED}
    environment["CODEX_HOME"] = str(home())
    return environment


def run(prompt: str, *, timeout: float = _TIMEOUT_SECONDS, model: str = "") -> str:
    """The model's final answer to ``prompt``. Raises ``BackendError``."""
    from .analyzer import BackendError

    with tempfile.TemporaryDirectory(prefix="rauteos-codex-") as workdir:
        answer = Path(workdir) / "answer.txt"
        argv = [
            "codex", "exec",
            "--skip-git-repo-check", "--ephemeral", "--color", "never",
            "--sandbox", "read-only",
            "-c", 'forced_login_method="chatgpt"',
            "--cd", workdir,
            "--output-last-message", str(answer),
        ]
        if model:
            argv += ["--model", model]
        argv.append("-")  # the prompt comes on stdin, never as an argument
        try:
            completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, prompt on stdin
                argv, input=prompt, capture_output=True, text=True, timeout=timeout,
                check=False, shell=False, env=env(), cwd=workdir,
            )
        except subprocess.TimeoutExpired as exc:
            raise BackendError(f"codex exec timed out after {timeout}s") from exc
        except FileNotFoundError as exc:
            raise BackendError("codex CLI not found on PATH") from exc
        text = answer.read_text(encoding="utf-8", errors="replace") if answer.exists() else ""
    if completed.returncode != 0:
        detail = ((completed.stderr or "") + "\n" + (completed.stdout or "")).strip()[-500:]
        raise BackendError(f"codex exec failed ({completed.returncode}): {detail}")
    if not text.strip():
        raise BackendError("OpenAI (Codex) returned no text")
    return text.strip()
