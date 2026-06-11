"""RQ job functions for background task execution."""

from __future__ import annotations

import asyncio
import csv
import io
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, UTC
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from sqlalchemy import update

import app.core.models  # noqa: F401
from app.core.slug import slugify
from app.core.storage import LocalFileStorage
from app.core.db import SessionFactory, engine
from app.modules.tasks.domain import JsonPayload
from app.modules.tasks.domain.enums import TaskStatus
from app.modules.tasks.infrastructure import Task, TaskFile, TaskFileRepository, TaskRepository

HTTP_TIMEOUT_SECONDS = 15
SITEMAP_ENTRY_LIMIT = 100
SITEMAP_STATUS_CHECK_TIMEOUT_SECONDS = 10
SITEMAP_STATUS_CHECK_MAX_CONCURRENCY = 10
MAX_REDIRECTS = 10
CRAWL_PROGRESS_CHECKPOINT_EVERY_PAGES = 50
NON_HTML_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".svg",
    ".bmp",
    ".ico",
    ".tif",
    ".tiff",
    ".avif",
}


@dataclass(slots=True, frozen=True)
class _TaskExecutionResult:
    """Internal representation of task execution output."""

    result_payload: JsonPayload
    export_urls: list[str] | None = None
    export_sitemap_rows: list[tuple[str, int | None]] | None = None
    export_csv_content: str | None = None


class _TaskCancellationRequestedError(RuntimeError):
    """Raised when a task was cancelled by a user request."""


class _TaskCancellationWithResultError(_TaskCancellationRequestedError):
    """Raised when a cancelled task still has a partial execution result to persist."""

    def __init__(self, message: str, *, execution_result: _TaskExecutionResult) -> None:
        """Store partial execution result for persistence on cancellation."""

        super().__init__(message)
        self.execution_result = execution_result


@dataclass(slots=True, frozen=True)
class _CrawlQueueItem:
    """One URL scheduled for crawling."""

    url: str
    source_url: str | None
    depth: int


@dataclass(slots=True, frozen=True)
class _CrawlRow:
    """One output row produced by the crawler."""

    status_code: int | None
    url: str
    final_url: str
    source_url: str | None
    meta_title: str | None
    meta_description: str | None
    canonical_url: str | None
    meta_robots: str | None
    depth: int
    content_type: str | None
    fetch_error: str | None = None


@dataclass(slots=True, frozen=True)
class _ExtractedPageData:
    """Parsed SEO fields and links from an HTML page."""

    meta_title: str | None
    meta_description: str | None
    canonical_url: str | None
    meta_robots: str | None
    links: list[str]


@dataclass(slots=True, frozen=True)
class _CrawlPageResult:
    """Result of crawling a single page."""

    row: _CrawlRow
    discovered_urls: list[_CrawlQueueItem]
    query_links_seen: int = 0
    robots_filtered_links: int = 0
    is_5xx: bool = False


@dataclass(slots=True, frozen=True)
class _CrawlRunResult:
    """Aggregate result of a crawl task."""

    rows: list[_CrawlRow]
    pages_crawled: int
    pages_discovered: int
    query_links_seen: int
    robots_filtered_links: int
    total_5xx_responses: int
    status_summary: dict[str, int]
    diagnostics: list[str]


class _PageMetadataParser(HTMLParser):
    """Extract minimal page metadata from HTML."""

    def __init__(self) -> None:
        """Initialize parser state."""

        super().__init__()
        self.title: str | None = None
        self.h1: str | None = None
        self._current_tag: str | None = None
        self._title_parts: list[str] = []
        self._h1_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track title and first h1 tags."""

        if tag == "title" and self.title is None:
            self._current_tag = "title"
        elif tag == "h1" and self.h1 is None:
            self._current_tag = "h1"

    def handle_endtag(self, tag: str) -> None:
        """Finalize title and h1 values."""

        if tag == "title" and self._current_tag == "title":
            self.title = _clean_text("".join(self._title_parts))
            self._current_tag = None
        elif tag == "h1" and self._current_tag == "h1":
            self.h1 = _clean_text("".join(self._h1_parts))
            self._current_tag = None

    def handle_data(self, data: str) -> None:
        """Collect text for tracked tags."""

        if self._current_tag == "title":
            self._title_parts.append(data)
        elif self._current_tag == "h1":
            self._h1_parts.append(data)


class _CrawlerHTMLParser(HTMLParser):
    """Extract SEO fields and links from HTML."""

    def __init__(self) -> None:
        """Initialize parser state."""

        super().__init__()
        self.meta_title: str | None = None
        self.meta_description: str | None = None
        self.canonical_href: str | None = None
        self.meta_robots: str | None = None
        self.links: list[str] = []
        self._current_tag: str | None = None
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track SEO-related HTML elements."""

        attrs_map = {key.lower(): value for key, value in attrs}
        if tag == "title" and self.meta_title is None:
            self._current_tag = "title"
            return

        if tag == "meta":
            name = (attrs_map.get("name") or "").lower()
            content = attrs_map.get("content")
            if name == "description" and self.meta_description is None and content:
                self.meta_description = _clean_text(content)
            elif name == "robots" and self.meta_robots is None and content:
                self.meta_robots = _clean_text(content)
            return

        if tag == "link":
            rel = (attrs_map.get("rel") or "").lower()
            href = attrs_map.get("href")
            if "canonical" in rel.split() and self.canonical_href is None and href:
                self.canonical_href = href
            return

        if tag == "a":
            href = attrs_map.get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        """Finalize title extraction."""

        if tag == "title" and self._current_tag == "title":
            self.meta_title = _clean_text("".join(self._title_parts))
            self._current_tag = None

    def handle_data(self, data: str) -> None:
        """Collect text inside <title>."""

        if self._current_tag == "title":
            self._title_parts.append(data)


class _FetchedResponse:
    """Simple container for fetched HTTP response data."""

    def __init__(
        self,
        *,
        url: str,
        final_url: str,
        status_code: int,
        content_type: str | None,
        body: bytes,
        redirect_status_code: int | None = None,
    ) -> None:
        """Store normalized HTTP response fields."""

        self.url = url
        self.final_url = final_url
        self.status_code = status_code
        self.content_type = content_type
        self.body = body
        self.redirect_status_code = redirect_status_code


@dataclass(slots=True, frozen=True)
class _RobotsPolicy:
    """Minimal robots.txt allow/disallow policy for crawler filtering."""

    allow: tuple[str, ...]
    disallow: tuple[str, ...]


