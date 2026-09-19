"""Durable background press releases and real writing progress."""
import sqlalchemy as sa
from alembic import op
revision = '0062_default_drafts'
down_revision = '0061_opportunity_assets'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('default_draft_jobs',
        sa.Column('angle_id', sa.Integer(), sa.ForeignKey('angles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('stage', sa.String(20), nullable=False),
        sa.Column('preview', sa.Text(), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('token', sa.String(36), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_default_draft_jobs_client_id', 'default_draft_jobs', ['client_id'])
    op.create_index('ix_default_draft_jobs_status', 'default_draft_jobs', ['status'])


def downgrade():
    op.drop_table('default_draft_jobs')
