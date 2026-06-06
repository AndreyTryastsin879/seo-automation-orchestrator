"""Application configuration primitives."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    app_env: str
    app_debug: bool
    database_url: str
    redis_url: str
    storage_root: Path
    bot_token: str | None
    bot_proxy: str | None
    bot_webhook_url: str | None
    bot_webhook_secret: str | None


def _as_bool(value: str, *, default: bool = False) -> bool:
    """Convert a string environment value to boolean."""

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")

    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        app_debug=_as_bool(os.getenv("APP_DEBUG", "false")),
        database_url=database_url,
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        storage_root=Path(os.getenv("STORAGE_ROOT", "./storage")),
        bot_token=os.getenv("BOT_TOKEN"),
        bot_proxy=os.getenv("BOT_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY"),
        bot_webhook_url=os.getenv("BOT_WEBHOOK_URL"),
        bot_webhook_secret=os.getenv("BOT_WEBHOOK_SECRET"),
    )
