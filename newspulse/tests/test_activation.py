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
    assert web.post(path(),json={'kind':'pitch'}).status_code==422
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
    activation.run(db,2,invoke=reviewer)
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
    assert db.get(OpportunityAssetRun,identity).status=='failed'


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
