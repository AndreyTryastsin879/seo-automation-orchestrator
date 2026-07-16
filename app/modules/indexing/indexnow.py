"""File-backed IndexNow queues and encrypted per-project credentials."""

from __future__ import annotations

import csv
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.core.storage import LocalFileStorage

QUEUE_HEADERS = ("queue_id", "URL")
URL_HEADER_CANDIDATES = {"url", "urls", "url страницы"}


@dataclass(frozen=True, slots=True)
class IndexNowQueueEntry:
    """One pending IndexNow URL with a stable identity."""

    queue_id: str
    url: str


def get_indexnow_queue_path(project_slug: str) -> Path:
    """Return the project queue path, creating its parent directory."""

    storage = LocalFileStorage()
    path = storage.root / "indexing" / "indexnow" / "submit" / f"{project_slug}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_indexnow_queue_count(project_slug: str) -> int:
    """Return the number of URL entries waiting for IndexNow submission."""

    return len(_read_queue(get_indexnow_queue_path(project_slug)))


def get_sitemap_export_path(project_slug: str) -> Path:
    """Return the latest sitemap CSV export path for a saved project."""

    return LocalFileStorage().root / "sitemap_parsing" / f"{project_slug}.csv"


def read_sitemap_export_urls(project_slug: str) -> list[str] | None:
    """Read URL values from a project's existing sitemap parsing CSV."""

    source_path = get_sitemap_export_path(project_slug)
    if not source_path.exists():
        return None
    with source_path.open("r", encoding="utf-8-sig", newline="") as source_file:
        reader = csv.DictReader(source_file)
        if reader.fieldnames is None:
            return []
        url_column = next(
            (field for field in reader.fieldnames if field and field.strip().lower() in URL_HEADER_CANDIDATES),
            None,
        )
        if url_column is None:
            raise ValueError(f"В файле {source_path.name} не найдена колонка URL.")
        return [value.strip() for row in reader if (value := (row.get(url_column) or "").strip())]


def prepend_indexnow_urls(project_slug: str, urls: list[str]) -> int:
    """Put URLs before existing entries without removing duplicates."""

    return _add_urls(project_slug, urls, prepend=True)


def append_indexnow_urls(project_slug: str, urls: list[str]) -> int:
    """Put URLs after existing entries without removing duplicates."""

    return _add_urls(project_slug, urls, prepend=False)


def replace_indexnow_urls(project_slug: str, urls: list[str]) -> int:
    """Replace a queue with the complete URL set from a sitemap export."""

    queue_path = get_indexnow_queue_path(project_slug)
    entries = [IndexNowQueueEntry(queue_id=uuid.uuid4().hex, url=url.strip()) for url in urls if url.strip()]
    with _locked_file(queue_path):
        _write_queue(queue_path, entries)
    return len(entries)


def peek_indexnow_queue(project_slug: str, *, limit: int) -> list[IndexNowQueueEntry]:
    """Read the leading queue slice without changing it."""

    queue_path = get_indexnow_queue_path(project_slug)
    with _locked_file(queue_path):
        return _read_queue(queue_path)[:limit]


def remove_indexnow_queue_entries(project_slug: str, queue_ids: set[str]) -> int:
    """Remove accepted entries while preserving later additions and duplicates."""

    if not queue_ids:
        return 0
    queue_path = get_indexnow_queue_path(project_slug)
    with _locked_file(queue_path):
        entries = _read_queue(queue_path)
        updated_entries = [entry for entry in entries if entry.queue_id not in queue_ids]
        _write_queue(queue_path, updated_entries)
    return len(entries) - len(updated_entries)


def _add_urls(project_slug: str, urls: list[str], *, prepend: bool) -> int:
    """Mutate one queue under a cross-process lock."""

    accepted_urls = [url.strip() for url in urls if url.strip()]
    if not accepted_urls:
        return 0
    queue_path = get_indexnow_queue_path(project_slug)
    new_entries = [IndexNowQueueEntry(queue_id=uuid.uuid4().hex, url=url) for url in accepted_urls]
    with _locked_file(queue_path):
        existing_entries = _read_queue(queue_path)
        _write_queue(queue_path, new_entries + existing_entries if prepend else existing_entries + new_entries)
    return len(new_entries)


def _read_queue(queue_path: Path) -> list[IndexNowQueueEntry]:
    """Read a human-editable CSV queue and accept common URL headers."""

    if not queue_path.exists():
        return []
    with queue_path.open("r", encoding="utf-8-sig", newline="") as queue_file:
        reader = csv.reader(queue_file)
        header_row = next(reader, None)
        if not header_row:
            return []
        headers = [value.strip().lower() for value in header_row]
        queue_id_index = headers.index("queue_id") if "queue_id" in headers else None
        url_index = next((index for index, header in enumerate(headers) if header in URL_HEADER_CANDIDATES), None)
        if url_index is None:
            raise ValueError(f"В файле {queue_path.name} не найдена колонка URL.")
        entries: list[IndexNowQueueEntry] = []
        for row_number, row in enumerate(reader, start=2):
            if url_index >= len(row):
                continue
            url = row[url_index].strip()
            if not url:
                continue
            queue_id = row[queue_id_index].strip() if queue_id_index is not None and queue_id_index < len(row) else ""
            # Legacy one-column CSV files have no hidden id. A deterministic id keeps
            # their entries removable during this first submission pass.
            fallback_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{queue_path}:{row_number}:{url}").hex
            entries.append(IndexNowQueueEntry(queue_id=queue_id or fallback_id, url=url))
    return entries


def _write_queue(queue_path: Path, entries: list[IndexNowQueueEntry]) -> None:
    """Atomically write queue contents so readers never see a partial file."""

    with NamedTemporaryFile(
        dir=queue_path.parent,
        suffix=".csv",
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        writer = csv.writer(temp_file)
        writer.writerow(QUEUE_HEADERS)
        writer.writerows((entry.queue_id, entry.url) for entry in entries)
    try:
        os.replace(temp_path, queue_path)
    finally:
        temp_path.unlink(missing_ok=True)


class _locked_file:
    """Cross-process advisory lock for queue mutations."""

    def __init__(self, target_path: Path) -> None:
        self._lock_path = target_path.with_suffix(f"{target_path.suffix}.lock")
        self._handle = None

    def __enter__(self) -> None:
        import fcntl

        self._handle = self._lock_path.open("a+")
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        import fcntl

        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
