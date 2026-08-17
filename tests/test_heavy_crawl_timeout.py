"""Regression checks for long-running heavy crawl jobs."""

import unittest

from app.modules.tasks.infrastructure.queue import (
    CRAWL_HEAVY_QUEUE_NAME,
    HEAVY_CRAWL_JOB_TIMEOUT_SECONDS,
    TASK_EXECUTION_JOB,
    TaskQueue,
)


class _QueueSpy:
    """Minimal RQ queue substitute that records enqueue options."""

    name = CRAWL_HEAVY_QUEUE_NAME

    def __init__(self) -> None:
        self.job_name: str | None = None
        self.args: tuple[object, ...] = ()
        self.job_timeout: int | None = None

    def enqueue(self, job_name: str, *args: object, job_timeout: int) -> None:
        self.job_name = job_name
        self.args = args
        self.job_timeout = job_timeout


class HeavyCrawlTimeoutTests(unittest.TestCase):
    """Ensure new heavy crawl jobs have a multi-day safety limit."""

    def test_heavy_crawl_uses_seven_day_timeout(self) -> None:
        queue_spy = _QueueSpy()
        task_queue = object.__new__(TaskQueue)
        task_queue._queue = queue_spy

        task_queue.enqueue(17, task_type="crawl_site")

        self.assertEqual(queue_spy.job_name, TASK_EXECUTION_JOB)
        self.assertEqual(queue_spy.args, (17,))
        self.assertEqual(HEAVY_CRAWL_JOB_TIMEOUT_SECONDS, 7 * 24 * 60 * 60)
        self.assertEqual(queue_spy.job_timeout, HEAVY_CRAWL_JOB_TIMEOUT_SECONDS)
