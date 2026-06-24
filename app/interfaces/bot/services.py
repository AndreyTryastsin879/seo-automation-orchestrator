"""Application helpers used by the Telegram bot interface."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import app.core.models  # noqa: F401
from app.core.config import get_settings
from app.core.db import SessionFactory
from app.core.redis import get_redis_connection
from app.core.storage import LocalFileStorage
from app.modules.projects.application import (
    CreateProjectCommand,
    CreateProjectUseCase,
    DeleteProjectUseCase,
    GetProjectUseCase,
    ListProjectsUseCase,
    ProjectDTO,
    UpdateProjectCommand,
    UpdateProjectUseCase,
)
from app.modules.projects.domain import CrawlSegment
from app.modules.projects.infrastructure import ProjectRepository
from app.modules.tasks.application import (
    CreateTaskBatchCommand,
    CreateTaskBatchUseCase,
    CreateTaskCommand,
    CreateTaskUseCase,
    TaskBatchDTO,
    TaskDTO,
)
from app.modules.tasks.domain import TaskBatchStatus, TaskBatchType, TaskStatus
from app.modules.tasks.infrastructure import (
    Task,
    TaskBatch,
    TaskFile,
    TaskBatchRepository,
    TaskFileRepository,
    TaskQueue,
    TaskRepository,
)
from app.modules.tasks.infrastructure.queue import (
    CRAWL_DEFAULT_QUEUE_NAME,
    CRAWL_HEAVY_QUEUE_NAME,
    TASK_QUEUE_NAMES,
)
from rq import Queue
from rq.command import send_stop_job_command
from rq.registry import StartedJobRegistry

DEFAULT_CRAWL_MAX_PAGES = 8000
DEFAULT_CRAWL_MAX_DEPTH = 3
DEFAULT_CRAWL_MAX_CONCURRENCY = 5
DEFAULT_CRAWL_RESPECT_ROBOTS_DISALLOW = True
DEFAULT_CRAWL_DELAY_BETWEEN_REQUESTS_MS = 0
DEFAULT_CRAWL_REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_CRAWL_RETRY_ON_5XX = False
DEFAULT_CRAWL_MAX_5XX_BEFORE_STOP = 20
DEFAULT_CRAWL_RETRY_DELAY_MS = 1000
DEFAULT_HEAVY_CRAWL_MAX_PAGES = 8000
DEFAULT_HEAVY_CRAWL_MAX_DEPTH = 2
DEFAULT_HEAVY_CRAWL_MAX_CONCURRENCY = 1
DEFAULT_HEAVY_CRAWL_RESPECT_ROBOTS_DISALLOW = True
DEFAULT_HEAVY_CRAWL_DELAY_BETWEEN_REQUESTS_MS = 1000
DEFAULT_HEAVY_CRAWL_REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_HEAVY_CRAWL_RETRY_ON_5XX = True
DEFAULT_HEAVY_CRAWL_MAX_5XX_BEFORE_STOP = 10
DEFAULT_HEAVY_CRAWL_RETRY_DELAY_MS = 5000
DEFAULT_SITEMAP_RESOLVE_STATUS_CODES = True


@dataclass(slots=True, frozen=True)
class CrawlLaunchSettings:
    """User-facing crawl settings used to build crawl_site payloads."""

    max_pages: int = DEFAULT_CRAWL_MAX_PAGES
    max_depth: int = DEFAULT_CRAWL_MAX_DEPTH
    max_concurrency: int = DEFAULT_CRAWL_MAX_CONCURRENCY
    respect_robots_disallow: bool = DEFAULT_CRAWL_RESPECT_ROBOTS_DISALLOW
    delay_between_requests_ms: int = DEFAULT_CRAWL_DELAY_BETWEEN_REQUESTS_MS
    request_timeout_seconds: int = DEFAULT_CRAWL_REQUEST_TIMEOUT_SECONDS
    retry_on_5xx: bool = DEFAULT_CRAWL_RETRY_ON_5XX
    max_5xx_before_stop: int = DEFAULT_CRAWL_MAX_5XX_BEFORE_STOP
    retry_delay_ms: int = DEFAULT_CRAWL_RETRY_DELAY_MS


@dataclass(slots=True, frozen=True)
class RecentTaskSummary:
    """Compact task info for Telegram task lists."""

    task_id: int
    task_type: str
    status: str
    label: str


@dataclass(slots=True, frozen=True)
class RecentBatchSummary:
    """Compact batch info for Telegram launch lists."""

    batch_id: int
    title: str
    status: str
    total_tasks: int
    finished_tasks: int


@dataclass(slots=True, frozen=True)
class BatchStatusResult:
    """Batch details prepared for Telegram responses."""

    batch: TaskBatchDTO
    tasks: list[RecentTaskSummary]


@dataclass(slots=True, frozen=True)
class AdHocCrawlLaunchResult:
    """Result of creating an ad-hoc crawl task from the bot."""

    batch: TaskBatchDTO
    task: TaskDTO
    project_name: str
    start_url: str


@dataclass(slots=True, frozen=True)
class AdHocUrlListCrawlLaunchResult:
    """Result of creating a fixed URL list crawl task from the bot."""

    batch: TaskBatchDTO
    task: TaskDTO
    project_name: str
    start_url: str
    url_count: int


@dataclass(slots=True, frozen=True)
class AdHocSitemapLaunchResult:
    """Result of creating an ad-hoc sitemap parsing task from the bot."""

    batch: TaskBatchDTO
    task: TaskDTO
    sitemap_url: str


@dataclass(slots=True, frozen=True)
class AdHocRobotsLaunchResult:
    """Result of creating an ad-hoc robots parsing task from the bot."""

    batch: TaskBatchDTO
    task: TaskDTO
    robots_url: str


@dataclass(slots=True, frozen=True)
class TaskStatusResult:
    """Task details prepared for Telegram responses."""

    task: TaskDTO
    xlsx_path: Path | None
    csv_path: Path | None


@dataclass(slots=True, frozen=True)
class ProjectCrawlLaunchResult:
    """Result of launching a crawl for an existing project."""

    batch: TaskBatchDTO
    project: ProjectDTO
    task: TaskDTO


@dataclass(slots=True, frozen=True)
class ProjectSitemapLaunchResult:
    """Result of launching sitemap parsing for an existing project."""

    batch: TaskBatchDTO
    project: ProjectDTO
    task: TaskDTO


@dataclass(slots=True, frozen=True)
class ProjectRobotsLaunchResult:
    """Result of launching robots parsing for an existing project."""

    batch: TaskBatchDTO
    project: ProjectDTO
    task: TaskDTO


@dataclass(slots=True, frozen=True)
class BulkProjectCrawlLaunchResult:
    """Result of launching crawl tasks for all projects."""

    batch: TaskBatchDTO | None
    total_projects: int
    task_ids: list[int]
    tasks: list[RecentTaskSummary]


@dataclass(slots=True, frozen=True)
class BulkProjectSitemapLaunchResult:
    """Result of launching sitemap parsing tasks for all projects."""

    batch: TaskBatchDTO | None
    total_projects: int
    task_ids: list[int]
    tasks: list[RecentTaskSummary]


@dataclass(slots=True, frozen=True)
class CancelCrawlTasksResult:
    """Summary of a crawl cancellation request."""

    pending_cancelled: int
    running_cancel_requested: int


@dataclass(slots=True, frozen=True)
class CancelTaskBatchResult:
    """Summary of a task batch cancellation request."""

    batch_id: int
    pending_cancelled: int
    running_cancel_requested: int


def launch_ad_hoc_crawl(
    start_url: str,
    *,
    project_name: str | None = None,
    settings: CrawlLaunchSettings | None = None,
) -> AdHocCrawlLaunchResult:
    """Create an ad-hoc crawl task without writing a project record."""

    settings = settings or CrawlLaunchSettings()
    normalized_start_url = _ensure_absolute_url(start_url)
    webmaster_host = _normalize_webmaster_host(normalized_start_url)
    derived_project_name = project_name or _derive_project_name(webmaster_host)
    session = SessionFactory()
    try:
        task_batch = _create_task_batch(
            session=session,
            batch_type=TaskBatchType.CRAWL_ADHOC,
            title=f"Разовый сайт: {derived_project_name}",
            payload={
                "start_url": normalized_start_url,
                "project_name": derived_project_name,
                "crawl_settings": _settings_payload(settings),
            },
        )
        task = _create_crawl_task(
            session=session,
            batch_id=task_batch.id,
            project_id=None,
            start_url=normalized_start_url,
            project_name=derived_project_name,
            settings=settings,
            queue_name=CRAWL_DEFAULT_QUEUE_NAME,
        )
        session.commit()
        TaskQueue(queue_name=task.queue_name).enqueue(task.id, task_type="crawl_site")
        return AdHocCrawlLaunchResult(
            batch=task_batch,
            task=task,
            project_name=derived_project_name,
            start_url=normalized_start_url,
        )
    finally:
        session.close()


def launch_ad_hoc_url_list_crawl(
    urls: list[str],
    *,
    project_name: str | None = None,
    settings: CrawlLaunchSettings | None = None,
) -> AdHocUrlListCrawlLaunchResult:
    """Create a crawl task that processes only the provided URL list."""

    if not urls:
        raise ValueError("Список URL пуст.")

    normalized_urls = _normalize_url_list(urls)
    settings = settings or CrawlLaunchSettings()
    effective_settings = replace(settings, max_pages=max(settings.max_pages, len(normalized_urls)))
    webmaster_host = _normalize_webmaster_host(normalized_urls[0])
    derived_project_name = project_name or _derive_project_name(webmaster_host)
    session = SessionFactory()
    try:
        task_batch = _create_task_batch(
            session=session,
            batch_type=TaskBatchType.CRAWL_ADHOC,
            title=f"Список URL: {derived_project_name}",
            payload={
                "start_url": normalized_urls[0],
                "seed_urls": normalized_urls,
                "follow_links": False,
                "project_name": derived_project_name,
                "crawl_settings": _settings_payload(effective_settings),
            },
        )
        task = _create_crawl_task(
            session=session,
            batch_id=task_batch.id,
            project_id=None,
            start_url=normalized_urls[0],
            project_name=derived_project_name,
            settings=effective_settings,
            queue_name=CRAWL_DEFAULT_QUEUE_NAME,
            seed_urls=normalized_urls,
            follow_links=False,
        )
        session.commit()
        TaskQueue(queue_name=task.queue_name).enqueue(task.id, task_type="crawl_site")
        return AdHocUrlListCrawlLaunchResult(
            batch=task_batch,
            task=task,
            project_name=derived_project_name,
            start_url=normalized_urls[0],
            url_count=len(normalized_urls),
        )
    finally:
        session.close()

def launch_ad_hoc_sitemap(
    sitemap_url: str,
    *,
    resolve_status_codes: bool = DEFAULT_SITEMAP_RESOLVE_STATUS_CODES,
) -> AdHocSitemapLaunchResult:
    """Create an ad-hoc sitemap parsing task without writing a project record."""

    normalized_url = _ensure_absolute_url(sitemap_url)
    session = SessionFactory()
    try:
        task_batch = _create_task_batch(
            session=session,
            batch_type=TaskBatchType.CRAWL_ADHOC,
            title=f"Парсинг sitemap: {urlsplit(normalized_url).netloc.lower()}",
            payload={
                "url": normalized_url,
                "resolve_status_codes": resolve_status_codes,
            },
        )
        task = _create_fetch_sitemap_task(
            session=session,
            batch_id=task_batch.id,
            project_id=None,
            sitemap_url=normalized_url,
            resolve_status_codes=resolve_status_codes,
            queue_name=CRAWL_DEFAULT_QUEUE_NAME,
        )
        session.commit()
        TaskQueue(queue_name=task.queue_name).enqueue(task.id, task_type="fetch_sitemap")
        return AdHocSitemapLaunchResult(
            batch=task_batch,
            task=task,
            sitemap_url=normalized_url,
        )
    finally:
        session.close()


def launch_ad_hoc_robots(
    robots_url: str,
    *,
    resolve_status_codes: bool = DEFAULT_SITEMAP_RESOLVE_STATUS_CODES,
) -> AdHocRobotsLaunchResult:
    """Create an ad-hoc robots parsing task without writing a project record."""

    normalized_url = _ensure_absolute_url(robots_url)
    session = SessionFactory()
    try:
        task_batch = _create_task_batch(
            session=session,
            batch_type=TaskBatchType.CRAWL_ADHOC,
            title=f"Парсинг robots.txt: {urlsplit(normalized_url).netloc.lower()}",
            payload={
                "url": normalized_url,
                "resolve_status_codes": resolve_status_codes,
            },
        )
        task = _create_fetch_robots_task(
            session=session,
            batch_id=task_batch.id,
            project_id=None,
            robots_url=normalized_url,
            resolve_status_codes=resolve_status_codes,
            queue_name=CRAWL_DEFAULT_QUEUE_NAME,
        )
        session.commit()
        TaskQueue(queue_name=task.queue_name).enqueue(task.id, task_type="fetch_robots")
        return AdHocRobotsLaunchResult(
            batch=task_batch,
            task=task,
            robots_url=normalized_url,
        )
    finally:
        session.close()


def list_projects(*, crawl_segment: CrawlSegment = CrawlSegment.DEFAULT) -> list[ProjectDTO]:
    """Return projects for Telegram bot selection."""

    session = SessionFactory()
    try:
        repository = ProjectRepository(session)
        use_case = ListProjectsUseCase(repository)
        return use_case.execute(crawl_segment=crawl_segment)
    finally:
        session.close()


def list_all_projects() -> list[ProjectDTO]:
    """Return all projects without segment filtering."""

    session = SessionFactory()
    try:
        repository = ProjectRepository(session)
        return ListProjectsUseCase(repository).execute()
    finally:
        session.close()


def get_project(project_id: int) -> ProjectDTO | None:
    """Return one project by id for the bot."""

    session = SessionFactory()
    try:
        repository = ProjectRepository(session)
        return GetProjectUseCase(repository).execute(project_id)
    finally:
        session.close()


def create_project(
    *,
    project_name: str,
    sitemap_path: str | None,
    start_url: str | None,
    crawl_segment: CrawlSegment,
    is_multi_sitemap: bool,
    pagination_view: str | None,
    yandex_webmaster_host: str | None,
    pagination_sample: str | None,
    pagination_marker: str | None,
    card_sample: str | None,
    category_sample: str | None,
    contain_subdomains: bool,
) -> ProjectDTO:
    """Create a project from bot-collected input."""

    session = SessionFactory()
    try:
        repository = ProjectRepository(session)
        existing_project = repository.get_by_name(project_name)
        if existing_project is not None:
            raise ValueError("Проект с таким названием уже существует.")

        use_case = CreateProjectUseCase(repository)
        project = use_case.execute(
            CreateProjectCommand(
                project_name=project_name,
                sitemap_path=sitemap_path,
                start_url=start_url,
                crawl_segment=crawl_segment,
                is_multi_sitemap=is_multi_sitemap,
                pagination_view=pagination_view,
                yandex_webmaster_host=yandex_webmaster_host,
                pagination_sample=pagination_sample,
                pagination_marker=pagination_marker,
                card_sample=card_sample,
                category_sample=category_sample,
                contain_subdomains=contain_subdomains,
            )
        )
        session.commit()
        return project
    finally:
        session.close()


def update_project(
    project_id: int,
    *,
    project_name: str,
    sitemap_path: str | None,
    start_url: str | None,
    crawl_segment: CrawlSegment,
    is_multi_sitemap: bool,
    pagination_view: str | None,
    yandex_webmaster_host: str | None,
    pagination_sample: str | None,
    pagination_marker: str | None,
    card_sample: str | None,
    category_sample: str | None,
    contain_subdomains: bool,
) -> ProjectDTO | None:
    """Update a project from bot-collected input."""

    session = SessionFactory()
    try:
        repository = ProjectRepository(session)
        existing_project = repository.get_by_name(project_name)
        if existing_project is not None and existing_project.id != project_id:
            raise ValueError("Проект с таким названием уже существует.")

        use_case = UpdateProjectUseCase(repository)
        project = use_case.execute(
            project_id,
            UpdateProjectCommand(
                project_name=project_name,
                sitemap_path=sitemap_path,
                start_url=start_url,
                crawl_segment=crawl_segment,
                is_multi_sitemap=is_multi_sitemap,
                pagination_view=pagination_view,
                yandex_webmaster_host=yandex_webmaster_host,
                pagination_sample=pagination_sample,
                pagination_marker=pagination_marker,
                card_sample=card_sample,
                category_sample=category_sample,
                contain_subdomains=contain_subdomains,
            ),
        )
        if project is None:
            session.rollback()
            return None
        session.commit()
        return project
    finally:
        session.close()


def delete_project(project_id: int) -> bool:
    """Delete one project by id."""

    session = SessionFactory()
    try:
        repository = ProjectRepository(session)
        deleted = DeleteProjectUseCase(repository).execute(project_id)
        if not deleted:
            session.rollback()
            return False
        session.commit()
        return True
    finally:
        session.close()


def launch_project_crawl(
    project_id: int,
    *,
    settings: CrawlLaunchSettings | None = None,
) -> ProjectCrawlLaunchResult | None:
    """Create a crawl task for an existing project."""

    settings = settings or CrawlLaunchSettings()
    session = SessionFactory()
    try:
        project_repository = ProjectRepository(session)
        project = project_repository.get_by_id(project_id)
        if project is None:
            return None

        start_url = _resolve_project_start_url(
            start_url=project.start_url,
            sitemap_path=project.sitemap_path,
        )
        task_batch = _create_task_batch(
            session=session,
            batch_type=TaskBatchType.CRAWL_PROJECT,
            title=f"Парсинг проекта: {project.project_name}",
            payload={
                "project_id": project.id,
                "project_name": project.project_name,
                "start_url": start_url,
                "crawl_settings": _settings_payload(settings),
            },
        )
        task = _create_crawl_task(
            session=session,
            batch_id=task_batch.id,
            project_id=project.id,
            start_url=start_url,
            settings=settings,
            queue_name=_queue_name_for_segment(project.crawl_segment),
        )
        session.commit()
        TaskQueue(queue_name=task.queue_name).enqueue(task.id, task_type="crawl_site")
        return ProjectCrawlLaunchResult(batch=task_batch, project=project, task=task)
    finally:
        session.close()


def launch_project_sitemap(
    project_id: int,
    *,
    resolve_status_codes: bool = DEFAULT_SITEMAP_RESOLVE_STATUS_CODES,
) -> ProjectSitemapLaunchResult | None:
    """Create a sitemap parsing task for an existing project."""

    session = SessionFactory()
    try:
        project_repository = ProjectRepository(session)
        project = project_repository.get_by_id(project_id)
        if project is None:
            return None

        sitemap_url = _resolve_project_sitemap_url(project.sitemap_path)
        task_batch = _create_task_batch(
            session=session,
            batch_type=TaskBatchType.CRAWL_PROJECT,
            title=f"Парсинг sitemap: {project.project_name}",
            payload={
                "project_id": project.id,
                "project_name": project.project_name,
                "url": sitemap_url,
                "resolve_status_codes": resolve_status_codes,
            },
        )
        task = _create_fetch_sitemap_task(
            session=session,
            batch_id=task_batch.id,
            project_id=project.id,
            sitemap_url=sitemap_url,
            resolve_status_codes=resolve_status_codes,
            queue_name=CRAWL_DEFAULT_QUEUE_NAME,
        )
        session.commit()
        TaskQueue(queue_name=task.queue_name).enqueue(task.id, task_type="fetch_sitemap")
        return ProjectSitemapLaunchResult(batch=task_batch, project=project, task=task)
    finally:
        session.close()


def launch_project_robots(
    project_id: int,
    *,
    resolve_status_codes: bool = DEFAULT_SITEMAP_RESOLVE_STATUS_CODES,
) -> ProjectRobotsLaunchResult | None:
    """Create a robots parsing task for an existing project."""

    session = SessionFactory()
    try:
        project_repository = ProjectRepository(session)
        project = project_repository.get_by_id(project_id)
        if project is None:
            return None

        start_url = _resolve_project_start_url(
            start_url=project.start_url,
            sitemap_path=project.sitemap_path,
        )
        task_batch = _create_task_batch(
            session=session,
            batch_type=TaskBatchType.CRAWL_PROJECT,
            title=f"Парсинг robots.txt: {project.project_name}",
            payload={
                "project_id": project.id,
                "project_name": project.project_name,
                "url": start_url,
                "resolve_status_codes": resolve_status_codes,
            },
        )
        task = _create_fetch_robots_task(
            session=session,
            batch_id=task_batch.id,
            project_id=project.id,
            robots_url=start_url,
            resolve_status_codes=resolve_status_codes,
            queue_name=CRAWL_DEFAULT_QUEUE_NAME,
        )
        session.commit()
        TaskQueue(queue_name=task.queue_name).enqueue(task.id, task_type="fetch_robots")
        return ProjectRobotsLaunchResult(batch=task_batch, project=project, task=task)
    finally:
        session.close()


def launch_all_projects_crawl(*, settings: CrawlLaunchSettings | None = None) -> BulkProjectCrawlLaunchResult:
    """Create crawl tasks for all default-segment projects."""

    settings = settings or CrawlLaunchSettings()
    session = SessionFactory()
    try:
        project_repository = ProjectRepository(session)
        projects = ListProjectsUseCase(project_repository).execute(crawl_segment=CrawlSegment.DEFAULT)
        if not projects:
            return BulkProjectCrawlLaunchResult(
                batch=None,
                total_projects=0,
                task_ids=[],
                tasks=[],
            )

        task_batch = _create_task_batch(
            session=session,
            batch_type=TaskBatchType.CRAWL_ALL_PROJECTS,
            title="Парсинг всех проектов",
            payload={
                "project_ids": [project.id for project in projects],
                "crawl_settings": _settings_payload(settings),
            },
        )

        task_ids: list[int] = []
        task_summaries: list[RecentTaskSummary] = []
        for project in projects:
            start_url = _resolve_project_start_url(
                start_url=project.start_url,
                sitemap_path=project.sitemap_path,
            )
            task = _create_crawl_task(
                session=session,
                batch_id=task_batch.id,
                project_id=project.id,
                start_url=start_url,
                settings=settings,
                queue_name=CRAWL_DEFAULT_QUEUE_NAME,
            )
            task_ids.append(task.id)
            task_summaries.append(
                RecentTaskSummary(
                    task_id=task.id,
                    task_type=task.task_type,
                    status=task.status.value,
                    label=project.project_name,
                )
            )

        session.commit()

        for task_id in task_ids:
            TaskQueue(queue_name=CRAWL_DEFAULT_QUEUE_NAME).enqueue(task_id, task_type="crawl_site")

        return BulkProjectCrawlLaunchResult(
            batch=task_batch,
            total_projects=len(projects),
            task_ids=task_ids,
            tasks=task_summaries,
        )
    finally:
        session.close()


def launch_all_projects_sitemap(
    *,
    resolve_status_codes: bool = DEFAULT_SITEMAP_RESOLVE_STATUS_CODES,
) -> BulkProjectSitemapLaunchResult:
    """Create sitemap parsing tasks for all projects in default-then-heavy order."""

    session = SessionFactory()
    try:
        project_repository = ProjectRepository(session)
        all_projects = ListProjectsUseCase(project_repository).execute()
        eligible_projects = [project for project in all_projects if project.sitemap_path]
        eligible_projects.sort(key=lambda project: (project.crawl_segment == CrawlSegment.HEAVY, project.project_name.lower()))
        if not eligible_projects:
            return BulkProjectSitemapLaunchResult(
                batch=None,
                total_projects=0,
                task_ids=[],
                tasks=[],
            )

        task_batch = _create_task_batch(
            session=session,
            batch_type=TaskBatchType.CRAWL_ALL_PROJECTS,
            title="Парсинг sitemap всех проектов",
            payload={
                "project_ids": [project.id for project in eligible_projects],
                "resolve_status_codes": resolve_status_codes,
            },
        )

        task_ids: list[int] = []
        task_summaries: list[RecentTaskSummary] = []
        for project in eligible_projects:
            sitemap_url = _resolve_project_sitemap_url(project.sitemap_path)
            task = _create_fetch_sitemap_task(
                session=session,
                batch_id=task_batch.id,
                project_id=project.id,
                sitemap_url=sitemap_url,
                resolve_status_codes=resolve_status_codes,
                queue_name=CRAWL_DEFAULT_QUEUE_NAME,
            )
            task_ids.append(task.id)
            task_summaries.append(
                RecentTaskSummary(
                    task_id=task.id,
                    task_type=task.task_type,
                    status=task.status.value,
                    label=project.project_name,
                )
            )

        session.commit()

        for task_id in task_ids:
            TaskQueue(queue_name=CRAWL_DEFAULT_QUEUE_NAME).enqueue(task_id, task_type="fetch_sitemap")

        return BulkProjectSitemapLaunchResult(
            batch=task_batch,
            total_projects=len(eligible_projects),
            task_ids=task_ids,
            tasks=task_summaries,
        )
    finally:
        session.close()


def get_batch_status(batch_id: int) -> BatchStatusResult | None:
    """Load a task batch and its tasks for the bot."""

    session = SessionFactory()
    try:
        _reconcile_inactive_running_tasks(session)
        _refresh_task_batch_states(session)
        batch_repository = TaskBatchRepository(session)
        task_repository = TaskRepository(session)
        task_batch = batch_repository.get_by_id(batch_id)
        if task_batch is None:
            return None

        tasks = task_repository.list_by_batch_id(batch_id)
        return BatchStatusResult(
            batch=_to_task_batch_dto(task_batch),
            tasks=[_to_recent_task_summary(task) for task in tasks],
        )
    finally:
        session.close()


def get_task_status(task_id: int) -> TaskStatusResult | None:
    """Load a task and its preferred XLSX artifact for the bot."""

    session = SessionFactory()
    try:
        _reconcile_inactive_running_tasks(session)
        _refresh_task_batch_states(session)
        task_repository = TaskRepository(session)
        task = task_repository.get_by_id(task_id)
        if task is None:
            return None

        task_file_repository = TaskFileRepository(session)
        task_files = task_file_repository.list_by_task_id(task_id)
        storage_root = get_settings().storage_root.expanduser().resolve()

        preferred_xlsx_path: Path | None = None
        preferred_csv_path: Path | None = None
        preferred_csv_relative_path: str | None = None
        for task_file in task_files:
            if task_file.file_path.lower().endswith(".xlsx"):
                preferred_xlsx_path = storage_root / task_file.file_path
            elif task_file.file_path.lower().endswith(".csv") and preferred_csv_path is None:
                preferred_csv_path = storage_root / task_file.file_path
                preferred_csv_relative_path = task_file.file_path

        if (
            preferred_csv_path is not None
            and preferred_csv_relative_path is not None
            and task.task_type == "crawl_site"
            and (
                preferred_xlsx_path is None
                or not preferred_xlsx_path.exists()
                or preferred_csv_path.stat().st_mtime > preferred_xlsx_path.stat().st_mtime
            )
        ):
            preferred_xlsx_path = _ensure_partial_xlsx_from_csv(
                session=session,
                task=task,
                csv_absolute_path=preferred_csv_path,
                csv_relative_path=preferred_csv_relative_path,
            )

        return TaskStatusResult(task=task, xlsx_path=preferred_xlsx_path, csv_path=preferred_csv_path)
    finally:
        session.close()


def cancel_active_crawl_tasks() -> CancelCrawlTasksResult:
    """Cancel pending and running crawl_site tasks."""

    session = SessionFactory()
    try:
        task_repository = TaskRepository(session)
        pending_tasks = task_repository.list_by_task_type_and_statuses(
            task_type="crawl_site",
            statuses=(TaskStatus.PENDING,),
        )
        running_tasks = task_repository.list_by_task_type_and_statuses(
            task_type="crawl_site",
            statuses=(TaskStatus.RUNNING,),
        )

        pending_task_ids = {task.id for task in pending_tasks}
        _delete_pending_jobs(pending_task_ids)
        started_jobs_by_task_id = _get_started_jobs_by_task_id()
        now = datetime.now(UTC)
        pending_cancelled = 0
        for task in pending_tasks:
            task.status = TaskStatus.FAILED
            task.error_message = "Остановлено пользователем."
            task.finished_at = now
            task.cancel_requested = True
            task_repository.update(task)
            pending_cancelled += 1

        running_cancel_requested = 0
        for task in running_tasks:
            task.cancel_requested = True
            task_repository.update(task)
            job_id = started_jobs_by_task_id.get(task.id)
            if job_id is not None:
                send_stop_job_command(get_redis_connection(), job_id)
            running_cancel_requested += 1

        session.commit()
        return CancelCrawlTasksResult(
            pending_cancelled=pending_cancelled,
            running_cancel_requested=running_cancel_requested,
        )
    finally:
        session.close()


def cancel_task_batch(batch_id: int) -> CancelTaskBatchResult | None:
    """Cancel pending and running crawl tasks only for a single batch."""

    session = SessionFactory()
    try:
        _reconcile_inactive_running_tasks(session)
        batch_repository = TaskBatchRepository(session)
        task_repository = TaskRepository(session)
        task_batch = batch_repository.get_by_id(batch_id)
        if task_batch is None:
            return None

        tasks = task_repository.list_by_batch_id(batch_id)
        pending_tasks = [task for task in tasks if task.task_type == "crawl_site" and task.status == TaskStatus.PENDING]
        running_tasks = [task for task in tasks if task.task_type == "crawl_site" and task.status == TaskStatus.RUNNING]

        pending_task_ids = {task.id for task in pending_tasks}
        _delete_pending_jobs(pending_task_ids)
        started_jobs_by_task_id = _get_started_jobs_by_task_id()
        now = datetime.now(UTC)
        pending_cancelled = 0
        for task in pending_tasks:
            task.status = TaskStatus.FAILED
            task.error_message = "Остановлено пользователем."
            task.finished_at = now
            task.cancel_requested = True
            task_repository.update(task)
            pending_cancelled += 1

        running_cancel_requested = 0
        for task in running_tasks:
            task.cancel_requested = True
            task_repository.update(task)
            job_id = started_jobs_by_task_id.get(task.id)
            if job_id is not None:
                send_stop_job_command(get_redis_connection(), job_id)
            running_cancel_requested += 1

        session.commit()
        return CancelTaskBatchResult(
            batch_id=batch_id,
            pending_cancelled=pending_cancelled,
            running_cancel_requested=running_cancel_requested,
        )
    finally:
        session.close()


def list_recent_batches(*, limit: int = 10) -> list[RecentBatchSummary]:
    """Return recent task batches for quick selection in the bot."""

    session = SessionFactory()
    try:
        _reconcile_inactive_running_tasks(session)
        _refresh_task_batch_states(session)
        batch_repository = TaskBatchRepository(session)
        task_repository = TaskRepository(session)
        recent_batches = batch_repository.list_recent(limit=limit)
        summaries: list[RecentBatchSummary] = []
        for task_batch in recent_batches:
            tasks = task_repository.list_by_batch_id(task_batch.id)
            terminal_statuses = {TaskStatus.SUCCESS, TaskStatus.FAILED}
            finished_tasks = sum(1 for task in tasks if task.status in terminal_statuses)
            summaries.append(
                RecentBatchSummary(
                    batch_id=task_batch.id,
                    title=task_batch.title,
                    status=task_batch.status.value,
                    total_tasks=len(tasks),
                    finished_tasks=finished_tasks,
                )
            )
        return summaries
    finally:
        session.close()


def _create_task_batch(
    *,
    session,
    batch_type: TaskBatchType,
    title: str,
    payload: dict[str, object] | None,
) -> TaskBatchDTO:
    """Create a task batch through the application layer."""

    batch_repository = TaskBatchRepository(session)
    create_batch = CreateTaskBatchUseCase(batch_repository)
    return create_batch.execute(
        CreateTaskBatchCommand(
            batch_type=batch_type,
            title=title,
            payload=payload,
        )
    )


def _create_crawl_task(
    *,
    session,
    batch_id: int | None,
    project_id: int | None,
    start_url: str,
    settings: CrawlLaunchSettings,
    queue_name: str,
    project_name: str | None = None,
    seed_urls: list[str] | None = None,
    follow_links: bool = True,
) -> TaskDTO:
    """Create a crawl_site task through the application layer."""

    task_repository = TaskRepository(session)
    create_task = CreateTaskUseCase(task_repository)
    payload = {
        "start_url": start_url,
        "max_pages": settings.max_pages,
        "max_depth": settings.max_depth,
        "max_concurrency": settings.max_concurrency,
        "respect_robots_disallow": settings.respect_robots_disallow,
        "delay_between_requests_ms": settings.delay_between_requests_ms,
        "request_timeout_seconds": settings.request_timeout_seconds,
        "retry_on_5xx": settings.retry_on_5xx,
        "max_5xx_before_stop": settings.max_5xx_before_stop,
        "retry_delay_ms": settings.retry_delay_ms,
    }
    if project_name:
        payload["project_name"] = project_name
    if seed_urls:
        payload["seed_urls"] = seed_urls
    if not follow_links:
        payload["follow_links"] = False
    return create_task.execute(
        CreateTaskCommand(
            batch_id=batch_id,
            project_id=project_id,
            queue_name=queue_name,
            task_type="crawl_site",
            payload=payload,
        )
    )


def _create_fetch_sitemap_task(
    *,
    session,
    batch_id: int | None,
    project_id: int | None,
    sitemap_url: str,
    resolve_status_codes: bool,
    queue_name: str,
) -> TaskDTO:
    """Create a fetch_sitemap task through the application layer."""

    task_repository = TaskRepository(session)
    create_task = CreateTaskUseCase(task_repository)
    return create_task.execute(
        CreateTaskCommand(
            batch_id=batch_id,
            project_id=project_id,
            queue_name=queue_name,
            task_type="fetch_sitemap",
            payload={
                "url": sitemap_url,
                "resolve_status_codes": resolve_status_codes,
            },
        )
    )


def _create_fetch_robots_task(
    *,
    session,
    batch_id: int | None,
    project_id: int | None,
    robots_url: str,
    resolve_status_codes: bool,
    queue_name: str,
) -> TaskDTO:
    """Create a fetch_robots task through the application layer."""

    task_repository = TaskRepository(session)
    create_task = CreateTaskUseCase(task_repository)
    return create_task.execute(
        CreateTaskCommand(
            batch_id=batch_id,
            project_id=project_id,
            queue_name=queue_name,
            task_type="fetch_robots",
            payload={
                "url": robots_url,
                "resolve_status_codes": resolve_status_codes,
            },
        )
    )


def build_default_crawl_settings() -> CrawlLaunchSettings:
    """Return default-segment crawl settings."""

    return CrawlLaunchSettings()


def build_heavy_crawl_settings() -> CrawlLaunchSettings:
    """Return heavy-segment crawl settings."""

    return CrawlLaunchSettings(
        max_depth=DEFAULT_HEAVY_CRAWL_MAX_DEPTH,
        max_concurrency=DEFAULT_HEAVY_CRAWL_MAX_CONCURRENCY,
        max_pages=DEFAULT_HEAVY_CRAWL_MAX_PAGES,
        respect_robots_disallow=DEFAULT_HEAVY_CRAWL_RESPECT_ROBOTS_DISALLOW,
        delay_between_requests_ms=DEFAULT_HEAVY_CRAWL_DELAY_BETWEEN_REQUESTS_MS,
        request_timeout_seconds=DEFAULT_HEAVY_CRAWL_REQUEST_TIMEOUT_SECONDS,
        retry_on_5xx=DEFAULT_HEAVY_CRAWL_RETRY_ON_5XX,
        max_5xx_before_stop=DEFAULT_HEAVY_CRAWL_MAX_5XX_BEFORE_STOP,
        retry_delay_ms=DEFAULT_HEAVY_CRAWL_RETRY_DELAY_MS,
    )


def _settings_payload(settings: CrawlLaunchSettings) -> dict[str, object]:
    """Convert crawl settings to a serializable payload."""

    return {
        "max_pages": settings.max_pages,
        "max_depth": settings.max_depth,
        "max_concurrency": settings.max_concurrency,
        "respect_robots_disallow": settings.respect_robots_disallow,
        "delay_between_requests_ms": settings.delay_between_requests_ms,
        "request_timeout_seconds": settings.request_timeout_seconds,
        "retry_on_5xx": settings.retry_on_5xx,
        "max_5xx_before_stop": settings.max_5xx_before_stop,
        "retry_delay_ms": settings.retry_delay_ms,
    }


def _normalize_url_list(urls: list[str]) -> list[str]:
    """Normalize and deduplicate a user-provided URL list preserving order."""

    normalized_urls: list[str] = []
    seen: set[str] = set()
    for raw_url in urls:
        normalized = _ensure_absolute_url(raw_url)
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_urls.append(normalized)
    return normalized_urls


def _queue_name_for_segment(crawl_segment: CrawlSegment) -> str:
    """Map project segment to queue name."""

    if crawl_segment == CrawlSegment.HEAVY:
        return CRAWL_HEAVY_QUEUE_NAME
    return CRAWL_DEFAULT_QUEUE_NAME


def _normalize_webmaster_host(start_url: str) -> str:
    """Normalize a crawl start URL to the webmaster host root."""

    parsed = urlsplit(_ensure_absolute_url(start_url))
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Укажи полный URL со схемой, например https://example.com")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "/", "", ""))


def _resolve_project_sitemap_url(sitemap_path: str | None) -> str:
    """Resolve and validate a project's sitemap URL."""

    if not sitemap_path:
        raise ValueError("У проекта не задан sitemap.")
    return _ensure_absolute_url(sitemap_path)


