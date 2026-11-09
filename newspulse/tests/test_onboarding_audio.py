import datetime as dt
from sqlalchemy import select
from newspulse import onboarding_audio as audio
from newspulse.models import CustomerOnboardingAudio as Audio, ClientFact
from test_customer_onboarding import setup, invite
WAV=b'RIFF'+b'\x00'*4+b'WAVEfmt '+b'\x00'*80

def upload(web,h,mode='audio'):
    r=web.post('/api/onboarding/audio/Q01.02?mode='+mode,headers=h,content=WAV)
    assert r.status_code==200,r.text
    return r.json()

def run(factory,invoke=None):
    with factory() as s: job=audio.claim(s)
    assert job
    audio.work(factory,*job,invoke=invoke or (lambda *a:('Ein klares Ziel.',4)))

def test_audio_scope_and_durable_processing(setup):
    web,f=setup;_,h=invite(web);_,other=invite(web,2);a=upload(web,h);path='/api/onboarding/audio/'+a['id']
    assert web.get(path,headers=other).status_code==404
    assert web.get(path+'/content').status_code==401
    assert web.get('/client/1/onboarding-audio').status_code==401
    assert web.put('/api/onboarding/answers/Q01.03',headers=h,json={'audio_id':a['id'],'mode':'audio'}).status_code==422
    assert web.put('/api/onboarding/answers/Q01.02',headers=h,json={'audio_id':a['id'],'mode':'audio'}).status_code==200
    run(f)
    answer=web.get('/api/onboarding',headers=h).json()['answers']['Q01.02']
    assert answer['value']=='Ein klares Ziel.' and answer['audio_id']==a['id']
    assert web.get(path+'/content',headers=h).content==WAV
    with f() as s:
        fact=s.scalar(select(ClientFact).where(ClientFact.key=='Q01.02'))
        assert 'Deepgram Nova-3' in fact.source_title and fact.verified_at is None
    listed=web.get('/client/1/onboarding-audio',auth=('agency','test-password')).json()
    assert listed[0]['transcript']=='Ein klares Ziel.' and 'content' not in listed[0]

def test_transcript_drops_original_and_requires_review(setup,monkeypatch):
    monkeypatch.setenv('DEEPGRAM_API_KEY','fake');web,f=setup;_,h=invite(web);a=upload(web,h,'transcript');run(f)
    with f() as s:
        assert s.get(Audio,a['id']).content is None
        assert s.scalar(select(ClientFact).where(ClientFact.key=='Q01.02')) is None
    assert web.get('/api/onboarding/audio/'+a['id']+'/content',headers=h).status_code==404
    assert web.put('/api/onboarding/answers/Q01.02',headers=h,json={'value':'Korrigiert','audio_id':a['id'],'mode':'transcript'}).status_code==200
    assert web.get('/api/onboarding',headers=h).json()['answers']['Q01.02']['value']=='Korrigiert'

def test_failure_keeps_audio_and_can_retry(setup):
    web,f=setup;_,h=invite(web);a=upload(web,h);path='/api/onboarding/audio/'+a['id']
    def fail(*a):raise ValueError('Vorübergehend nicht verfügbar')
    run(f,fail)
    assert web.get(path,headers=h).json()['status']=='failed'
    assert web.get(path+'/content',headers=h).content==WAV
    assert web.post(path+'/retry',headers=h).status_code==200
    run(f)
    assert web.get(path,headers=h).json()['status']=='ready'

def test_upload_validation_missing_key_and_auth(setup,monkeypatch):
    web,_=setup;_,h=invite(web);monkeypatch.delenv('DEEPGRAM_API_KEY',raising=False);monkeypatch.delenv('NEWSPULSE_DEEPGRAM_API_KEY',raising=False)
    assert web.post('/api/onboarding/audio/Q01.02',headers=h,content=WAV).status_code==503
    assert web.post('/api/onboarding/audio/Q01.02?mode=audio',headers=h,content=b'<html>not audio</html>').status_code==415
    monkeypatch.setattr(audio,'MAX_BYTES',30)
    assert web.post('/api/onboarding/audio/Q01.02?mode=audio',headers=h,content=WAV).status_code==413
    assert web.post('/api/onboarding/audio/Q01.02?mode=audio',content=WAV).status_code==401

def test_stale_worker_and_replaced_answer(setup):
    web,f=setup;_,h=invite(web);a=upload(web,h)
    with f() as s:
        first=audio.claim(s);s.get(Audio,a['id']).lease_until=dt.datetime.now(dt.UTC)-dt.timedelta(seconds=1);s.commit();second=audio.claim(s)
    audio.work(f,*first,invoke=lambda *a:('stale',2))
    assert web.get('/api/onboarding/audio/'+a['id'],headers=h).json()['status']=='processing'
    assert web.put('/api/onboarding/answers/Q01.02',headers=h,json={'value':'Neue Antwort'}).status_code==200
    audio.work(f,*second,invoke=lambda *a:('Audio text',2))
    assert web.get('/api/onboarding',headers=h).json()['answers']['Q01.02']['value']=='Neue Antwort'

