"""Task-related enumerations."""

from enum import StrEnum


class TaskBatchType(StrEnum):
    """Task batch category values."""

    CRAWL_ALL_PROJECTS = "crawl_all_projects"
    CRAWL_PROJECT = "crawl_project"
    CRAWL_ADHOC = "crawl_adhoc"
    SITEMAP_ALL_PROJECTS = "sitemap_all_projects"
    SITEMAP_PROJECT = "sitemap_project"
    SITEMAP_ADHOC = "sitemap_adhoc"


class TaskBatchStatus(StrEnum):
    """Task batch execution status values."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    """Task execution status values."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
