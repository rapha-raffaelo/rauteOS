"""Customer-email-first activation preserves provenance, drafts and checks."""
import datetime as dt
import json
import re
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,func,select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from newspulse import activation,asset_evidence
from newspulse.models import (Angle,Asset,Base,Client,ClientAction,ClientFact,Contact,JournalistProfile,
    OpportunityAssetRun,OpportunityWorkspace,Outreach)
from newspulse.web.app import create_app,get_db
from newspulse.web.routes import activation_api as api


@pytest.fixture
def db():
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine,expire_on_commit=False)() as session:
        session.add_all([Client(name='Demo',comms_guide='Keine Klimaneutralität behaupten.'),Client(name='Other')]);session.flush()
        session.add(Angle(client_id=1,subject='BioLNG',message='Study proposal',context='Planning'))
        session.add_all([ClientFact(client_id=1,key='ceo',value='Anna CEO',confidentiality='Public',external_use='Allowed'),
            ClientFact(client_id=1,key='geschaeftsfeld',value='400 % THG-Minderung',evidence_type='Client Statement',
                source_title='Questionnaire',confidentiality='Public',external_use='Approval Required')])
        session.add(Contact(name='A Journalist',outlet='Paper'));session.flush()
        session.add(JournalistProfile(contact_id=1,preferences='Kurzer CEO-Kommentar',last_interaction_at=dt.datetime.now(dt.UTC)))
        session.add(OpportunityWorkspace(client_id=1,context_kind='developed',context_id=1,angle_id=1,
            storyline='Propose a data study',speaker_statement_id=1,contact_ids=[1],status='active'))
        session.commit();yield session
    engine.dispose()


@pytest.fixture
def web(db,monkeypatch):
    monkeypatch.setattr(api,'start_or_release',lambda *args,**kwargs:None)
    app=create_app();app.dependency_overrides[get_db]=lambda:db
    with TestClient(app) as client:yield client


def path(client=1):return f'/api/v1/clients/{client}/opportunities/developed/1/activation'


def launch(web,kind='kundenmail',**extra):
    response=web.post(path(),json={'kind':kind,**extra})
    assert response.status_code==202,response.text
    return response.json()['id']


def draft(*args,**kwargs):
    return json.dumps(dict(title='Studienvorschlag',body='Der Kunde nennt 400 % THG-Minderung. Bitte prüfen wir die Berechnungsgrundlage.',speaker=''))


def reviewer(prompt,**kwargs):
    # Read the real numbered segments from the fenced JSON, then return an
    # intentionally overconfident model answer. The server must downgrade it.
    data=json.loads(prompt.split('<<<ZITAT Zu prüfende Daten\n',1)[1].split('\nZITAT>>>',1)[0])
    return json.dumps(dict(findings=[dict(index=i,classification='Fact',statement_ids=[2] if '400' in sentence else [],
        source_ids=[],contradiction_ids=[],no_go_rules=[],reason='Matched the supplied statement') for i,sentence in data['segments']]))


def test_customer_email_is_saved_and_claim_is_not_promoted_to_fact(web,db):
    identity=launch(web);activation.run(db,identity,invoke=draft,review_invoke=reviewer)
    row=db.get(OpportunityAssetRun,identity)
    assert row.status=='complete' and row.asset_id
    result=web.get(path()).json()['texts'][0]
    claim=next(f for f in result['quality']['findings'] if '400' in f['quote'])
    assert claim['classification']=='Client Statement' and claim['warnings']
    assert result['quality_stale'] is False
    assert db.get(Asset,row.asset_id).released_at is None
    assert db.scalar(select(func.count()).select_from(ClientAction))==0


def test_failed_check_preserves_draft_and_does_not_claim_it_was_checked(web,db):
    identity=launch(web)
    activation.run(db,identity,invoke=draft,review_invoke=lambda *args,**kwargs:'invalid')
    result=web.get(path()).json()['texts'][0]
    assert result['body'].startswith('Der Kunde') and result['quality']['status']=='failed'
    assert db.get(Asset,result['id']).reviewed_by==''


