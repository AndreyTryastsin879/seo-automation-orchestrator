"""Use cases for the projects module."""

from __future__ import annotations

from app.modules.projects.application.dto import CreateProjectCommand, ProjectDTO, UpdateProjectCommand
from app.modules.projects.domain import CrawlSegment
from app.modules.projects.infrastructure.models import Project
from app.modules.projects.infrastructure.repositories import ProjectRepository


def _to_project_dto(project: Project) -> ProjectDTO:
    """Convert an ORM project model to an application DTO."""

    return ProjectDTO(
        id=project.id,
        project_name=project.project_name,
        sitemap_path=project.sitemap_path,
        start_url=project.start_url,
        crawl_segment=project.crawl_segment,
        is_multi_sitemap=project.is_multi_sitemap,
        pagination_view=project.pagination_view,
        yandex_webmaster_host=project.yandex_webmaster_host,
        pagination_sample=project.pagination_sample,
        pagination_marker=project.pagination_marker,
        card_sample=project.card_sample,
        category_sample=project.category_sample,
        contain_subdomains=project.contain_subdomains,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


class CreateProjectUseCase:
    """Create a new project record."""

    def __init__(self, repository: ProjectRepository) -> None:
        """Bind the use case to a project repository."""

        self._repository = repository

    def execute(self, command: CreateProjectCommand) -> ProjectDTO:
        """Create a project and return its application DTO."""

        project = Project(
            project_name=command.project_name,
            sitemap_path=command.sitemap_path,
            start_url=command.start_url,
            crawl_segment=command.crawl_segment,
            is_multi_sitemap=command.is_multi_sitemap,
            pagination_view=command.pagination_view,
            yandex_webmaster_host=command.yandex_webmaster_host,
            pagination_sample=command.pagination_sample,
            pagination_marker=command.pagination_marker,
            card_sample=command.card_sample,
            category_sample=command.category_sample,
            contain_subdomains=command.contain_subdomains,
        )
        created_project = self._repository.create(project)
        return _to_project_dto(created_project)


class ListProjectsUseCase:
    """Return the list of projects."""

    def __init__(self, repository: ProjectRepository) -> None:
        """Bind the use case to a project repository."""

        self._repository = repository

    def execute(self, *, crawl_segment: CrawlSegment | None = None) -> list[ProjectDTO]:
        """Return projects as application DTOs, optionally filtered by segment."""

        projects = self._repository.list(crawl_segment=crawl_segment)
        return [_to_project_dto(project) for project in projects]


class GetProjectUseCase:
    """Return a project by identifier."""

    def __init__(self, repository: ProjectRepository) -> None:
        """Bind the use case to a project repository."""

        self._repository = repository

    def execute(self, project_id: int) -> ProjectDTO | None:
        """Return a project DTO or None when it does not exist."""

        project = self._repository.get_by_id(project_id)
        if project is None:
            return None
        return _to_project_dto(project)


class UpdateProjectUseCase:
    """Update an existing project record."""

    def __init__(self, repository: ProjectRepository) -> None:
        """Bind the use case to a project repository."""

        self._repository = repository

    def execute(self, project_id: int, command: UpdateProjectCommand) -> ProjectDTO | None:
        """Update a project and return its application DTO."""

        project = self._repository.get_by_id(project_id)
        if project is None:
            return None

        project.project_name = command.project_name
        project.sitemap_path = command.sitemap_path
        project.start_url = command.start_url
        project.crawl_segment = command.crawl_segment
        project.is_multi_sitemap = command.is_multi_sitemap
        project.pagination_view = command.pagination_view
        project.yandex_webmaster_host = command.yandex_webmaster_host
        project.pagination_sample = command.pagination_sample
        project.pagination_marker = command.pagination_marker
        project.card_sample = command.card_sample
        project.category_sample = command.category_sample
        project.contain_subdomains = command.contain_subdomains

        updated_project = self._repository.update(project)
        return _to_project_dto(updated_project)


class DeleteProjectUseCase:
    """Delete an existing project record."""

    def __init__(self, repository: ProjectRepository) -> None:
        """Bind the use case to a project repository."""

        self._repository = repository

    def execute(self, project_id: int) -> bool:
        """Delete a project by id and return whether it existed."""

        project = self._repository.get_by_id(project_id)
        if project is None:
            return False
        self._repository.delete(project)
        return True