def _ensure_absolute_url(start_url: str) -> str:
    """Ensure a user-provided URL has a scheme before parsing."""

    normalized = start_url.strip()
    if not normalized:
        raise ValueError("Укажи адрес сайта, например https://example.com")
    if "://" not in normalized:
        normalized = f"https://{normalized}"
    return normalized


def _derive_project_name(webmaster_host: str) -> str:
    """Derive a default project name from the host."""

    return urlsplit(webmaster_host).netloc.lower()


def _resolve_project_start_url(*, start_url: str | None, sitemap_path: str | None) -> str:
    """Resolve the crawl start URL for a project."""

    if start_url:
        return _normalize_webmaster_host(start_url)

    if not sitemap_path:
        raise ValueError("У проекта не задан ни start_url, ни sitemap_path.")

    parsed = urlsplit(_ensure_absolute_url(sitemap_path))
    if not parsed.netloc:
        raise ValueError("У проекта не удалось определить стартовый URL.")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "/", "", ""))


def _reconcile_inactive_running_tasks(session) -> None:
    """Update DB statuses for running tasks that no longer exist in RQ started registry."""

    repository = TaskRepository(session)
    running_tasks = repository.list_by_statuses(statuses=(TaskStatus.RUNNING,))
    if not running_tasks:
        return

    started_task_ids = set(_get_started_jobs_by_task_id())

    now = datetime.now(UTC)
    changed = False
    for task in running_tasks:
        if task.id in started_task_ids:
            continue
        task.status = TaskStatus.FAILED
        task.finished_at = now
        if task.cancel_requested:
            task.error_message = "Остановлено пользователем."
        elif not task.error_message:
            task.error_message = "Задача прервана: worker был остановлен или потерял выполнение."
        repository.update(task)
        changed = True

    if changed:
        session.commit()


