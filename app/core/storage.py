"""Local file storage primitives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class StoredFile:
    """Metadata about a stored local file."""

    relative_path: str
    absolute_path: Path
    size: int


class LocalFileStorage:
    """Store files in a local directory configured via settings."""

    def __init__(self, root: Path | None = None) -> None:
        """Initialize storage using the configured or provided root path."""

        storage_root = root or get_settings().storage_root
        self._root = storage_root.expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        """Return the absolute storage root."""

        return self._root

    def write_text(self, relative_path: str, content: str, *, encoding: str = "utf-8") -> StoredFile:
        """Write text content under the storage root."""

        target_path = self._root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding=encoding)
        return StoredFile(
            relative_path=relative_path,
            absolute_path=target_path,
            size=target_path.stat().st_size,
        )

    def write_bytes(self, relative_path: str, content: bytes) -> StoredFile:
        """Write binary content under the storage root."""

        target_path = self._root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)
        return StoredFile(
            relative_path=relative_path,
            absolute_path=target_path,
            size=target_path.stat().st_size,
        )
