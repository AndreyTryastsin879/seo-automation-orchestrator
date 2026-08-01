"""Storage helpers for static XML sitemap snapshots."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.storage import LocalFileStorage

MANIFEST_FILE_NAME = "manifest.json"


@dataclass(frozen=True, slots=True)
class StaticSitemapManifest:
    """Metadata needed to publish and submit one static sitemap snapshot."""

    source_url: str
    files: list[str]
    created_at: str


def get_static_sitemap_project_dir(project_slug: str) -> Path:
    """Return the storage directory containing one project's static maps."""

    return LocalFileStorage().root / "static_sitemaps" / project_slug


def save_static_sitemap_snapshot(
    *,
    project_slug: str,
    source_url: str,
    files: dict[str, bytes],
) -> StaticSitemapManifest:
    """Replace a project's entire snapshot only after all files are prepared."""

    target_dir = get_static_sitemap_project_dir(project_slug)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    manifest = StaticSitemapManifest(
        source_url=source_url,
        files=list(files),
        created_at=datetime.now(UTC).isoformat(),
    )
    with TemporaryDirectory(dir=target_dir.parent, prefix=f".{project_slug}-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        for file_name, body in files.items():
            (temp_dir / file_name).write_bytes(body)
        (temp_dir / MANIFEST_FILE_NAME).write_text(
            json.dumps(
                {"source_url": manifest.source_url, "files": manifest.files, "created_at": manifest.created_at},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        backup_dir = target_dir.with_name(f".{target_dir.name}-previous")
        shutil.rmtree(backup_dir, ignore_errors=True)
        if target_dir.exists():
            os.replace(target_dir, backup_dir)
        os.replace(temp_dir, target_dir)
        shutil.rmtree(backup_dir, ignore_errors=True)
    return manifest


def read_static_sitemap_manifest(project_slug: str) -> StaticSitemapManifest | None:
    """Read an existing snapshot manifest without touching sitemap source URLs."""

    manifest_path = get_static_sitemap_project_dir(project_slug) / MANIFEST_FILE_NAME
    if not manifest_path.exists():
        return None
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = payload.get("files") if isinstance(payload, dict) else None
    source_url = payload.get("source_url") if isinstance(payload, dict) else None
    created_at = payload.get("created_at") if isinstance(payload, dict) else None
    if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
        raise ValueError(f"Некорректный manifest статических карт: {manifest_path.name}.")
    if not isinstance(source_url, str) or not isinstance(created_at, str):
        raise ValueError(f"Некорректный manifest статических карт: {manifest_path.name}.")
    return StaticSitemapManifest(source_url=source_url, files=files, created_at=created_at)
