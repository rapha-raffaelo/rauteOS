"""The light and dark theme are two sets of token values, nothing more.

That holds only while no rule paints a colour of its own: one hard-coded white
is a white box on the dark page. So the app's stylesheets, and the style blocks
in the page templates, may name colours through tokens only. Logos are the
exception, because a logo is drawn for a white ground.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "newspulse" / "src" / "newspulse" / "web"
STYLESHEETS = [WEB / "static" / "app.css", WEB / "static" / "studio.css",
               *sorted((ROOT / "frontend" / "src").glob("*.css")),
               *sorted((ROOT / "frontend" / "src").glob("*/*.css"))]
# Pages that leave the app: printed documents and the client's own
# questionnaire. They are always light, on purpose.
STANDALONE = {"onboarding.css"}
LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\((?!\s*var)|:\s*(white|black)\b")


def _literals(css):
    css = re.sub(r":root(\[data-theme=\"dark\"\])?\s*\{[^}]*\}", "", css)
    for rule in re.findall(r"[^{}]*\{[^{}]*\}", css):
        selector, body = rule.split("{", 1)
        for decl in body.rstrip("}").split(";"):
            decl = decl.strip()
            if not decl or decl.startswith("--") or "shadow" in decl:
                continue
            if "logo" in selector and decl.replace(" ", "") == "background:#fff":
                continue
            if LITERAL.search(decl):
                yield f"{selector.strip()[-60:]} {{ {decl} }}"


def test_the_app_styles_name_colours_only_through_tokens():
    found = [f"{path.name}: {hit}" for path in STYLESHEETS if path.name not in STANDALONE
             for hit in _literals(path.read_text())]
    assert found == []


def test_the_page_style_blocks_name_colours_only_through_tokens():
    found = []
    for page in (WEB / "templates").rglob("*.html"):
        text = page.read_text()
        if "<html" in text and "{% extends" not in text:
            continue  # a standalone document: report, plan, packet, login
        for block in re.findall(r"<style[^>]*>(.*?)</style>", text, re.S):
            found += [f"{page.name}: {hit}" for hit in _literals(block)]
    assert found == []


def test_dunkel_is_the_prototype_and_hell_the_original():
    css = (WEB / "static" / "app.css").read_text()
    light = re.search(r":root\s*\{([^}]*)\}", css).group(1)
    dark = re.search(r":root\[data-theme=\"dark\"\]\s*\{([^}]*)\}", css).group(1)
    assert "--accent-rgb: 109 74 255" in light, "Hell keeps the violet"
    assert "--side-bg: #f0f2f5" in light, "and the light sidebar"
    assert "--side-bg: #181a19" in dark, "Dunkel has the black sidebar"
    assert "--side-on-bg: var(--lime)" in dark and "--assist: var(--lime)" in dark


def test_the_theme_is_set_before_the_first_paint():
    base = (WEB / "templates" / "base.html").read_text()
    head = base[: base.index("</head>")]
    assert "raute-theme" in head and "data-theme" in head
    assert head.index("raute-theme") < head.index("app.css")
