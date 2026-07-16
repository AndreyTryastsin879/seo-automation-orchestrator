"""Persistence layer for IndexNow credentials."""

from app.modules.indexnow.infrastructure.models import IndexNowCredential
from app.modules.indexnow.infrastructure.repositories import IndexNowCredentialRepository

__all__ = ["IndexNowCredential", "IndexNowCredentialRepository"]
