"""Telegram bot application factory."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.redis import RedisStorage

from app.core.config import get_settings
from app.interfaces.bot.handlers import register_handlers


def create_bot() -> Bot:
    """Create a Telegram bot instance from runtime settings."""

    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN environment variable is not set.")
    session = None
    if settings.bot_proxy:
        session = AiohttpSession(proxy=settings.bot_proxy)
    return Bot(token=settings.bot_token, session=session)


def create_dispatcher() -> Dispatcher:
    """Create and configure the Telegram dispatcher."""

    settings = get_settings()
    dispatcher = Dispatcher(storage=RedisStorage.from_url(settings.redis_url))
    register_handlers(dispatcher)
    return dispatcher
