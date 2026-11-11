"""Independent task favorites and a fourth priority."""
from alembic import op
import sqlalchemy as sa
revision = "0081_task_favorites_urgent"
down_revision = "0080_dismissed_task_sources"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("favorite", sa.Boolean(), nullable=False, server_default="0"))
        batch.drop_constraint("ck_tasks_priority", type_="check")
        batch.create_check_constraint("ck_tasks_priority", "priority IN ('urgent','hoch','mittel','niedrig')")
    op.execute(sa.text("UPDATE tasks SET favorite=1 WHERE priority='hoch'"))

def downgrade():
    op.execute(sa.text("UPDATE tasks SET priority='hoch' WHERE priority='urgent'"))
    with op.batch_alter_table("tasks") as batch:
        batch.drop_column("favorite")
        batch.drop_constraint("ck_tasks_priority", type_="check")
        batch.create_check_constraint("ck_tasks_priority", "priority IN ('hoch','mittel','niedrig')")
