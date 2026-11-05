"""The company behind a brand: a mandate is the brand, this is its legal entity."""
import sqlalchemy as sa
from alembic import op

revision = '0068_client_legal_name'
down_revision = '0067_tasks_linkedin_deals'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('clients', sa.Column('legal_name', sa.String(255), nullable=False, server_default=''))


def downgrade():
    op.drop_column('clients', 'legal_name')
