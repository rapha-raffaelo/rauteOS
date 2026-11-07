"""The mandate's phone book: the people at the client, and who of them speaks.

A person is a row, not a sentence in a profile field, so a chance can name one
of them as its speaker. Who may speak to the press is the "Medien" switch;
RauteOS proposes among those by their Themenverantwortung.

The profile's free-text field "Sprecher" is what every older reader (crisis
texts, scenarios, the speaker picker of a mandate without a phone book) still
asks for, so the media contacts are written into it as one line each time the
book changes. The book is the consultant's own entry, and so is that line.
"Pressekontakt" stays a field of its own: the research proposes it.
"""
from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import profile
from .models import Client, ClientPerson

_LINKEDIN = re.compile(r"^https://([a-z]{2,3}\.)?linkedin\.com/in/[^/?#\s]+/?$", re.IGNORECASE)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_WORD = re.compile(r"[a-zäöüß0-9]{4,}", re.IGNORECASE)


class Invalid(ValueError):
    """A value the book does not take, said in German for the page."""


def book(session: Session, client_id: int) -> list[ClientPerson]:
    """Media contacts first, then by name."""
    rows = session.scalars(select(ClientPerson).where(ClientPerson.client_id == client_id))
    return sorted(rows, key=lambda p: (not p.media_contact, p.name.casefold()))


def media(session: Session, client_id: int) -> list[ClientPerson]:
    return [p for p in book(session, client_id) if p.media_contact]


def label(person: ClientPerson) -> str:
    """How a text names the person: "Name, Position"."""
    return ", ".join(v for v in (person.name, person.position) if v)


def _text(form: Mapping, key: str, limit: int) -> str:
    return str(form.get(key) or "").strip()[:limit]


def save(session: Session, client: Client, form: Mapping, person: ClientPerson | None = None) -> ClientPerson:
    name = _text(form, "name", 200)
    if not name:
        raise Invalid("Bitte einen Namen.")
    email = _text(form, "email", 320)
    if email and not _EMAIL.match(email):
        raise Invalid("Die E-Mail-Adresse sieht nicht vollständig aus.")
    linkedin = _text(form, "linkedin_url", 500)
    if linkedin and not linkedin.lower().startswith("http"):
        linkedin = "https://" + linkedin
    if linkedin and not _LINKEDIN.match(linkedin):
        raise Invalid("Der LinkedIn-Link führt nicht auf ein Profil (linkedin.com/in/…).")
    person = person or ClientPerson(client_id=client.id)
    person.name = name
    person.position = _text(form, "position", 200)
    person.phone = _text(form, "phone", 80)
    person.email = email
    person.linkedin_url = linkedin
    person.topics = _text(form, "topics", 2000)
    person.media_contact = str(form.get("media_contact", "")) in {"1", "on", "true"}
    person.updated_at = dt.datetime.now(dt.UTC)
    session.add(person)
    session.commit()
    sync_profile(session, client)
    return person


def set_media(session: Session, client: Client, person: ClientPerson, on: bool) -> ClientPerson:
    person.media_contact = on
    person.updated_at = dt.datetime.now(dt.UTC)
    session.commit()
    sync_profile(session, client)
    return person


def delete(session: Session, client: Client, person: ClientPerson) -> None:
    session.delete(person)
    session.commit()
    sync_profile(session, client)


def sync_profile(session: Session, client: Client) -> None:
    """Write the media contacts into "Sprecher".

    Only while there are media contacts: a book without one leaves whatever the
    fields said before, because an empty book is not a statement that nobody
    speaks.
    """
    speakers = media(session, client.id)
    if not speakers:
        return
    line = "; ".join(label(p) + (f" (Themen: {p.topics.strip()})" if p.topics.strip() else "")
                     for p in speakers)
    profile.save(session, client, "sprecher", line[:2000])


def _words(text: str) -> set[str]:
    return {w.casefold() for w in _WORD.findall(text or "")}


def _shared(topics: set[str], text: set[str]) -> set[str]:
    """Topic words the text also uses, by stem: German builds compounds, so
    "Kredite" is in "Kreditkosten" and "Regulierung" in "Bankenregulierung"."""
    def stem(word: str) -> str:
        return word[:max(5, len(word) - 2)]
    return {t for t in topics if any(stem(t) in w for w in text)}


def proposal(session: Session, client_id: int, about: str) -> tuple[ClientPerson, str] | None:
    """The media contact whose Themenverantwortung shares most words with
    ``about``, and why. One media contact is the proposal by default; several
    with nothing in common with the chance are not guessed between."""
    speakers = media(session, client_id)
    if not speakers:
        return None
    wanted = _words(about)
    scored = sorted(((len(_shared(_words(p.topics), wanted)), p) for p in speakers), key=lambda s: -s[0])
    best, person = scored[0]
    if best:
        hits = _shared(_words(person.topics), wanted)
        shared = list(dict.fromkeys(w for w in _WORD.findall(person.topics) if w.casefold() in hits))[:3]
        return person, f"Themenverantwortung passt: {', '.join(shared)}"
    if len(speakers) == 1:
        return person, "Einziger Medienansprechpartner im Profil"
    return None


def as_dict(person: ClientPerson) -> dict:
    return dict(id=person.id, name=person.name, position=person.position, phone=person.phone,
                email=person.email, linkedin_url=person.linkedin_url,
                topics=person.topics, media_contact=person.media_contact)
