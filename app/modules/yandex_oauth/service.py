"""Encrypted storage for the shared manually issued Yandex OAuth token."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.db import SessionFactory
from app.core.secrets import decrypt_secret, encrypt_secret
from app.modules.yandex_oauth.infrastructure import YandexOAuthCredential, YandexOAuthCredentialRepository

MANUAL_TOKEN_LIFETIME = timedelta(days=180)


def save_yandex_access_token(access_token: str) -> datetime:
    """Encrypt and store a shared Yandex token entered by the root admin."""

    normalized_token = access_token.strip()
    if not normalized_token:
        raise ValueError("Токен не должен быть пустым.")

    expires_at = datetime.now(UTC) + MANUAL_TOKEN_LIFETIME
    session = SessionFactory()
    try:
        repository = YandexOAuthCredentialRepository(session)
        credential = repository.get()
        if credential is None:
            credential = YandexOAuthCredential(
                id=1,
                encrypted_access_token=encrypt_secret(normalized_token),
                encrypted_refresh_token=encrypt_secret(""),
                expires_at=expires_at,
                scope="webmaster",
                is_manual_token=True,
            )
        else:
            credential.encrypted_access_token = encrypt_secret(normalized_token)
            credential.encrypted_refresh_token = encrypt_secret("")
            credential.expires_at = expires_at
            credential.scope = "webmaster"
            credential.is_manual_token = True
        repository.save(credential)
        session.commit()
        return expires_at
    finally:
        session.close()


def get_yandex_access_token() -> str:
    """Return the saved token or require the root admin to replace an expired one."""

    session = SessionFactory()
    try:
        credential = YandexOAuthCredentialRepository(session).get()
        if credential is None:
            raise RuntimeError("Яндекс не подключён. Добавь OAuth-токен в разделе «Индексирование».")
        if credential.expires_at <= datetime.now(UTC):
            raise RuntimeError("Срок действия токена Яндекс истёк. Обнови его в разделе «Индексирование».")
        return decrypt_secret(credential.encrypted_access_token)
    finally:
        session.close()


def get_yandex_connection_status() -> tuple[bool, datetime | None, bool]:
    """Return connection state, expected expiry and whether the token was entered manually."""

    session = SessionFactory()
    try:
        credential = YandexOAuthCredentialRepository(session).get()
        if credential is None:
            return False, None, False
        return True, credential.expires_at, credential.is_manual_token
    finally:
        session.close()
