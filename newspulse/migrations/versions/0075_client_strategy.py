"""Separate PR strategy and workshop source documents from the communication guide."""
from alembic import op
import sqlalchemy as sa
revision = '0075_client_strategy'
down_revision = '0074_task_assignees'
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
    op.drop_table('strategy_sources')
    op.drop_table('client_strategies')
