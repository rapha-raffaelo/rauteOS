import json
from types import SimpleNamespace
import pytest
from newspulse import claude_login as login

@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.setattr(login, '_current', None)
    monkeypatch.setattr(login, '_cache', (0, {}))

@pytest.mark.parametrize('url', ['https://evil.test/oauth/authorize?a=b', 'https://claude.ai.evil.test/oauth/authorize', 'https://claude.ai:bad/oauth/authorize', 'https://user@claude.ai/oauth/authorize', 'https://claude.ai/other'])
def test_untrusted_urls_rejected(url):
    assert login.login_url(url) is None

def test_oauth_url():
    url='https://claude.ai/oauth/authorize?code_challenge=abc&state=xyz'
    assert login.login_url('\x1b[32mOpen '+url+'\x1b[0m') == url

@pytest.mark.parametrize('payload,expected', [({'loggedIn':True},'connected'),({'loggedIn':False},'login_required'),({},'unknown'),({'loggedIn':True,'loginExpiresAt':'2020-01-01T00:00:00Z'},'login_required')])
def test_status(monkeypatch,payload,expected):
    monkeypatch.setattr(login.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=json.dumps(payload)))
    assert login.status(force=True)['state']==expected

def test_owner_and_code_safety(monkeypatch):
    session={'id':'abc','owner':'a','state':'waiting','fd':42,'url':'https://claude.ai/oauth/authorize'}
    monkeypatch.setattr(login,'_current',session)
    with pytest.raises(KeyError): login.poll('abc','b')
    with pytest.raises(ValueError): login.submit('abc','a','abc\ncommand')
    written=[]
    monkeypatch.setattr(login.os,'write',lambda fd,value:written.append((fd,value)))
    result=login.submit('abc','a','valid-code#state')
    assert written==[(42,b'valid-code#state\n')]
    assert result['state']=='checking'
    assert 'fd' not in result and 'owner' not in result

def test_start_reuses_owner_and_cancel(monkeypatch):
    monkeypatch.setattr(login.threading.Thread,'start',lambda self:None)
    first=login.start('a')
    assert login.start('a')['id']==first['id']
    with pytest.raises(ValueError): login.start('b')
    assert login.cancel(first['id'],'a')['state']=='cancelled'
    assert login.start('b')['id']!=first['id']

def test_pty_login_roundtrip(monkeypatch):
    import sys, time
    original=login.subprocess.Popen
    script="print('https://claude.ai/oauth/authorize?state=test',flush=True); input(); print('done',flush=True)"
    monkeypatch.setattr(login.subprocess,'Popen',lambda args,**kwargs:original([sys.executable,'-c',script],**kwargs))
    monkeypatch.setattr(login,'status',lambda **kwargs:{'state':'connected'})
    session=login.start('alice')
    deadline=time.monotonic()+5
    while login.poll(session['id'],'alice')['state']=='starting' and time.monotonic()<deadline: time.sleep(.02)
    assert login.poll(session['id'],'alice')['state']=='waiting'
    login.submit(session['id'],'alice','test-code#state')
    while login.poll(session['id'],'alice')['state']=='checking' and time.monotonic()<deadline: time.sleep(.02)
    assert login.poll(session['id'],'alice')['state']=='connected'
    assert login.poll(session['id'],'alice')['url'] is None