def test_pitch_uses_existing_outreach_and_persistent_journalist_context(web,db):
    identity=launch(web,'pitch',contact_id=1);prompts=[]
    def write(prompt,**kwargs):
        prompts.append(prompt)
        return json.dumps(dict(subject='Study offer',message='Eine Studie könnte neue Fragen beantworten.',hook='Research topic'))
    activation.run(db,identity,invoke=write,review_invoke=reviewer)
    row=db.get(OpportunityAssetRun,identity)
    assert row.outreach_id and not row.asset_id
    assert db.get(Outreach,row.outreach_id).journalist=='A Journalist'
    assert 'Kurzer CEO-Kommentar' in prompts[0]
    assert 'Die bisherige Berichterstattung ist nicht vollständig bekannt' in prompts[0]
    assert 'Hat über diesen Mandanten noch nie geschrieben' not in prompts[0]
    assert 'Propose a data study' in prompts[0]
    assert db.get(Outreach,row.outreach_id).released_at is None


def test_unknown_or_unselected_recipients_and_missing_custom_instruction_are_rejected(web):
    assert web.post(path(),json={'kind':'interviewangebot'}).status_code==422
    assert web.post(path(),json={'kind':'pitch','contact_id':999}).status_code==422
    assert web.post(path(),json={'kind':'custom'}).status_code==422
    assert web.get(path(2)).status_code==404


def test_edit_invalidates_check_and_stale_editor_cannot_overwrite(web,db):
    identity=launch(web);activation.run(db,identity,invoke=draft,review_invoke=reviewer)
    original=web.get(path()).json()['texts'][0]
    edit_path=path()+f"/asset/{original['id']}"
    body=dict(digest=original['digest'],title=original['title'],body='Eine neue Formulierung muss geprüft werden.')
    response=web.put(edit_path,json=body)
    assert response.status_code==200,response.text
    assert response.json()['texts'][0]['quality_stale']
    assert web.put(edit_path,json=body).status_code==409
    assert web.post(edit_path+'/check').status_code==202
    activation.run(db,2,invoke=draft,review_invoke=reviewer)
    assert web.get(path()).json()['texts'][0]['quality_stale'] is False


def test_twin_change_invalidates_existing_check(web,db):
    identity=launch(web);activation.run(db,identity,invoke=draft,review_invoke=reviewer)
    db.get(ClientFact,2).value='Correction';db.commit()
    assert web.get(path()).json()['texts'][0]['quality_stale']


def test_existing_draft_edit_while_model_runs_is_preserved(web,db):
    identity=launch(web);activation.run(db,identity,invoke=draft,review_invoke=reviewer)
    identity=launch(web)
    def concurrent(*args,**kwargs):
        db.get(Asset,1).body='A human correction';db.commit()
        return draft()
    activation.run(db,identity,invoke=concurrent,review_invoke=reviewer)
    assert db.get(Asset,1).body=='A human correction'
    job=db.get(OpportunityAssetRun,identity)
    assert job.status=='complete' and job.asset_id!=1
    assert db.scalar(select(func.count()).select_from(Asset))==2


def test_review_requires_every_segment_and_rejects_invented_no_gos():
    context={'statements':[],'sources':[],'guide':'Keine Klimaneutralität behaupten.'}
    with pytest.raises(ValueError):
        asset_evidence.review('Title','One sentence. Another sentence.',context,invoke=lambda *args,**kwargs:'{"findings":[]}')
    with pytest.raises(ValueError):
        asset_evidence.review('','Sentence',context,invoke=lambda *args,**kwargs:json.dumps(dict(findings=[dict(
            index=0,classification='Unverified',statement_ids=[],source_ids=[],contradiction_ids=[],no_go_rules=['Invented policy'],reason='No-Go')])))


def test_no_database_transaction_is_held_during_writing_or_review(web,db):
    identity=launch(web)
    def write(prompt,**kwargs):
        assert not db.in_transaction()
        return draft()
    def check(prompt,**kwargs):
        assert not db.in_transaction()
        return reviewer(prompt)
    activation.run(db,identity,invoke=write,review_invoke=check)
    assert db.get(OpportunityAssetRun,identity).status=='complete'


