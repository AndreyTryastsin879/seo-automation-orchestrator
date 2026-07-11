"""Local polling runner for the Telegram bot."""

from __future__ import annotations

import asyncio

from app.core.logging import configure_logging, get_logger, log_event
from app.interfaces.bot.app import create_bot, create_dispatcher

LOGGER = get_logger("app.bot.polling")


async def run_polling() -> None:
    """Run the Telegram bot in long-polling mode."""

    bot = create_bot()
    dispatcher = create_dispatcher()
    log_event(LOGGER, "bot_polling_started")
    try:
        await dispatcher.start_polling(bot)
    finally:
        log_event(LOGGER, "bot_polling_stopped")


def main() -> None:
    """Run long polling inside a fresh event loop."""

    configure_logging(service="bot_polling")
    asyncio.run(run_polling())
