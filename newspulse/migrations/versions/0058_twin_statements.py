"""Multiple Twin statements, revision history and staged questionnaire imports."""
import sqlalchemy as sa
from alembic import op

revision = "0058_twin_statements"
down_revision = "0057_fact_evidence"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("client_facts") as batch:
        batch.add_column(sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("note", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("verification_note", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("verified_by", sa.String(200), nullable=True))
        batch.add_column(sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("import_hash", sa.String(64), nullable=True))
        batch.drop_constraint("uq_client_facts_key", type_="unique")
    op.create_index("uq_client_facts_primary", "client_facts", ["client_id", "key"], unique=True,
                    sqlite_where=sa.text("is_primary = 1"), postgresql_where=sa.text("is_primary = true"))
    op.create_index("uq_client_facts_import", "client_facts", ["client_id", "import_hash"], unique=True)
    op.create_table("client_fact_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fact_id", sa.Integer(), sa.ForeignKey("client_facts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by", sa.String(200), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False))
    op.create_index("ix_client_fact_history_client_id", "client_fact_history", ["client_id"])
    op.create_index("ix_client_fact_history_fact_id", "client_fact_history", ["fact_id"])
    op.create_table("twin_import_previews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False))
    op.create_index("ix_twin_import_previews_client_id", "twin_import_previews", ["client_id"])


def downgrade():
    # Rolling back must never silently choose one of several statements to keep.
    conn = op.get_bind()
    duplicate = conn.execute(sa.text(
        "SELECT 1 FROM client_facts GROUP BY client_id, key HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicate:
        raise RuntimeError("Twin contains multiple statements per field; export/reconcile them before downgrade.")
    op.drop_table("twin_import_previews")
    op.drop_table("client_fact_history")
    op.drop_index("uq_client_facts_primary", table_name="client_facts")
    op.drop_index("uq_client_facts_import", table_name="client_facts")
    with op.batch_alter_table("client_facts") as batch:
        for name in ("is_primary", "revision", "note", "verification_note", "verified_by", "verified_at", "import_hash"):
            batch.drop_column(name)
        batch.create_unique_constraint("uq_client_facts_key", ["client_id", "key"])
