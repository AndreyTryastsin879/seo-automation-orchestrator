"""Projects domain layer."""

from __future__ import annotations

from enum import StrEnum


class CrawlSegment(StrEnum):
    """Logical crawl segment used for queue and UI separation."""

    DEFAULT = "default"
    HEAVY = "heavy"


__all__ = ["CrawlSegment"]
