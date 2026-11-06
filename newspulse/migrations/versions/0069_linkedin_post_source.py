"""Where a LinkedIn post came from: the text RauteOS wrote, or the chance it picks up."""
import sqlalchemy as sa
from alembic import op

revision = '0069_linkedin_post_source'
down_revision = '0068_client_legal_name'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('linkedin_posts') as batch:
        batch.add_column(sa.Column('asset_id', sa.Integer(), sa.ForeignKey(
            'assets.id', ondelete='SET NULL', name='fk_linkedin_posts_asset_id'), nullable=True))
        batch.add_column(sa.Column('context_href', sa.String(300), nullable=False, server_default=''))
        batch.create_index('ix_linkedin_posts_asset_id', ['asset_id'])


def downgrade():
    with op.batch_alter_table('linkedin_posts') as batch:
        batch.drop_index('ix_linkedin_posts_asset_id')
        batch.drop_column('context_href')
        batch.drop_column('asset_id')
