"""Webhook bot application entrypoint."""

from app.interfaces.bot.webhook import app


def main():
    """Return the configured webhook bot application."""

    return app
