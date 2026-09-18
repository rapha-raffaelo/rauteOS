"""Automatic content is one missing press release, never a rewrite or a send."""
import datetime as dt
from sqlalchemy import select, func
from newspulse import assets
from newspulse.models import Asset
from test_assets import factory, session, _mandate, _drafted


def test_new_impulse_gets_one_unreleased_press_release(session, monkeypatch, no_default_press_release):
    client, angle = _mandate(session)
    real = assets.produce
    calls = []
    def produce(session, fmt, client, angle, **kwargs):
        calls.append(fmt.key)
        return real(session, fmt, client, angle, invoke=lambda *a, **k: _drafted(fmt), **kwargs)
    monkeypatch.setattr(assets, 'produce', produce)
    monkeypatch.setattr(assets, 'check', lambda *a, **k: None)
    first = no_default_press_release(session, client, angle)
    assert first is not None and first.kind == 'pressemitteilung'
    assert first.released_at is None and not first.reviewed_by
    assert assets.state_of(first) is assets.AssetState.ENTWURF
    first.body = 'Manually edited draft'
    first.edited_at = dt.datetime.now(dt.UTC)
    session.commit()
    again = no_default_press_release(session, client, angle)
    assert again.id == first.id and again.body == 'Manually edited draft'
    assert set(calls) == {'pressemitteilung'}
    assert session.scalar(select(func.count()).select_from(Asset)) == 1


def test_missing_profile_or_failed_writer_keeps_the_impulse(session, monkeypatch, no_default_press_release):
    client, angle = _mandate(session, facts={})
    notes = []
    assert no_default_press_release(session, client, angle, note=notes.append) is None
    assert notes and session.get(type(angle), angle.id) is not None
    def fail(*a, **k):
        raise RuntimeError('model unavailable')
    monkeypatch.setattr(assets, 'produce', fail)
    assert no_default_press_release(session, client, angle, note=notes.append) is None
    assert session.scalar(select(func.count()).select_from(Asset)) == 0
    assert 'model unavailable' in notes[-1]


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


def test_default_activation_only_starts_a_missing_press_release(session, monkeypatch, no_default_starter):
    from newspulse.web.routes import assets_view
    client, angle = _mandate(session)
    calls = []
    monkeypatch.setattr(assets_view, '_spawn', lambda *args, **kwargs: calls.append((args, kwargs)))
    no_default_starter(session, client, angle)
    assert len(calls) == 1 and calls[0][1]['kinds'] == ('pressemitteilung',)
    session.add(Asset(client_id=client.id, angle_id=angle.id, kind='pressemitteilung', title='Draft', body='Saved'))
    session.commit()
    no_default_starter(session, client, angle)
    assert len(calls) == 1


def test_default_activation_waits_for_required_profile_data(session, monkeypatch, no_default_starter):
    from newspulse.web.routes import assets_view
    client, angle = _mandate(session, facts={})
    calls = []
    monkeypatch.setattr(assets_view, '_spawn', lambda *args, **kwargs: calls.append(args))
    no_default_starter(session, client, angle)
    assert not calls
