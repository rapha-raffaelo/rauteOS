"""Private onboarding audio and durable Nova-3 transcription jobs."""
import sqlalchemy as sa
from alembic import op
revision = '0065_onboarding_audio'
down_revision = '0064_onboarding_workflow'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('customer_onboarding_audio',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('invite_id', sa.Integer(), sa.ForeignKey('customer_onboarding_invites.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_key', sa.String(32), nullable=False),
        sa.Column('mode', sa.String(20), nullable=False),
        sa.Column('filename', sa.String(200), nullable=False),
        sa.Column('mime', sa.String(80), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('transcript', sa.Text(), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    for col in ('client_id', 'invite_id', 'status'):
        op.create_index('ix_customer_onboarding_audio_' + col, 'customer_onboarding_audio', [col])


def downgrade():
    op.drop_table('customer_onboarding_audio')
