"""Statische Dateien sagen, wie lange sie gelten dürfen.

Am 13.10.2026 an der Produktion gemessen: die Antwort trug ein ETag und *kein*
``Cache-Control``. Damit fragt der Browser bei jedem Seitenwechsel jede Datei
erneut nach und wartet auf je eine 304-Antwort — app.css mit 156 kB,
jsx-runtime mit 214 kB, platform mit 50 kB, dazu der Chunk der Seite.

Der Server antwortet in 40 Millisekunden. Die Zeit, die beim Durchklicken
spürbar war, verging im Warten auf diese Rückfragen.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from newspulse.web.app import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def _cache(response) -> str:
    return response.headers.get("cache-control", "")


def test_a_hashed_bundle_may_be_kept_for_a_year(client):
    """Ändert sich der Inhalt, ändert sich der Name. ``immutable`` sagt dem
    Browser genau das — er fragt dann nicht einmal mehr nach."""
    import pathlib

    from newspulse.web import app as web_app

    assets = pathlib.Path(web_app._STATIC_DIR) / "react" / "assets"
    hashed = sorted(assets.glob("*-*.js")) if assets.is_dir() else []
    if not hashed:
        pytest.skip("kein gebautes Frontend in diesem Baum")

    response = client.get(f"/static/react/assets/{hashed[0].name}")

    assert response.status_code == 200
    assert "immutable" in _cache(response)
    assert "max-age=31536000" in _cache(response)


def test_a_file_without_a_hash_gets_a_short_life(client):
    """app.css trägt seinen Stand in der Abfrage, nicht im Namen. Eine Stunde
    ist kurz genug, dass ein vergessener Versionsparameter nicht zum
    Tagesproblem wird — und lang genug, dass der Klick von Seite zu Seite sie
    nicht erneut holt."""
    response = client.get("/static/app.css")

    assert response.status_code == 200
    assert "max-age=3600" in _cache(response)
    assert "immutable" not in _cache(response)


@pytest.mark.parametrize(
    "name",
    [
        "app.css",
        "logo.svg",
        "htmx.min.js",          # mitgeliefert, aber ohne Hash im Namen
        "react/assets/x.js",    # zu kurz, um ein Hash zu sein
        "style-v2.css",
    ],
)
def test_only_a_real_content_hash_counts_as_one(name):
    """Der teure Fehler liegt in dieser Richtung: eine Datei ohne Inhalts-Hash
    ein Jahr lang festzuschreiben heisst, eine Korrektur erst nach einem Jahr
    auszuliefern."""
    from newspulse.web.app import _CachedStatic

    assert not _CachedStatic._HASHED.search(name)


@pytest.mark.parametrize(
    "name",
    [
        "platform-D-D-sGf3.js",
        "jsx-runtime-CiBsg3rq.js",
        "TwinPage-T5BYDw5_.js",
        "index-a1b2c3d4.css",
    ],
)
def test_vite_output_is_recognised_as_hashed(name):
    from newspulse.web.app import _CachedStatic

    assert _CachedStatic._HASHED.search(name)