def test_released_text_and_its_checks_are_immutable(web,db):
    identity=launch(web)
    def release_during_check(prompt,**kwargs):
        row=db.get(Asset,1)
        row.released_at=dt.datetime.now(dt.UTC)
        row.review='Original release review'
        db.commit()
        return reviewer(prompt)
    activation.run(db,identity,invoke=draft,review_invoke=release_during_check)
    assert db.get(Asset,1).review=='Original release review'
    assert db.get(OpportunityAssetRun,identity).status=='stale'
    assert web.post(path()+'/asset/1/check').status_code==409


def test_asset_can_be_created_without_an_optional_contact(web, db):
    workspace = db.scalar(select(OpportunityWorkspace))
    workspace.speaker_statement_id = None
    workspace.speaker_person_id = None
    db.commit()
    identity = launch(web)
    activation.run(db, identity, invoke=draft, review_invoke=reviewer)
    assert db.get(OpportunityAssetRun, identity).status == 'complete'


def test_without_a_second_model_the_writer_never_checks_its_own_text(web,db,monkeypatch):
    """Every asset has a designer and a reviewer. With no reviewer connected the
    draft is kept but stays unchecked; the model that wrote it is never asked."""
    from newspulse import gemini
    def no_reviewer():
        raise RuntimeError('Kein Zweitmodell verbunden.')
    monkeypatch.setattr(gemini,'reviewer',no_reviewer)
    calls=[]
    def write(prompt,**kwargs):
        calls.append(prompt);return draft()
    identity=launch(web);activation.run(db,identity,invoke=write)
    row=db.get(OpportunityAssetRun,identity)
    assert len(calls)==1 and row.asset_id
    assert row.quality['status']=='failed' and 'Kein Zweitmodell' in row.quality['note']


def test_asset_stage_is_shared_with_task_board_and_delete_is_recoverable(web,db):
    from newspulse import worklists, recycle_bin
    from newspulse.models import Task, TrashEntry
    identity=launch(web)
    activation.run(db,identity,invoke=draft,review_invoke=reviewer)
    text=web.get(path()).json()['texts'][0]
    task=db.get(Task,text['task_id'])
    assert task.status==text['stage']=='offen'
    assert task.board_id==next(b.id for b in worklists.task_boards(db) if b.system_key=='decisions')
    response=web.put(f"{path()}/asset/{text['id']}/stage",json={'stage':'review'})
    assert response.status_code==200
    assert response.json()['texts'][0]['stage']=='review'
    db.refresh(task)
    assert task.status=='review'
    worklists.set_task_status(task,'in_arbeit');db.commit()
    assert web.get(path()).json()['texts'][0]['stage']=='in_arbeit'
    assert db.get(Asset,text['id']).released_at is None
    response=web.request('DELETE',f"{path()}/asset/{text['id']}",json={'digest':text['digest']})
    assert response.status_code==200,response.text
    assert response.json()['texts']==[]
    entry=db.scalar(select(TrashEntry).where(TrashEntry.record_type=='assets'))
    assert entry and entry.expires_at-entry.deleted_at==dt.timedelta(weeks=12)
    assert db.get(Asset,text['id']) is None
    assert len(db.scalars(select(TrashEntry)).all())==1
    assert web.get('/trash').status_code==200
    recycle_bin.restore(db,entry.id)
    restored=web.get(path()).json()['texts'][0]
    assert restored['body']==text['body'] and restored['stage']=='in_arbeit'


def test_asset_delete_rejects_stale_text_and_other_client(web,db):
    identity=launch(web)
    activation.run(db,identity,invoke=draft,review_invoke=reviewer)
    text=web.get(path()).json()['texts'][0]
    response=web.request('DELETE',f"{path()}/asset/{text['id']}",json={'digest':'0'*64})
    assert response.status_code==409
    assert db.get(Asset,text['id']) is not None
    assert web.put(f"{path(2)}/asset/{text['id']}/stage",json={'stage':'erledigt'}).status_code==404


