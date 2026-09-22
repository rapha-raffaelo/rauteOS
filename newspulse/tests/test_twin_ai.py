import datetime as dt
import json

import pytest
from sqlalchemy import select

from test_twin import db, web
from newspulse import twin, twin_ai, twin_import
from newspulse.models import ClientFact, TwinImportPreview
from newspulse.web.routes import twin_api


def prepare(db, **kwargs):
    row = twin_ai.start(db, 1, dict(text='Company presentation', source_title='Deck', section='', web=False, **kwargs))
    return row.id, row.payload['generation']


def answer(**kwargs):
    return dict(key='A01.01', value='Mandate GmbH', source_ids=['input'], reason='From deck', **kwargs)


def test_preview_does_not_write_and_only_selected_answers_are_committed(db):
    identity, generation = prepare(db)
    twin_ai.generate(db, identity, generation, invoke=lambda p: json.dumps({'answers':[answer()]}))
    db.expire_all()
    assert not db.scalars(select(ClientFact)).all()
    job = db.get(TwinImportPreview, identity)
    preview = db.get(TwinImportPreview, job.payload['preview_id'])
    proposal = preview.payload['rows'][0]
    assert proposal['data']['fact_status'] == 'Needs Verification'
    assert proposal['data']['evidence_type'] == 'Derived Insight'
    assert proposal['data']['external_use'] == 'Approval Required'
    assert twin_import.commit(db, 1, preview.id, [0], 'Reviewer')['created'] == 1
    fact = db.scalar(select(ClientFact))
    assert fact.verified_at is None and fact.filled_by == 'ki'
    assert twin_import.commit(db, 1, preview.id, [0], 'Reviewer')['already_committed']


def test_unknown_fields_and_fabricated_sources_are_not_importable(db):
    identity, generation = prepare(db)
    candidates = [dict(answer(), key='nonsense'), dict(answer(), source_ids=['invented']), answer()]
    twin_ai.generate(db, identity, generation, invoke=lambda p: json.dumps({'answers':candidates}))
    db.expire_all()
    preview = db.get(TwinImportPreview, db.get(TwinImportPreview, identity).payload['preview_id'])
    assert len(preview.payload['rows']) == 1


def test_manual_answer_after_preview_is_preserved(db):
    identity, generation = prepare(db)
    twin_ai.generate(db, identity, generation, invoke=lambda p: json.dumps({'answers':[answer()]}))
    db.expire_all()
    preview_id = db.get(TwinImportPreview, identity).payload['preview_id']
    twin.apply(db, 1, twin.StatementInput(key='A01.01', value='Human answer'), 'Reviewer')
    db.commit()
    result = twin_import.commit(db, 1, preview_id, [0], 'Reviewer')
    assert result['created'] == 0 and result['skipped'] == 1
    assert db.scalar(select(ClientFact)).value == 'Human answer'


def test_existing_fields_are_excluded_from_prompt_and_result(db):
    twin.apply(db, 1, twin.StatementInput(key='A01.01', value='Existing'), 'Reviewer'); db.commit()
    identity, generation = prepare(db)
    def invoke(prompt):
        payload=json.loads(prompt.split('DATEN:\n')[1])
        assert 'A01.01' not in {f['key'] for f in payload['fields']}
        return json.dumps({'answers':[answer()]})
    twin_ai.generate(db, identity, generation, invoke=invoke)
    db.expire_all()
    preview = db.get(TwinImportPreview, db.get(TwinImportPreview, identity).payload['preview_id'])
    assert preview.payload['rows'] == []


def test_job_is_locked_and_old_worker_cannot_replace_new_status(db):
    identity, generation = prepare(db)
    with pytest.raises(ValueError): prepare(db)
    db.rollback()
    twin_ai.finish(db, identity, generation, dict(status='failed', preview_id=None, note='Retry'))
    _, newer = prepare(db)
    twin_ai.finish(db, identity, generation, dict(status='complete', preview_id='wrong'))
    db.expire_all()
    assert db.get(TwinImportPreview, identity).payload['generation'] == newer
    assert db.get(TwinImportPreview, identity).payload['status'] == 'running'


def test_routes_scope_resume_and_expiry(web, db, monkeypatch):
    monkeypatch.setattr(twin_api, 'start_or_release', lambda *a, **k: None)
    result=web.post('/api/v1/clients/1/twin/ai-import',json={'web':False})
    assert result.status_code==202 and 'input' not in result.json()
    assert web.post('/api/v1/clients/1/twin/ai-import',json={}).status_code==409
    assert web.get('/api/v1/clients/2/twin/ai-import').json()['job'] is None
    assert web.post('/api/v1/clients/3/twin/ai-import',json={}).status_code==404
    assert web.post('/api/v1/clients/1/twin/ai-import',json={'section':'invented'}).status_code==422
    row=db.get(TwinImportPreview,twin_ai.slot_id(1));row.expires_at=dt.datetime.now(dt.UTC)-dt.timedelta(seconds=1);db.commit()
    assert web.get('/api/v1/clients/1/twin/ai-import').json()['job']['status']=='failed'


