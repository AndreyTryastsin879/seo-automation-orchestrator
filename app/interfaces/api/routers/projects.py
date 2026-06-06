"""Project API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.interfaces.api.dependencies import get_db_session
from app.interfaces.api.schemas import ProjectCreateRequest, ProjectResponse, ProjectUpdateRequest
from app.modules.projects.application import (
    CreateProjectCommand,
    CreateProjectUseCase,
    DeleteProjectUseCase,
    GetProjectUseCase,
    ListProjectsUseCase,
    UpdateProjectCommand,
    UpdateProjectUseCase,
)
from app.modules.projects.domain import CrawlSegment
from app.modules.projects.infrastructure import ProjectRepository

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: ProjectCreateRequest,
    session: Session = Depends(get_db_session),
) -> ProjectResponse:
    """Create a new project."""

    repository = ProjectRepository(session)
    _ensure_project_name_is_unique(session, repository, request.project_name)
    use_case = CreateProjectUseCase(repository)
    try:
        project = use_case.execute(
            CreateProjectCommand(
                project_name=request.project_name.strip(),
                sitemap_path=_normalize_optional_text(request.sitemap_path),
                start_url=_normalize_optional_url(request.start_url),
                crawl_segment=request.crawl_segment,
                is_multi_sitemap=request.is_multi_sitemap,
                pagination_view=_normalize_optional_text(request.pagination_view),
                yandex_webmaster_host=_normalize_optional_text(request.yandex_webmaster_host),
                pagination_sample=_normalize_optional_text(request.pagination_sample),
                pagination_marker=_normalize_optional_text(request.pagination_marker),
                card_sample=_normalize_optional_text(request.card_sample),
                category_sample=_normalize_optional_text(request.category_sample),
                contain_subdomains=request.contain_subdomains,
            )
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project with this name already exists.",
        ) from error
    return ProjectResponse.from_dto(project)


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    crawl_segment: CrawlSegment | None = None,
    session: Session = Depends(get_db_session),
) -> list[ProjectResponse]:
    """Return all projects."""

    repository = ProjectRepository(session)
    use_case = ListProjectsUseCase(repository)
    projects = use_case.execute(crawl_segment=crawl_segment)
    return [ProjectResponse.from_dto(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    session: Session = Depends(get_db_session),
) -> ProjectResponse:
    """Return a project by identifier."""

    repository = ProjectRepository(session)
    use_case = GetProjectUseCase(repository)
    project = use_case.execute(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return ProjectResponse.from_dto(project)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    request: ProjectUpdateRequest,
    session: Session = Depends(get_db_session),
) -> ProjectResponse:
    """Update an existing project."""

    repository = ProjectRepository(session)
    existing_project = repository.get_by_id(project_id)
    if existing_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    other_project = repository.get_by_name(request.project_name.strip())
    if other_project is not None and other_project.id != project_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project with this name already exists.",
        )

    use_case = UpdateProjectUseCase(repository)
    try:
        project = use_case.execute(
            project_id,
            UpdateProjectCommand(
                project_name=request.project_name.strip(),
                sitemap_path=_normalize_optional_text(request.sitemap_path),
                start_url=_normalize_optional_url(request.start_url),
                crawl_segment=request.crawl_segment,
                is_multi_sitemap=request.is_multi_sitemap,
                pagination_view=_normalize_optional_text(request.pagination_view),
                yandex_webmaster_host=_normalize_optional_text(request.yandex_webmaster_host),
                pagination_sample=_normalize_optional_text(request.pagination_sample),
                pagination_marker=_normalize_optional_text(request.pagination_marker),
                card_sample=_normalize_optional_text(request.card_sample),
                category_sample=_normalize_optional_text(request.category_sample),
                contain_subdomains=request.contain_subdomains,
            ),
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project with this name already exists.",
        ) from error

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return ProjectResponse.from_dto(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    session: Session = Depends(get_db_session),
) -> None:
    """Delete an existing project."""

    repository = ProjectRepository(session)
    use_case = DeleteProjectUseCase(repository)
    deleted = use_case.execute(project_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    session.commit()


def _ensure_project_name_is_unique(session: Session, repository: ProjectRepository, project_name: str) -> None:
    """Raise a conflict error when a project name is already used."""

    existing_project = repository.get_by_name(project_name.strip())
    if existing_project is None:
        return
    session.rollback()
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Project with this name already exists.",
    )


def _normalize_optional_text(value: str | None) -> str | None:
    """Normalize optional text values by stripping blanks."""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_optional_url(value: str | None) -> str | None:
    """Normalize optional project URLs while keeping empty values null."""

    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    if "://" not in normalized:
        return f"https://{normalized}"
    return normalized
