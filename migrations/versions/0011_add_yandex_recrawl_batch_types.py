"""Add Yandex Webmaster recrawl task batch types.

Revision ID: 0011_yandex_recrawl_batch_types
Revises: 0010_yandex_oauth
"""

from alembic import op

revision = "0011_yandex_recrawl_batch_types"
down_revision = "0010_yandex_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE task_batch_type ADD VALUE IF NOT EXISTS 'yandex_webmaster_recrawl_project'")
    op.execute("ALTER TYPE task_batch_type ADD VALUE IF NOT EXISTS 'yandex_webmaster_recrawl_all'")


def downgrade() -> None:
    # PostgreSQL does not support removing individual enum values safely.
    pass
