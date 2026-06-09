"""Production webhook application for the Telegram bot."""

from __future__ import annotations

from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request, status

from app.core.config import get_settings
from app.interfaces.bot.app import create_bot, create_dispatcher

WEBHOOK_PATH = "/bot/webhook"
HEALTH_PATH = "/bot/health"


def _validate_webhook_secret(received_secret: str | None) -> None:
    """Validate Telegram webhook secret when it is configured."""

    settings = get_settings()
    expected_secret = settings.bot_webhook_secret
    if not expected_secret:
        return
    if received_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret.",
        )


async def _configure_webhook(bot: Bot) -> None:
    """Register the webhook URL in Telegram when configured."""

    settings = get_settings()
    if not settings.bot_webhook_url:
        return

    await bot.set_webhook(
        url=settings.bot_webhook_url,
        secret_token=settings.bot_webhook_secret,
        drop_pending_updates=False,
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Create and dispose webhook dependencies for the bot service."""

    bot = create_bot()
    dispatcher = create_dispatcher()
    app.state.bot = bot
    app.state.dispatcher = dispatcher
    await _configure_webhook(bot)
    try:
        yield
    finally:
        await bot.session.close()


def create_webhook_app() -> FastAPI:
    """Create a FastAPI application for Telegram webhook delivery."""

    app = FastAPI(title="SEO Automation Orchestrator Bot Webhook", lifespan=_lifespan)

    @app.get(HEALTH_PATH)
    async def bot_healthcheck() -> dict[str, str]:
        """Return a simple healthcheck response for bot infrastructure."""

        return {"status": "ok"}

    @app.post(WEBHOOK_PATH)
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        """Accept one Telegram update and pass it to aiogram."""

        _validate_webhook_secret(x_telegram_bot_api_secret_token)
        update_data = await request.json()
        update = Update.model_validate(update_data)
        bot: Bot = request.app.state.bot
        dispatcher: Dispatcher = request.app.state.dispatcher
        await dispatcher.feed_webhook_update(bot, update)
        return {"ok": True}

    return app


app = create_webhook_app()
