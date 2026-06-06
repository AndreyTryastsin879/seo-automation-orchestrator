"""Add task cancel_requested flag."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_task_cancel_flag"
down_revision = "0004_split_project_urls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add cancel_requested to tasks."""

    op.add_column(
        "tasks",
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    """Remove cancel_requested from tasks."""

    op.drop_column("tasks", "cancel_requested")
