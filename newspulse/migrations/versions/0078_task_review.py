"""Allow tasks to wait for review between work and completion."""
from alembic import op
import sqlalchemy as sa

revision = '0078_task_review'
down_revision = '0077_ensure_client_strategy'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tasks') as batch:
        batch.drop_constraint('ck_tasks_status', type_='check')
        batch.create_check_constraint('ck_tasks_status', "status IN ('offen','in_arbeit','review','erledigt')")


def downgrade():
    op.execute(sa.text("UPDATE tasks SET status='in_arbeit' WHERE status='review'"))
    with op.batch_alter_table('tasks') as batch:
        batch.drop_constraint('ck_tasks_status', type_='check')
        batch.create_check_constraint('ck_tasks_status', "status IN ('offen','in_arbeit','erledigt')")
