"""Add JSON payload fields to tasks."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_add_task_json_payloads"
down_revision = "0001_project_task_taskfile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert task payload to JSONB and add task result payload."""

    op.add_column("tasks", sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.alter_column(
        "tasks",
        "payload",
        existing_type=sa.Text(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
        postgresql_using="CASE WHEN payload IS NULL THEN NULL ELSE to_jsonb(payload) END",
    )


def downgrade() -> None:
    """Revert task payload fields to the previous schema."""

    op.alter_column(
        "tasks",
        "payload",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using="payload::text",
    )
    op.drop_column("tasks", "result_payload")
