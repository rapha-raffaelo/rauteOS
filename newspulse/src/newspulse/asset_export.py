"""Assets as Word or PDF (Spec 12): one asset, or a whole Thema with its Deep Dive.

A document here is a list of sections, each a heading and its paragraphs, so
one builder serves both formats and both sizes. The text is the stored text,
never re-generated: what is exported is what Lucas saved.
"""
from __future__ import annotations

import datetime as dt
import io
import re
from dataclasses import dataclass, field

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF = "application/pdf"
MIME = {"docx": DOCX, "pdf": PDF}


@dataclass(frozen=True)
class Section:
    heading: str
    body: str
    kicker: str = ""


@dataclass(frozen=True)
class Document:
    title: str
    client: str
    sections: list[Section] = field(default_factory=list)
    when: dt.date = field(default_factory=lambda: dt.date.today())
    #: The logo in the head of the page, as image bytes; ``None`` for none.
    logo: bytes | None = None


def _png(data: bytes | None) -> tuple[bytes, float] | None:
    """The logo as PNG and its aspect ratio, or ``None`` if it is no image."""
    if not data:
        return None
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(data))
        image.load()
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA")
        out = io.BytesIO()
        image.save(out, format="PNG")
        return out.getvalue(), image.height / max(1, image.width)
    except Exception:  # noqa: BLE001 - a logo that does not decode is left out, never the document
        return None


def filename(document: Document, fmt: str) -> str:
    stem = re.sub(r"[^\w\- ]+", "", f"{document.when:%Y-%m-%d} {document.client} {document.title}").strip()
    stem = re.sub(r"\s+", " ", stem)[:120]
    return f"{stem}.{fmt}"


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]


def docx(document: Document) -> bytes:
    from docx import Document as Word
    from docx.shared import Pt

    word = Word()
    word.core_properties.title = document.title
    logo = _png(document.logo)
    if logo:
        from docx.shared import Cm

        word.add_picture(io.BytesIO(logo[0]), width=Cm(min(4.5, 1.6 / max(logo[1], 0.01))))
    word.add_paragraph(f"{document.client} · {document.when:%d.%m.%Y}").runs[0].font.size = Pt(9)
    word.add_heading(document.title, level=1)
    for section in document.sections:
        if section.kicker:
            word.add_paragraph(section.kicker).runs[0].font.size = Pt(9)
        if section.heading:
            word.add_heading(section.heading, level=2)
        for paragraph in _paragraphs(section.body):
            word.add_paragraph(paragraph)
    out = io.BytesIO()
    word.save(out)
    return out.getvalue()


def pdf(document: Document) -> bytes:
    from xml.sax.saxutils import escape

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm, title=document.title)
    story = []
    logo = _png(document.logo)
    if logo:
        width = min(4.5 * cm, 1.6 * cm / max(logo[1], 0.01))
        picture = Image(io.BytesIO(logo[0]), width=width, height=width * logo[1])
        picture.hAlign = "LEFT"
        story += [picture, Spacer(1, 10)]
    story += [Paragraph(escape(f"{document.client} · {document.when:%d.%m.%Y}"), styles["Normal"]),
              Spacer(1, 8), Paragraph(escape(document.title), styles["Title"])]
    for section in document.sections:
        if section.kicker:
            story.append(Paragraph(escape(section.kicker), styles["Italic"]))
        if section.heading:
            story.append(Paragraph(escape(section.heading), styles["Heading2"]))
        for paragraph in _paragraphs(section.body):
            story.append(Paragraph(escape(paragraph).replace("\n", "<br/>"), styles["BodyText"]))
            story.append(Spacer(1, 4))
    doc.build(story)
    return out.getvalue()


def render(document: Document, fmt: str) -> bytes:
    if fmt == "docx":
        return docx(document)
    if fmt == "pdf":
        return pdf(document)
    raise ValueError("Unbekanntes Format.")
