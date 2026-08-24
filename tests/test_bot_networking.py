"""Regression checks for Telegram networking configuration."""

import socket
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.interfaces.bot.app import create_bot


class BotNetworkingTests(unittest.TestCase):
    """Ensure the direct Telegram session avoids an unavailable IPv6 route."""

    @patch("app.interfaces.bot.app.get_settings")
    def test_direct_bot_session_uses_ipv4(self, get_settings) -> None:
        get_settings.return_value = SimpleNamespace(bot_token="123:token", bot_proxy=None)

        bot = create_bot()

        self.assertEqual(bot.session._connector_init["family"], socket.AF_INET)
