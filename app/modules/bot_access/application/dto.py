"""DTOs for bot access management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class BotAccessUserDTO:
    """Application-facing representation of an allowed bot user."""

    id: int
    phone_number: str
    telegram_user_id: int | None
    username: str | None
    first_name: str | None
    last_name: str | None
    is_active: bool
    last_authorized_at: datetime | None
    created_at: datetime
    updated_at: datetime
