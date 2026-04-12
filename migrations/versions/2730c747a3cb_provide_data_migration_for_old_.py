"""Provide data migration for old pearslocal URLs.

Revision ID: 2730c747a3cb
Revises: 44660b29fb3d
Create Date: 2026-04-10 21:17:37.005248

"""
import re
import unicodedata
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2730c747a3cb'
down_revision = '44660b29fb3d'
branch_labels = None
depends_on = None


def _make_slug(text, max_length=40):
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text).strip('-')
    return text[:max_length].rstrip('-')


def upgrade():
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, url, title, snippet, contributor, share FROM urls WHERE url LIKE 'pearslocal%'"
    )).fetchall()

    seen_slugs = set()
    for row in rows:
        slug = _make_slug(row.title) if row.title else 'untitled'
        base_url = f"content-{row.contributor}-{slug}"
        url = base_url
        c = 2
        while url in seen_slugs:
            url = f"{base_url}-{c}"
            c += 1
        seen_slugs.add(url)

        share = row.share
        if share:
            share = share.replace('api/get?url=' + row.url, 'api/show?url=' + url)

        conn.execute(
            sa.text("UPDATE urls SET url=:new_url, content=:content, doctype='content', share=:share WHERE id=:id"),
            {"new_url": url, "content": row.snippet, "share": share, "id": row.id}
        )
