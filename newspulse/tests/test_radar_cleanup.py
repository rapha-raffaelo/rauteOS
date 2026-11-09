"""The one-off broom for radar hits that were never this mandate's field."""

from __future__ import annotations

from react_render import rendered

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse import radar_cleanup
from newspulse.models import Article, Base, Client, TopicHit

_NOW = dt.datetime(2026, 8, 15, 9, 0, tzinfo=dt.UTC)


@pytest.fixture
def session():
    # StaticPool, because the TestClient below serves the request on another
    # thread: a plain :memory: engine hands that thread its own empty database and
    # the route fails with "no such table: clients".
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as sess:
        yield sess


def _hit(session, client, title, source="Cointelegraph", *, days=2):
    article = Article(
        title=title, url=f"https://ex.de/{abs(hash(title)) % 10**7}", source=source,
        published_at=_NOW - dt.timedelta(days=days), fetched_at=_NOW,
        summary_text=None, language="de", title_hash=f"{abs(hash(title)):016d}"[:16],
    )
    session.add(article)
    session.flush()
    session.add(TopicHit(client_id=client.id, article_id=article.id, found_at=_NOW))
    session.commit()
    return article


def _client(session, name="Qonto", keywords=("Firmenkunden-Banking",)):
    client = Client(name=name, aliases=[], keywords=list(keywords), alert_topics=[])
    session.add(client)
    session.commit()
    return client


def test_a_survey_changes_nothing(session):
    """The default has to be safe: this deletes rows on a live database."""
    client = _client(session)
    _hit(session, client, "Strategy sells 1,638 Bitcoin to fund dividends")

    found = radar_cleanup.survey(session)

    assert len(found) == 1
    assert session.query(TopicHit).count() == 1


def test_removing_takes_exactly_the_pairs_it_is_given(session):
    """Not "whatever a fresh survey finds": the page renders a bounded list and
    the operator is told to read it, so the button must delete that list and not
    a second query's answer."""
    client = _client(session)
    keep = _hit(session, client, "Firmenkunden-Banking wird zum Preiskampf", "Handelsblatt")
    stray = _hit(session, client, "Putin Signs Russia's First Crypto Law")

    removed = radar_cleanup.remove(session, [(client.id, stray.id)])

    assert removed == 1
    remaining = session.query(TopicHit).all()
    assert [row.article_id for row in remaining] == [keep.id]


def test_removing_nothing_is_not_an_error(session):
    """An empty form posts no rows at all."""
    client = _client(session)
    _hit(session, client, "Putin Signs Russia's First Crypto Law")

    assert radar_cleanup.remove(session, []) == 0
    assert session.query(TopicHit).count() == 1


def test_a_hit_outside_the_window_is_left_alone(session):
    """A mandate given a radar last night would otherwise have its whole archive
    judged against four terms chosen the same night."""
    client = _client(session)
    _hit(session, client, "Uraltes Krypto-Thema", days=200)

    assert radar_cleanup.survey(session) == []


def test_the_article_itself_survives(session):
    """It is another mandate's market, not rubbish. Only the link is cut."""
    client = _client(session)
    stray = _hit(session, client, "Putin Signs Russia's First Crypto Law")

    radar_cleanup.remove(session, [(client.id, stray.id)])

    assert session.get(Article, stray.id) is not None


def test_a_mandate_without_themes_is_left_alone(session):
    """No themes, nothing to judge against — and no radar either. Deleting on a
    standard that cannot be evaluated is guessing."""
    client = _client(session, name="Ohne Themen", keywords=())
    _hit(session, client, "Irgendeine Meldung")

    assert radar_cleanup.survey(session) == []
