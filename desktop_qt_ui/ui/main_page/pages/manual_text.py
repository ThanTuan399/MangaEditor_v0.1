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
    """Return readable prose without any stored typesetting line breaks.

    This is a *view* of historical JSON: opening an OCR project never modifies
    its saved manual [BR] layout or rich text. The prior renderer could split a
    single word across [BR]. Rejoin only a very short fragment (one letter) or
    two fragments whose joined spelling occurs as a word in the original OCR
    (e.g. Ya[BR]mamoto with YAMAMOTO in the source). Otherwise use a space:
    do not silently turn intentional separate words into one word.
    """
    source_words = {
        word.casefold()
        for word in _WORD.findall(str(original_ocr or ""))
    }
    parts = _BREAK.split(str(translation or "").replace("\r\n", "\n").replace("\r", "\n"))
    merged = ""
    for fragment in parts:
        fragment = " ".join(fragment.split())
        if not fragment:
            continue
        if not merged:
            merged = fragment
            continue
        previous = _WORD.findall(merged)
        following = _WORD.match(fragment)
        prev_word = previous[-1] if previous and merged.endswith(previous[-1]) else ""
        next_word = following.group(0) if following else ""
        joined = prev_word + next_word
        should_join = (
            bool(prev_word and next_word)
            and (
                len(prev_word) == 1
                or (bool(source_words) and joined.casefold() in source_words)
            )
        )
        merged += ("" if should_join else " ") + fragment
    return " ".join(merged.split())


def translation_input_to_plain(value: str | None) -> str:
    """Normalize pasted/typed OCR translation as prose, never as typesetting.

    Even pressing Enter or pasting [BR] in OCR Workspace is not a request to
    alter image layout; manual hard breaks belong exclusively to the Editor.
    """
    return " ".join(
        _BREAK.sub(" ", str(value or "").replace("\r\n", "\n").replace("\r", "\n")).split()
    )
