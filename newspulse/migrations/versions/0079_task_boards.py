"""Shared task workspaces and stable links for decision-board entries."""
from alembic import op
import sqlalchemy as sa

revision = '0079_task_boards'
down_revision = '0078_task_review'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('task_boards',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('name_key', sa.String(80), nullable=False),
        sa.Column('system_key', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('name_key', name='uq_task_boards_name_key'),
        sa.UniqueConstraint('system_key', name='uq_task_boards_system_key'))
    op.execute(sa.text("""INSERT INTO task_boards (id,name,name_key,system_key,created_at) VALUES
        (1,'Allgemein','allgemein','general',CURRENT_TIMESTAMP),
        (2,'Offene Entscheidungen','offene entscheidungen','decisions',CURRENT_TIMESTAMP),
        (3,'rauteOS','rauteos','rauteos',CURRENT_TIMESTAMP)"""))
    with op.batch_alter_table('tasks') as batch:
        batch.add_column(sa.Column('board_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('source_key', sa.String(100), nullable=True))
        batch.add_column(sa.Column('source_kind', sa.String(40), nullable=False, server_default=''))
        batch.add_column(sa.Column('source_open', sa.Boolean(), nullable=True))
        batch.create_foreign_key('fk_tasks_board_id','task_boards',['board_id'],['id'],ondelete='RESTRICT')
        batch.create_unique_constraint('uq_tasks_source_key',['source_key'])
        batch.create_index('ix_tasks_board_id',['board_id'])
    op.execute(sa.text('UPDATE tasks SET board_id=1'))


def downgrade():
    with op.batch_alter_table('tasks') as batch:
        batch.drop_index('ix_tasks_board_id')
        batch.drop_constraint('uq_tasks_source_key',type_='unique')
        batch.drop_constraint('fk_tasks_board_id',type_='foreignkey')
        for column in ('source_open','source_kind','source_key','board_id'):
            batch.drop_column(column)
    op.drop_table('task_boards')
