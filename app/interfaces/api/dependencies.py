"""FastAPI-oriented dependency providers."""

from __future__ import annotations

from typing import Iterator

from sqlalchemy.orm import Session

from app.core.db import get_session


def get_db_session() -> Iterator[Session]:
    """Yield a sync SQLAlchemy session for request handlers."""

    yield from get_session()
