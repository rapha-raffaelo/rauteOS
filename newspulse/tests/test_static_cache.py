"""Loading speed: what the browser may keep, and what it may fetch ahead."""
from fastapi.testclient import TestClient

from newspulse.web import frontend
from newspulse.web.app import _STATIC_DIR, create_app


def test_a_versioned_file_is_kept_for_a_year_and_the_rest_is_checked():
    web = TestClient(create_app())
    assert web.get("/static/app.css?v=abc").headers["cache-control"] == "public, max-age=31536000, immutable"
    assert web.get("/static/app.css").headers["cache-control"] == "no-cache"
    bundles = sorted((_STATIC_DIR / "react" / "assets").glob("*.js")) if (_STATIC_DIR / "react" / "assets").is_dir() else []
    if bundles:
        assert "immutable" in web.get(f"/static/react/assets/{bundles[0].name}").headers["cache-control"]


def test_a_page_names_the_chunks_it_imports_for_preloading():
    found = frontend.page_assets("mailbox")
    if found is None:  # a checkout without a frontend build
        return
    assert found["script"].startswith("/static/react/") and isinstance(found["preload"], list)
    assert all(path.startswith("/static/react/") for path in found["preload"])
