"""Persistent journalist profiles and dated opportunity-specific research."""
import sqlalchemy as sa
from alembic import op
revision = "0059_journalist_intelligence"
down_revision = "0058_twin_statements"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('journalist_profiles',
        sa.Column('contact_id',sa.Integer(),sa.ForeignKey('contacts.id',ondelete='CASCADE'),primary_key=True),
        *(sa.Column(name,sa.JSON(),nullable=False) for name in ('topics','specialties','story_types','companies','source_aliases')),
        sa.Column('preferences',sa.Text(),nullable=False),
        sa.Column('relationship_status',sa.String(40),nullable=False),
        sa.Column('last_interaction_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('revision',sa.Integer(),nullable=False))
    op.create_table('journalist_evidence',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('url',sa.String(2048),nullable=False,unique=True),
        sa.Column('title',sa.Text(),nullable=False),sa.Column('source',sa.String(255),nullable=False),
        sa.Column('author',sa.String(255),nullable=False),sa.Column('published_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('fetched_at',sa.DateTime(timezone=True),nullable=False),sa.Column('snippet',sa.Text(),nullable=False),
        sa.Column('provider',sa.String(40),nullable=False))
    op.create_index('ix_journalist_evidence_published_at','journalist_evidence',['published_at'])
    op.create_table('journalist_research',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('client_id',sa.Integer(),sa.ForeignKey('clients.id',ondelete='CASCADE'),nullable=False),
        sa.Column('context_kind',sa.String(16),nullable=False),sa.Column('context_id',sa.Integer(),nullable=False),
        sa.Column('query',sa.String(300),nullable=False),sa.Column('status',sa.String(16),nullable=False),
        sa.Column('started_at',sa.DateTime(timezone=True),nullable=False),sa.Column('finished_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('providers',sa.JSON(),nullable=False),sa.Column('results',sa.JSON(),nullable=False),sa.Column('note',sa.Text(),nullable=False))
    op.create_index('ix_journalist_research_client_id','journalist_research',['client_id'])
    op.create_index('uq_journalist_research_running','journalist_research',['client_id','context_kind','context_id'],unique=True,
                    sqlite_where=sa.text("status = 'running'"),postgresql_where=sa.text("status = 'running'"))


def downgrade():
    op.drop_table('journalist_research')
    op.drop_table('journalist_evidence')
    op.drop_table('journalist_profiles')
