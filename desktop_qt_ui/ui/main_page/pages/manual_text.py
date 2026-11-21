"""Manual manga typesetting text conversions.

Hard breaks are explicit [BR] markers in saved JSON. QTextEdit's soft visual
line wraps are never included by toPlainText(), so only Enter creates [BR].
These helpers have no Qt dependency and can be tested without the GUI.
"""
from __future__ import annotations

import re


_BREAK = re.compile(r"\[BR\]|【BR】|<br\s*/?>", re.IGNORECASE)


def manual_text_to_editor(translation: str | None) -> str:
    """Show deliberate hard breaks as real paragraphs for manual editing."""
    return _BREAK.sub("\n", str(translation or ""))


def manual_editor_to_text(value: str | None) -> str:
    """Persist deliberate paragraph breaks, never widget soft wraps."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", "[BR]")


def next_untranslated_region(regions: list[dict], after: int) -> int | None:
    """Locate next untranslated OCR region, wrapping around the current page."""
    count = len(regions)
    if not count:
        return None
    for step in range(1, count + 1):
        idx = (after + step) % count
        if not str(regions[idx].get("translation") or "").strip():
            return idx
    return None


def translated_region_counts(regions: list[dict]) -> tuple[int, int]:
    return (
        sum(bool(str(region.get("translation") or "").strip()) for region in regions),
        len(regions),
    )



_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def translation_plain_for_ui(
    translation: str | None, original_ocr: str | None = None
) -> str:
    """Display translated prose without damaging saved Editor hard breaks.

    A legacy page may contain old [BR] between syllables or literal spaces
    left over after a previous cleanup. Reconstruct only high-confidence
    word fragments; any still-ambiguous boundary displays as a space.
    """
    from manga_translator.rendering.legacy_word_recovery import recover_split_words

    return recover_split_words(translation, original_ocr, prose=True)


def translation_input_to_plain(value: str | None) -> str:
    """Normalize pasted/typed OCR translation as prose, never as typesetting.

    Even pressing Enter or pasting [BR] in OCR Workspace is not a request to
    alter image layout; manual hard breaks belong exclusively to the Editor.
    """
    return " ".join(
        _BREAK.sub(" ", str(value or "").replace("\r\n", "\n").replace("\r", "\n")).split()
    )
