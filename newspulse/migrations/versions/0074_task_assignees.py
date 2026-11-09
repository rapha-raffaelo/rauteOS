"""A task names who does it: the team members tagged on it (Raphael, Lucas)."""
import json

import sqlalchemy as sa
from alembic import op

revision = '0074_task_assignees'
down_revision = '0073_merge_profile_heads'
branch_labels = None
depends_on = None

#: The free-text "Zuständig" before tags: a name that matches a team member
#: becomes that member's tag, anything else stays in the note-free owner field.
_NAMES = {'raphael': 'raphael', 'lucas': 'lucas'}


def upgrade():
    with op.batch_alter_table('tasks') as batch:
        batch.add_column(sa.Column('assignees', sa.JSON(), nullable=False, server_default='[]'))
    bind = op.get_bind()
    for task_id, owner in bind.execute(sa.text("SELECT id, owner FROM tasks WHERE owner != ''")).all():
        tags = [key for word, key in _NAMES.items() if word in (owner or '').casefold()]
        if tags:
            bind.execute(sa.text("UPDATE tasks SET assignees = :a WHERE id = :i"),
                         {"a": json.dumps(tags), "i": task_id})


def downgrade():
    with op.batch_alter_table('tasks') as batch:
        batch.drop_column('assignees')
