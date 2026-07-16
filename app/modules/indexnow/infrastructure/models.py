"""SQLAlchemy model for per-project IndexNow credentials."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class IndexNowCredential(TimestampMixin, Base):
    """Encrypted IndexNow key and its public verification-file URL."""

    __tablename__ = "indexnow_credentials"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_location: Mapped[str | None] = mapped_column(String(2048), nullable=True)
