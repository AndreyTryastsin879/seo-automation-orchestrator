"""Queue integration for task execution."""

from __future__ import annotations

from redis import Redis
from rq import Queue

from app.core.logging import get_logger, log_event
from app.core.redis import get_redis_connection

DEFAULT_TASK_QUEUE_NAME = "tasks"
CRAWL_DEFAULT_QUEUE_NAME = "crawl_default"
CRAWL_HEAVY_QUEUE_NAME = "crawl_heavy"
TASK_QUEUE_NAMES = (
    DEFAULT_TASK_QUEUE_NAME,
    CRAWL_DEFAULT_QUEUE_NAME,
    CRAWL_HEAVY_QUEUE_NAME,
)
TASK_EXECUTION_JOB = "app.interfaces.worker.execute_task"
DEFAULT_JOB_TIMEOUT_SECONDS = 300
SITEMAP_JOB_TIMEOUT_SECONDS = 1800
HEAVY_CRAWL_JOB_TIMEOUT_SECONDS = 86400
JOB_TIMEOUT_BY_TASK_TYPE: dict[str, int] = {
    "crawl_site": 3600,
    "fetch_sitemap": SITEMAP_JOB_TIMEOUT_SECONDS,
    "fetch_robots": SITEMAP_JOB_TIMEOUT_SECONDS,
}
LOGGER = get_logger("app.tasks.queue")


class TaskQueue:
    """Thin wrapper around the Redis-backed task queue."""

    def __init__(self, connection: Redis | None = None, *, queue_name: str | None = None) -> None:
        """Create a task queue using an existing or default Redis connection."""

        self._queue = Queue(
            queue_name or DEFAULT_TASK_QUEUE_NAME,
            connection=connection or get_redis_connection(),
        )

    def enqueue(self, task_id: int, *, task_type: str | None = None) -> None:
        """Enqueue a task for later execution by a worker."""

        job_timeout = JOB_TIMEOUT_BY_TASK_TYPE.get(task_type or "", DEFAULT_JOB_TIMEOUT_SECONDS)
        if self._queue.name == CRAWL_HEAVY_QUEUE_NAME and task_type == "crawl_site":
            job_timeout = HEAVY_CRAWL_JOB_TIMEOUT_SECONDS
        self._queue.enqueue(TASK_EXECUTION_JOB, task_id, job_timeout=job_timeout)
        log_event(
            LOGGER,
            "task_enqueued",
            task_id=task_id,
            task_type=task_type,
            queue_name=self._queue.name,
            job_timeout_seconds=job_timeout,
        )
