"""A customer's recording waits under its question until it is archived; the answer written from it."""
import sqlalchemy as sa
from alembic import op

revision = '0072_onboarding_audio_review'
down_revision = '0071_client_people'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('customer_onboarding_audio') as batch:
        batch.add_column(sa.Column('review', sa.String(20), nullable=False, server_default=''))
        batch.add_column(sa.Column('answer_fact_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_onboarding_audio_answer_fact', 'client_facts',
                                 ['answer_fact_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('customer_onboarding_audio') as batch:
        batch.drop_constraint('fk_onboarding_audio_answer_fact', type_='foreignkey')
        batch.drop_column('answer_fact_id')
        batch.drop_column('review')
