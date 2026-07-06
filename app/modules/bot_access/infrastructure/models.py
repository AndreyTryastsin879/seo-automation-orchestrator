"""SQLAlchemy models for bot access management."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class BotAccessUser(TimestampMixin, Base):
    """Allowed bot user identified by phone number."""

    __tablename__ = "bot_access_users"
    __table_args__ = (
        Index("ix_bot_access_users_phone_number", "phone_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    last_authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
