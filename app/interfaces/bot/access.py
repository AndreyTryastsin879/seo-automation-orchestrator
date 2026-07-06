"""Access control middleware for Telegram bot usage."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, TelegramObject

from app.core.config import get_settings
from app.core.db import SessionFactory
from app.core.redis import get_redis_connection
from app.interfaces.bot.keyboards import build_main_menu_keyboard, build_phone_access_keyboard
from app.modules.bot_access.application import normalize_phone_number
from app.modules.bot_access.infrastructure import BotAccessUserRepository

AUTHORIZED_PHONE_KEY_PREFIX = "bot_access:user_phone:"


def _root_admin_phone_numbers() -> set[str]:
    """Return normalized root admin phone whitelist from settings."""

    return {
        normalized
        for normalized in (
            normalize_phone_number(value) for value in get_settings().bot_allowed_phone_numbers
        )
        if normalized
    }


def _authorization_key(user_id: int) -> str:
    """Build redis key for authorized Telegram user mapping."""

    return f"{AUTHORIZED_PHONE_KEY_PREFIX}{user_id}"


def _is_access_restricted() -> bool:
    """Return whether the bot currently enforces phone-based access."""

    return bool(_root_admin_phone_numbers())


def _is_allowed_phone_number(phone_number: str) -> bool:
    """Return whether the phone number is allowed by root env or DB allowlist."""

    normalized_phone = normalize_phone_number(phone_number)
    if normalized_phone in _root_admin_phone_numbers():
        return True

    session = SessionFactory()
    try:
        access_user = BotAccessUserRepository(session).get_by_phone(normalized_phone)
        return access_user is not None and access_user.is_active
    finally:
        session.close()


def _is_authorized_user(user_id: int) -> bool:
    """Return whether a Telegram user is already authorized."""

    stored_phone = get_redis_connection().get(_authorization_key(user_id))
    if not stored_phone:
        return False
    if isinstance(stored_phone, bytes):
        stored_phone = stored_phone.decode("utf-8", errors="ignore")
    return _is_allowed_phone_number(str(stored_phone))


def is_root_admin_user(user_id: int) -> bool:
    """Return whether the authorized Telegram user belongs to a root admin phone."""

    stored_phone = get_redis_connection().get(_authorization_key(user_id))
    if not stored_phone:
        return False
    if isinstance(stored_phone, bytes):
        stored_phone = stored_phone.decode("utf-8", errors="ignore")
    return normalize_phone_number(str(stored_phone)) in _root_admin_phone_numbers()


def _authorize_user(user_id: int, phone_number: str) -> None:
    """Persist authorized Telegram user mapping in Redis."""

    normalized_phone = normalize_phone_number(phone_number)
    get_redis_connection().set(_authorization_key(user_id), normalized_phone)


def _sync_access_user_identity(
    *,
    user_id: int,
    phone_number: str,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> None:
    """Persist Telegram identity details for an allowed non-root user."""

    normalized_phone = normalize_phone_number(phone_number)
    if normalized_phone in _root_admin_phone_numbers():
        return

    session = SessionFactory()
    try:
        repository = BotAccessUserRepository(session)
        access_user = repository.get_by_phone(normalized_phone)
        if access_user is None:
            return
        access_user.telegram_user_id = user_id
        access_user.username = username
        access_user.first_name = first_name
        access_user.last_name = last_name
        access_user.last_authorized_at = datetime.now(UTC)
        repository.update(access_user)
        session.commit()
    finally:
        session.close()


async def _prompt_for_phone(message: Message, *, invalid_phone: bool = False) -> None:
    """Ask the user to share their phone number for access validation."""

    text = (
        "Доступ к этому боту ограничен.\n\n"
        "Чтобы продолжить, нажми кнопку ниже и отправь номер телефона, который добавлен в список доступа."
    )
    if invalid_phone:
        text = (
            "Этот номер телефона не входит в список доступа.\n\n"
            "Попробуй отправить другой номер, который заранее разрешён для работы с ботом."
        )
    await message.answer(text, reply_markup=build_phone_access_keyboard())


class BotAccessMiddleware(BaseMiddleware):
    """Restrict bot usage to users who confirm an allowed phone number."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not _is_access_restricted():
            return await handler(event, data)

        if isinstance(event, Message):
            user = event.from_user
            if user is None:
                return

            if _is_authorized_user(user.id):
                return await handler(event, data)

            if event.contact is not None:
                contact = event.contact
                if contact.user_id is not None and contact.user_id != user.id:
                    await _prompt_for_phone(event, invalid_phone=True)
                    return

                normalized_phone = normalize_phone_number(contact.phone_number)
                if _is_allowed_phone_number(normalized_phone):
                    _authorize_user(user.id, contact.phone_number)
                    _sync_access_user_identity(
                        user_id=user.id,
                        phone_number=contact.phone_number,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name,
                    )
                    await event.answer(
                        "Доступ подтверждён. Добро пожаловать.",
                        reply_markup=ReplyKeyboardRemove(),
                    )
                    await event.answer(
                        "Главное меню доступно ниже.",
                        reply_markup=build_main_menu_keyboard(),
                    )
                    return

                await _prompt_for_phone(event, invalid_phone=True)
                return

            await _prompt_for_phone(event)
            return

        if isinstance(event, CallbackQuery):
            user = event.from_user
            if user is None:
                return
            if _is_authorized_user(user.id):
                return await handler(event, data)

            await event.answer("Сначала подтвердите доступ по номеру телефона.", show_alert=True)
            if event.message is not None:
                await _prompt_for_phone(event.message)
            return

        return await handler(event, data)
