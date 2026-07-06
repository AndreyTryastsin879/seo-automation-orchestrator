"""Use cases for bot access management."""

from __future__ import annotations

from app.modules.bot_access.application.dto import BotAccessUserDTO
from app.modules.bot_access.infrastructure.models import BotAccessUser
from app.modules.bot_access.infrastructure.repositories import BotAccessUserRepository


def normalize_phone_number(phone_number: str) -> str:
    """Normalize phone number for whitelist comparison."""

    digits = "".join(ch for ch in phone_number if ch.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


def _to_dto(access_user: BotAccessUser) -> BotAccessUserDTO:
    return BotAccessUserDTO(
        id=access_user.id,
        phone_number=access_user.phone_number,
        telegram_user_id=access_user.telegram_user_id,
        username=access_user.username,
        first_name=access_user.first_name,
        last_name=access_user.last_name,
        is_active=access_user.is_active,
        last_authorized_at=access_user.last_authorized_at,
        created_at=access_user.created_at,
        updated_at=access_user.updated_at,
    )


class ListBotAccessUsersUseCase:
    """Return allowed non-root bot users."""

    def __init__(self, repository: BotAccessUserRepository) -> None:
        self._repository = repository

    def execute(self) -> list[BotAccessUserDTO]:
        return [_to_dto(item) for item in self._repository.list_active()]


class CreateBotAccessUserUseCase:
    """Allow a bot user by phone number."""

    def __init__(self, repository: BotAccessUserRepository) -> None:
        self._repository = repository

    def execute(self, phone_number: str) -> BotAccessUserDTO:
        normalized_phone = normalize_phone_number(phone_number)
        if not normalized_phone:
            raise ValueError("Номер телефона пуст.")

        existing = self._repository.get_by_phone(normalized_phone)
        if existing is not None:
            if not existing.is_active:
                existing.is_active = True
                self._repository.update(existing)
            return _to_dto(existing)

        created = self._repository.create(
            BotAccessUser(
                phone_number=normalized_phone,
                is_active=True,
            )
        )
        return _to_dto(created)


class DeleteBotAccessUserUseCase:
    """Delete a non-root allowed user by id."""

    def __init__(self, repository: BotAccessUserRepository) -> None:
        self._repository = repository

    def execute(self, access_user_id: int) -> bool:
        access_user = self._repository.get_by_id(access_user_id)
        if access_user is None:
            return False
        self._repository.delete(access_user)
        return True
