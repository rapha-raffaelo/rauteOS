"""Durable research jobs and client onboarding contacts."""
import sqlalchemy as sa
from alembic import op
revision = '0064_onboarding_workflow'
down_revision = '0063_customer_onboarding'
branch_labels = None
depends_on = None


def upgrade():
    for name, size in [('contact_name', 255), ('contact_email', 320), ('contact_role', 255), ('contact_phone', 80)]:
        op.add_column('clients', sa.Column(name, sa.String(size), nullable=False, server_default=''))
    op.create_table('customer_onboarding_jobs',
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('stage', sa.String(100), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('checkpoint', sa.JSON(), nullable=False),
        sa.Column('invite_id', sa.Integer(), sa.ForeignKey('customer_onboarding_invites.id'), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('customer_onboarding_jobs')
    for name in ('contact_name', 'contact_email', 'contact_role', 'contact_phone'):
        op.drop_column('clients', name)
