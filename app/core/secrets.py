"""Encryption helpers for credentials persisted by application integrations."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def encrypt_secret(value: str) -> str:
    """Encrypt one integration secret using the server-local Fernet key."""

    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    """Decrypt one integration secret or raise a clear configuration error."""

    try:
        return _get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as error:
        raise RuntimeError("Не удалось расшифровать данные интеграции Яндекс.") from error


def _get_fernet() -> Fernet:
    """Build Fernet from the deployment-only encryption key."""

    key = get_settings().secrets_encryption_key
    if not key:
        raise RuntimeError("SECRETS_ENCRYPTION_KEY environment variable is not set.")
    try:
        return Fernet(key.encode("utf-8"))
    except ValueError as error:
        raise RuntimeError("SECRETS_ENCRYPTION_KEY must be a valid Fernet key.") from error
