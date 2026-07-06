"""Repositories for bot access records."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.bot_access.infrastructure.models import BotAccessUser


class BotAccessUserRepository:
    """Data access layer for bot access records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, access_user: BotAccessUser) -> BotAccessUser:
        self._session.add(access_user)
        self._session.flush()
        return access_user

    def get_by_id(self, access_user_id: int) -> BotAccessUser | None:
        statement = select(BotAccessUser).where(BotAccessUser.id == access_user_id)
        return self._session.scalar(statement)

    def get_by_phone(self, phone_number: str) -> BotAccessUser | None:
        statement = select(BotAccessUser).where(BotAccessUser.phone_number == phone_number)
        return self._session.scalar(statement)

    def list_active(self) -> list[BotAccessUser]:
        statement = (
            select(BotAccessUser)
            .where(BotAccessUser.is_active.is_(True))
            .order_by(BotAccessUser.id)
        )
        return list(self._session.scalars(statement).all())

    def update(self, access_user: BotAccessUser) -> BotAccessUser:
        self._session.add(access_user)
        self._session.flush()
        return access_user

    def delete(self, access_user: BotAccessUser) -> None:
        self._session.delete(access_user)
        self._session.flush()
