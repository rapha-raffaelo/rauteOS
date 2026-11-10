"""Ensure strategy tables exist on databases which ran the placeholder 0075.

Replacing 0075 alone cannot repair databases already at 0076: Alembic will
not run it again. This forward-only repair supports both the placeholder path
and the original strategy migration, without changing existing data.
"""
from alembic import op
import sqlalchemy as sa

revision = '0077_ensure_client_strategy'
down_revision = '0076_ensure_task_assignees'
branch_labels = None
depends_on = None

def upgrade():
    # Production already created these tables through the former migration
    # chain. Keep existing workshop uploads and strategy text intact.
    bind = op.get_bind()
    if not sa.inspect(bind).has_table('client_strategies'):
        op.create_table('client_strategies',
            sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('revision', sa.Integer(), nullable=False))
    if not sa.inspect(bind).has_table('strategy_sources'):
        op.create_table('strategy_sources',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('filename', sa.String(255), nullable=False),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False))
    indexes = {index['name'] for index in sa.inspect(bind).get_indexes('strategy_sources')}
    if 'ix_strategy_sources_client_id' not in indexes:
        op.create_index('ix_strategy_sources_client_id', 'strategy_sources', ['client_id'])


def downgrade():
    # These tables belong to 0075. It drops them when downgrading past 0075.
    pass
