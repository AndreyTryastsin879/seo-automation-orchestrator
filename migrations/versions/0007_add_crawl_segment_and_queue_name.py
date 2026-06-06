"""Add project crawl_segment and task queue_name."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_crawl_segment_queue"
down_revision = "0006_task_batch"
branch_labels = None
depends_on = None


crawl_segment_enum = postgresql.ENUM(
    "default",
    "heavy",
    name="crawl_segment",
    create_type=False,
)


def upgrade() -> None:
    """Add crawl segment to projects and queue name to tasks."""

    bind = op.get_bind()
    crawl_segment_enum.create(bind, checkfirst=True)

    op.add_column(
        "projects",
        sa.Column(
            "crawl_segment",
            crawl_segment_enum,
            nullable=False,
            server_default=sa.text("'default'"),
        ),
    )
    op.create_index(op.f("ix_projects_crawl_segment"), "projects", ["crawl_segment"], unique=False)

    op.add_column("tasks", sa.Column("queue_name", sa.String(length=100), nullable=True))
    op.create_index(op.f("ix_tasks_queue_name"), "tasks", ["queue_name"], unique=False)

    op.execute("UPDATE tasks SET queue_name = 'crawl_default' WHERE task_type = 'crawl_site'")
    op.execute("UPDATE tasks SET queue_name = 'tasks' WHERE queue_name IS NULL")


def downgrade() -> None:
    """Remove crawl segment from projects and queue name from tasks."""

    op.drop_index(op.f("ix_tasks_queue_name"), table_name="tasks")
    op.drop_column("tasks", "queue_name")

    op.drop_index(op.f("ix_projects_crawl_segment"), table_name="projects")
    op.drop_column("projects", "crawl_segment")

    bind = op.get_bind()
    crawl_segment_enum.drop(bind, checkfirst=True)
