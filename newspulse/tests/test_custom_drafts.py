import io
import json
import threading

import pytest
from sqlalchemy import select

from newspulse import assets, streaming
from newspulse.models import Asset, Client
from newspulse.schemas import AssetDraft
from newspulse.web.routes import custom_drafts, assets_view
from test_assets_view import factory, session, web
from test_assets import _mandate

_real_recheck = assets.recheck


@pytest.fixture(autouse=True)
def safe_models(monkeypatch):
    monkeypatch.setattr(assets, 'recheck', lambda *a, **k: None)
    monkeypatch.setattr(custom_drafts, 'start_or_release', lambda target, *, args, **k: target(*args))
    def stream(prompt, **kwargs):
        raw = json.dumps({'title': 'Eine eigene Nachricht', 'body': 'Hallo zusammen,\n\nwir schlagen ein Hintergrundgespräch vor. Welche Fragen sind für Sie relevant?', 'speaker': ''}, ensure_ascii=False)
        for start in range(0, len(raw), 7):
            yield streaming.StreamEvent('text', raw[start:start + 7])
        yield streaming.StreamEvent('done')
    monkeypatch.setattr(custom_drafts, 'stream_assistant', stream)
    yield
    assert not assets_view._generating.locked()


def url(client, angle):
    return f'/api/v1/clients/{client.id}/impulses/{angle.id}/custom-draft'


def events(response):
    return [(frame.splitlines()[0][7:], json.loads(frame.splitlines()[1][6:])) for frame in response.text.strip().split('\n\n') if frame.startswith('event:')]


def test_streams_partial_words_then_persists_custom_without_touching_release(web, session):
    client, angle = _mandate(session)
    release = assets.store(session, assets.definition('pressemitteilung'), client, angle, AssetDraft(title='PM', body='Unveränderte Pressemitteilung', speaker='', brain_version=0))
    response = web.post(url(client, angle), json={'instruction': 'Eine freundliche Kundenmail'})
    assert response.status_code == 200
    received = events(response)
    previews = [data for kind, data in received if kind == 'preview' and data]
    assert len(previews) > 3 and previews[0] != previews[-1]
    saved = json.loads(next(data for kind, data in received if kind == 'saved'))
    row = session.get(Asset, saved['id'])
    assert row.kind == 'custom' and row.body == previews[-1] and row.released_at is None
    session.refresh(release)
    assert release.body == 'Unveränderte Pressemitteilung'
    html = web.get(f'/client/{client.id}/advice?eintrag=anlass-{angle.id}').text
    assert 'data-custom-composer' in html and row.body.splitlines()[0] in html


def test_rejects_cross_client_empty_and_busy_requests_without_generation(web, session):
    client, angle = _mandate(session)
    other = Client(name='Andere Firma', keywords=[])
    session.add(other); session.commit()
    assert web.post(url(other, angle), json={'instruction': 'Text'}).status_code == 404
    assert web.post(url(client, angle), json={'instruction': '   '}).status_code == 422
    assets_view._generating.acquire()
    try:
        assert web.post(url(client, angle), json={'instruction': 'Text'}).status_code == 409
    finally:
        assets_view._generating.release()
    assert not session.scalars(select(Asset)).all()


def test_failure_does_not_store_partial_or_overwrite_existing(web, session, monkeypatch):
    client, angle = _mandate(session)
    row = assets.store(session, assets.definition('custom'), client, angle, AssetDraft(title='Von Hand', body='Dieser Text bleibt erhalten.', speaker='', brain_version=0))
    def broken(*a, **k):
        yield streaming.StreamEvent('text', '{"body":"Ein halber Text')
        yield streaming.StreamEvent('error', 'Provider unavailable')
    monkeypatch.setattr(custom_drafts, 'stream_assistant', broken)
    response = web.post(url(client, angle), json={'instruction': 'Text', 'version': assets.version(row)})
    assert any(kind == 'error' for kind, _ in events(response))
    assert not any(kind == 'saved' for kind, _ in events(response))
    session.refresh(row)
    assert row.body == 'Dieser Text bleibt erhalten.'
    assert web.post(url(client, angle), json={'instruction': 'Text'}).status_code == 409


