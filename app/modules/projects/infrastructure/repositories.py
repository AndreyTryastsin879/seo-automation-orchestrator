"""Repositories for the projects module."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.projects.domain import CrawlSegment
from app.modules.projects.infrastructure.models import Project


class ProjectRepository:
    """Data access layer for project records."""

    def __init__(self, session: Session) -> None:
        """Bind repository to an existing SQLAlchemy session."""

        self._session = session

    def create(self, project: Project) -> Project:
        """Persist a new project instance."""

        self._session.add(project)
        self._session.flush()
        return project

    def get_by_id(self, project_id: int) -> Project | None:
        """Return a project by its primary key."""

        statement = select(Project).where(Project.id == project_id)
        return self._session.scalar(statement)

    def get_by_name(self, project_name: str) -> Project | None:
        """Return a project by its unique name."""

        statement = select(Project).where(Project.project_name == project_name)
        return self._session.scalar(statement)

    def get_by_start_url(self, start_url: str) -> Project | None:
        """Return a project by its crawl start URL."""

        statement = select(Project).where(Project.start_url == start_url)
        return self._session.scalar(statement)

    def list(self, *, crawl_segment: CrawlSegment | None = None) -> list[Project]:
        """Return projects ordered by identifier, optionally filtered by segment."""

        statement = select(Project).order_by(Project.id)
        if crawl_segment is not None:
            statement = statement.where(Project.crawl_segment == crawl_segment)
        return list(self._session.scalars(statement).all())

    def update(self, project: Project) -> Project:
        """Flush changes for an existing project instance."""

        self._session.add(project)
        self._session.flush()
        return project

    def delete(self, project: Project) -> None:
        """Delete an existing project instance."""

        self._session.delete(project)
        self._session.flush()
