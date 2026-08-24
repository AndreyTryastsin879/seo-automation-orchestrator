"""Add site audit task batch type.

Revision ID: 0016_site_audit
Revises: 0015_static_sitemaps
"""

from alembic import op


revision = "0016_site_audit"
down_revision = "0015_static_sitemaps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE task_batch_type ADD VALUE IF NOT EXISTS 'site_audit_project'")


def downgrade() -> None:
    pass