def test_foreign_preview_cannot_be_committed(db):
    identity,generation=prepare(db)
    twin_ai.generate(db,identity,generation,invoke=lambda p:json.dumps({'answers':[answer()]}))
    db.expire_all()
    with pytest.raises(LookupError):
        twin_import.commit(db,2,db.get(TwinImportPreview,identity).payload['preview_id'],[0],'Reviewer')


def test_failed_web_research_is_visible_without_invented_citations(db):
    row=twin_ai.start(db,1,dict(text='Deck',source_title='Deck',section='',web=True))
    def research(client): raise RuntimeError('Unavailable')
    twin_ai.generate(db,row.id,row.payload['generation'],invoke=lambda p:json.dumps({'answers':[answer()]}),research=research)
    db.expire_all()
    assert 'Webrecherche nicht verfügbar' in db.get(TwinImportPreview,row.id).payload['note']


def test_job_record_is_never_a_committable_preview(db):
    identity, _ = prepare(db)
    with pytest.raises(ValueError, match='Antwortvorschläge'):
        twin_import.commit(db, 1, identity, [0], 'Reviewer')
    assert not db.scalars(select(ClientFact)).all()


def test_spawn_failure_is_persisted_and_allows_retry(web, db, monkeypatch):
    def fail(*args, **kwargs):
        kwargs['release']()
        raise RuntimeError('No worker')
    monkeypatch.setattr(twin_api, 'start_or_release', fail)
    assert web.post('/api/v1/clients/1/twin/ai-import', json={'web':False}).status_code == 503
    db.expire_all()
    assert web.get('/api/v1/clients/1/twin/ai-import').json()['job']['status'] == 'failed'
    monkeypatch.setattr(twin_api, 'start_or_release', lambda *a, **k: None)
    assert web.post('/api/v1/clients/1/twin/ai-import', json={'web':False}).status_code == 202


def test_derived_answer_preserves_restricted_source_permissions(db):
    source=twin.apply(db,1,twin.StatementInput(key='geschaeftsfeld',value='Restricted context',
        confidentiality='Highly Restricted',external_use='Internal Only'),'Reviewer');db.commit()
    identity,generation=prepare(db)
    twin_ai.generate(db,identity,generation,invoke=lambda p:json.dumps({'answers':[dict(answer(),source_ids=[f'twin-{source.id}'])]}))
    db.expire_all()
    preview=db.get(TwinImportPreview,db.get(TwinImportPreview,identity).payload['preview_id'])
    assert preview.payload['rows'][0]['data']['confidentiality']=='Highly Restricted'
    assert preview.payload['rows'][0]['data']['external_use']=='Internal Only'


@pytest.mark.parametrize('prefix,suffix', [
    ('', '\nHinweis: Bitte die Quellen prüfen.'),
    ('Hier sind die Vorschläge:\n', '\nNoch nicht unabhängig bestätigt.'),
    ('', ''),
])
def test_complete_json_fence_with_commentary_produces_reviewable_preview(db, prefix, suffix):
    identity, generation = prepare(db)
    raw = prefix + '```json\n' + json.dumps({'answers': [answer()]}) + '\n```' + suffix
    twin_ai.generate(db, identity, generation, invoke=lambda _: raw)
    db.expire_all()
    job = db.get(TwinImportPreview, identity)
    assert job.payload['status'] == 'complete'
    preview = db.get(TwinImportPreview, job.payload['preview_id'])
    assert len(preview.payload['rows']) == 1
    assert preview.payload['rows'][0]['data']['fact_status'] == 'Needs Verification'
    assert not db.scalars(select(ClientFact)).all()


@pytest.mark.parametrize('raw', [
    '```json\n{"answers": [\n```\nIncomplete',
    '```json\n{"answers": []}',
    '```json\n{"answers": []}\n```\n```json\n{"answers": []}\n```',
    '{"answers": []}{"answers": []}',
    '[]', '{"answers": "not a list"}',
    json.dumps({'answers': [answer()] * 101}),
])
def test_incomplete_ambiguous_or_invalid_response_is_not_imported(db, raw):
    from newspulse.analyzer import ParseError
    identity, generation = prepare(db)
    with pytest.raises(ParseError):
        twin_ai.generate(db, identity, generation, invoke=lambda _: raw)
    assert not db.scalars(select(ClientFact)).all()
    assert db.get(TwinImportPreview, identity).payload['preview_id'] is None


