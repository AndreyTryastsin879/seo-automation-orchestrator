"""Add static sitemap task batch types.

Revision ID: 0015_static_sitemaps
Revises: 0014_indexnow_sitemap_replace
"""

from alembic import op

revision = "0015_static_sitemaps"
down_revision = "0014_indexnow_sitemap_replace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE task_batch_type ADD VALUE IF NOT EXISTS 'static_sitemap_create_project'")
    op.execute("ALTER TYPE task_batch_type ADD VALUE IF NOT EXISTS 'static_sitemap_create_all'")
    op.execute("ALTER TYPE task_batch_type ADD VALUE IF NOT EXISTS 'yandex_webmaster_static_sitemap_project'")
    op.execute("ALTER TYPE task_batch_type ADD VALUE IF NOT EXISTS 'yandex_webmaster_static_sitemap_all'")


def downgrade() -> None:
    pass
