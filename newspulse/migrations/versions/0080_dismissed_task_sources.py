"""Remember deleted decision cards without changing their source."""
from alembic import op
import sqlalchemy as sa
revision = "0080_dismissed_task_sources"
down_revision = "0079_task_boards"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("dismissed_task_sources", sa.Column("source_key", sa.String(100), primary_key=True))

def downgrade():
    op.drop_table("dismissed_task_sources")