def test_plain_json_can_contain_literal_markdown_and_malformed_fields_are_skipped(db):
    identity, generation = prepare(db)
    candidates = [dict(answer(), key=['A01.01']), dict(answer(), value='Literal ``` fence'),
                  dict(answer(), key='A01.02', source_ids=['invented'])]
    twin_ai.generate(db, identity, generation, invoke=lambda _: json.dumps({'answers': candidates}))
    db.expire_all()
    preview = db.get(TwinImportPreview, db.get(TwinImportPreview, identity).payload['preview_id'])
    assert len(preview.payload['rows']) == 1
    assert preview.payload['rows'][0]['data']['value'] == 'Literal ``` fence'


@pytest.mark.parametrize('kind,code', [('parse', 'invalid_response'), ('timeout', 'timeout'),
                                      ('provider', 'provider_unavailable'), ('internal', 'internal_error')])
def test_worker_reports_actionable_failure_without_logging_source_content(db, monkeypatch, caplog, kind, code):
    from sqlalchemy.orm import sessionmaker
    from newspulse.analyzer import BackendError, ParseError
    errors = {'parse': ParseError('private source'), 'timeout': BackendError('private source timed out'),
              'provider': BackendError('private source unavailable'), 'internal': TypeError('private source')}
    identity, generation = prepare(db)
    def fail(*args):
        raise errors[kind]
    monkeypatch.setattr(twin_ai, 'generate', fail)
    twin_api.ai_worker(sessionmaker(bind=db.get_bind(), expire_on_commit=False), identity, generation)
    db.expire_all()
    job = db.get(TwinImportPreview, identity)
    assert job.payload['status'] == 'failed' and job.payload['error_code'] == code
    assert job.payload['input']['text'] == 'Company presentation'
    assert 'input' not in twin_ai.job_data(job) and 'checkpoint' not in twin_ai.job_data(job)
    assert 'private source' not in json.dumps(job.payload)
    assert code in caplog.text and 'private source' not in caplog.text
    assert not db.scalars(select(ClientFact)).all()
    # A failed worker releases the slot for an explicit retry.
    assert prepare(db)[1] != generation


def test_batched_import_keeps_successful_answers_after_timeout(db):
    from newspulse.analyzer import BackendError
    identity, generation = prepare(db)
    calls = []
    def invoke(prompt):
        data = json.loads(prompt.split('DATEN:\n')[1])
        fields = data['fields']
        assert 0 < len(fields) <= 60
        assert all(set(f) == {'key', 'label', 'group'} for f in fields)
        job = db.get(TwinImportPreview, identity)
        assert job.payload['completed_batches'] == len(calls)
        assert job.payload['input']['text'] == 'Company presentation'
        calls.append(fields)
        if len(calls) == 2:
            raise BackendError('Claude timed out')
        return json.dumps({'answers': [dict(answer(), key=fields[0]['key'])]})
    twin_ai.generate(db, identity, generation, invoke=invoke)
    db.expire_all()
    job = db.get(TwinImportPreview, identity)
    assert len(calls) > 2
    assert {f['key'] for batch in calls for f in batch} == {f['key'] for f in twin.CATALOG}
    assert job.payload['status'] == 'complete' and job.payload['partial']
    preview = db.get(TwinImportPreview, job.payload['preview_id'])
    assert len(preview.payload['rows']) == len(calls) - 1
    assert preview.payload['partial']
    assert not db.scalars(select(ClientFact)).all()


def test_old_batch_worker_stops_when_new_generation_owns_slot(db):
    identity, generation = prepare(db)
    calls = []
    def invoke(prompt):
        calls.append(prompt)
        twin_ai.finish(db, identity, generation, dict(status='failed', note='Replaced'))
        prepare(db)
        return json.dumps({'answers': [answer()]})
    twin_ai.generate(db, identity, generation, invoke=invoke)
    db.expire_all()
    assert len(calls) == 1
    job = db.get(TwinImportPreview, identity)
    assert job.payload['generation'] != generation
    assert job.payload['status'] == 'running'
    assert not db.scalars(select(TwinImportPreview).where(TwinImportPreview.id != identity)).all()


def test_expired_job_cannot_publish_progress_or_call_provider(db):
    identity, generation = prepare(db)
    row = db.get(TwinImportPreview, identity)
    row.expires_at = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
    db.commit()
    def invoke(prompt):
        pytest.fail('Expired generation must stop before a provider request')
    twin_ai.generate(db, identity, generation, invoke=invoke)
    assert not twin_ai.progress(db, identity, generation, note='Too late')


