"""Add IndexNow sitemap replacement batch types.

Revision ID: 0014_indexnow_sitemap_replace
Revises: 0013_indexnow
"""

from alembic import op

revision = "0014_indexnow_sitemap_replace"
down_revision = "0013_indexnow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE task_batch_type ADD VALUE IF NOT EXISTS 'indexnow_sitemap_replace_project'")
    op.execute("ALTER TYPE task_batch_type ADD VALUE IF NOT EXISTS 'indexnow_sitemap_replace_all'")


def downgrade() -> None:
    pass