def test_revoked_link_cannot_read_audio(setup):
    web,_=setup;link,h=invite(web);a=upload(web,h)
    web.post(f"/client/1/onboarding-invites/{link['id']}/revoke",auth=('agency','test-password'))
    assert web.get('/api/onboarding/audio/'+a['id']+'/content',headers=h).status_code==401

def test_audio_survives_link_renewal_but_not_accessible_to_other_link(setup):
    from newspulse.models import CustomerOnboardingJob, CustomerOnboardingInvite
    web,f=setup;link,h=invite(web);_,other=invite(web);a=upload(web,h)
    assert web.put('/api/onboarding/answers/Q01.02',headers=h,json={'audio_id':a['id'],'mode':'audio'}).status_code==200
    assert web.get('/api/onboarding/audio/'+a['id'],headers=other).status_code==404
    with f() as s:
        s.add(CustomerOnboardingJob(client_id=1,status='ready',invite_id=link['id']));s.commit()
    response=web.post('/client/1/onboarding-workflow/link',auth=('agency','test-password'))
    assert response.status_code==200
    from newspulse.onboarding_workflow import invite_token
    with f() as s:
        renewed={'X-Onboarding-Token':invite_token(s.get(CustomerOnboardingInvite,response.json()['invite_id']))}
    run(f)
    assert web.get('/api/onboarding/audio/'+a['id']+'/content',headers=renewed).content==WAV
    assert web.get('/api/onboarding',headers=renewed).json()['answers']['Q01.02']['value']=='Ein klares Ziel.'
    assert web.get('/api/onboarding/audio/'+a['id'],headers=h).status_code==401

def test_delete_scoped_audio_preserves_text(setup):
    web,f=setup;_,h=invite(web);_,other=invite(web,2);a=upload(web,h);path='/api/onboarding/audio/'+a['id']
    assert web.delete(path,headers=other).status_code==404
    web.put('/api/onboarding/answers/Q01.02',headers=h,json={'audio_id':a['id'],'mode':'audio'})
    run(f)
    response=web.delete(path,headers=h)
    assert response.status_code==200
    assert response.json()['answer']['value']=='Ein klares Ziel.'
    assert 'audio_id' not in response.json()['answer']
    assert web.get(path+'/content',headers=h).status_code==404
    with f() as s: assert s.get(Audio,a['id']) is None

def test_deleted_pending_audio_cannot_publish(setup):
    web,f=setup;_,h=invite(web);a=upload(web,h)
    web.put('/api/onboarding/answers/Q01.02',headers=h,json={'audio_id':a['id'],'mode':'audio'})
    with f() as s: job=audio.claim(s)
    assert web.delete('/api/onboarding/audio/'+a['id'],headers=h).json()['answer'] is None
    audio.work(f,*job,invoke=lambda *a:('Should not appear',4))
    assert 'Q01.02' not in web.get('/api/onboarding',headers=h).json()['answers']


def test_agency_answer_archives_atomically_and_delete_preserves_answer(setup):
    web, factory = setup
    _, headers = invite(web)
    item = upload(web, headers)
    path = '/client/1/onboarding-audio/' + item['id']
    auth = ('agency', 'test-password')
    assert web.post(path + '/answer', json={'value': 'Antwort'}).status_code == 401
    assert web.post(path.replace('/client/1/', '/client/2/') + '/answer', auth=auth, json={'value': 'Antwort'}).status_code == 404
    assert web.post(path + '/answer', auth=auth, json={'value': '   '}).status_code == 422
    assert web.get('/client/1/onboarding-audio', auth=auth).json()[0]['review'] == ''
    response = web.post(path + '/answer', auth=auth, json={'value': 'Unsere geprüfte Antwort.'})
    assert response.status_code == 200, response.text
    assert response.json()['review'] == 'archiviert'
    assert response.json()['answer'] == 'Unsere geprüfte Antwort.'
    assert response.json()['question'] != 'Q01.02'
    assert web.get(path + '/content', auth=auth).content == WAV
    assert web.post(path + '/answer', auth=auth, json={'value': 'Duplikat'}).status_code == 409
    run(factory)
    with factory() as session:
        row = session.get(Audio, item['id'])
        fact_id = row.answer_fact_id
        assert session.get(ClientFact, fact_id).value == 'Unsere geprüfte Antwort.'
    assert web.delete(path.replace('/client/1/', '/client/2/'), auth=auth).status_code == 404
    assert web.delete(path, auth=auth).status_code == 200
    assert web.get(path + '/content', auth=auth).status_code == 404
    with factory() as session:
        assert session.get(ClientFact, fact_id).value == 'Unsere geprüfte Antwort.'
