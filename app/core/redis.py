"""Redis connection primitives."""

from __future__ import annotations

from functools import lru_cache

from redis import Redis

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_redis_connection() -> Redis:
    """Return a cached Redis connection configured from settings."""

    settings = get_settings()
    return Redis.from_url(settings.redis_url)
