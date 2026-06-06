"""Create project, task, and task_file tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_project_task_taskfile"
down_revision = None
branch_labels = None
depends_on = None


task_status_enum = postgresql.ENUM(
    "pending",
    "running",
    "success",
    "failed",
    name="task_status",
    create_type=False,
)


def upgrade() -> None:
    """Create the initial project and task schema."""

    bind = op.get_bind()
    task_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_name", sa.String(length=255), nullable=False),
        sa.Column("sitemap_path", sa.Text(), nullable=False),
        sa.Column("is_multi_sitemap", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("pagination_view", sa.String(length=50), nullable=True),
        sa.Column("webmaster_host", sa.String(length=255), nullable=True),
        sa.Column("pagination_sample", sa.Text(), nullable=True),
        sa.Column("pagination_marker", sa.String(length=255), nullable=True),
        sa.Column("card_sample", sa.Text(), nullable=True),
        sa.Column("category_sample", sa.Text(), nullable=True),
        sa.Column("contain_subdomains", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.UniqueConstraint("project_name", name=op.f("uq_projects_project_name")),
    )
    op.create_index(op.f("ix_projects_project_name"), "projects", ["project_name"], unique=False)
    op.create_index("ix_projects_webmaster_host", "projects", ["webmaster_host"], unique=False)

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column("status", task_status_enum, server_default=sa.text("'pending'"), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_tasks_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(op.f("ix_tasks_project_id"), "tasks", ["project_id"], unique=False)
    op.create_index("ix_tasks_project_id_status", "tasks", ["project_id", "status"], unique=False)
    op.create_index("ix_tasks_project_id_task_type", "tasks", ["project_id", "task_type"], unique=False)
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)
    op.create_index(op.f("ix_tasks_task_type"), "tasks", ["task_type"], unique=False)

    op.create_table(
        "task_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_task_files_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_files")),
    )
    op.create_index(op.f("ix_task_files_task_id"), "task_files", ["task_id"], unique=False)
    op.create_index("ix_task_files_task_id_file_name", "task_files", ["task_id", "file_name"], unique=False)


def downgrade() -> None:
    """Drop the initial project and task schema."""

    op.drop_index("ix_task_files_task_id_file_name", table_name="task_files")
    op.drop_index(op.f("ix_task_files_task_id"), table_name="task_files")
    op.drop_table("task_files")

    op.drop_index(op.f("ix_tasks_task_type"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_status"), table_name="tasks")
    op.drop_index("ix_tasks_project_id_task_type", table_name="tasks")
    op.drop_index("ix_tasks_project_id_status", table_name="tasks")
    op.drop_index(op.f("ix_tasks_project_id"), table_name="tasks")
    op.drop_table("tasks")

    op.drop_index("ix_projects_webmaster_host", table_name="projects")
    op.drop_index(op.f("ix_projects_project_name"), table_name="projects")
    op.drop_table("projects")

    bind = op.get_bind()
    task_status_enum.drop(bind, checkfirst=True)
