"""The Twin preserves independent claims and only writes reviewed input."""
import datetime as dt
import io
import json

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from newspulse import profile, twin
from newspulse.models import Base, Client, ClientFact, ClientFactHistory, TwinImportPreview
from newspulse.web.app import create_app, get_db


@pytest.fixture
def db():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        session.add_all([Client(name='Mandate'), Client(name='Another'), Client(name='Competitor', is_competitor=True)])
        session.commit()
        yield session
    engine.dispose()


@pytest.fixture
def web(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client


def path(client=1):
    return f'/api/v1/clients/{client}/twin'


def create(web, **values):
    response = web.post(path() + '/statements', json={'key': 'A02.01', 'value': 'BioLNG', **values})
    assert response.status_code == 201, response.text
    return response.json()


def workbook(rows):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = '01_Client Facts'
    sheet.append(['ID', 'Antwort / Input', 'Evidence Type', 'Quelle / Dokument', 'Datum', 'Vertraulichkeit'])
    for row in rows: sheet.append(row)
    stream = io.BytesIO(); book.save(stream)
    return stream.getvalue()


def upload(web, data, name='questions.xlsx', client=1, mapping=None):
    return web.post(path(client) + '/import/preview', files={'file': (name, data)},
                    data={'mapping': json.dumps(mapping or {})})


def test_multiple_statements_keep_independent_sources_in_prompts(web, db):
    a = create(web, value='400 % THG-Minderung', source_title='Client questionnaire')
    b = create(web, value='Calculation needs review', evidence_type='RAUTE Hypothesis', source_title='Our analysis')
    assert a['id'] != b['id']
    assert a['is_primary'] and not b['is_primary']
    facts = profile.stored(db, 1)
    assert facts['geschaeftsfeld'].value == '400 % THG-Minderung'
    context = profile.as_prompt_lines(facts)
    assert '400 % THG-Minderung' in context and 'Calculation needs review' in context
    assert 'Client Statement' in context and 'RAUTE Hypothesis' in context
    assert 'nicht als Fakt behaupten' in context
    assert 'Client questionnaire' in context and 'Our analysis' in context


def test_reject_removes_claim_from_generation_but_keeps_it_and_its_history(web, db):
    row = create(web)
    response = web.post(path() + f"/statements/{row['id']}/reject", json={'revision': row['revision']})
    assert response.status_code == 200
    assert 'BioLNG' not in profile.as_prompt_lines(profile.stored(db, 1))
    assert db.get(ClientFact, row['id']).value == 'BioLNG'
    assert web.get(path() + f"/statements/{row['id']}/history").json()[0]['snapshot']['value'] == 'BioLNG'


def test_confirmation_requires_independent_source_and_edit_invalidates_it(web, db):
    row = create(web, key='mitarbeiter', value='42', source_title='Company website', source_type='Website')
    url = path() + f"/statements/{row['id']}"
    assert web.post(url+'/confirm', json={'revision':row['revision'],'note':'Checked'}).status_code == 422
    payload = twin.StatementInput(key='mitarbeiter', value='42', source_title='Independent register',
                                  source_type='Public Database').model_dump(mode='json')
    changed = web.put(url, json={**payload,'revision':row['revision']}).json()
    confirmed = web.post(url+'/confirm', json={'revision':changed['revision'],'note':'Compared register entry'}).json()
    assert confirmed['evidence_type'] == 'Fact' and confirmed['verified_by'] == 'mensch'
    assert confirmed['external_use'] == 'Approval Required'
    assert 'unabhängig bestätigt' in profile.as_prompt_lines(profile.stored(db,1))
    edited = web.put(url,json={**payload,'value':'43','revision':confirmed['revision']}).json()
    assert edited['verified_at'] is None and edited['verified_by'] is None
    assert len(web.get(url+'/history').json()) == 3


def test_stale_edits_do_not_overwrite_current_values(web):
    row = create(web)
    payload = twin.StatementInput(key=row['key'], value='Newer').model_dump(mode='json')
    url = path()+f"/statements/{row['id']}"
    assert web.put(url,json={**payload,'revision':row['revision']}).status_code == 200
    assert web.put(url,json={**payload,'value':'Stale','revision':row['revision']}).status_code == 409
    assert web.get(path()).json()['statements'][0]['value'] == 'Newer'


def test_client_scope_and_origin_guard_cover_all_mutations(web):
    row = create(web)
    assert web.post(path(2)+f"/statements/{row['id']}/reject",json={'revision':row['revision']}).status_code == 404
    assert web.get(path(2)+f"/statements/{row['id']}/history").status_code == 404
    assert web.post(path()+'/statements',json={'key':'ceo','value':'X'},headers={'Origin':'https://evil.example'}).status_code == 403
    assert web.get(path(3)).status_code == 404


def test_import_is_previewed_selected_atomic_and_idempotent(web, db):
    data = workbook([['A02.01','BioLNG','Client Statement','Kickoff','2026-09-08'],
                     ['A02.02','Subscriptions','Management Belief'], ['A01.01',None]])
    preview = upload(web,data).json()
    assert [r['state'] for r in preview['rows']] == ['ready','ready','empty']
    assert not list(db.scalars(select(ClientFact)))
    commit = {'preview_id':preview['id'],'selected':[0]}
    assert web.post(path(2)+'/import/commit',json=commit).status_code == 404
    result = web.post(path()+'/import/commit',json=commit).json()
    assert result['created'] == 1
    assert web.post(path()+'/import/commit',json=commit).json()['already_committed']
    rows = list(db.scalars(select(ClientFact)))
    assert len(rows) == 1 and rows[0].value == 'BioLNG'
    assert rows[0].as_of.date() == dt.date(2026,9,8)
    assert upload(web,data).json()['rows'][0]['state'] == 'duplicate'
    assert db.get(TwinImportPreview,preview['id']).payload == {}


def test_duplicate_file_does_not_overwrite_a_subsequent_manual_edit(web, db):
    data = workbook([['A02.01','Original']])
    preview = upload(web,data).json()
    web.post(path()+'/import/commit',json={'preview_id':preview['id'],'selected':[0]})
    row = db.scalar(select(ClientFact))
    twin.apply(db,1,twin.StatementInput(key=row.key,value='Corrected'),'mensch',row=row);db.commit()
    assert upload(web,data).json()['rows'][0]['state'] == 'duplicate'
    assert db.get(ClientFact,row.id).value == 'Corrected'


def test_bad_rows_formulas_and_unknown_vocabulary_are_visible_not_silently_imported(web, db):
    data = workbook([['A02.01','Valid','Client Statement'],['A02.02','=1+1'],
                     ['unknown','No'],['A01.03','2020','Probably fact']])
    preview = upload(web,data).json()
    assert [r['state'] for r in preview['rows']] == ['ready','error','error','error']
    response = web.post(path()+'/import/commit',json={'preview_id':preview['id'],'selected':[0,1]})
    assert response.status_code == 422
    assert not list(db.scalars(select(ClientFact)))


def test_csv_can_map_custom_columns_and_preserves_zero(web):
    response = upload(web,b'Question;Answer\nA01.07;0\n',name='custom.csv')
    assert response.json()['rows'][0]['state'] == 'error'
    preview = upload(web,b'Question;Answer\nA01.07;0\n',name='custom.csv',mapping={'key':'Question','value':'Answer'}).json()
    assert preview['rows'][0]['data']['value'] == '0'


def test_required_completeness_does_not_count_optional_or_duplicate_answers(web):
    before = web.get(path()).json()['progress']
    create(web,key='A01.05')
    assert web.get(path()).json()['progress']['required_filled'] == before['required_filled']
    create(web); create(web,value='Another answer to the same required field')
    progress = web.get(path()).json()['progress']
    assert progress['required_total'] == 127
    assert progress['required_filled'] == before['required_filled'] + 1
    assert progress['verified'] == 0
    desk = web.get('/api/v1/desk').json()
    assert next(r for r in desk['rows'] if r['client']['id'] == 1)['twin']['percent'] == progress['percent']


def test_classified_fact_in_workbook_is_not_independent_confirmation(web,db):
    preview = upload(web,workbook([['A02.01','Unverified number','Fact','Client questionnaire']])).json()
    assert 'Bestätigung' in preview['rows'][0]['message']
    web.post(path()+'/import/commit',json={'preview_id':preview['id'],'selected':[0]})
    assert db.scalar(select(ClientFact)).verified_at is None
    assert 'nicht als Fakt behaupten' in profile.as_prompt_lines(profile.stored(db,1))


def test_external_context_excludes_explicitly_confidential_claims(web,db):
    create(web,value='SECRET',confidentiality='Highly Restricted',external_use='Internal Only')
    assert 'SECRET' not in profile.as_prompt_lines(profile.stored(db,1),for_outside=True)


def test_legacy_edit_resets_verification_and_keeps_all_sibling_statements(web,db):
    row = create(web,key='ceo',value='Person A',source_title='Register',source_type='Public Database')
    create(web,key='ceo',value='Person B')
    web.post(path()+f"/statements/{row['id']}/confirm",json={'revision':row['revision'],'note':'Reviewed'})
    profile.save(db,db.get(Client,1),'ceo','Person C')
    primary = db.get(ClientFact,row['id'])
    assert primary.verified_at is None and primary.fact_status == 'Needs Verification'
    assert len(profile.stored(db,1).statements) == 2
    assert db.scalar(select(ClientFactHistory).where(ClientFactHistory.fact_id == row['id']))


def test_preview_expires_without_importing(web, db):
    preview = upload(web,workbook([['A02.01','Value']])).json()
    record = db.get(TwinImportPreview,preview['id']);record.expires_at = dt.datetime.now(dt.UTC)-dt.timedelta(seconds=1);db.commit()
    assert web.post(path()+'/import/commit',json={'preview_id':preview['id'],'selected':[0]}).status_code == 422
    assert not list(db.scalars(select(ClientFact)))
