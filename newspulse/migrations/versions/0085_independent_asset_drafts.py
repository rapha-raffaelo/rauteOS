"""Keep explicit workspace creations as separate documents.

Automatic refreshes retain their singleton draft slot. Existing workspace
outputs are protected from that refresh path as well; no content is rewritten.
"""
from alembic import op
import sqlalchemy as sa

revision = '0085_independent_asset_drafts'
down_revision = '0084_recycle_bin'
branch_labels = None
depends_on = None

_INDEX = 'ux_assets_angle_kind_unreleased'


def upgrade():
    for table in ('assets', 'outreach'):
        op.add_column(table, sa.Column('independent_draft', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.drop_index(_INDEX, table_name='assets')
    op.create_index(_INDEX, 'assets', ['angle_id', 'kind'], unique=True,
        sqlite_where=sa.text('released_at IS NULL AND independent_draft = false'),
        postgresql_where=sa.text('released_at IS NULL AND independent_draft = false'))
    for table, reference in (('assets', 'asset_id'), ('outreach', 'outreach_id')):
        op.execute(sa.text(f'UPDATE {table} SET independent_draft = true WHERE id IN '
            f'(SELECT {reference} FROM opportunity_asset_runs WHERE {reference} IS NOT NULL)'))


def downgrade():
    # Returning to the old singleton constraint must never discard variants.
    duplicates = op.get_bind().execute(sa.text('SELECT angle_id, kind FROM assets '
        'WHERE released_at IS NULL AND angle_id IS NOT NULL GROUP BY angle_id, kind '
        'HAVING COUNT(*) > 1 LIMIT 1')).first()
    if duplicates:
        raise RuntimeError('Cannot downgrade: multiple unreleased assets exist. No drafts were removed.')
    op.drop_index(_INDEX, table_name='assets')
    op.create_index(_INDEX, 'assets', ['angle_id', 'kind'], unique=True,
        sqlite_where=sa.text('released_at IS NULL'), postgresql_where=sa.text('released_at IS NULL'))
    for table in ('outreach', 'assets'):
        op.drop_column(table, 'independent_draft')
