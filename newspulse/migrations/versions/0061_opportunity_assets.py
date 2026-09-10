"""Context snapshots and evidence checks for opportunity asset requests."""
import sqlalchemy as sa
from alembic import op
revision='0061_opportunity_assets'
down_revision='0060_opportunity_workspace'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('opportunity_asset_runs',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('workspace_id',sa.Integer(),sa.ForeignKey('opportunity_workspaces.id',ondelete='CASCADE'),nullable=False),
        sa.Column('kind',sa.String(40),nullable=False),sa.Column('status',sa.String(16),nullable=False),
        sa.Column('asset_id',sa.Integer(),sa.ForeignKey('assets.id',ondelete='SET NULL'),nullable=True),
        sa.Column('outreach_id',sa.Integer(),sa.ForeignKey('outreach.id',ondelete='SET NULL'),nullable=True),
        sa.Column('context',sa.JSON(),nullable=False),sa.Column('quality',sa.JSON(),nullable=False),
        sa.Column('text_digest',sa.String(64),nullable=False),sa.Column('note',sa.Text(),nullable=False),
        sa.Column('started_at',sa.DateTime(timezone=True),nullable=False),sa.Column('finished_at',sa.DateTime(timezone=True),nullable=True))
    op.create_index('ix_opportunity_asset_runs_workspace_id','opportunity_asset_runs',['workspace_id'])
    op.create_index('uq_opportunity_asset_running','opportunity_asset_runs',['workspace_id'],unique=True,
        sqlite_where=sa.text("status = 'running'"),postgresql_where=sa.text("status = 'running'"))


def downgrade():
    op.drop_table('opportunity_asset_runs')
