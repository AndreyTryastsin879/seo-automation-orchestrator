"""Database model for the single shared Yandex OAuth connection."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class YandexOAuthCredential(TimestampMixin, Base):
    """Encrypted OAuth tokens used by all Yandex integrations."""

    __tablename__ = "yandex_oauth_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    encrypted_access_token: Mapped[str] = mapped_column(String(4096), nullable=False)
    encrypted_refresh_token: Mapped[str] = mapped_column(String(4096), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_manual_token: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
