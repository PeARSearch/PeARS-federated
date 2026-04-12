"""Added content and license information to URL model

Revision ID: 44660b29fb3d
Revises:
Create Date: 2026-04-09 21:00:36.881313

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '44660b29fb3d'
down_revision = None
branch_labels = None
depends_on = None


def _column_exists(table, column):
    conn = op.get_bind()
    result = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in result)


def upgrade():
    with op.batch_alter_table('pods', schema=None) as batch_op:
        if _column_exists('pods', 'word_vector'):
            batch_op.drop_column('word_vector')
        if _column_exists('pods', 'DS_vector'):
            batch_op.drop_column('DS_vector')

    with op.batch_alter_table('suggestions', schema=None) as batch_op:
        if not _column_exists('suggestions', 'url_license'):
            batch_op.add_column(sa.Column('url_license', sa.String(length=1000), nullable=True))
        if not _column_exists('suggestions', 'allows_reproduction'):
            batch_op.add_column(sa.Column('allows_reproduction', sa.Boolean(), nullable=True))
        if not _column_exists('suggestions', 'licensing_notes'):
            batch_op.add_column(sa.Column('licensing_notes', sa.String(length=1000), nullable=True))

    with op.batch_alter_table('urls', schema=None) as batch_op:
        if not _column_exists('urls', 'content'):
            batch_op.add_column(sa.Column('content', sa.String(length=10000), nullable=True))
        if not _column_exists('urls', 'url_license'):
            batch_op.add_column(sa.Column('url_license', sa.String(length=1000), nullable=True))
        if not _column_exists('urls', 'allows_reproduction'):
            batch_op.add_column(sa.Column('allows_reproduction', sa.Boolean(), nullable=True))
        if not _column_exists('urls', 'licensing_notes'):
            batch_op.add_column(sa.Column('licensing_notes', sa.String(length=1000), nullable=True))


def downgrade():
    with op.batch_alter_table('urls', schema=None) as batch_op:
        batch_op.drop_column('licensing_notes')
        batch_op.drop_column('allows_reproduction')
        batch_op.drop_column('url_license')
        batch_op.drop_column('content')

    with op.batch_alter_table('suggestions', schema=None) as batch_op:
        batch_op.drop_column('licensing_notes')
        batch_op.drop_column('allows_reproduction')
        batch_op.drop_column('url_license')

    with op.batch_alter_table('pods', schema=None) as batch_op:
        batch_op.add_column(sa.Column('DS_vector', sa.VARCHAR(length=7000), nullable=True))
        batch_op.add_column(sa.Column('word_vector', sa.VARCHAR(length=7000), nullable=True))
