"""Webhook primitives for the future production bot setup."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from fastapi import APIRouter

WEBHOOK_PATH = "/bot/webhook"


def create_webhook_router(bot: Bot, dispatcher: Dispatcher) -> APIRouter:
    """Return a placeholder router for future webhook integration."""

    _ = bot
    _ = dispatcher
    router = APIRouter()

    @router.get("/bot/health")
    async def bot_healthcheck() -> dict[str, str]:
        """Return a simple healthcheck response for bot infrastructure."""

        return {"status": "ok"}

    return router
