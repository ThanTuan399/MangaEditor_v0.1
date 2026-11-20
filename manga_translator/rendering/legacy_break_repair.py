"""Conservative repair for *legacy* render-persisted [BR] mistakes.

Pre-v2 JSON persisted auto-wrapped text. We cannot reliably reconstruct every
paragraph's intent, so only fix unmistakable corruption: a single-character
word fragment split from its continuation, or a trailing empty [BR]. Never
rewrite the rest of a line or remove a reasonable manual paragraph break.
Styled rich documents are never modified. New v2 files are never modified.
"""
from __future__ import annotations

import re
from typing import Any

_BR = r"(?:\[BR\]|【BR】|<br\s*/?>)"
_SINGLE_LETTER_SPLIT = re.compile(
    rf"(?<![^\W\d_])([^\W\d_])\s*{_BR}\s*([^\W\d_]{{2,}})",
    re.IGNORECASE,
)
_TRAILING_BREAKS = re.compile(rf"(?:\s*{_BR}\s*)+$", re.IGNORECASE)


def repair_legacy_auto_break_text(text: str) -> str:
    """Join a one-letter fragment with its continuation; drop empty final BR."""
    if not isinstance(text, str) or not text:
        return text
    fixed = _SINGLE_LETTER_SPLIT.sub(lambda m: m.group(1) + m.group(2), text)
    return _TRAILING_BREAKS.sub("", fixed)


def repair_legacy_region_breaks(region: dict, image_data: dict) -> bool:
    """Patch in-memory legacy region, preserving manual paragraphs and rich style.

    Only legacy JSON created from previously rendered pages (the old
    skip_text_replacements marker) is eligible. The caller persists the repair
    through their normal Save JSON path, so existing files aren't changed until
    the user saves/exports the page.
    """
    if not isinstance(region, dict) or not isinstance(image_data, dict):
        return False
    if image_data.get("render_text_source_version", 0) == 2:
        return False
    if not image_data.get("skip_text_replacements", False):
        return False
    original = region.get("translation")
    if not isinstance(original, str) or not original:
        return False
    replacement = repair_legacy_auto_break_text(original)
    if replacement == original:
        return False

    rich = region.get("translation_rich")
    if rich:
        try:
            from .rich_text import is_redundant_plain_document

            if not is_redundant_plain_document(rich, original):
                return False  # User-styled paragraph: do not lose rich styles.
        except (ValueError, TypeError):
            return False

    region["translation"] = replacement
    if region.get("translation_raw") == original:
        region["translation_raw"] = replacement
    if rich:
        region.pop("translation_rich", None)  # Regenerate unstyled paragraphs.
    return True


def repair_legacy_image_regions(image_data: Any) -> int:
    """Return number of conservatively repaired regions in image JSON."""
    if not isinstance(image_data, dict):
        return 0
    regions = image_data.get("regions", [])
    if not isinstance(regions, list):
        return 0
    return sum(bool(repair_legacy_region_breaks(r, image_data)) for r in regions)
