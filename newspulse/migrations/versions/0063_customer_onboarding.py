"""Scoped customer onboarding links."""
import sqlalchemy as sa
from alembic import op
revision = '0063_customer_onboarding'
down_revision = '0062_default_drafts'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('customer_onboarding_invites',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('prefill', sa.JSON(), nullable=False),
        sa.Column('prefill_confirmed', sa.Boolean(), nullable=False))
    op.create_index('ix_customer_onboarding_invites_client_id', 'customer_onboarding_invites', ['client_id'])


def downgrade():
    op.drop_table('customer_onboarding_invites')
