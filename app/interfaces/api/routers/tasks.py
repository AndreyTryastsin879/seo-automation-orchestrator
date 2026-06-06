"""Task API routes."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.interfaces.api.dependencies import get_db_session
from app.interfaces.api.schemas import CrawlAdHocRequest, TaskCreateRequest, TaskFileResponse, TaskResponse
from app.modules.tasks.application import (
    CreateTaskCommand,
    CreateTaskUseCase,
    GetTaskUseCase,
    ListTaskFilesUseCase,
    ListTasksUseCase,
)
from app.modules.tasks.infrastructure import TaskFileRepository, TaskQueue, TaskRepository
from app.modules.tasks.infrastructure.queue import CRAWL_DEFAULT_QUEUE_NAME

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    request: TaskCreateRequest,
    session: Session = Depends(get_db_session),
) -> TaskResponse:
    """Create a new task."""

    repository = TaskRepository(session)
    use_case = CreateTaskUseCase(repository)
    task = use_case.execute(
        CreateTaskCommand(
            batch_id=request.batch_id,
            project_id=request.project_id,
            queue_name=request.queue_name,
            task_type=request.task_type,
            payload=request.payload,
        )
    )
    session.commit()
    TaskQueue(queue_name=task.queue_name).enqueue(task.id, task_type=request.task_type)
    return TaskResponse.from_dto(task)


@router.post("/crawl-ad-hoc", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_ad_hoc_crawl_task(
    request: CrawlAdHocRequest,
    session: Session = Depends(get_db_session),
) -> TaskResponse:
    """Create an ad-hoc crawl task without writing a project record."""

    start_url = _ensure_absolute_url(request.start_url)
    webmaster_host = _normalize_webmaster_host(start_url)
    project_name = request.project_name or _derive_project_name(webmaster_host)

    task_repository = TaskRepository(session)
    create_task = CreateTaskUseCase(task_repository)
    task = create_task.execute(
        CreateTaskCommand(
            batch_id=None,
            project_id=None,
            queue_name=CRAWL_DEFAULT_QUEUE_NAME,
            task_type="crawl_site",
            payload=request.to_payload(
                start_url=start_url,
                project_name=project_name,
            ),
        )
    )
    session.commit()
    TaskQueue(queue_name=task.queue_name).enqueue(task.id, task_type="crawl_site")
    return TaskResponse.from_dto(task)


@router.get("", response_model=list[TaskResponse])
def list_tasks(session: Session = Depends(get_db_session)) -> list[TaskResponse]:
    """Return all tasks."""

    repository = TaskRepository(session)
    use_case = ListTasksUseCase(repository)
    tasks = use_case.execute()
    return [TaskResponse.from_dto(task) for task in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    session: Session = Depends(get_db_session),
) -> TaskResponse:
    """Return a task by identifier."""

    repository = TaskRepository(session)
    use_case = GetTaskUseCase(repository)
    task = use_case.execute(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )
    return TaskResponse.from_dto(task)


@router.get("/{task_id}/files", response_model=list[TaskFileResponse])
def list_task_files(
    task_id: int,
    session: Session = Depends(get_db_session),
) -> list[TaskFileResponse]:
    """Return files generated for a task."""

    task_repository = TaskRepository(session)
    get_task_use_case = GetTaskUseCase(task_repository)
    task = get_task_use_case.execute(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    task_file_repository = TaskFileRepository(session)
    use_case = ListTaskFilesUseCase(task_file_repository)
    task_files = use_case.execute(task_id)
    return [TaskFileResponse.from_dto(task_file) for task_file in task_files]


def _normalize_webmaster_host(start_url: str) -> str:
    """Normalize a crawl start URL to the webmaster host root."""

    parsed = urlsplit(_ensure_absolute_url(start_url))
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_url must be an absolute URL with scheme and host.",
        )
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "/", "", ""))


def _ensure_absolute_url(start_url: str) -> str:
    """Ensure a start URL has a scheme before further normalization."""

    normalized = start_url.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_url must not be empty.",
        )
    if "://" not in normalized:
        normalized = f"https://{normalized}"
    return normalized


def _derive_project_name(webmaster_host: str) -> str:
    """Derive a default project name from the host."""

    return urlsplit(webmaster_host).netloc.lower()
