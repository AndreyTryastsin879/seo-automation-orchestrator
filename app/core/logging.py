"""Central logging configuration for application services."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any


class _ConsoleFormatter(logging.Formatter):
    """Render compact human-readable logs for local development."""

    def format(self, record: logging.LogRecord) -> str:
        """Format one log record with structured context at the end."""

        timestamp = datetime.fromtimestamp(record.created, UTC).astimezone().isoformat(timespec="seconds")
        event = getattr(record, "event", record.getMessage())
        service = getattr(record, "service", "app")
        context = _format_context(getattr(record, "context", {}))
        rendered = f"{timestamp} {record.levelname:<8} [{service}] {record.name}: {event}"
        if context:
            rendered = f"{rendered} {context}"
        if record.exc_info:
            rendered = f"{rendered}\n{self.formatException(record.exc_info)}"
        return rendered


class _JsonFormatter(logging.Formatter):
    """Render one JSON object per line for Docker production logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record without exposing arbitrary record attributes."""

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", "app"),
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
        }
        context = getattr(record, "context", {})
        if isinstance(context, dict) and context:
            payload.update(context)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(*, service: str) -> None:
    """Configure root logging for one independently running application service."""

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "console").lower()
    formatter: logging.Formatter
    if log_format == "json":
        formatter = _JsonFormatter()
    else:
        formatter = _ConsoleFormatter()

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(_ServiceFilter(service))
    logging.basicConfig(level=log_level, handlers=[handler], force=True)
    logging.captureWarnings(True)

    # Third-party clients can be very verbose at DEBUG and contain low-value details.
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced application logger."""

    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, *, level: int = logging.INFO, **context: Any) -> None:
    """Write a structured application event."""

    logger.log(level, event, extra={"event": event, "context": context})


def log_exception(logger: logging.Logger, event: str, **context: Any) -> None:
    """Write a structured error event with the active exception traceback."""

    logger.error(event, extra={"event": event, "context": context}, exc_info=True)


class _ServiceFilter(logging.Filter):
    """Attach the current process service name to every record."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self._service
        return True


def _format_context(context: object) -> str:
    """Render structured context safely in the local console format."""

    if not isinstance(context, dict):
        return ""
    return " ".join(f"{key}={value!r}" for key, value in context.items())
