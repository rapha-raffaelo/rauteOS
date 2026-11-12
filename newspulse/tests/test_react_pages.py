"""React page contracts: bootstrap safety, scoped data and existing writes."""
import datetime as dt
import json
import re

import pytest
from sqlalchemy import select, func
from test_workbench import db, web
from newspulse.models import Client, ClientFact
from newspulse.web.react_pages import view_data

JSON = {'Accept': 'application/json'}

@pytest.mark.parametrize('path,page', [('/mandant/neu','new_client'),('/archive','archive'),('/client/1','archive'),('/settings','settings'),('/settings?edit=1','settings'),('/client/1/twin','profile'),('/client/1/profil','profile')])
def test_pages_ship_json_and_react_mounts_not_jinja_page_bodies(web,path,page):
    response=web.get(path)
    assert response.status_code==200,response.text
    assert f'id="react-platform" data-page="{page}"' in response.text
    assert 'id="react-shell-data"' in response.text
    assert '<form' not in response.text  # React owns forms and navigation.
    assert response.headers['cache-control']=='no-store'
    data=web.get(path,headers=JSON)
    assert data.status_code==200 and data.headers['content-type'].startswith('application/json')
    assert 'Vary' in data.headers and data.headers['cache-control']=='no-store'


def test_profile_sources_and_disagreements_remain_scoped(web,db):
    db.add_all([ClientFact(client_id=1,key='ceo',value='Alice',source_title='Register',source_url='https://example.org/source',filled_by='research'),ClientFact(client_id=2,key='ceo',value='Other mandate')]);db.commit()
    data=web.get('/client/1/twin',headers=JSON).json()
    assert data['company']['facts']['ceo']['source_title']=='Register'
    assert data['company']['facts']['ceo']['filled_by']=='research'
    assert 'Other mandate' not in json.dumps(data)
    assert set(data)=={'client','view','company','people','people_error','people_draft'}
    assert set(web.get('/client/1/wettbewerb',headers=JSON).json())=={'client','view','rivals','market'}
    assert web.get('/client/3/twin',headers=JSON).status_code==404


def test_bootstrap_cannot_close_script_and_execute_client_text(web,db):
    attack='</script><script>alert("client")</script>'
    db.get(Client,1).name=attack;db.commit()
    body=web.get('/client/1/twin').text
    assert attack not in body
    raw=re.search(r'<script id="react-page-data" type="application/json">(.*?)</script>',body,re.S)[1]
    assert json.loads(raw)['client']['name']==attack


def test_settings_contract_excludes_secrets_and_serializes_proposals(web,monkeypatch):
    from newspulse.web.routes import settings
    from newspulse.schemas import RivalSuggestion
    monkeypatch.setitem(settings.themework.rivals_job.state,1,{'state':'fertig','rivals':[RivalSuggestion(name='Example',website='https://example.org',industry='Finance',aliases=['Example AG'])]})
    data=web.get('/settings?edit=1',headers=JSON).json()
    assert data['rival_work']['1']['rivals'][0]['aliases']==['Example AG']
    assert data['edit_id']==1 and len(data['clients'])==3
    from newspulse.gmail_link import Link
    assert {'email','scopes','connected_at','lost','is_connected','may_send','may_manage','scope_words'}==set(view_data(Link(email='example@example.org')))
    assert 'comms_guide' not in data['clients'][0]
    with pytest.raises(TypeError):view_data(object())


def test_brain_version_arrival_and_coach_findings_are_serializable(web,db):
    from newspulse import brain
    from newspulse.schemas import CoachFinding
    key=next(iter(brain.shipped()))
    brain.edit(db,key,'A new standard.')
    data=web.get(f'/settings/brain/{key}?fassung=1',headers=JSON).json()
    assert data['brain_from_change']['version']==1
    assert data['brain_history'][0]['text']=='A new standard.'
    finding=CoachFinding(kind='luecke',headline='Check',detail='Evidence needed',evidence=[])
    assert view_data(finding)['headline']=='Check'


def test_computed_research_status_is_in_the_json_contract():
    from newspulse.themes import ThemeProbe
    from newspulse.industry import Candidate
    from newspulse.web.routes.settings import RunView
    assert view_data(ThemeProbe(term='Market',reason='',external=4,own=0))['usable'] is True
    assert view_data(ThemeProbe(term='Own only',reason='',external=0,own=4))['usable'] is False
    assert 'usable' in view_data(Candidate(term='Tech',hits=50))
    assert view_data(RunView(started_at=dt.datetime.now(dt.UTC),finished_at=None,status='running',articles_found=0,errors=[]))['is_running'] is True


def test_the_profile_heading_is_the_mandate_with_its_mark(web,db):
    from react_render import rendered
    client=db.get(Client,1)
    page=rendered(web.get('/client/1/twin'))
    heading=re.search(r'<h1>(.*?)</h1>',page,re.S).group(1)
    assert client.name in heading and 'src="/client/1/logo"' in heading


def test_the_logo_address_serves_the_mark_or_the_monogram(web,db):
    client=db.get(Client,1)
    plain=web.get('/client/1/logo')
    assert plain.headers['content-type'].startswith('image/svg+xml') and '<svg' in plain.text
    client.logo_url='data:image/png;base64,iVBORw0KGgo=';db.commit()
    mark=web.get('/client/1/logo')
    assert mark.headers['content-type']=='image/png' and mark.content==b'\x89PNG\r\n\x1a\n'
    client.logo_url='javascript:alert(1)';db.commit()
    assert web.get('/client/1/logo').headers['content-type'].startswith('image/svg+xml')
    assert web.get('/client/3/logo').status_code==404
