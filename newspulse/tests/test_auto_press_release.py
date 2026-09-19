import datetime as dt
import pytest
from newspulse.models import Asset, Client
from newspulse import default_drafts
from newspulse.web.routes import assets_view
from test_assets_view import factory, session, web, clean_module_state
from test_assets import _mandate


@pytest.fixture
def starter(monkeypatch, no_default_starter):
    monkeypatch.setattr(assets_view, 'start_default', no_default_starter)
    calls=[]
    real = default_drafts.enqueue
    def enqueue(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)
    monkeypatch.setattr(default_drafts, 'enqueue', enqueue)
    return calls


def path(client, angle):return f'/api/v1/clients/{client.id}/impulses/{angle.id}/press-release'


def test_missing_legacy_draft_starts_once_and_get_stays_read_only(session,web,starter):
    client,angle=_mandate(session)
    assert web.get(path(client,angle)).json()['status']=='needed'
    assert not starter
    assert web.post(path(client,angle)).json()['status']=='queued'
    assert web.post(path(client,angle)).json()['status']=='queued'
    assert len(starter)==1


@pytest.mark.parametrize('released',[False,True])
def test_existing_or_released_text_is_returned_without_regeneration(session,web,starter,released):
    client,angle=_mandate(session)
    row=Asset(client_id=client.id,angle_id=angle.id,kind='pressemitteilung',title='Vorhanden',body='Menschliche Fassung',released_at=dt.datetime.now(dt.UTC) if released else None)
    session.add(row);session.commit()
    for url in [path(client,angle),path(client,angle)+'?retry=true']:
        data=web.post(url).json()
        assert data['status']=='ready' and data['body']=='Menschliche Fassung'
    assert not starter


def test_other_client_and_missing_profile_never_start_writer(session,web,starter):
    client,angle=_mandate(session,facts={})
    other=Client(name='Andere Firma',keywords=[]);session.add(other);session.commit()
    assert web.post(path(other,angle)).status_code==404
    data=web.post(path(client,angle)).json()
    assert data['status']=='blocked' and data['reason']
    assert not starter


def test_busy_writer_defers_without_recording_permanent_failure(session,web,starter):
    client,angle=_mandate(session)
    assets_view._generating.acquire()
    try:assert web.post(path(client,angle)).json()['status']=='waiting'
    finally:assets_view._generating.release()
    assert not starter
    assert web.post(path(client,angle)).json()['status']=='queued'
    assert len(starter)==1


def test_failure_does_not_autoretry_on_every_page_visit(session,web,starter):
    client,angle=_mandate(session)
    assets_view._remember(angle.id,'pressemitteilung','Modell nicht verfügbar')
    for _ in range(3):assert web.post(path(client,angle)).json()['status']=='failed'
    assert not starter
    assert web.post(path(client,angle)+'?retry=true').json()['status']=='queued'
    assert len(starter)==1
