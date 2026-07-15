"""Repository for shared Yandex OAuth credentials."""

from sqlalchemy.orm import Session

from app.modules.yandex_oauth.infrastructure.models import YandexOAuthCredential


class YandexOAuthCredentialRepository:
    """Persist one shared Yandex OAuth credential record."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> YandexOAuthCredential | None:
        return self._session.get(YandexOAuthCredential, 1)

    def save(self, credential: YandexOAuthCredential) -> YandexOAuthCredential:
        self._session.add(credential)
        self._session.flush()
        return credential
