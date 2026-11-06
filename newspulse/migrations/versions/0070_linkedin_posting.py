"""A LinkedIn post RauteOS publishes itself: when, as whom, and what LinkedIn answered."""
import sqlalchemy as sa
from alembic import op

revision = '0070_linkedin_posting'
down_revision = '0069_linkedin_post_source'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('linkedin_posts') as batch:
        batch.add_column(sa.Column('post_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('post_as', sa.String(254), nullable=False, server_default=''))
        batch.add_column(sa.Column('linkedin_urn', sa.String(120), nullable=False, server_default=''))
        batch.add_column(sa.Column('post_error', sa.String(300), nullable=False, server_default=''))
        batch.create_index('ix_linkedin_posts_post_at', ['post_at'])


def downgrade():
    with op.batch_alter_table('linkedin_posts') as batch:
        batch.drop_index('ix_linkedin_posts_post_at')
        batch.drop_column('post_error')
        batch.drop_column('linkedin_urn')
        batch.drop_column('post_as')
        batch.drop_column('post_at')
