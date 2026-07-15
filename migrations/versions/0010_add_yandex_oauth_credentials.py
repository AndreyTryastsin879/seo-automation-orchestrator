"""Add encrypted shared Yandex OAuth credentials.

Revision ID: 0010_yandex_oauth
Revises: 0009_bot_access
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_yandex_oauth"
down_revision = "0009_bot_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "yandex_oauth_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("encrypted_access_token", sa.String(length=4096), nullable=False),
        sa.Column("encrypted_refresh_token", sa.String(length=4096), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("yandex_oauth_credentials")
