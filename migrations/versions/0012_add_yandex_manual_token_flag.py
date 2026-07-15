"""Track manually entered Yandex OAuth tokens.

Revision ID: 0012_yandex_manual_token
Revises: 0011_yandex_recrawl_batch_types
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_yandex_manual_token"
down_revision = "0011_yandex_recrawl_batch_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "yandex_oauth_credentials",
        sa.Column("is_manual_token", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("yandex_oauth_credentials", "is_manual_token")
