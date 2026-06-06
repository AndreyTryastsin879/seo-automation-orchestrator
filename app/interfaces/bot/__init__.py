"""Telegram bot interface package."""

from app.interfaces.bot.app import create_bot, create_dispatcher

__all__ = ["create_bot", "create_dispatcher"]
