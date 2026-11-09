"""Make sure tasks.assignees exists, whichever way the database reached 0075.

A database stamped ``0075_client_strategy`` by unpushed work never ran this
repository's ``0074_task_assignees``. Adding the column only where it is
missing keeps both paths correct.
"""
import sqlalchemy as sa
from alembic import op

revision = '0076_ensure_task_assignees'
down_revision = '0075_client_strategy'
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("tasks")}
    if "assignees" not in columns:
        with op.batch_alter_table('tasks') as batch:
            batch.add_column(sa.Column('assignees', sa.JSON(), nullable=False, server_default='[]'))


def downgrade():
    pass