def test_pitch_without_recipient_is_saved_and_kept_separate_from_personal_pitch(web,db):
    def write(*args,**kwargs):
        return json.dumps(dict(subject='Study offer',message='Eine Studie könnte neue Fragen beantworten.',hook='Research topic'))
    personal=launch(web,'pitch',contact_id=1)
    activation.run(db,personal,invoke=write,review_invoke=reviewer)
    for _ in range(2):
        identity=launch(web,'pitch')
        activation.run(db,identity,invoke=write,review_invoke=reviewer)
        job=db.get(OpportunityAssetRun,identity)
        assert job.status=='complete'
        row=db.get(Outreach,job.outreach_id)
        assert row.contact_id is None and row.journalist=='' and row.outlet==''
        assert row.released_at is None
        assert job.context['journalist'] is None
    assert db.scalar(select(func.count()).select_from(Outreach))==3
    assert db.get(Outreach,db.get(OpportunityAssetRun,personal).outreach_id).journalist=='A Journalist'


@pytest.mark.parametrize('kind',['kundenmail','linkedin','custom','pitch'])
def test_repeated_asset_creation_keeps_every_draft_and_instruction(web,db,kind):
    ids=[]
    for i in range(3):
        identity=launch(web,kind,instruction=f'Instruction {i}',**({'contact_id':1} if kind=='pitch' else {}))
        def write(*args,**kwargs):
            return json.dumps(dict(subject=f'Pitch {i}',message=f'Entwurf Nummer {i}.',hook='Research')) if kind=='pitch' else json.dumps(dict(title=f'Asset {i}',body=f'Entwurf Nummer {i}.',speaker=''))
        activation.run(db,identity,invoke=write,review_invoke=reviewer)
        job=db.get(OpportunityAssetRun,identity)
        assert job.status=='complete'
        assert job.context['instruction']==f'Instruction {i}'
        ids.append(job.outreach_id if kind=='pitch' else job.asset_id)
    assert len(set(ids))==3
    texts=web.get(path()).json()['texts']
    assert [t['id'] for t in texts]==list(reversed(ids))
    assert [t['body'] for t in texts]==['Entwurf Nummer 2.','Entwurf Nummer 1.','Entwurf Nummer 0.']
    model=Outreach if kind=='pitch' else Asset
    assert all(db.get(model,i).independent_draft for i in ids)
    # Re-delivering the same completed request is not another user request.
    activation.run(db,identity,invoke=lambda *a,**kw:pytest.fail('Completed job repeated'))
    assert db.scalar(select(func.count()).select_from(model))==3


def test_duplicate_worker_during_review_cannot_append_another_asset(web,db):
    identity=launch(web)
    def check(*args,**kwargs):
        activation.run(db,identity,invoke=lambda *a,**kw:pytest.fail('Already persisted job regenerated'))
        return reviewer(*args,**kwargs)
    activation.run(db,identity,invoke=draft,review_invoke=check)
    assert db.get(OpportunityAssetRun,identity).status=='complete'
    assert db.scalar(select(func.count()).select_from(Asset))==1


def test_deleting_and_restoring_one_variant_keeps_other_drafts(web,db):
    from newspulse.models import TrashEntry
    from newspulse import recycle_bin
    for _ in range(2):
        identity=launch(web)
        activation.run(db,identity,invoke=draft,review_invoke=reviewer)
    texts=web.get(path()).json()['texts']
    original=texts[1]
    deleted=web.request('DELETE',f"{path()}/asset/{original['id']}",json={'digest':original['digest']})
    assert deleted.status_code==200
    assert [t['id'] for t in deleted.json()['texts']]==[texts[0]['id']]
    entry=db.scalar(select(TrashEntry))
    recycle_bin.restore(db,entry.id)
    assert {t['id'] for t in web.get(path()).json()['texts']}=={t['id'] for t in texts}
