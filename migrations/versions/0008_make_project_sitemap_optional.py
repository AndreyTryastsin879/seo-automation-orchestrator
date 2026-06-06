"""Make project sitemap_path optional.

Revision ID: 0008_sitemap_optional
Revises: 0007_crawl_segment_queue
Create Date: 2026-05-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_sitemap_optional"
down_revision = "0007_crawl_segment_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Allow null sitemap_path values for projects."""

    op.alter_column("projects", "sitemap_path", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    """Restore required sitemap_path values for projects."""

    op.alter_column("projects", "sitemap_path", existing_type=sa.Text(), nullable=False)
