"""Make task project_id optional for ad-hoc tasks."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_make_task_project_optional"
down_revision = "0002_add_task_json_payloads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Allow tasks without a linked project."""

    op.alter_column(
        "tasks",
        "project_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    """Require linked project again."""

    op.alter_column(
        "tasks",
        "project_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
