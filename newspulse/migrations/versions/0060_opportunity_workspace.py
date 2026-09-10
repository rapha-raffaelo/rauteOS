"""Developed opportunities, saved activation choices and activity history."""
import sqlalchemy as sa
from alembic import op
revision = '0060_opportunity_workspace'
down_revision = '0059_journalist_intelligence'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('opportunity_workspaces',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('client_id',sa.Integer(),sa.ForeignKey('clients.id',ondelete='CASCADE'),nullable=False),
        sa.Column('context_kind',sa.String(16),nullable=False),sa.Column('context_id',sa.Integer(),nullable=False),
        sa.Column('angle_id',sa.Integer(),sa.ForeignKey('angles.id',ondelete='CASCADE'),nullable=True),
        sa.Column('data',sa.JSON(),nullable=False),sa.Column('storyline',sa.Text(),nullable=False),
        sa.Column('speaker_statement_id',sa.Integer(),sa.ForeignKey('client_facts.id',ondelete='SET NULL'),nullable=True),
        sa.Column('contact_ids',sa.JSON(),nullable=False),sa.Column('status',sa.String(16),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('client_id','context_kind','context_id',name='uq_opportunity_workspace_context'))
    op.create_index('ix_opportunity_workspaces_client_id','opportunity_workspaces',['client_id'])
    op.create_table('opportunity_developments',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('client_id',sa.Integer(),sa.ForeignKey('clients.id',ondelete='CASCADE'),nullable=False),
        sa.Column('focus',sa.String(300),nullable=False),sa.Column('status',sa.String(24),nullable=False),
        sa.Column('started_at',sa.DateTime(timezone=True),nullable=False),sa.Column('finished_at',sa.DateTime(timezone=True),nullable=True),
        *(sa.Column(name,sa.JSON(),nullable=False) for name in ('queries','sources','workspace_ids')),
        sa.Column('note',sa.Text(),nullable=False),sa.Column('brain_version',sa.Integer(),nullable=True))
    op.create_index('ix_opportunity_developments_client_id','opportunity_developments',['client_id'])
    op.create_index('uq_opportunity_development_running','opportunity_developments',['client_id'],unique=True,
        sqlite_where=sa.text("status = 'running'"),postgresql_where=sa.text("status = 'running'"))
    op.create_table('opportunity_events',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('workspace_id',sa.Integer(),sa.ForeignKey('opportunity_workspaces.id',ondelete='CASCADE'),nullable=False),
        sa.Column('kind',sa.String(40),nullable=False),sa.Column('detail',sa.JSON(),nullable=False),
        sa.Column('actor',sa.String(200),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_opportunity_events_workspace_id','opportunity_events',['workspace_id'])


def downgrade():
    op.drop_table('opportunity_events')
    op.drop_table('opportunity_developments')
    op.drop_table('opportunity_workspaces')
