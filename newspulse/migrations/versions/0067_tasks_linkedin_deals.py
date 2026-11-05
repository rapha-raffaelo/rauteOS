"""Aufgaben, LinkedIn-Beiträge und Sales-CRM-Deals (spec 10)."""
import sqlalchemy as sa
from alembic import op

revision = '0067_tasks_linkedin_deals'
down_revision = '0066_client_archive'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('note', sa.Text(), nullable=False, server_default=''),
        sa.Column('priority', sa.String(10), nullable=False, server_default='mittel'),
        sa.Column('status', sa.String(10), nullable=False, server_default='offen'),
        sa.Column('due_on', sa.Date(), nullable=True),
        sa.Column('owner', sa.String(120), nullable=False, server_default=''),
        sa.Column('context_href', sa.String(300), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('done_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("priority IN ('hoch','mittel','niedrig')", name='ck_tasks_priority'),
        sa.CheckConstraint("status IN ('offen','in_arbeit','erledigt')", name='ck_tasks_status'),
    )
    op.create_index('ix_tasks_client_id', 'tasks', ['client_id'])
    op.create_index('ix_tasks_status', 'tasks', ['status'])
    op.create_index('ix_tasks_due_on', 'tasks', ['due_on'])
    op.create_table(
        'linkedin_posts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author', sa.String(120), nullable=False, server_default=''),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', sa.String(20), nullable=False, server_default='idee'),
        sa.Column('planned_on', sa.Date(), nullable=True),
        sa.Column('published_url', sa.String(500), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('idee','entwurf','freigabe','geplant','veroeffentlicht')",
                           name='ck_linkedin_posts_status'),
    )
    op.create_index('ix_linkedin_posts_client_id', 'linkedin_posts', ['client_id'])
    op.create_index('ix_linkedin_posts_status', 'linkedin_posts', ['status'])
    op.create_table(
        'deals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company', sa.String(200), nullable=False),
        sa.Column('contact_name', sa.String(120), nullable=False, server_default=''),
        sa.Column('contact_email', sa.String(200), nullable=False, server_default=''),
        sa.Column('stage', sa.String(20), nullable=False, server_default='lead'),
        sa.Column('value_eur', sa.Integer(), nullable=True),
        sa.Column('owner', sa.String(120), nullable=False, server_default=''),
        sa.Column('next_step', sa.String(300), nullable=False, server_default=''),
        sa.Column('next_step_on', sa.Date(), nullable=True),
        sa.Column('note', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("stage IN ('lead','gespraech','angebot','verhandlung','gewonnen','verloren')",
                           name='ck_deals_stage'),
    )
    op.create_index('ix_deals_stage', 'deals', ['stage'])


def downgrade():
    op.drop_table('deals')
    op.drop_table('linkedin_posts')
    op.drop_table('tasks')
