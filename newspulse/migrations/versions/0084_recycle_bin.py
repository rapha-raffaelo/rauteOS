"""Recoverable deleted records with a twelve-week expiry."""
from alembic import op
import sqlalchemy as sa
revision = '0084_recycle_bin'
down_revision = '0083_task_subtasks'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('trash_entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('record_type', sa.String(100), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False))
    op.create_index('ix_trash_entries_expires_at', 'trash_entries', ['expires_at'])

def downgrade():
    op.drop_table('trash_entries')
