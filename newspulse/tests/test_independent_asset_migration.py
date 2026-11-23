"""Independent workspace documents survive migration and safe rollback checks."""
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session
from newspulse import config
from newspulse.models import Client,Angle,Asset,Outreach,OpportunityWorkspace,OpportunityAssetRun


@pytest.fixture
def migrated(tmp_path,monkeypatch):
    path=tmp_path/'independent.db'
    monkeypatch.setattr(config,'DATABASE_PATH',path)
    root=Path(__file__).resolve().parents[1]
    cfg=Config(str(root/'alembic.ini'))
    cfg.set_main_option('script_location',str(root/'migrations'))
    command.upgrade(cfg,'head')
    engine=create_engine(f'sqlite:///{path}')
    yield cfg,engine
    engine.dispose()


def seed(engine,*,duplicates=False):
    with Session(engine) as s:
        client=Client(name='Migration Client');s.add(client);s.flush()
        angle=Angle(client_id=client.id,subject='Anlass',message='Thema',context='Kontext');s.add(angle);s.flush()
        workspace=OpportunityWorkspace(client_id=client.id,context_kind='developed',context_id=angle.id,angle_id=angle.id)
        s.add(workspace);s.flush()
        rows=[Asset(client_id=client.id,angle_id=angle.id,kind='kundenmail',title='Erhalten',body='Text 1',independent_draft=duplicates),
              Asset(client_id=client.id,angle_id=angle.id,kind='kundenmail' if duplicates else 'statement',title='Zweiter Text',body='Text 2',independent_draft=duplicates)]
        letter=Outreach(client_id=client.id,angle_id=angle.id,message='Pitch bleibt',journalist='Anna',outlet='Zeitung')
        s.add_all([*rows,letter]);s.flush()
        s.add_all([OpportunityAssetRun(workspace_id=workspace.id,kind='kundenmail',status='complete',asset_id=rows[0].id),
                   OpportunityAssetRun(workspace_id=workspace.id,kind='pitch',status='complete',outreach_id=letter.id)])
        s.commit()


def test_upgrade_preserves_content_and_marks_existing_workspace_outputs(migrated):
    cfg,engine=migrated
    seed(engine)
    command.downgrade(cfg,'0084_recycle_bin')
    assert 'independent_draft' not in {c['name'] for c in inspect(engine).get_columns('assets')}
    command.upgrade(cfg,'head')
    with Session(engine) as s:
        rows=list(s.scalars(select(Asset).order_by(Asset.id)))
        assert [(r.body,r.independent_draft) for r in rows]==[('Text 1',True),('Text 2',False)]
        assert s.scalar(select(Outreach)).independent_draft is True
        s.add(Asset(client_id=rows[0].client_id,angle_id=rows[0].angle_id,kind='kundenmail',body='Variante',independent_draft=True))
        s.commit()
        assert len(list(s.scalars(select(Asset))))==3


def test_downgrade_refuses_to_discard_independent_variants(migrated):
    cfg,engine=migrated
    seed(engine,duplicates=True)
    with pytest.raises(RuntimeError,match='multiple unreleased assets'):
        command.downgrade(cfg,'0084_recycle_bin')
    with engine.connect() as conn:
        assert conn.scalar(text('select count(*) from assets'))==2
        assert conn.scalar(text('select version_num from alembic_version'))=='0085_independent_asset_drafts'
    assert 'independent_draft' in {c['name'] for c in inspect(engine).get_columns('assets')}