def test_edit_during_generation_is_preserved(web, session, monkeypatch, factory):
    client, angle = _mandate(session)
    row = assets.store(session, assets.definition('custom'), client, angle, AssetDraft(title='Original', body='Originaler Entwurf', speaker='', brain_version=0))
    original = custom_drafts.stream_assistant
    def stream(*a, **k):
        with factory() as other:
            assets.edit(other, other.get(Asset, row.id), title='Bearbeitet', body='Neue menschliche Fassung')
        yield from original(*a, **k)
    monkeypatch.setattr(custom_drafts, 'stream_assistant', stream)
    response = web.post(url(client, angle), json={'instruction': 'Text', 'version': assets.version(row)})
    assert any(kind == 'error' for kind, _ in events(response))
    session.refresh(row)
    assert row.body == 'Neue menschliche Fassung'


def test_check_failure_keeps_saved_draft(web, session, monkeypatch):
    client, angle = _mandate(session)
    def fail(*a, **k): raise RuntimeError('checker offline')
    monkeypatch.setattr(assets, 'recheck', fail)
    response = web.post(url(client, angle), json={'instruction': 'Text'})
    saved = json.loads(next(data for kind, data in events(response) if kind == 'saved'))
    row = session.get(Asset, saved['id'])
    assert assets.state_of(row) == assets.AssetState.ENTWURF


@pytest.mark.parametrize('value', ['Umlaute äöü', 'Zitat: "Hallo"\nNeue Zeile', 'Emoji 🙂'])
def test_partial_json_preview_is_always_decoded_prefix(value):
    raw = json.dumps({'body': value})
    for end in range(len(raw) + 1):
        assert value.startswith(custom_drafts.preview_body(raw[:end]))
    assert custom_drafts.preview_body(raw) == value


def test_claude_partial_events_not_duplicated_by_final_message(monkeypatch):
    lines = [
        {'type':'stream_event','event':{'delta':{'type':'text_delta','text':'Hallo '}}},
        {'type':'stream_event','event':{'delta':{'type':'text_delta','text':'Welt'}}},
        {'type':'assistant','message':{'content':[{'type':'text','text':'Hallo Welt'}]}},
        {'type':'result','is_error':False},
    ]
    class Process:
        stdout = io.StringIO('\n'.join(json.dumps(line) for line in lines))
        stderr = io.StringIO('')
        def wait(self, timeout): return 0
        def poll(self): return 0
    monkeypatch.setattr(streaming.subprocess, 'Popen', lambda *a, **k: Process())
    result = list(streaming.stream_claude('prompt'))
    assert ''.join(e.data for e in result if e.kind == 'text') == 'Hallo Welt'
    assert result[-1].kind == 'done'


def test_stream_timeout_kills_a_silent_writer(monkeypatch):
    stopped = threading.Event()
    class Process:
        stderr = io.StringIO('')
        @property
        def stdout(self):
            stopped.wait(1)
            return iter(())
        def poll(self): return 1 if stopped.is_set() else None
        def kill(self): stopped.set()
    monkeypatch.setattr(streaming.subprocess, 'Popen', lambda *a, **k: Process())
    result = list(streaming.stream_claude('prompt', timeout=.01))
    assert stopped.is_set()
    assert result[-1].kind == 'error' and 'Zeitüberschreitung' in result[-1].data


def test_cancelled_custom_request_never_stores(factory, session):
    client, angle = _mandate(session)
    import queue
    cancelled = threading.Event(); cancelled.set()
    assets_view._generating.acquire()
    custom_drafts.work(factory, client.id, angle.id, custom_drafts.CustomInput(instruction='Text'), queue.Queue(), cancelled)
    assert not session.scalars(select(Asset)).all()


def test_review_does_not_mark_a_concurrently_edited_text_as_checked(session, factory, monkeypatch):
    client, angle = _mandate(session)
    row = assets.store(session, assets.definition('custom'), client, angle,
        AssetDraft(title='Original', body='Originaler Entwurf', speaker='', brain_version=0))
    def check(*args, **kwargs):
        with factory() as other:
            assets.edit(other, other.get(Asset, row.id), title='Bearbeitet', body='Während der Prüfung bearbeitet')
        return None
    monkeypatch.setattr(assets, 'check', check)
    with pytest.raises(assets.Refused, match='während der Prüfung geändert'):
        _real_recheck(session, client, row)
    session.refresh(row)
    assert row.body == 'Während der Prüfung bearbeitet'
    assert not row.reviewed_by
