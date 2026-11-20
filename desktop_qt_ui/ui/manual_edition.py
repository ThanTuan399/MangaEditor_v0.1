"""Manual-first navigation without removing legacy translation backends.

MangaEditor is an OCR-assisted typesetting tool by default. The full legacy
AI workflow remains installed and can be shown with MANGA_EDITOR_UI=full.
This is deliberately an interface choice, *not* a data conversion.
"""
from __future__ import annotations

import os
from collections.abc import Iterable, Mapping


MANUAL_KEYS = ("ocr_workspace", "settings", "batch_edit", "replacements", "about")


def manual_edition_enabled(environment: Mapping[str, str] | None = None) -> bool:
    environ = os.environ if environment is None else environment
    profile = str(environ.get("MANGA_EDITOR_UI", "manual")).strip().lower()
    return profile not in ("full", "legacy", "automatic")


def filter_manual_navigation(pages: Iterable[tuple]) -> list[tuple]:
    """Keep useful editing pages in a compact, predictable navigation order."""
    indexed = {page[0]: page for page in pages}
    return [indexed[key] for key in MANUAL_KEYS if key in indexed]


def initial_manual_page_key(enabled: bool) -> str:
    return "ocr_workspace" if enabled else "translation"
