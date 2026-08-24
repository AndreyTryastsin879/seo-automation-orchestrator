"""Regression checks for ad-hoc crawl worker routing."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.interfaces.bot.services import (
    build_heavy_crawl_settings,
    launch_ad_hoc_crawl,
    launch_ad_hoc_url_list_crawl,
)
from app.modules.projects.domain import CrawlSegment
from app.modules.tasks.infrastructure.queue import CRAWL_HEAVY_QUEUE_NAME


class _SessionSpy:
    """Minimal database session substitute for launch-service tests."""

    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass


class _TaskQueueSpy:
    """Capture queue construction without connecting to Redis."""

    queue_names: list[str | None] = []

    def __init__(self, *, queue_name: str | None = None) -> None:
        self.queue_names.append(queue_name)

    def enqueue(self, task_id: int, *, task_type: str | None = None) -> None:
        pass


class AdHocCrawlQueueTests(unittest.TestCase):
    """Ensure Heavy ad-hoc modes use the heavy RQ worker."""

    def setUp(self) -> None:
        _TaskQueueSpy.queue_names = []

    def test_heavy_profile_routes_both_adhoc_crawl_modes_to_heavy_queue(self) -> None:
        for launch, args in (
            (launch_ad_hoc_crawl, ("https://example.com",)),
            (launch_ad_hoc_url_list_crawl, (["https://example.com/a", "https://example.com/b"],)),
        ):
            with self.subTest(launch=launch.__name__):
                _TaskQueueSpy.queue_names = []
                with (
                    patch("app.interfaces.bot.services.SessionFactory", return_value=_SessionSpy()),
                    patch(
                        "app.interfaces.bot.services._create_task_batch",
                        return_value=SimpleNamespace(id=101),
                    ),
                    patch(
                        "app.interfaces.bot.services._create_crawl_task",
                        return_value=SimpleNamespace(id=202, queue_name=CRAWL_HEAVY_QUEUE_NAME),
                    ) as create_task,
                    patch("app.interfaces.bot.services.TaskQueue", _TaskQueueSpy),
                ):
                    launch(
                        *args,
                        settings=build_heavy_crawl_settings(),
                        crawl_segment=CrawlSegment.HEAVY,
                    )

                self.assertEqual(create_task.call_args.kwargs["queue_name"], CRAWL_HEAVY_QUEUE_NAME)
                self.assertEqual(_TaskQueueSpy.queue_names, [CRAWL_HEAVY_QUEUE_NAME])
