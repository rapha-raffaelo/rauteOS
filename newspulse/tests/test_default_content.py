"""Automatic content is one missing press release, never a rewrite or a send."""
import datetime as dt
from sqlalchemy import select, func
from newspulse import assets
from newspulse.models import Asset, DefaultDraftJob
from test_assets import factory, session, _mandate, _drafted


def test_new_impulse_queues_once_without_waiting_for_a_model(session, monkeypatch, no_default_press_release):
    client, angle = _mandate(session)
    def forbidden(*a, **k): raise AssertionError('Generation belongs to the background worker')
    monkeypatch.setattr(assets, 'produce', forbidden)
    first = no_default_press_release(session, client, angle)
    again = no_default_press_release(session, client, angle)
    assert first.angle_id == again.angle_id == angle.id
    assert first.status == 'queued'
    assert session.scalar(select(func.count()).select_from(DefaultDraftJob)) == 1
    assert session.scalar(select(func.count()).select_from(Asset)) == 0


def test_automatic_write_keeps_a_draft_saved_while_model_was_working(session, monkeypatch):
    client, angle = _mandate(session)
    fmt = assets.definition('pressemitteilung')
    def invoke(*a, **k):
        session.add(Asset(client_id=client.id, angle_id=angle.id, kind=fmt.key,
                          title='Saved by a person', body='Keep this text'))
        session.commit()
        return _drafted(fmt)
    monkeypatch.setattr(assets, 'check', lambda *a, **k: None)
    result = assets.produce(session, fmt, client, angle, invoke=invoke, only_if_missing=True)
    assert result.body == 'Keep this text'
    assert session.scalar(select(func.count()).select_from(Asset)) == 1


def test_existing_release_costs_no_model_call(session, monkeypatch):
    client, angle = _mandate(session)
    row = Asset(client_id=client.id, angle_id=angle.id, kind='pressemitteilung',
                title='Approved', body='Keep', released_at=dt.datetime.now(dt.UTC))
    session.add(row); session.commit()
    def forbidden(*a, **k):
        raise AssertionError('Existing content must not be generated again')
    result = assets.produce(session, assets.definition('pressemitteilung'), client, angle,
                            invoke=forbidden, only_if_missing=True)
    assert result.id == row.id and result.body == 'Keep'


def test_default_activation_only_queues_a_missing_press_release(session, no_default_starter):
    client, angle = _mandate(session)
    no_default_starter(session, client, angle)
    assert session.get(DefaultDraftJob, angle.id).status == 'queued'
    session.add(Asset(client_id=client.id, angle_id=angle.id, kind='pressemitteilung', title='Draft', body='Saved'))
    session.commit()
    no_default_starter(session, client, angle)
    assert session.scalar(select(func.count()).select_from(DefaultDraftJob)) == 1
