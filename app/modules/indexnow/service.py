"""Encrypted storage and validation for IndexNow project credentials."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.core.db import SessionFactory
from app.core.secrets import decrypt_secret, encrypt_secret
from app.modules.indexnow.infrastructure import IndexNowCredential, IndexNowCredentialRepository
from app.modules.projects.infrastructure import ProjectRepository

INDEXNOW_KEY_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,128}$")


@dataclass(frozen=True, slots=True)
class IndexNowCredentialValue:
    """Decrypted credential used by a worker only during API submission."""

    key: str
    key_location: str | None


def save_indexnow_credential(*, project_id: int, key: str, key_location: str | None) -> None:
    """Validate, encrypt and save one project's IndexNow key."""

    normalized_key = key.strip()
    if not INDEXNOW_KEY_PATTERN.fullmatch(normalized_key):
        raise ValueError("Ключ IndexNow должен содержать 8-128 букв, цифр или дефисов.")
    normalized_location = _normalize_key_location(key_location)
    session = SessionFactory()
    try:
        project = ProjectRepository(session).get_by_id(project_id)
        if project is None:
            raise ValueError("Проект не найден.")
        if normalized_location and project.start_url:
            project_host = urlsplit(project.start_url).hostname
            location_host = urlsplit(normalized_location).hostname
            if project_host and location_host and project_host.lower() != location_host.lower():
                raise ValueError("Ключевой файл должен находиться на том же хосте, что и стартовый URL проекта.")
        repository = IndexNowCredentialRepository(session)
        credential = repository.get_by_project_id(project_id)
        if credential is None:
            credential = IndexNowCredential(
                project_id=project_id,
                encrypted_key=encrypt_secret(normalized_key),
                key_location=normalized_location,
            )
        else:
            credential.encrypted_key = encrypt_secret(normalized_key)
            credential.key_location = normalized_location
        repository.save(credential)
        session.commit()
    finally:
        session.close()


def get_indexnow_credential(project_id: int) -> IndexNowCredentialValue | None:
    """Return a project's decrypted key only inside the worker process."""

    session = SessionFactory()
    try:
        credential = IndexNowCredentialRepository(session).get_by_project_id(project_id)
        if credential is None:
            return None
        return IndexNowCredentialValue(
            key=decrypt_secret(credential.encrypted_key),
            key_location=credential.key_location,
        )
    finally:
        session.close()


def has_indexnow_credential(project_id: int) -> bool:
    """Return whether a project has a saved IndexNow key."""

    session = SessionFactory()
    try:
        return IndexNowCredentialRepository(session).get_by_project_id(project_id) is not None
    finally:
        session.close()


def _normalize_key_location(value: str | None) -> str | None:
    """Accept a blank location or a complete HTTP(S) URL on the project host."""

    normalized_value = (value or "").strip()
    if not normalized_value:
        return None
    parsed = urlsplit(normalized_value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Укажи полный URL ключевого файла, например https://example.com/key.txt.")
    return normalized_value
