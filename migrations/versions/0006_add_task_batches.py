"""Add task_batches and tasks.batch_id."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_task_batch"
down_revision = "0005_task_cancel_flag"
branch_labels = None
depends_on = None


task_batch_status_enum = postgresql.ENUM(
    "pending",
    "running",
    "success",
    "failed",
    "cancelled",
    name="task_batch_status",
    create_type=False,
)

task_batch_type_enum = postgresql.ENUM(
    "crawl_all_projects",
    "crawl_project",
    "crawl_adhoc",
    name="task_batch_type",
    create_type=False,
)


def upgrade() -> None:
    """Create task batch table and link tasks to it."""

    bind = op.get_bind()
    task_batch_status_enum.create(bind, checkfirst=True)
    task_batch_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "task_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_type", task_batch_type_enum, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", task_batch_status_enum, server_default=sa.text("'pending'"), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_batches")),
    )
    op.create_index(op.f("ix_task_batches_batch_type"), "task_batches", ["batch_type"], unique=False)
    op.create_index(op.f("ix_task_batches_status"), "task_batches", ["status"], unique=False)

    op.add_column("tasks", sa.Column("batch_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_tasks_batch_id"), "tasks", ["batch_id"], unique=False)
    op.create_index("ix_tasks_batch_id_status", "tasks", ["batch_id", "status"], unique=False)
    op.create_foreign_key(
        op.f("fk_tasks_batch_id_task_batches"),
        "tasks",
        "task_batches",
        ["batch_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Drop task batch table and task link."""

    op.drop_constraint(op.f("fk_tasks_batch_id_task_batches"), "tasks", type_="foreignkey")
    op.drop_index("ix_tasks_batch_id_status", table_name="tasks")
    op.drop_index(op.f("ix_tasks_batch_id"), table_name="tasks")
    op.drop_column("tasks", "batch_id")

    op.drop_index(op.f("ix_task_batches_status"), table_name="task_batches")
    op.drop_index(op.f("ix_task_batches_batch_type"), table_name="task_batches")
    op.drop_table("task_batches")

    bind = op.get_bind()
    task_batch_type_enum.drop(bind, checkfirst=True)
    task_batch_status_enum.drop(bind, checkfirst=True)
