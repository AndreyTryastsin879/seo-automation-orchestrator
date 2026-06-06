"""Local polling runner for the Telegram bot."""

from __future__ import annotations

import asyncio

from app.interfaces.bot.app import create_bot, create_dispatcher


async def run_polling() -> None:
    """Run the Telegram bot in long-polling mode."""

    bot = create_bot()
    dispatcher = create_dispatcher()
    await dispatcher.start_polling(bot)


def main() -> None:
    """Run long polling inside a fresh event loop."""

    asyncio.run(run_polling())
