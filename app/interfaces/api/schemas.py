"""Pydantic schemas for the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.modules.projects.domain import CrawlSegment
from app.modules.projects.application import ProjectDTO
from app.modules.tasks.application import TaskDTO, TaskFileDTO
from app.modules.tasks.domain import JsonPayload, TaskStatus


class ProjectCreateRequest(BaseModel):
    """Request body for creating a project."""

    project_name: str
    sitemap_path: str | None = None
    start_url: str | None = None
    crawl_segment: CrawlSegment = CrawlSegment.DEFAULT
    is_multi_sitemap: bool = False
    pagination_view: str | None = None
    yandex_webmaster_host: str | None = None
    pagination_sample: str | None = None
    pagination_marker: str | None = None
    card_sample: str | None = None
    category_sample: str | None = None
    contain_subdomains: bool = False


class ProjectUpdateRequest(BaseModel):
    """Request body for updating a project."""

    project_name: str
    sitemap_path: str | None = None
    start_url: str | None = None
    crawl_segment: CrawlSegment = CrawlSegment.DEFAULT
    is_multi_sitemap: bool = False
    pagination_view: str | None = None
    yandex_webmaster_host: str | None = None
    pagination_sample: str | None = None
    pagination_marker: str | None = None
    card_sample: str | None = None
    category_sample: str | None = None
    contain_subdomains: bool = False


class ProjectResponse(BaseModel):
    """Response schema for a project."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_name: str
    sitemap_path: str | None
    start_url: str | None
    crawl_segment: CrawlSegment
    is_multi_sitemap: bool
    pagination_view: str | None
    yandex_webmaster_host: str | None
    pagination_sample: str | None
    pagination_marker: str | None
    card_sample: str | None
    category_sample: str | None
    contain_subdomains: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, project: ProjectDTO) -> "ProjectResponse":
        """Build a response model from an application DTO."""

        return cls.model_validate(project)


class TaskCreateRequest(BaseModel):
    """Request body for creating a task."""

    batch_id: int | None = None
    project_id: int
    task_type: str
    queue_name: str | None = None
    payload: JsonPayload | None = None


class CrawlAdHocRequest(BaseModel):
    """Request body for starting an ad-hoc crawl without a pre-created project."""

    start_url: str
    project_name: str | None = None
    max_pages: int = 8000
    max_depth: int = 3
    max_concurrency: int = 5
    respect_robots_disallow: bool = True
    delay_between_requests_ms: int = 0
    request_timeout_seconds: int = 15
    retry_on_5xx: bool = False
    max_5xx_before_stop: int = 20
    retry_delay_ms: int = 1000

    def to_payload(
        self,
        *,
        start_url: str | None = None,
        project_name: str | None = None,
    ) -> dict[str, Any]:
        """Convert request fields to crawl_site task payload."""

        return {
            "start_url": start_url or self.start_url,
            "project_name": project_name or self.project_name,
            "max_pages": self.max_pages,
            "max_depth": self.max_depth,
            "max_concurrency": self.max_concurrency,
            "respect_robots_disallow": self.respect_robots_disallow,
            "delay_between_requests_ms": self.delay_between_requests_ms,
            "request_timeout_seconds": self.request_timeout_seconds,
            "retry_on_5xx": self.retry_on_5xx,
            "max_5xx_before_stop": self.max_5xx_before_stop,
            "retry_delay_ms": self.retry_delay_ms,
        }


class TaskResponse(BaseModel):
    """Response schema for a task."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int | None
    project_id: int | None
    queue_name: str | None
    task_type: str
    status: TaskStatus
    payload: JsonPayload | None
    result_payload: JsonPayload | None
    cancel_requested: bool
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_dto(cls, task: TaskDTO) -> "TaskResponse":
        """Build a response model from an application DTO."""

        return cls.model_validate(task)


class TaskFileResponse(BaseModel):
    """Response schema for a task file."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    file_name: str
    file_path: str
    file_type: str | None
    file_size: int | None
    created_at: datetime

    @classmethod
    def from_dto(cls, task_file: TaskFileDTO) -> "TaskFileResponse":
        """Build a response model from an application DTO."""

        return cls.model_validate(task_file)
