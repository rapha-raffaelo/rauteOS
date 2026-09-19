import datetime as dt
import json

import pytest
from sqlalchemy import select, func

from newspulse import assets, default_drafts
from newspulse.models import Angle, Asset, Client, DefaultDraftJob
from newspulse.streaming import StreamEvent
from test_assets import factory, session, _mandate, _drafted


def test_discovery_backfills_each_active_client_newest_first_without_page_visit(session):
    c1, a1 = _mandate(session)
    c2, a2 = _mandate(session, articles=0)
    old = Angle(client_id=c1.id, subject='Old', message='Old', context='Old', generated_at=dt.datetime(2020,1,1,tzinfo=dt.UTC))
    dismissed = Angle(client_id=c1.id, subject='Gone', message='', context='', dismissed_at=dt.datetime.now(dt.UTC))
    c3, a3 = _mandate(session, articles=0); c3.active = False
    c4, a4 = _mandate(session, articles=0); c4.is_competitor = True
    session.add_all([old, dismissed]); session.commit()
    default_drafts.discover(session)
    default_drafts.discover(session)
    jobs = session.scalars(select(DefaultDraftJob).order_by(DefaultDraftJob.created_at)).all()
    assert {j.angle_id for j in jobs[:2]} == {a1.id, a2.id}
    assert [j.angle_id for j in jobs[2:]] == [old.id]
    assert all(j.status == 'queued' for j in jobs)
    assert session.scalar(select(func.count()).select_from(Asset)) == 0


def test_streamed_preview_is_durable_then_checked_and_stored(session, monkeypatch, factory):
    client, angle = _mandate(session)
    default_drafts.enqueue(session, client, angle)
    identity, token = default_drafts.claim(session)
    assert default_drafts.claim(session) is None
    raw = _drafted(assets.definition('pressemitteilung'))
    def stream(prompt, **kwargs):
        assert client.name in prompt
        for chunk in [raw[:100], raw[100:]]:
            yield StreamEvent('text', chunk)
        yield StreamEvent('done')
    def check(*args, **kwargs):
        # A separate connection/request can restore a full body while checks run.
        with factory() as reader:
            state = default_drafts.status(reader, identity)
            assert state['stage'] == 'checking'
            assert state['preview'] == json.loads(raw)['body']
            assert state['words'] == len(json.loads(raw)['body'].split())
            assert reader.scalar(select(func.count()).select_from(Asset)) == 0
        return None
    monkeypatch.setattr(assets, 'check', check)
    default_drafts.work(session, identity, token, stream=stream)
    session.expire_all()
    assert default_drafts.status(session, identity)['status'] == 'ready'
    row = session.scalar(select(Asset))
    assert row.body == json.loads(raw)['body'] and row.released_at is None
    assert assets.state_of(row) == assets.AssetState.ENTWURF
    assert default_drafts.enqueue(session, client, angle, retry=True) is None


def test_interrupted_stream_stays_failed_until_explicit_retry(session):
    client, angle = _mandate(session)
    default_drafts.enqueue(session, client, angle)
    def stream(*args, **kwargs):
        yield StreamEvent('text', '{"body":"An unfinished text')
    default_drafts.work(session, *default_drafts.claim(session), stream=stream)
    assert default_drafts.status(session, angle.id)['status'] == 'failed'
    default_drafts.discover(session)
    assert default_drafts.claim(session) is None
    assert session.scalar(select(func.count()).select_from(Asset)) == 0
    default_drafts.enqueue(session, client, angle, retry=True)
    assert default_drafts.claim(session)[0] == angle.id


def test_expired_lease_resumes_but_old_worker_cannot_publish(session):
    client, angle = _mandate(session)
    default_drafts.enqueue(session, client, angle)
    identity, old = default_drafts.claim(session)
    job = session.get(DefaultDraftJob, identity)
    job.lease_until = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1); session.commit()
    assert default_drafts.status(session, identity)['status'] == 'queued'
    _, new = default_drafts.claim(session)
    assert new != old
    with pytest.raises(default_drafts.Superseded):
        default_drafts.publish(session, identity, old, status='ready', preview='stale')
    assert default_drafts.status(session, identity)['status'] == 'running'
    assert default_drafts.status(session, identity)['preview'] == ''


def test_missing_profile_does_not_spend_calls_and_recovers_after_profile_filled(session, monkeypatch):
    from newspulse import profile
    from test_assets import _FULL_PROFILE
    client, angle = _mandate(session, facts={})
    default_drafts.enqueue(session, client, angle)
    def stream(*args, **kwargs): pytest.fail('No provider call without required facts')
    default_drafts.work(session, *default_drafts.claim(session), stream=stream)
    assert default_drafts.status(session, angle.id)['status'] == 'blocked'
    default_drafts.discover(session)
    assert default_drafts.claim(session) is None
    for key, value in _FULL_PROFILE.items(): profile.save(session, client, key, value)
    session.commit(); default_drafts.discover(session)
    assert default_drafts.claim(session)[0] == angle.id


def test_human_text_saved_during_generation_wins(session, monkeypatch):
    client, angle = _mandate(session)
    default_drafts.enqueue(session, client, angle)
    def stream(*args, **kwargs):
        session.add(Asset(client_id=client.id, angle_id=angle.id, kind='pressemitteilung', title='Human', body='Keep this'))
        session.commit()
        yield StreamEvent('text', _drafted(assets.definition('pressemitteilung')))
        yield StreamEvent('done')
    monkeypatch.setattr(assets, 'check', lambda *a, **k: None)
    default_drafts.work(session, *default_drafts.claim(session), stream=stream)
    assert session.scalar(select(func.count()).select_from(Asset)) == 1
    assert session.scalar(select(Asset)).body == 'Keep this'
    assert default_drafts.status(session, angle.id)['preview'] == 'Keep this'


def test_deactivated_client_is_skipped_even_if_already_queued(session):
    client, angle = _mandate(session)
    default_drafts.enqueue(session, client, angle)
    client.active = False; session.commit()
    default_drafts.work(session, *default_drafts.claim(session))
    assert session.get(DefaultDraftJob, angle.id).status == 'skipped'
    assert session.scalar(select(func.count()).select_from(Asset)) == 0


def test_new_daily_impulse_precedes_historical_backlog(session):
    client, old = _mandate(session)
    default_drafts.enqueue(session, client, old)
    new = Angle(client_id=client.id, subject='Today', message='Today', context='Today')
    session.add(new); session.commit()
    default_drafts.enqueue(session, client, new)
    assert default_drafts.claim(session)[0] == new.id


def test_queue_tick_yields_to_interactive_writer_but_keeps_requests(session, factory, monkeypatch):
    from newspulse.web.routes import assets_view
    client, angle = _mandate(session)
    monkeypatch.setattr(default_drafts, 'get_session', factory)
    assets_view._generating.acquire()
    try:
        default_drafts.tick()
        session.expire_all()
        assert session.get(DefaultDraftJob, angle.id).status == 'queued'
        assert session.get(DefaultDraftJob, angle.id).attempts == 0
    finally:
        assets_view._generating.release()
