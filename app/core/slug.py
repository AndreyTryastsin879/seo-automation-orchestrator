"""Slug helpers for filesystem-safe names."""

from __future__ import annotations

import re
import unicodedata

_CYRILLIC_TRANSLIT_MAP = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)


def slugify(value: str) -> str:
    """Convert arbitrary text into a filesystem-safe slug."""

    transliterated = value.strip().lower().translate(_CYRILLIC_TRANSLIT_MAP)
    normalized = unicodedata.normalize("NFKD", transliterated)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    hyphenated = re.sub(r"\s+", "-", ascii_text)
    cleaned = re.sub(r"[^a-z0-9-]", "", hyphenated)
    collapsed = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return collapsed or "project"
