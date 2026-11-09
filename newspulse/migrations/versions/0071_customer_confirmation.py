"""Customer acknowledgement is distinct from independent fact verification."""
import sqlalchemy as sa
from alembic import op
revision = '0071_customer_confirmation'
down_revision = '0070_linkedin_posting'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('client_facts', sa.Column('customer_confirmed_at', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column('client_facts', 'customer_confirmed_at')
