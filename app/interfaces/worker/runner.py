"""RQ worker runner."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from redis import Redis
from rq import Queue, Worker
from rq.registry import StartedJobRegistry

from app.core.config import get_settings
from app.core.db import SessionFactory
from app.modules.tasks.domain import TaskStatus
from app.modules.tasks.infrastructure import TaskRepository
from app.modules.tasks.infrastructure.queue import DEFAULT_TASK_QUEUE_NAME, TASK_QUEUE_NAMES


def run_worker() -> None:
    """Run the RQ worker for the task queue."""

    settings = get_settings()
    redis_conn = Redis.from_url(settings.redis_url)
    queue_name = os.environ.get("RQ_QUEUE", DEFAULT_TASK_QUEUE_NAME)
    queue = Queue(queue_name, connection=redis_conn)
    _reconcile_abandoned_running_tasks(queue)
    worker = Worker([queue], connection=redis_conn)
    worker.work()


def _reconcile_abandoned_running_tasks(queue: Queue) -> None:
    """Mark DB tasks as finished when RQ no longer has them as started jobs."""

    started_task_ids: set[int] = set()
    for queue_name in TASK_QUEUE_NAMES:
        current_queue = Queue(queue_name, connection=queue.connection)
        started_registry = StartedJobRegistry(queue=current_queue)
        for job_id in started_registry.get_job_ids():
            job = current_queue.fetch_job(job_id)
            if job is None:
                continue
            args = tuple(job.args or ())
            if not args:
                continue
            task_id = args[0]
            if isinstance(task_id, int):
                started_task_ids.add(task_id)

    session = SessionFactory()
    try:
        repository = TaskRepository(session)
        running_tasks = repository.list_by_statuses(statuses=(TaskStatus.RUNNING,))
        if not running_tasks:
            return

        now = datetime.now(UTC)
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

        session.commit()
    finally:
        session.close()
