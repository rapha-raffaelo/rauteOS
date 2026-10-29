"""RauteOS shows no disclosure triangles: every fold opens from a quiet button."""
from pathlib import Path

WEB = Path(__file__).parents[1] / "src" / "newspulse" / "web"


def test_the_shared_stylesheet_hides_every_marker():
    css = (WEB / "static" / "app.css").read_text()
    assert "summary { list-style: none; cursor: pointer; }" in css
    assert "summary::-webkit-details-marker { display: none; }" in css
    assert 'summary::marker { content: ""; }' in css


def test_standalone_documents_with_a_fold_hide_the_marker_themselves():
    """Pages without app.css carry their own rule, or the triangle returns there."""
    for page in (WEB / "templates").glob("*.html"):
        html = page.read_text()
        if "<details" in html and "app.css" not in html and 'extends "base.html"' not in html:
            assert "::-webkit-details-marker { display: none; }" in html, page.name
