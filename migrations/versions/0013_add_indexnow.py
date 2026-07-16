"""Add IndexNow credentials and task batch types.

Revision ID: 0013_indexnow
Revises: 0012_yandex_manual_token
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_indexnow"
down_revision = "0012_yandex_manual_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "indexnow_credentials",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column("key_location", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id"),
    )
    op.execute("ALTER TYPE task_batch_type ADD VALUE IF NOT EXISTS 'indexnow_submit_project'")
    op.execute("ALTER TYPE task_batch_type ADD VALUE IF NOT EXISTS 'indexnow_submit_all'")


def downgrade() -> None:
    op.drop_table("indexnow_credentials")
