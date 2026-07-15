"""Yandex OAuth persistence primitives."""

from app.modules.yandex_oauth.infrastructure.models import YandexOAuthCredential
from app.modules.yandex_oauth.infrastructure.repositories import YandexOAuthCredentialRepository

__all__ = ["YandexOAuthCredential", "YandexOAuthCredentialRepository"]