def _get_started_jobs_by_task_id() -> dict[int, str]:
    """Return started jobs keyed by task id across all configured queues."""

    redis_connection = get_redis_connection()
    started_jobs_by_task_id: dict[int, str] = {}
    for queue_name in TASK_QUEUE_NAMES:
        queue = Queue(queue_name, connection=redis_connection)
        started_registry = StartedJobRegistry(queue=queue)
        for job_id in started_registry.get_job_ids():
            job = queue.fetch_job(job_id)
            if job is None:
                continue
            args = tuple(job.args or ())
            if not args:
                continue
            task_id = args[0]
            if isinstance(task_id, int):
                started_jobs_by_task_id[task_id] = job.id
    return started_jobs_by_task_id


def _delete_pending_jobs(task_ids: set[int]) -> None:
    """Delete pending jobs across all configured queues."""

    if not task_ids:
        return

    redis_connection = get_redis_connection()
    for queue_name in TASK_QUEUE_NAMES:
        queue = Queue(queue_name, connection=redis_connection)
        for job in queue.get_jobs():
            args = tuple(job.args or ())
            if not args:
                continue
            task_id = args[0]
            if isinstance(task_id, int) and task_id in task_ids:
                job.delete()


def _ensure_partial_xlsx_from_csv(
    *,
    session,
    task: TaskDTO | Task,
    csv_absolute_path: Path,
    csv_relative_path: str,
) -> Path | None:
    """Build and register a partial XLSX export from an existing crawl CSV."""

    if not csv_absolute_path.exists():
        return None

    xlsx_relative_path = str(Path(csv_relative_path).with_suffix(".xlsx"))
    rows = _parse_csv_rows(csv_absolute_path.read_text(encoding="utf-8"))
    storage = LocalFileStorage()
    xlsx_file = storage.write_bytes(
        xlsx_relative_path,
        _build_xlsx_bytes_from_rows(rows),
    )

    repository = TaskFileRepository(session)
    existing_files = repository.list_by_task_id(task.id)
    xlsx_file_name = Path(xlsx_relative_path).name
    for existing_file in existing_files:
        if existing_file.file_name != xlsx_file_name:
            continue
        existing_file.file_path = xlsx_file.relative_path
        existing_file.file_type = "xlsx"
        existing_file.file_size = xlsx_file.size
        session.add(existing_file)
        session.flush()
        session.commit()
        return xlsx_file.absolute_path

    repository.create(
        TaskFile(
            task_id=task.id,
            file_name=xlsx_file_name,
            file_path=xlsx_file.relative_path,
            file_type="xlsx",
            file_size=xlsx_file.size,
        )
    )
    session.commit()
    return xlsx_file.absolute_path


