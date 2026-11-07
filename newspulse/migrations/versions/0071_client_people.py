"""The mandate's phone book, and a chance's speaker taken from it."""
import sqlalchemy as sa
from alembic import op

revision = '0071_client_people'
down_revision = '0070_linkedin_posting'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'client_people',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('position', sa.String(200), nullable=False, server_default=''),
        sa.Column('phone', sa.String(80), nullable=False, server_default=''),
        sa.Column('email', sa.String(320), nullable=False, server_default=''),
        sa.Column('linkedin_url', sa.String(500), nullable=False, server_default=''),
        sa.Column('topics', sa.Text(), nullable=False, server_default=''),
        sa.Column('media_contact', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_client_people_client_id', 'client_people', ['client_id'])
    with op.batch_alter_table('opportunity_workspaces') as batch:
        batch.add_column(sa.Column('speaker_person_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_opportunity_workspaces_speaker_person', 'client_people',
                                 ['speaker_person_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('opportunity_workspaces') as batch:
        batch.drop_constraint('fk_opportunity_workspaces_speaker_person', type_='foreignkey')
        batch.drop_column('speaker_person_id')
    op.drop_index('ix_client_people_client_id', 'client_people')
    op.drop_table('client_people')