def test_interrupted_import_restores_checkpoint_in_new_session_without_repeating_packages(db, web):
    from sqlalchemy.orm import sessionmaker
    identity, generation = prepare(db)
    prompts = []
    def interrupted(prompt):
        fields = json.loads(prompt.split('DATEN:\n')[1])['fields']
        prompts.append(fields)
        if len(prompts) == 2:
            raise RuntimeError('simulated process termination')
        return json.dumps({'answers': [dict(answer(), key=fields[0]['key'])]})
    with pytest.raises(RuntimeError):
        twin_ai.generate(db, identity, generation, invoke=interrupted)
    db.expire_all()
    job = db.get(TwinImportPreview, identity)
    assert job.payload['checkpoint']['next_batch'] == 1
    preview_id = job.payload['preview_id']
    assert len(db.get(TwinImportPreview, preview_id).payload['rows']) == 1
    with pytest.raises(ValueError, match='läuft noch'):
        twin_import.commit(db, 1, preview_id, [0], 'Reviewer')
    db.rollback()
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    with factory() as fresh:
        resumed = twin_ai.resume(fresh, 1, recovering=True)
        newer = resumed.payload['generation']
        def finish(prompt):
            fields = json.loads(prompt.split('DATEN:\n')[1])['fields']
            assert fields != prompts[0]
            return json.dumps({'answers': [dict(answer(), key=fields[0]['key'])]})
        twin_ai.generate(fresh, identity, newer, invoke=finish, research=lambda _: pytest.fail('research repeated'))
    assert not twin_ai.progress(db, identity, generation, note='old worker')
    db.expire_all()
    job = db.get(TwinImportPreview, identity)
    assert job.payload['status'] == 'complete'
    assert job.payload['preview_id'] == preview_id
    assert len(db.get(TwinImportPreview, preview_id).payload['rows']) == job.payload['total_batches']
    assert not db.scalars(select(ClientFact)).all()


def test_old_ai_preview_survives_expiry_cleanup_and_can_be_reviewed(web, db):
    identity, generation = prepare(db)
    twin_ai.generate(db, identity, generation, invoke=lambda _: json.dumps({'answers':[answer()]}))
    db.expire_all()
    job = db.get(TwinImportPreview, identity)
    preview = db.get(TwinImportPreview, job.payload['preview_id'])
    preview.expires_at = job.expires_at = dt.datetime.now(dt.UTC)-dt.timedelta(days=2)
    db.commit()
    twin_import.preview(db, 2, b'ID,Antwort / Input\nA01.01,Other\n', 'other.csv', {})
    restored = web.get('/api/v1/clients/1/twin/ai-import').json()
    assert restored['preview']['id'] == preview.id
    assert len(restored['previews']) == 1
    assert 'input' not in restored['job'] and 'checkpoint' not in restored['job']
    assert web.get('/api/v1/clients/2/twin/ai-import', params={'preview_id': preview.id}).status_code == 404
    assert twin_import.commit(db, 1, preview.id, [0], 'Reviewer')['created'] == 1


def test_resume_is_explicit_scoped_and_fences_stale_workers(web, db, monkeypatch):
    identity, generation = prepare(db)
    monkeypatch.setattr(twin_api, 'start_or_release', lambda *a, **k: None)
    assert web.post('/api/v1/clients/1/twin/ai-import/resume').status_code == 409
    assert web.post('/api/v1/clients/2/twin/ai-import/resume').status_code == 409
    row=db.get(TwinImportPreview,identity);row.expires_at=dt.datetime.now(dt.UTC)-dt.timedelta(seconds=1);db.commit()
    result=web.post('/api/v1/clients/1/twin/ai-import/resume')
    assert result.status_code == 202
    assert result.json()['generation'] != generation
    assert 'input' not in result.json() and 'checkpoint' not in result.json()
    assert not twin_ai.progress(db, identity, generation, note='must not overwrite')


def test_startup_recovery_rotates_interrupted_job_and_spawns_worker(db, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from newspulse import db as database
    identity, generation = prepare(db)
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(database, 'get_session', factory)
    launches = []
    monkeypatch.setattr(twin_api, 'start_or_release', lambda target, **kwargs: launches.append((target, kwargs)))
    twin_api.recover_ai_imports()
    db.expire_all()
    resumed = db.get(TwinImportPreview, identity)
    assert resumed.payload['generation'] != generation
    assert resumed.payload['input']['text'] == 'Company presentation'
    assert len(launches) == 1 and launches[0][0] is twin_api.ai_worker
    assert launches[0][1]['args'][1:] == (identity, resumed.payload['generation'])
    assert not twin_ai.progress(db, identity, generation, note='stale result')