def _parse_csv_rows(csv_content: str) -> list[list[str]]:
    """Parse plain CSV content into rows for XLSX conversion."""

    buffer = io.StringIO(csv_content)
    reader = csv.reader(buffer)
    return [list(row) for row in reader]


def _build_xlsx_bytes_from_rows(rows: list[list[str]]) -> bytes:
    """Build XLSX bytes from parsed CSV rows."""

    from openpyxl import Workbook

    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet(title="crawl_pages")
    for row in rows:
        worksheet.append(list(row))

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _refresh_task_batch_states(session) -> None:
    """Synchronize task batch statuses with their child tasks."""

    batch_repository = TaskBatchRepository(session)
    task_repository = TaskRepository(session)
    task_batches = batch_repository.list()
    if not task_batches:
        return

    changed = False
    for task_batch in task_batches:
        tasks = task_repository.list_by_batch_id(task_batch.id)
        if not tasks:
            continue

        next_status = _derive_batch_status(tasks)
        next_started_at = min(
            (task.started_at for task in tasks if task.started_at is not None),
            default=task_batch.started_at,
        )
        terminal_task_statuses = {TaskStatus.SUCCESS, TaskStatus.FAILED}
        if all(task.status in terminal_task_statuses for task in tasks):
            next_finished_at = max(
                (task.finished_at for task in tasks if task.finished_at is not None),
                default=task_batch.finished_at or datetime.now(UTC),
            )
        else:
            next_finished_at = None

        next_error_message: str | None = None
        if next_status == TaskBatchStatus.CANCELLED:
            next_error_message = "Остановлено пользователем."
        elif next_status == TaskBatchStatus.FAILED:
            failed_messages = [
                task.error_message
                for task in tasks
                if task.status == TaskStatus.FAILED and task.error_message
            ]
            next_error_message = failed_messages[0] if failed_messages else None

        if (
            task_batch.status != next_status
            or task_batch.started_at != next_started_at
            or task_batch.finished_at != next_finished_at
            or task_batch.error_message != next_error_message
        ):
            task_batch.status = next_status
            task_batch.started_at = next_started_at
            task_batch.finished_at = next_finished_at
            task_batch.error_message = next_error_message
            batch_repository.update(task_batch)
            changed = True

    if changed:
        session.commit()


