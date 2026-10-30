"""When a mandate went into the archive, so it can be deleted three months later.

Mandates already inactive start their three months today: the day they were
deactivated was never stored, and guessing it from an old date would delete one
the moment this deploys.
"""
import datetime as dt

import sqlalchemy as sa
from alembic import op
revision = '0066_client_archive'
down_revision = '0065_onboarding_audio'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('clients', sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True))
    now = dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M:%S.%f')
    op.execute(sa.text('UPDATE clients SET deactivated_at = :now WHERE active = 0').bindparams(now=now))


def downgrade():
    op.drop_column('clients', 'deactivated_at')
