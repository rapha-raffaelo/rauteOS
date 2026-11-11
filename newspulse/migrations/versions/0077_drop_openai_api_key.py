"""OpenAI runs over the ChatGPT subscription now: drop a stored API key.

The key field is gone from the settings and nothing reads it any more; leaving
the encrypted key in the database would only keep a billing credential around.
The API model name goes too: Codex picks the subscription's own model.
"""
import sqlalchemy as sa
from alembic import op

revision = '0077_drop_openai_api_key'
down_revision = '0076_ensure_task_assignees'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("DELETE FROM settings WHERE key IN ('ai_key:openai', 'ai_model:openai')"))


def downgrade():
    pass
