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
