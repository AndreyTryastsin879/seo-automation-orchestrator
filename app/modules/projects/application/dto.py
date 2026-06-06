"""Application DTOs for the projects module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.modules.projects.domain import CrawlSegment


@dataclass(slots=True, frozen=True)
class CreateProjectCommand:
    """Input data for creating a project."""

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


@dataclass(slots=True, frozen=True)
class UpdateProjectCommand:
    """Input data for updating a project."""

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


@dataclass(slots=True, frozen=True)
class ProjectDTO:
    """Application representation of a project."""

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
