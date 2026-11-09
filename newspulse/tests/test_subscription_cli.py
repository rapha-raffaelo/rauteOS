import subprocess
import pytest
from newspulse import subscription_cli as cli, analyzer, shared_guides


def test_codex_uses_subscription_without_shell_or_api_keys(monkeypatch,tmp_path):
    monkeypatch.setenv('NEWSPULSE_CODEX_HOME',str(tmp_path))
    monkeypatch.setenv('OPENAI_API_KEY','secret')
    monkeypatch.setenv('CODEX_API_KEY','secret')
    monkeypatch.setenv('OTHER_APP_SECRET','secret')
    monkeypatch.setattr(shared_guides,'enrich_prompt',lambda prompt,**kw:prompt+' knowledge')
    def run(argv,**kwargs):
        assert argv[:2]==['codex','exec']
        assert 'forced_login_method="chatgpt"' in argv
        assert 'features.shell_tool=false' in argv
        assert 'web_search="disabled"' in argv
        assert not any(k in kwargs['env'] for k in ['OPENAI_API_KEY','CODEX_API_KEY','OTHER_APP_SECRET'])
        assert kwargs['env']['CODEX_HOME']==str(tmp_path)
        assert kwargs['input']=='question knowledge'
        assert kwargs['shell'] is False
        return subprocess.CompletedProcess(argv,0,'{"queries":[]}', '')
    monkeypatch.setattr(subprocess,'run',run)
    assert cli.generate('codex','question')=='{"queries":[]}'


def test_claude_tools_disabled_and_metered_credentials_not_inherited(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY','secret')
    monkeypatch.setattr(shared_guides,'enrich_prompt',lambda p,**kw:p)
    def run(argv,**kwargs):
        assert argv[argv.index('--tools')+1]==''
        assert 'ANTHROPIC_API_KEY' not in kwargs['env']
        return subprocess.CompletedProcess(argv,0,'{"result":"ok"}', '')
    monkeypatch.setattr(subprocess,'run',run)
    assert cli.generate('claude','question')=='ok'


def test_cli_errors_do_not_log_secrets(monkeypatch):
    monkeypatch.setattr(shared_guides,'enrich_prompt',lambda p,**kw:p)
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:subprocess.CompletedProcess([],1,'token','secret'))
    with pytest.raises(analyzer.BackendError) as error:cli.generate('codex','question')
    assert 'secret' not in str(error.value) and 'token' not in str(error.value)