def _derive_batch_status(tasks: list[Task]) -> TaskBatchStatus:
    """Derive batch status from child task states."""

    statuses = [task.status for task in tasks]
    if any(status == TaskStatus.RUNNING for status in statuses):
        return TaskBatchStatus.RUNNING

    if any(status == TaskStatus.PENDING for status in statuses):
        if any(status != TaskStatus.PENDING for status in statuses):
            return TaskBatchStatus.RUNNING
        return TaskBatchStatus.PENDING

    if all(status == TaskStatus.SUCCESS for status in statuses):
        return TaskBatchStatus.SUCCESS

    if all(status == TaskStatus.FAILED for status in statuses) and all(
        task.cancel_requested or task.error_message == "Остановлено пользователем."
        for task in tasks
    ):
        return TaskBatchStatus.CANCELLED

    return TaskBatchStatus.FAILED


def _to_task_batch_dto(task_batch: TaskBatch) -> TaskBatchDTO:
    """Convert ORM task batch model to DTO."""

    return TaskBatchDTO(
        id=task_batch.id,
        batch_type=task_batch.batch_type,
        title=task_batch.title,
        status=task_batch.status,
        payload=task_batch.payload,
        result_payload=task_batch.result_payload,
        error_message=task_batch.error_message,
        created_at=task_batch.created_at,
        updated_at=task_batch.updated_at,
        started_at=task_batch.started_at,
        finished_at=task_batch.finished_at,
    )


def _to_recent_task_summary(task: Task) -> RecentTaskSummary:
    """Build a compact task summary for Telegram."""

    return RecentTaskSummary(
        task_id=task.id,
        task_type=task.task_type,
        status=task.status.value,
        label=_resolve_task_label(task),
    )


def _resolve_task_label(task: TaskDTO | Task | object) -> str:
    """Resolve a human-readable task label from project or payload."""

    project = getattr(task, "project", None)
    if project is not None and getattr(project, "project_name", None):
        return str(project.project_name)

    payload = getattr(task, "payload", None)
    if isinstance(payload, dict):
        project_name = payload.get("project_name")
        if isinstance(project_name, str) and project_name.strip():
            return project_name.strip()

        start_url = payload.get("start_url") or payload.get("url")
        if isinstance(start_url, str) and start_url.strip():
            return start_url.strip()

    return f"Task {getattr(task, 'id', '?')}"
