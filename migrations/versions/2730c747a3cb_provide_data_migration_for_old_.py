"""Provide data migration for old pearslocal URLs.

Revision ID: 2730c747a3cb
Revises: 
Create Date: 2026-04-10 21:17:37.005248

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2730c747a3cb'
down_revision = '44660b29fb3d'
branch_labels = None
depends_on = None


def upgrade():
    # Get database connection
    urls_table = sa.table(
        'urls',
        sa.column('url', sa.String),
        sa.column('title', sa.String),
        sa.column('snippet', sa.String),
        sa.column('content', sa.String),
        sa.column('contributor', sa.String),
        sa.column('doctype', sa.String)
    )

    op.execute(
        urls_table.update()
        .where(urls_table.c.url.startswith('pearslocal'))
        .values(
            url='content-'+urls_table.c.contributor+'-'+sa.func.substr(sa.func.replace(urls_table.c.title, ' ', '-'),1,40),
            content=urls_table.c.snippet,
            doctype="content"
            )
    )
