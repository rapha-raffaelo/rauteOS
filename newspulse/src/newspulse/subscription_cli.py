"""Headless subscription transports for daily search planning; no API keys."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

from . import analyzer, config, shared_guides


def codex_home() -> Path:
    return Path(os.environ.get('NEWSPULSE_CODEX_HOME', str(config.DATABASE_PATH.parent / 'codex')))


def generate(provider: str, prompt: str, *, timeout: float = 180) -> str:
    prompt = shared_guides.enrich_prompt(prompt, channel=f'daily_news_{provider}')
    if provider == 'claude':
        argv = ['claude', '-p', '--output-format', 'json', '--tools', '']
        env = analyzer.claude_env()
        for key in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN'):
            env.pop(key, None)
    elif provider == 'codex':
        argv = ['codex', 'exec', '--skip-git-repo-check', '--ephemeral',
                '--sandbox', 'read-only', '-c', 'approval_policy="never"',
                '-c', 'forced_login_method="chatgpt"', '-c', 'features.shell_tool=false',
                '-c', 'features.view_image=false', '-c', 'web_search="disabled"', '-']
        # Do not inherit app secrets, API credentials or a developer's config.
        env = {k: os.environ[k] for k in ('PATH', 'HOME', 'LANG', 'SSL_CERT_FILE', 'SSL_CERT_DIR') if k in os.environ}
        env['CODEX_HOME'] = str(codex_home())
    else:
        raise ValueError(f'Unknown subscription provider: {provider}')
    try:
        # An empty working directory keeps project instructions out of data-only jobs.
        with tempfile.TemporaryDirectory(prefix='rauteos-news-') as workdir:
            completed = subprocess.run(argv, input=prompt, capture_output=True, text=True,
                                       timeout=timeout, check=False, shell=False, env=env, cwd=workdir)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise analyzer.BackendError(f'{provider}: subscription call unavailable ({type(exc).__name__})') from exc
    if completed.returncode:
        # CLI stderr can contain login/session details. Keep it out of app logs.
        raise analyzer.BackendError(f'{provider}: subscription call failed (exit {completed.returncode}); check login or quota')
    if provider == 'claude':
        return analyzer._extract_cli_result(completed.stdout)
    text = completed.stdout.strip()
    if not text:
        raise analyzer.BackendError('codex: empty subscription response')
    return text
