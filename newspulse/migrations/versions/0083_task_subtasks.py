"""Checkable subtasks belonging to a task."""
from alembic import op
import sqlalchemy as sa
revision = "0083_task_subtasks"
down_revision = "0082_drop_openai_api_key"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("task_subtasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default="0"))
    op.create_index("ix_task_subtasks_task_id", "task_subtasks", ["task_id"])

def downgrade():
    op.drop_table("task_subtasks")