class _NoRedirectHandler(HTTPRedirectHandler):
    """Disable urllib automatic redirect following."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        """Return None so redirects can be handled manually."""

        return None


def execute_task(task_id: int) -> None:
    """Execute a queued task and update its status."""

    engine.dispose(close=False)
    session = SessionFactory()
    task_exists = False

    try:
        repository = TaskRepository(session)
        task = repository.get_by_id(task_id)

        if task is None:
            return

        task_exists = True
        session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(
                status=TaskStatus.RUNNING,
                started_at=datetime.now(UTC),
            )
        )
        session.commit()

        if task.cancel_requested:
            raise _TaskCancellationRequestedError("Остановлено пользователем.")

        execution_result = _execute_by_type(task.id, task.task_type, task.payload)
        if task.task_type == "fetch_sitemap":
            execution_result = _persist_fetch_sitemap_artifacts(
                session=session,
                task=task,
                execution_result=execution_result,
            )
        if task.task_type == "crawl_site":
            execution_result = _persist_crawl_site_artifacts(
                session=session,
                task=task,
                execution_result=execution_result,
            )

        session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(
                status=TaskStatus.SUCCESS,
                finished_at=datetime.now(UTC),
                result_payload=execution_result.result_payload,
                error_message=None,
            )
        )
        session.commit()

    except Exception as error:
        session.rollback()

        if task_exists:
            partial_result_payload = None
            if isinstance(error, _TaskCancellationWithResultError):
                execution_result = error.execution_result
                if task is not None and task.task_type == "fetch_sitemap":
                    execution_result = _persist_fetch_sitemap_artifacts(
                        session=session,
                        task=task,
                        execution_result=execution_result,
                    )
                if task is not None and task.task_type == "crawl_site":
                    execution_result = _persist_crawl_site_artifacts(
                        session=session,
                        task=task,
                        execution_result=execution_result,
                    )
                partial_result_payload = execution_result.result_payload

            session.execute(
                update(Task)
                .where(Task.id == task_id)
                .values(
                    status=TaskStatus.FAILED,
                    error_message=str(error),
                    finished_at=datetime.now(UTC),
                    result_payload=partial_result_payload,
                )
            )
            session.commit()

    finally:
        session.close()


def _execute_by_type(task_id: int, task_type: str, payload: JsonPayload | None) -> _TaskExecutionResult:
    """Dispatch task execution by task type."""

    if task_type == "demo":
        return _execute_demo_task(task_type)
    if task_type == "fetch_page":
        return _execute_fetch_page_task(payload)
    if task_type == "fetch_sitemap":
        return _execute_fetch_sitemap_task(payload)
    if task_type == "fetch_robots":
        return _execute_fetch_robots_task(payload)
    if task_type == "crawl_site":
        return _execute_crawl_site_task(task_id, payload)
    raise ValueError(f"Unsupported task_type: {task_type}")


def _execute_demo_task(task_type: str) -> _TaskExecutionResult:
    """Execute the demo task."""

    time.sleep(2)
    return _TaskExecutionResult(
        result_payload={
            "message": "Demo task completed.",
            "task_type": task_type,
        }
    )


def _execute_fetch_page_task(payload: JsonPayload | None) -> _TaskExecutionResult:
    """Fetch a single page and extract minimal SEO metadata."""

    if not isinstance(payload, dict):
        raise ValueError("fetch_page payload must be an object.")

    url = payload.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("fetch_page payload must contain non-empty string field 'url'.")

    fetched = _fetch_url(url.strip(), error_prefix="fetch_page")

    title = None
    h1 = None
    if _is_html_response(fetched.content_type):
        encoding = _extract_charset(fetched.content_type) or "utf-8"
        html = fetched.body.decode(encoding, errors="replace")
        parser = _PageMetadataParser()
        parser.feed(html)
        title = parser.title
        h1 = parser.h1

    result_payload: JsonPayload = {
        "url": fetched.url,
        "final_url": fetched.final_url,
        "status_code": fetched.status_code,
        "content_type": fetched.content_type,
        "title": title,
        "h1": h1,
    }
    if fetched.status_code != 200:
        result_payload = _with_diagnostic(
            result_payload,
            f"Страница вернула HTTP-статус {fetched.status_code}.",
        )

    return _TaskExecutionResult(result_payload=result_payload)


def _execute_fetch_sitemap_task(payload: JsonPayload | None) -> _TaskExecutionResult:
    """Fetch a sitemap-like XML document and extract URL entries."""

    if not isinstance(payload, dict):
        raise ValueError("fetch_sitemap payload must be an object.")

    url = payload.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("fetch_sitemap payload must contain non-empty string field 'url'.")

    fetched = _fetch_url(url.strip(), error_prefix="fetch_sitemap")

    if not _is_xml_response(fetched.content_type):
        result_payload: JsonPayload = {
            "url": fetched.url,
            "final_url": fetched.final_url,
            "status_code": fetched.status_code,
            "content_type": fetched.content_type,
            "sitemap_type": None,
            "url_count": 0,
            "urls": [],
        }
        result_payload = _with_diagnostic(
            result_payload,
            "Ответ не похож на XML sitemap.",
        )
        if fetched.status_code != 200:
            result_payload = _with_diagnostic(
                result_payload,
                f"Экспорт CSV пропущен, потому что sitemap вернул HTTP-статус {fetched.status_code}.",
            )
        return _TaskExecutionResult(result_payload=result_payload)

    aggregation = _collect_sitemap_urls(url.strip(), visited=set())
    export_urls = aggregation["urls"] if aggregation["status_code"] == 200 else None
    export_sitemap_rows = None
    if export_urls is not None:
        export_sitemap_rows = asyncio.run(
            _resolve_sitemap_status_rows(
                export_urls,
                timeout_seconds=SITEMAP_STATUS_CHECK_TIMEOUT_SECONDS,
                max_concurrency=SITEMAP_STATUS_CHECK_MAX_CONCURRENCY,
            )
        )
    result_payload: JsonPayload = {
        "url": fetched.url,
        "final_url": aggregation["final_url"],
        "status_code": aggregation["status_code"],
        "content_type": aggregation["content_type"],
        "sitemap_type": aggregation["sitemap_type"],
        "url_count": len(aggregation["urls"]),
        "urls": aggregation["urls"][:SITEMAP_ENTRY_LIMIT],
        "resolved_status_count": 0 if export_sitemap_rows is None else len(export_sitemap_rows),
    }
    if aggregation["status_code"] != 200:
        result_payload = _with_diagnostic(
            result_payload,
            f"Экспорт CSV пропущен, потому что sitemap вернул HTTP-статус {aggregation['status_code']}.",
        )

    return _TaskExecutionResult(
        result_payload=result_payload,
        export_urls=export_urls,
        export_sitemap_rows=export_sitemap_rows,
    )


def _execute_fetch_robots_task(payload: JsonPayload | None) -> _TaskExecutionResult:
    """Fetch and parse a robots.txt document."""

    if not isinstance(payload, dict):
        raise ValueError("fetch_robots payload must be an object.")

    url = payload.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("fetch_robots payload must contain non-empty string field 'url'.")

    normalized_url = _normalize_robots_url(url.strip())
    fetched = _fetch_url(normalized_url, error_prefix="fetch_robots")

    encoding = _extract_charset(fetched.content_type) or "utf-8"
    body_text = fetched.body.decode(encoding, errors="replace")
    parsed_robots = _parse_robots_txt(body_text)

    result_payload: JsonPayload = {
        "url": url.strip(),
        "requested_url": normalized_url,
        "final_url": fetched.final_url,
        "status_code": fetched.status_code,
        "content_type": fetched.content_type,
        "user_agents": parsed_robots["user_agents"],
        "sitemaps": parsed_robots["sitemaps"],
        "rules": parsed_robots["rules"],
    }

    if fetched.status_code == 404:
        result_payload = _with_diagnostic(
            result_payload,
            "Файл robots.txt не найден: сервер вернул HTTP-статус 404.",
        )
    elif fetched.status_code != 200:
        result_payload = _with_diagnostic(
            result_payload,
            f"Файл robots.txt вернул HTTP-статус {fetched.status_code}.",
        )

    if not parsed_robots["rules"] and not parsed_robots["sitemaps"]:
        result_payload = _with_diagnostic(
            result_payload,
            "В robots.txt не найдено ни одного правила или sitemap-директивы.",
        )

    return _TaskExecutionResult(result_payload=result_payload)


def _execute_crawl_site_task(task_id: int, payload: JsonPayload | None) -> _TaskExecutionResult:
    """Crawl one site and export collected page data to CSV."""

    if not isinstance(payload, dict):
        raise ValueError("crawl_site payload must be an object.")

    start_url = payload.get("start_url")
    if not isinstance(start_url, str) or not start_url.strip():
        raise ValueError("crawl_site payload must contain non-empty string field 'start_url'.")

    max_pages = _get_positive_int(payload, "max_pages")
    max_depth = _get_non_negative_int(payload, "max_depth")
    max_concurrency = _get_positive_int(payload, "max_concurrency")
    respect_robots_disallow = _get_bool(payload, "respect_robots_disallow", default=True)
    delay_between_requests_ms = _get_non_negative_int_with_default(payload, "delay_between_requests_ms", default=0)
    request_timeout_seconds = _get_positive_int_with_default(payload, "request_timeout_seconds", default=15)
    retry_on_5xx = _get_bool(payload, "retry_on_5xx", default=False)
    max_5xx_before_stop = _get_positive_int_with_default(payload, "max_5xx_before_stop", default=20)
    retry_delay_ms = _get_non_negative_int_with_default(payload, "retry_delay_ms", default=1000)

    normalized_start_url = _normalize_crawl_url(start_url.strip())
    try:
        crawl_result = asyncio.run(
            _run_crawler(
                task_id=task_id,
                start_url=normalized_start_url,
                max_pages=max_pages,
                max_depth=max_depth,
                max_concurrency=max_concurrency,
                respect_robots_disallow=respect_robots_disallow,
                delay_between_requests_ms=delay_between_requests_ms,
                request_timeout_seconds=request_timeout_seconds,
                retry_on_5xx=retry_on_5xx,
                max_5xx_before_stop=max_5xx_before_stop,
                retry_delay_ms=retry_delay_ms,
            )
        )
    except _TaskCancellationWithResultError as error:
        raise error
    except _TaskCancellationRequestedError as error:
        partial_result = _build_crawl_task_execution_result(
            normalized_start_url=normalized_start_url,
            max_depth=max_depth,
            max_pages=max_pages,
            max_concurrency=max_concurrency,
            respect_robots_disallow=respect_robots_disallow,
            delay_between_requests_ms=delay_between_requests_ms,
            request_timeout_seconds=request_timeout_seconds,
            retry_on_5xx=retry_on_5xx,
            max_5xx_before_stop=max_5xx_before_stop,
            retry_delay_ms=retry_delay_ms,
            crawl_result=_CrawlRunResult(
                rows=[],
                pages_crawled=0,
                pages_discovered=1,
                query_links_seen=0,
                robots_filtered_links=0,
                total_5xx_responses=0,
                status_summary={},
                diagnostics=["Обход остановлен пользователем до сохранения промежуточных результатов."],
            ),
        )
        raise _TaskCancellationWithResultError(str(error), execution_result=partial_result) from error

    return _build_crawl_task_execution_result(
        normalized_start_url=normalized_start_url,
        max_depth=max_depth,
        max_pages=max_pages,
        max_concurrency=max_concurrency,
        respect_robots_disallow=respect_robots_disallow,
        delay_between_requests_ms=delay_between_requests_ms,
        request_timeout_seconds=request_timeout_seconds,
        retry_on_5xx=retry_on_5xx,
        max_5xx_before_stop=max_5xx_before_stop,
        retry_delay_ms=retry_delay_ms,
        crawl_result=crawl_result,
    )


def _fetch_url(url: str, *, error_prefix: str, timeout_seconds: int = HTTP_TIMEOUT_SECONDS) -> _FetchedResponse:
    """Perform a GET request and return normalized response fields."""

    opener = build_opener(_NoRedirectHandler())
    current_url = url
    redirect_status_code: int | None = None

    for _ in range(MAX_REDIRECTS + 1):
        request = Request(
            current_url,
            headers={"User-Agent": "MegaToolsBot/0.1"},
            method="GET",
        )

        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                return _FetchedResponse(
                    url=url,
                    final_url=current_url,
                    status_code=response.status,
                    content_type=response.headers.get("Content-Type"),
                    body=response.read(),
                    redirect_status_code=redirect_status_code,
                )
        except HTTPError as error:
            location = error.headers.get("Location") if error.headers else None
            if error.code in {301, 302, 303, 307, 308} and location:
                if redirect_status_code is None:
                    redirect_status_code = error.code
                current_url = urljoin(current_url, location)
                continue

            return _FetchedResponse(
                url=url,
                final_url=error.geturl(),
                status_code=error.code,
                content_type=error.headers.get("Content-Type") if error.headers else None,
                body=error.read(),
                redirect_status_code=redirect_status_code,
            )
        except URLError as error:
            raise ValueError(f"{error_prefix} request failed: {error.reason}") from error

    raise ValueError(f"{error_prefix} request failed: too many redirects.")


def _build_crawl_task_execution_result(
    *,
    normalized_start_url: str,
    max_depth: int,
    max_pages: int,
    max_concurrency: int,
    respect_robots_disallow: bool,
    delay_between_requests_ms: int,
    request_timeout_seconds: int,
    retry_on_5xx: bool,
    max_5xx_before_stop: int,
    retry_delay_ms: int,
    crawl_result: _CrawlRunResult,
) -> _TaskExecutionResult:
    """Build a task execution result object from aggregated crawl output."""

    result_payload: JsonPayload = {
        "start_url": normalized_start_url,
        "pages_crawled": crawl_result.pages_crawled,
        "pages_discovered": crawl_result.pages_discovered,
        "query_links_seen": crawl_result.query_links_seen,
        "robots_filtered_links": crawl_result.robots_filtered_links,
        "max_depth": max_depth,
        "max_pages": max_pages,
        "max_concurrency": max_concurrency,
        "respect_robots_disallow": respect_robots_disallow,
        "delay_between_requests_ms": delay_between_requests_ms,
        "request_timeout_seconds": request_timeout_seconds,
        "retry_on_5xx": retry_on_5xx,
        "max_5xx_before_stop": max_5xx_before_stop,
        "retry_delay_ms": retry_delay_ms,
        "total_5xx_responses": crawl_result.total_5xx_responses,
        "status_summary": crawl_result.status_summary,
    }
    if crawl_result.diagnostics:
        result_payload = _with_diagnostic(result_payload, " ".join(crawl_result.diagnostics))
    if crawl_result.query_links_seen == 0:
        result_payload = _with_diagnostic(
            result_payload,
            "В HTML не обнаружено внутренних ссылок с query-параметрами в тегах <a href>.",
        )

    csv_content = _build_crawl_rows_csv(crawl_result.rows)
    return _TaskExecutionResult(
        result_payload=result_payload,
        export_csv_content=csv_content,
    )


def _build_crawl_progress_payload(
    *,
    normalized_start_url: str,
    max_depth: int,
    max_pages: int,
    max_concurrency: int,
    respect_robots_disallow: bool,
    delay_between_requests_ms: int,
    request_timeout_seconds: int,
    retry_on_5xx: bool,
    max_5xx_before_stop: int,
    retry_delay_ms: int,
    crawl_result: _CrawlRunResult,
    last_processed_url: str | None,
) -> JsonPayload:
    """Build lightweight in-progress crawl payload for checkpoints."""

    progress_payload: JsonPayload = {
        "start_url": normalized_start_url,
        "pages_crawled": crawl_result.pages_crawled,
        "pages_discovered": crawl_result.pages_discovered,
        "query_links_seen": crawl_result.query_links_seen,
        "robots_filtered_links": crawl_result.robots_filtered_links,
        "max_depth": max_depth,
        "max_pages": max_pages,
        "max_concurrency": max_concurrency,
        "respect_robots_disallow": respect_robots_disallow,
        "delay_between_requests_ms": delay_between_requests_ms,
        "request_timeout_seconds": request_timeout_seconds,
        "retry_on_5xx": retry_on_5xx,
        "max_5xx_before_stop": max_5xx_before_stop,
        "retry_delay_ms": retry_delay_ms,
        "total_5xx_responses": crawl_result.total_5xx_responses,
        "status_summary": crawl_result.status_summary,
        "progress": {
            "last_checkpoint_at": datetime.now(UTC).isoformat(),
            "last_processed_url": last_processed_url,
        },
    }
    if crawl_result.diagnostics:
        progress_payload = _with_diagnostic(progress_payload, " ".join(crawl_result.diagnostics))
    return progress_payload


def _checkpoint_crawl_progress(
    *,
    task_id: int,
    normalized_start_url: str,
    max_depth: int,
    max_pages: int,
    max_concurrency: int,
    respect_robots_disallow: bool,
    delay_between_requests_ms: int,
    request_timeout_seconds: int,
    retry_on_5xx: bool,
    max_5xx_before_stop: int,
    retry_delay_ms: int,
    crawl_result: _CrawlRunResult,
    last_processed_url: str | None,
) -> None:
    """Persist the latest crawl progress into the task result payload."""

    session = SessionFactory()
    try:
        task_repository = TaskRepository(session)
        task = task_repository.get_by_id(task_id)
        if task is None:
            return

        progress_payload = _build_crawl_progress_payload(
            normalized_start_url=normalized_start_url,
            max_depth=max_depth,
            max_pages=max_pages,
            max_concurrency=max_concurrency,
            respect_robots_disallow=respect_robots_disallow,
            delay_between_requests_ms=delay_between_requests_ms,
            request_timeout_seconds=request_timeout_seconds,
            retry_on_5xx=retry_on_5xx,
            max_5xx_before_stop=max_5xx_before_stop,
            retry_delay_ms=retry_delay_ms,
            crawl_result=crawl_result,
            last_processed_url=last_processed_url,
        )
        csv_content = _build_crawl_rows_csv(crawl_result.rows)
        csv_file = _persist_partial_crawl_csv(task=task, csv_content=csv_content)
        session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(
                result_payload={
                    **progress_payload,
                    "export_files": {"csv": csv_file.relative_path},
                }
            )
        )
        _upsert_task_file(
            session=session,
            task_id=task.id,
            file_name=f"{_resolve_task_slug(task)}.csv",
            file_path=csv_file.relative_path,
            file_type="text/csv",
            file_size=csv_file.size,
        )
        session.commit()
    finally:
        session.close()


async def _run_crawler(
    *,
    task_id: int,
    start_url: str,
    max_pages: int,
    max_depth: int,
    max_concurrency: int,
    respect_robots_disallow: bool,
    delay_between_requests_ms: int,
    request_timeout_seconds: int,
    retry_on_5xx: bool,
    max_5xx_before_stop: int,
    retry_delay_ms: int,
) -> _CrawlRunResult:
    """Run the async crawl pipeline and collect page rows."""

    queue: asyncio.Queue[_CrawlQueueItem | None] = asyncio.Queue()
    visited: set[str] = {start_url}
    rows: list[_CrawlRow] = []
    diagnostics: list[str] = []
    lock = asyncio.Lock()

    pages_crawled = 0
    pages_discovered = 1
    query_links_seen = 0
    robots_filtered_links = 0
    total_5xx_responses = 0
    status_summary_counter: Counter[str] = Counter()
    limit_reached = False
    stop_due_to_5xx = False
    start_netloc = urlsplit(start_url).netloc.lower()
    if respect_robots_disallow:
        robots_policy, robots_diagnostics = await asyncio.to_thread(
            _load_robots_policy,
            start_url,
            request_timeout_seconds,
        )
        diagnostics.extend(robots_diagnostics)
    else:
        robots_policy = _RobotsPolicy(allow=(), disallow=())
        diagnostics.append("Фильтрация по robots.txt отключена настройками запуска.")

    await queue.put(_CrawlQueueItem(url=start_url, source_url=None, depth=0))

    def build_partial_crawl_result(*, extra_diagnostic: str | None = None) -> _CrawlRunResult:
        """Build a partial crawl result from current in-memory progress."""

        partial_diagnostics = list(diagnostics)
        if limit_reached:
            partial_diagnostics.append(
                f"Обход ограничен лимитом max_pages={max_pages}: часть найденных URL не была обработана."
            )
        if stop_due_to_5xx:
            partial_diagnostics.append(
                f"Обход остановлен из-за количества ответов 5xx: достигнут порог max_5xx_before_stop={max_5xx_before_stop}."
            )
        if extra_diagnostic:
            partial_diagnostics.append(extra_diagnostic)

        partial_rows = sorted(rows, key=lambda row: (row.depth, row.url))
        return _CrawlRunResult(
            rows=partial_rows,
            pages_crawled=pages_crawled,
            pages_discovered=pages_discovered,
            query_links_seen=query_links_seen,
            robots_filtered_links=robots_filtered_links,
            total_5xx_responses=total_5xx_responses,
            status_summary=dict(status_summary_counter),
            diagnostics=partial_diagnostics,
        )

    def build_checkpoint_crawl_result() -> _CrawlRunResult:
        """Build a lightweight crawl result for checkpoint persistence."""

        partial_diagnostics = list(diagnostics)
        if limit_reached:
            partial_diagnostics.append(
                f"Обход ограничен лимитом max_pages={max_pages}: часть найденных URL не была обработана."
            )
        if stop_due_to_5xx:
            partial_diagnostics.append(
                f"Обход остановлен из-за количества ответов 5xx: достигнут порог max_5xx_before_stop={max_5xx_before_stop}."
            )

        partial_rows = sorted(rows, key=lambda row: (row.depth, row.url))
        return _CrawlRunResult(
            rows=partial_rows,
            pages_crawled=pages_crawled,
            pages_discovered=pages_discovered,
            query_links_seen=query_links_seen,
            robots_filtered_links=robots_filtered_links,
            total_5xx_responses=total_5xx_responses,
            status_summary=dict(status_summary_counter),
            diagnostics=partial_diagnostics,
        )

    async def worker() -> None:
        nonlocal pages_crawled, pages_discovered, query_links_seen, robots_filtered_links
        nonlocal total_5xx_responses, limit_reached, stop_due_to_5xx

        while True:
            if await asyncio.to_thread(_is_task_cancellation_requested, task_id):
                raise _TaskCancellationRequestedError("Остановлено пользователем.")

            item = await queue.get()
            if item is None:
                queue.task_done()
                break

            try:
                async with lock:
                    if stop_due_to_5xx:
                        continue

                async with lock:
                    if pages_crawled >= max_pages:
                        limit_reached = True
                        continue

                if delay_between_requests_ms > 0:
                    await asyncio.sleep(delay_between_requests_ms / 1000)

                page_result = await _crawl_page(
                    item,
                    start_netloc=start_netloc,
                    robots_policy=robots_policy,
                    request_timeout_seconds=request_timeout_seconds,
                    retry_on_5xx=retry_on_5xx,
                    retry_delay_ms=retry_delay_ms,
                )

                if await asyncio.to_thread(_is_task_cancellation_requested, task_id):
                    raise _TaskCancellationRequestedError("Остановлено пользователем.")

                urls_to_enqueue: list[_CrawlQueueItem] = []
                async with lock:
                    rows.append(page_result.row)
                    pages_crawled += 1
                    status_key = str(page_result.row.status_code) if page_result.row.status_code is not None else "error"
                    status_summary_counter[status_key] += 1
                    query_links_seen += page_result.query_links_seen
                    robots_filtered_links += page_result.robots_filtered_links
                    if page_result.is_5xx:
                        total_5xx_responses += 1
                        if total_5xx_responses >= max_5xx_before_stop:
                            stop_due_to_5xx = True

                    if not stop_due_to_5xx:
                        for discovered_item in page_result.discovered_urls:
                            if discovered_item.depth > max_depth:
                                continue
                            if discovered_item.url in visited:
                                continue
                            if pages_discovered >= max_pages:
                                limit_reached = True
                                break

                            visited.add(discovered_item.url)
                            pages_discovered += 1
                            urls_to_enqueue.append(discovered_item)

                    should_checkpoint = pages_crawled % CRAWL_PROGRESS_CHECKPOINT_EVERY_PAGES == 0
                    checkpoint_result = build_checkpoint_crawl_result() if should_checkpoint else None

                for discovered_item in urls_to_enqueue:
                    await queue.put(discovered_item)

                if checkpoint_result is not None:
                    await asyncio.to_thread(
                        _checkpoint_crawl_progress,
                        task_id=task_id,
                        normalized_start_url=start_url,
                        max_depth=max_depth,
                        max_pages=max_pages,
                        max_concurrency=max_concurrency,
                        respect_robots_disallow=respect_robots_disallow,
                        delay_between_requests_ms=delay_between_requests_ms,
                        request_timeout_seconds=request_timeout_seconds,
                        retry_on_5xx=retry_on_5xx,
                        max_5xx_before_stop=max_5xx_before_stop,
                        retry_delay_ms=retry_delay_ms,
                        crawl_result=checkpoint_result,
                        last_processed_url=page_result.row.final_url,
                    )
            finally:
                queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(max_concurrency)]
    try:
        await queue.join()

        for _ in workers:
            await queue.put(None)
        await asyncio.gather(*workers)
    except _TaskCancellationRequestedError as error:
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        raise _TaskCancellationWithResultError(
            str(error),
            execution_result=_build_crawl_task_execution_result(
                normalized_start_url=start_url,
                max_depth=max_depth,
                max_pages=max_pages,
                max_concurrency=max_concurrency,
                respect_robots_disallow=respect_robots_disallow,
                delay_between_requests_ms=delay_between_requests_ms,
                request_timeout_seconds=request_timeout_seconds,
                retry_on_5xx=retry_on_5xx,
                max_5xx_before_stop=max_5xx_before_stop,
                retry_delay_ms=retry_delay_ms,
                crawl_result=build_partial_crawl_result(
                    extra_diagnostic="Обход остановлен пользователем, сохранён промежуточный результат."
                ),
            ),
        ) from error

    return build_partial_crawl_result()


async def _crawl_page(
    item: _CrawlQueueItem,
    *,
    start_netloc: str,
    robots_policy: _RobotsPolicy,
    request_timeout_seconds: int,
    retry_on_5xx: bool,
    retry_delay_ms: int,
) -> _CrawlPageResult:
    """Fetch one page, extract SEO fields, and discover next URLs."""

    try:
        fetched = await _fetch_crawl_page_response(
            item.url,
            request_timeout_seconds=request_timeout_seconds,
            retry_on_5xx=retry_on_5xx,
            retry_delay_ms=retry_delay_ms,
        )
    except ValueError as error:
        return _CrawlPageResult(
            row=_CrawlRow(
                status_code=None,
                url=item.url,
                final_url=item.url,
                source_url=item.source_url,
                meta_title=None,
                meta_description=None,
                canonical_url=None,
                meta_robots=None,
                depth=item.depth,
                content_type=None,
                fetch_error=str(error),
            ),
            discovered_urls=[],
            is_5xx=False,
        )

    extracted = _extract_page_data(
        page_url=fetched.final_url,
        content_type=fetched.content_type,
        body=fetched.body,
    )

    discovered_urls: list[_CrawlQueueItem] = []
    query_links_seen = 0
    robots_filtered_links = 0
    if fetched.status_code == 200 and item.depth >= 0:
        next_depth = item.depth + 1
        for href in extracted.links:
            normalized_url, filter_reason = _normalize_internal_url(
                href=href,
                base_url=fetched.final_url,
                start_netloc=start_netloc,
                robots_policy=robots_policy,
            )
            if _looks_like_internal_query_url(href=href, base_url=fetched.final_url, start_netloc=start_netloc):
                query_links_seen += 1
            if filter_reason == "robots_disallow":
                robots_filtered_links += 1
            if normalized_url is None:
                continue
            discovered_urls.append(
                _CrawlQueueItem(
                    url=normalized_url,
                    source_url=fetched.final_url,
                    depth=next_depth,
                )
            )

    row = _CrawlRow(
        status_code=fetched.redirect_status_code or fetched.status_code,
        url=item.url,
        final_url=fetched.final_url,
        source_url=item.source_url,
        meta_title=extracted.meta_title,
        meta_description=extracted.meta_description,
        canonical_url=extracted.canonical_url,
        meta_robots=extracted.meta_robots,
        depth=item.depth,
        content_type=fetched.content_type,
        fetch_error=None,
    )
    return _CrawlPageResult(
        row=row,
        discovered_urls=discovered_urls,
        query_links_seen=query_links_seen,
        robots_filtered_links=robots_filtered_links,
        is_5xx=500 <= fetched.status_code <= 599,
    )


async def _fetch_crawl_page_response(
    url: str,
    *,
    request_timeout_seconds: int,
    retry_on_5xx: bool,
    retry_delay_ms: int,
) -> _FetchedResponse:
    """Fetch a crawl page with optional single retry for 5xx responses."""

    attempts = 2 if retry_on_5xx else 1
    fetched: _FetchedResponse | None = None
    for attempt in range(attempts):
        fetched = await asyncio.to_thread(
            _fetch_url,
            url,
            error_prefix="crawl_site",
            timeout_seconds=request_timeout_seconds,
        )
        if not retry_on_5xx or not 500 <= fetched.status_code <= 599 or attempt == attempts - 1:
            return fetched
        if retry_delay_ms > 0:
            await asyncio.sleep(retry_delay_ms / 1000)

    if fetched is None:
        raise ValueError("crawl_site request failed without response.")
    return fetched


def _extract_page_data(*, page_url: str, content_type: str | None, body: bytes) -> _ExtractedPageData:
    """Extract SEO fields and links from an HTML page."""

    if not _is_html_response(content_type):
        return _ExtractedPageData(
            meta_title=None,
            meta_description=None,
            canonical_url=None,
            meta_robots=None,
            links=[],
        )

    encoding = _extract_charset(content_type) or "utf-8"
    html = body.decode(encoding, errors="replace")
    parser = _CrawlerHTMLParser()
    parser.feed(html)

    canonical_url = None
    if parser.canonical_href:
        canonical_url = _normalize_absolute_url(urljoin(page_url, parser.canonical_href))

    return _ExtractedPageData(
        meta_title=parser.meta_title,
        meta_description=parser.meta_description,
        canonical_url=canonical_url,
        meta_robots=parser.meta_robots,
        links=parser.links,
    )


def _collect_sitemap_urls(url: str, *, visited: set[str]) -> JsonPayload:
    """Collect URLs from a sitemap or sitemap index."""

    if url in visited:
        return {
            "final_url": url,
            "status_code": None,
            "content_type": None,
            "sitemap_type": "cycle",
            "urls": [],
        }

    visited.add(url)
    fetched = _fetch_url(url, error_prefix="fetch_sitemap")
    if not _is_xml_response(fetched.content_type):
        raise ValueError("fetch_sitemap response does not look like XML sitemap.")

    try:
        root = ElementTree.fromstring(fetched.body)
    except ElementTree.ParseError as error:
        raise ValueError(f"fetch_sitemap XML parsing failed: {error}") from error

    sitemap_type = _detect_sitemap_type(root)
    if sitemap_type is None:
        raise ValueError("fetch_sitemap XML document is not a sitemap or sitemap index.")

    if sitemap_type == "urlset":
        urls = _extract_sitemap_locations(root)
        return {
            "final_url": fetched.final_url,
            "status_code": fetched.status_code,
            "content_type": fetched.content_type,
            "sitemap_type": sitemap_type,
            "urls": urls,
        }

    nested_sitemaps = _extract_sitemap_locations(root)
    aggregated_urls: list[str] = []
    for nested_url in nested_sitemaps:
        nested_result = _collect_sitemap_urls(nested_url, visited=visited)
        aggregated_urls.extend(nested_result["urls"])

    return {
        "final_url": fetched.final_url,
        "status_code": fetched.status_code,
        "content_type": fetched.content_type,
        "sitemap_type": sitemap_type,
        "urls": aggregated_urls,
    }


def _is_html_response(content_type: str | None) -> bool:
    """Return whether a response content type looks like HTML."""

    return content_type is not None and "text/html" in content_type.lower()


def _is_xml_response(content_type: str | None) -> bool:
    """Return whether a response content type looks like XML."""

    if content_type is None:
        return False
    normalized = content_type.lower()
    return "xml" in normalized or "text/plain" in normalized


def _detect_sitemap_type(root: ElementTree.Element) -> str | None:
    """Detect whether an XML root is urlset or sitemapindex."""

    local_name = _strip_namespace(root.tag)
    if local_name == "urlset":
        return "urlset"
    if local_name == "sitemapindex":
        return "sitemapindex"
    return None


def _extract_sitemap_locations(root: ElementTree.Element) -> list[str]:
    """Extract all sitemap location entries from an XML tree."""

    entries: list[str] = []
    for element in root.iter():
        if _strip_namespace(element.tag) != "loc" or element.text is None:
            continue
        location = element.text.strip()
        if location:
            entries.append(location)
    return entries


def _extract_charset(content_type: str | None) -> str | None:
    """Extract charset from a content type header."""

    if content_type is None:
        return None

    for part in content_type.split(";"):
        key, separator, value = part.strip().partition("=")
        if separator and key.lower() == "charset":
            return value.strip()
    return None


def _clean_text(value: str) -> str | None:
    """Normalize extracted HTML text."""

    cleaned = " ".join(value.split())
    return cleaned or None


def _strip_namespace(tag: str) -> str:
    """Return an XML tag name without its namespace."""

    if "}" in tag:
        return tag.rsplit("}", maxsplit=1)[-1]
    return tag


def _persist_fetch_sitemap_artifacts(
    *,
    session,
    task: Task,
    execution_result: _TaskExecutionResult,
) -> _TaskExecutionResult:
    """Persist sitemap CSV export and TaskFile metadata."""

    if execution_result.export_sitemap_rows is None:
        return execution_result

    project_slug = _resolve_task_slug(task)
    csv_relative_path = f"sitemap_parsing/{project_slug}.csv"
    xlsx_relative_path = f"sitemap_parsing/{project_slug}.xlsx"
    storage = LocalFileStorage()
    csv_content = _build_sitemap_rows_csv(execution_result.export_sitemap_rows)
    csv_file = storage.write_text(csv_relative_path, csv_content, encoding="utf-8")
    xlsx_file = storage.write_bytes(
        xlsx_relative_path,
        _build_xlsx_bytes_from_rows(
            rows=[
                ["url", "Ответ сервера"],
                *[
                    [url, "" if status_code is None else status_code]
                    for url, status_code in execution_result.export_sitemap_rows
                ],
            ],
            sheet_name="sitemap_urls",
        ),
    )

    _upsert_task_file(
        session=session,
        task_id=task.id,
        file_name=f"{project_slug}.csv",
        file_path=csv_file.relative_path,
        file_type="text/csv",
        file_size=csv_file.size,
    )
    _upsert_task_file(
        session=session,
        task_id=task.id,
        file_name=f"{project_slug}.xlsx",
        file_path=xlsx_file.relative_path,
        file_type="xlsx",
        file_size=xlsx_file.size,
    )

    result_payload = dict(execution_result.result_payload)
    result_payload["export_file"] = xlsx_file.relative_path
    result_payload["export_files"] = {
        "csv": csv_file.relative_path,
        "xlsx": xlsx_file.relative_path,
    }
    return _TaskExecutionResult(
        result_payload=result_payload,
        export_urls=execution_result.export_urls,
        export_sitemap_rows=execution_result.export_sitemap_rows,
    )


def _persist_crawl_site_artifacts(
    *,
    session,
    task: Task,
    execution_result: _TaskExecutionResult,
) -> _TaskExecutionResult:
    """Persist crawl CSV export and TaskFile metadata."""

    if execution_result.export_csv_content is None:
        return execution_result

    project_slug = _resolve_task_slug(task)
    csv_relative_path = f"crawl/{project_slug}.csv"
    xlsx_relative_path = f"crawl/{project_slug}.xlsx"
    storage = LocalFileStorage()
    csv_file = storage.write_text(csv_relative_path, execution_result.export_csv_content, encoding="utf-8")
    xlsx_file = storage.write_bytes(
        xlsx_relative_path,
        _build_crawl_rows_xlsx(_parse_crawl_rows_from_csv(execution_result.export_csv_content)),
    )

    task_file_repository = TaskFileRepository(session)
    task_file_repository.create(
        TaskFile(
            task_id=task.id,
            file_name=f"{project_slug}.csv",
            file_path=csv_file.relative_path,
            file_type="text/csv",
            file_size=csv_file.size,
        )
    )
    task_file_repository.create(
        TaskFile(
            task_id=task.id,
            file_name=f"{project_slug}.xlsx",
            file_path=xlsx_file.relative_path,
            file_type="xlsx",
            file_size=xlsx_file.size,
        )
    )

    result_payload = dict(execution_result.result_payload)
    result_payload["export_file"] = xlsx_file.relative_path
    result_payload["export_files"] = {
        "csv": csv_file.relative_path,
        "xlsx": xlsx_file.relative_path,
    }
    return _TaskExecutionResult(
        result_payload=result_payload,
        export_csv_content=execution_result.export_csv_content,
    )


def _persist_partial_crawl_csv(*, task: Task, csv_content: str):
    """Persist one overwriteable partial CSV snapshot for a crawl task."""

    project_slug = _resolve_task_slug(task)
    csv_relative_path = f"crawl/{project_slug}.csv"
    storage = LocalFileStorage()
    return storage.write_text(csv_relative_path, csv_content, encoding="utf-8")


def _upsert_task_file(
    *,
    session,
    task_id: int,
    file_name: str,
    file_path: str,
    file_type: str | None,
    file_size: int | None,
) -> None:
    """Create or update a task file record without accumulating duplicates."""

    task_file_repository = TaskFileRepository(session)
    existing_files = task_file_repository.list_by_task_id(task_id)
    for existing_file in existing_files:
        if existing_file.file_name != file_name:
            continue
        existing_file.file_path = file_path
        existing_file.file_type = file_type
        existing_file.file_size = file_size
        session.add(existing_file)
        session.flush()
        return

    task_file_repository.create(
        TaskFile(
            task_id=task_id,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
        )
    )


def _build_urls_csv(urls: list[str]) -> str:
    """Build UTF-8 CSV content for a list of URLs."""

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["url"])
    for url in urls:
        writer.writerow([url])
    return buffer.getvalue()


def _build_sitemap_rows_csv(rows: list[tuple[str, int | None]]) -> str:
    """Build UTF-8 CSV content for sitemap URLs with server response codes."""

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["url", "Ответ сервера"])
    for url, status_code in rows:
        writer.writerow([url, "" if status_code is None else status_code])
    return buffer.getvalue()


async def _resolve_sitemap_status_rows(
    urls: list[str],
    *,
    timeout_seconds: int,
    max_concurrency: int,
) -> list[tuple[str, int | None]]:
    """Resolve lightweight server response codes for sitemap URLs."""

    semaphore = asyncio.Semaphore(max_concurrency)

    async def resolve_one(url: str) -> tuple[str, int | None]:
        async with semaphore:
            status_code = await asyncio.to_thread(
                _fetch_status_code_only,
                url,
                timeout_seconds,
            )
            return (url, status_code)

    return await asyncio.gather(*(resolve_one(url) for url in urls))


def _fetch_status_code_only(url: str, timeout_seconds: int) -> int | None:
    """Fetch only the response code for a URL without downloading full page content."""

    status_code = _fetch_status_code_via_method(url, timeout_seconds=timeout_seconds, method="HEAD")
    if status_code == 405:
        status_code = _fetch_status_code_via_method(url, timeout_seconds=timeout_seconds, method="GET")
    return status_code


def _fetch_status_code_via_method(
    url: str,
    *,
    timeout_seconds: int,
    method: str,
) -> int | None:
    """Resolve one HTTP status code using a lightweight request method."""

    current_url = url
    opener = build_opener(_NoRedirectHandler())

    for _ in range(MAX_REDIRECTS + 1):
        request = Request(
            current_url,
            headers={
                "User-Agent": "MegaToolsBot/0.1",
                "Accept": "*/*",
            },
            method=method,
        )
        try:
            response = opener.open(request, timeout=timeout_seconds)
            try:
                return response.status
            finally:
                response.close()
        except HTTPError as error:
            if 300 <= error.code < 400:
                location = error.headers.get("Location")
                if not location:
                    return error.code
                current_url = urljoin(current_url, location)
                continue
            return error.code
        except URLError:
            return None

    return None


def _resolve_task_slug(task: Task) -> str:
    """Resolve a stable export slug for project-bound and ad-hoc tasks."""

    if task.project is not None:
        return slugify(task.project.project_name)

    payload = task.payload if isinstance(task.payload, dict) else {}
    project_name = payload.get("project_name")
    if isinstance(project_name, str) and project_name.strip():
        return slugify(project_name)

    start_url = payload.get("start_url") or payload.get("url")
    if isinstance(start_url, str) and start_url.strip():
        netloc = urlsplit(start_url.strip()).netloc
        if netloc:
            return slugify(netloc)

    return f"task-{task.id}"


def _is_task_cancellation_requested(task_id: int) -> bool:
    """Return whether cancellation was requested for a task."""

    session = SessionFactory()
    try:
        task = TaskRepository(session).get_by_id(task_id)
        return False if task is None else task.cancel_requested
    finally:
        session.close()


def _build_crawl_rows_csv(rows: list[_CrawlRow]) -> str:
    """Build UTF-8 CSV content for crawl results."""

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Ответ сервера",
            "URL страницы",
            "Title страницы",
            "Meta Description",
            "Источник",
            "Конечный URL",
            "Rel canonical",
            "Meta robots",
            "Тип контента",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.status_code,
                row.url,
                row.meta_title,
                row.meta_description,
                row.source_url,
                row.final_url,
                row.canonical_url,
                row.meta_robots,
                row.content_type,
            ]
        )
    return buffer.getvalue()


def _parse_crawl_rows_from_csv(csv_content: str) -> list[list[str]]:
    """Parse crawl CSV content into rows for XLSX export."""

    buffer = io.StringIO(csv_content)
    reader = csv.reader(buffer)
    return [list(row) for row in reader]


def _build_crawl_rows_xlsx(rows: list[list[str]]) -> bytes:
    """Build XLSX bytes for crawl rows."""

    return _build_xlsx_bytes_from_rows(rows=rows, sheet_name="crawl_pages")


def _build_xlsx_bytes_from_rows(*, rows: list[list[str] | list[object]], sheet_name: str) -> bytes:
    """Build an XLSX file in memory from plain row data."""

    from openpyxl import Workbook

    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet(title=sheet_name)
    for row in rows:
        worksheet.append(list(row))

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _normalize_robots_url(url: str) -> str:
    """Normalize input URL to the canonical robots.txt location."""

    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("fetch_robots payload must contain absolute URL with scheme and host.")

    path = parsed.path or "/"
    if path.endswith("/robots.txt"):
        normalized_path = "/robots.txt"
    else:
        normalized_path = "/robots.txt"

    return _sanitize_absolute_url(
        urlunsplit((parsed.scheme, parsed.netloc, normalized_path, "", ""))
    )


def _normalize_crawl_url(url: str) -> str:
    """Normalize a crawl start URL."""

    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("crawl_site payload must contain absolute start_url with scheme and host.")
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("crawl_site supports only http and https URLs.")

    path = parsed.path or "/"
    return _sanitize_absolute_url(
        urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))
    )


def _normalize_internal_url(
    *,
    href: str,
    base_url: str,
    start_netloc: str,
    robots_policy: _RobotsPolicy,
) -> tuple[str | None, str | None]:
    """Normalize one discovered URL and keep only allowed internal html-like links."""

    normalized_href = href.strip()
    if not normalized_href:
        return None, "empty"

    lowered_href = normalized_href.lower()
    if lowered_href.startswith(("javascript:", "mailto:", "tel:", "data:")):
        return None, "unsupported_scheme"

    absolute_url = urljoin(base_url, normalized_href)
    parsed = urlsplit(absolute_url)
    if parsed.scheme.lower() not in {"http", "https"}:
        return None, "unsupported_scheme"
    if parsed.netloc.lower() != start_netloc:
        return None, "external"
    if _has_non_html_extension(parsed.path):
        return None, "non_html_extension"

    normalized_url = _normalize_absolute_url(absolute_url)
    if not _is_allowed_by_robots(normalized_url, robots_policy):
        return None, "robots_disallow"

    return normalized_url, None


def _looks_like_internal_query_url(*, href: str, base_url: str, start_netloc: str) -> bool:
    """Return whether a discovered href points to an internal URL with query parameters."""

    normalized_href = href.strip()
    if not normalized_href:
        return False

    absolute_url = urljoin(base_url, normalized_href)
    parsed = urlsplit(absolute_url)
    if parsed.scheme.lower() not in {"http", "https"}:
        return False
    if parsed.netloc.lower() != start_netloc:
        return False
    return bool(parsed.query)


def _normalize_absolute_url(url: str) -> str:
    """Normalize an absolute URL while preserving query string and dropping fragment."""

    parsed = urlsplit(url)
    path = parsed.path or "/"
    return _sanitize_absolute_url(
        urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))
    )


def _sanitize_absolute_url(url: str) -> str:
    """Percent-encode unsafe URL characters in path and query."""

    parsed = urlsplit(url)
    sanitized_path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
    sanitized_query = quote(parsed.query, safe="=&%:@!$'()*+,;/-._~")
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            sanitized_path,
            sanitized_query,
            "",
        )
    )


def _has_non_html_extension(path: str) -> bool:
    """Return whether a URL path points to an image-like asset."""

    lowered_path = path.lower()
    return any(lowered_path.endswith(extension) for extension in NON_HTML_EXTENSIONS)


def _parse_robots_txt(content: str) -> JsonPayload:
    """Parse a robots.txt document into a minimal structured representation."""

    sitemaps: list[str] = []
    rules_by_user_agent: dict[str, dict[str, list[str] | str]] = {}
    user_agent_order: list[str] = []
    current_user_agents: list[str] = []
    last_directive_name: str | None = None

    for raw_line in content.splitlines():
        line = raw_line.split("#", maxsplit=1)[0].strip()
        if not line:
            continue

        directive, separator, value = line.partition(":")
        if not separator:
            continue

        directive_name = directive.strip().lower()
        directive_value = value.strip()
        if not directive_value:
            continue

        if directive_name == "user-agent":
            user_agent = directive_value
            if last_directive_name == "user-agent":
                current_user_agents.append(user_agent)
            else:
                current_user_agents = [user_agent]
            if user_agent not in rules_by_user_agent:
                rules_by_user_agent[user_agent] = {
                    "user_agent": user_agent,
                    "allow": [],
                    "disallow": [],
                    "clean_param": [],
                }
                user_agent_order.append(user_agent)
            last_directive_name = directive_name
            continue

        if directive_name == "sitemap":
            sitemaps.append(directive_value)
            last_directive_name = directive_name
            continue

        if not current_user_agents:
            last_directive_name = directive_name
            continue

        if directive_name not in {"allow", "disallow", "clean-param"}:
            last_directive_name = directive_name
            continue

        for user_agent in current_user_agents:
            rule = rules_by_user_agent[user_agent]
            if directive_name == "allow":
                rule["allow"].append(directive_value)
            elif directive_name == "disallow":
                rule["disallow"].append(directive_value)
            else:
                rule["clean_param"].append(directive_value)
        last_directive_name = directive_name

    rules: list[JsonPayload] = []
    for user_agent in user_agent_order:
        rule = dict(rules_by_user_agent[user_agent])
        rules.append(rule)

    return {
        "user_agents": user_agent_order,
        "sitemaps": sitemaps,
        "rules": rules,
    }


def _load_robots_policy(start_url: str, timeout_seconds: int) -> tuple[_RobotsPolicy, list[str]]:
    """Load robots.txt and build a minimal allow/disallow policy."""

    diagnostics: list[str] = []
    robots_url = _normalize_robots_url(start_url)
    fetched = _fetch_url(robots_url, error_prefix="crawl_site robots", timeout_seconds=timeout_seconds)

    if fetched.status_code != 200:
        diagnostics.append(
            f"robots.txt недоступен для фильтрации обхода: HTTP-статус {fetched.status_code}."
        )
        return _RobotsPolicy(allow=(), disallow=()), diagnostics

    encoding = _extract_charset(fetched.content_type) or "utf-8"
    body_text = fetched.body.decode(encoding, errors="replace")
    parsed_robots = _parse_robots_txt(body_text)
    for rule in parsed_robots["rules"]:
        if rule.get("user_agent") != "*":
            continue

        allow = tuple(
            value
            for value in rule.get("allow", [])
            if isinstance(value, str) and value.strip()
        )
        disallow = tuple(
            value
            for value in rule.get("disallow", [])
            if isinstance(value, str) and value.strip()
        )
        return _RobotsPolicy(allow=allow, disallow=disallow), diagnostics

    diagnostics.append("В robots.txt не найдено правил для User-agent: *.")
    return _RobotsPolicy(allow=(), disallow=()), diagnostics


def _is_allowed_by_robots(url: str, policy: _RobotsPolicy) -> bool:
    """Return whether a URL is allowed by robots.txt allow/disallow rules."""

    if not policy.allow and not policy.disallow:
        return True

    parsed = urlsplit(url)
    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"

    best_allow = max(
        (_robots_rule_length(rule) for rule in policy.allow if _robots_rule_matches(rule, target)),
        default=-1,
    )
    best_disallow = max(
        (_robots_rule_length(rule) for rule in policy.disallow if _robots_rule_matches(rule, target)),
        default=-1,
    )

    if best_disallow == -1:
        return True
    if best_allow >= best_disallow:
        return True
    return False


def _robots_rule_matches(rule: str, target: str) -> bool:
    """Match a robots.txt rule against a URL path/query."""

    normalized_rule = rule.strip()
    if not normalized_rule:
        return False

    anchored = normalized_rule.endswith("$")
    if anchored:
        normalized_rule = normalized_rule[:-1]

    pattern = re.escape(normalized_rule).replace(r"\*", ".*")
    if anchored:
        pattern = f"^{pattern}$"
    else:
        pattern = f"^{pattern}"
    return re.match(pattern, target) is not None


def _robots_rule_length(rule: str) -> int:
    """Return a comparable robots.txt rule length."""

    return len(rule.rstrip("$"))


def _get_positive_int(payload: JsonPayload, key: str) -> int:
    """Return a positive integer payload value."""

    value = payload.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"crawl_site payload must contain positive integer field '{key}'.")
    return value


def _get_non_negative_int(payload: JsonPayload, key: str) -> int:
    """Return a non-negative integer payload value."""

    value = payload.get(key)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"crawl_site payload must contain non-negative integer field '{key}'.")
    return value


def _get_positive_int_with_default(payload: JsonPayload, key: str, *, default: int) -> int:
    """Return a positive integer payload value with fallback default."""

    value = payload.get(key, default)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"crawl_site payload must contain positive integer field '{key}'.")
    return value


def _get_non_negative_int_with_default(payload: JsonPayload, key: str, *, default: int) -> int:
    """Return a non-negative integer payload value with fallback default."""

    value = payload.get(key, default)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"crawl_site payload must contain non-negative integer field '{key}'.")
    return value


def _get_bool(payload: JsonPayload, key: str, *, default: bool) -> bool:
    """Return a boolean payload value with a default fallback."""

    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"crawl_site payload field '{key}' must be boolean.")
    return value


def _build_status_summary(rows: list[_CrawlRow]) -> dict[str, int]:
    """Build a compact status summary for crawl results."""

    counter: Counter[str] = Counter()
    for row in rows:
        if row.status_code is None:
            counter["fetch_error"] += 1
        else:
            counter[str(row.status_code)] += 1
    return dict(counter)


def _with_diagnostic(result_payload: JsonPayload, message: str) -> JsonPayload:
    """Append a human-readable diagnostic message to a task result payload."""

    diagnostic = result_payload.get("diagnostic")
    updated_payload = dict(result_payload)
    if not isinstance(diagnostic, str) or not diagnostic.strip():
        updated_payload["diagnostic"] = message
        return updated_payload

    updated_payload["diagnostic"] = f"{diagnostic} {message}"
    return updated_payload
