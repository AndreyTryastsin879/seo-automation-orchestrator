"""Add bot access users table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_bot_access"
down_revision = "0008_sitemap_optional"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_access_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bot_access_users")),
        sa.UniqueConstraint("phone_number", name=op.f("uq_bot_access_users_phone_number")),
        sa.UniqueConstraint("telegram_user_id", name=op.f("uq_bot_access_users_telegram_user_id")),
    )
    op.create_index(
        op.f("ix_bot_access_users_phone_number"),
        "bot_access_users",
        ["phone_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_bot_access_users_phone_number"), table_name="bot_access_users")
    op.drop_table("bot_access_users")
