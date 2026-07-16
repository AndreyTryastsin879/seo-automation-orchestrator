"""Repository for IndexNow credentials."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.indexnow.infrastructure.models import IndexNowCredential


class IndexNowCredentialRepository:
    """Small persistence boundary for per-project IndexNow credentials."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_project_id(self, project_id: int) -> IndexNowCredential | None:
        return self._session.get(IndexNowCredential, project_id)

    def save(self, credential: IndexNowCredential) -> None:
        self._session.add(credential)
