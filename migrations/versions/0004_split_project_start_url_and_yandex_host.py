"""Split project start_url and yandex webmaster host."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_split_project_urls"
down_revision = "0003_make_task_project_optional"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename webmaster_host to start_url and add yandex_webmaster_host."""

    op.drop_index("ix_projects_webmaster_host", table_name="projects")
    op.alter_column("projects", "webmaster_host", new_column_name="start_url")
    op.create_index("ix_projects_start_url", "projects", ["start_url"], unique=False)
    op.add_column("projects", sa.Column("yandex_webmaster_host", sa.String(length=255), nullable=True))
    op.create_index(
        "ix_projects_yandex_webmaster_host",
        "projects",
        ["yandex_webmaster_host"],
        unique=False,
    )


def downgrade() -> None:
    """Revert project URL field split."""

    op.drop_index("ix_projects_yandex_webmaster_host", table_name="projects")
    op.drop_column("projects", "yandex_webmaster_host")
    op.drop_index("ix_projects_start_url", table_name="projects")
    op.alter_column("projects", "start_url", new_column_name="webmaster_host")
    op.create_index("ix_projects_webmaster_host", "projects", ["webmaster_host"], unique=False)
