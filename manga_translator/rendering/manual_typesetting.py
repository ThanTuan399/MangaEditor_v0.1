"""Manual Edition: fixed-size, word-safe reflow inside a user-drawn frame.

A white frame is a *layout constraint*, never a font-size control. Reflow is
ephemeral: callers construct temporary TextBlocks, and the translation and
manually saved [BR] content in JSON remain unchanged.

Rich text with individual character styling is left untouched rather than
silently flattening the user's formatting.
"""
from __future__ import annotations

import re
from typing import Callable

from .rich_text import plain_equivalent_text

_BREAK = re.compile(r"\[BR\]|【BR】|<br\s*/?>|\r?\n", re.IGNORECASE)


def wrap_words_fixed_font(
    text: str,
    max_width: float,
    measure_width: Callable[[str], float],
) -> str:
    """Fit words, never glyph fragments, preserving deliberate paragraph breaks.

    If a *single* word is too wide, leave it intact for an explicit font-size
    adjustment rather than splitting Vietnamese syllables or rewriting data.
    """
    if not text or max_width <= 0:
        return text
    paragraphs = _BREAK.split(text)
    # Construct paragraph by paragraph, avoiding duplicate boundaries.
    wrapped: list[str] = []
    for paragraph in paragraphs:
        words = paragraph.split()
        if not words:
            wrapped.append("")
            continue
        lines = [words[0]]
        for word in words[1:]:
            candidate = lines[-1] + " " + word
            if measure_width(candidate) <= max_width:
                lines[-1] = candidate
            else:
                lines.append(word)
        wrapped.append("[BR]".join(lines))
    return "[BR]".join(wrapped)


def custom_manual_frame_width(data: dict) -> float | None:
    if not isinstance(data, dict) or not data.get("has_custom_white_frame", False):
        return None
    rect = data.get("white_frame_rect_local")
    if not isinstance(rect, (list, tuple)) or len(rect) != 4:
        return None
    try:
        width = float(rect[2]) - float(rect[0])
    except (TypeError, ValueError):
        return None
    return width if width > 0 else None


def wrap_textblock_for_manual_frame(region, *, measure_width=None) -> bool:
    """Reflow a temporary TextBlock at its stored font size.

    Returns True only when temporary paragraph layout changed. Does not
    recalculate font_size or resize white_frame_rect_local.
    """
    width = getattr(region, "manual_frame_width", None)
    try:
        width = float(width)
    except (TypeError, ValueError):
        return False
    if width <= 0 or not getattr(region, "horizontal", False):
        return False
    font_size = int(getattr(region, "font_size", 0) or 0)
    if font_size <= 0:
        return False
    raw = str(getattr(region, "translation", "") or "")
    if not raw:
        return False
    rich = getattr(region, "translation_rich", None)
    if rich:
        plain = plain_equivalent_text(rich)
        if plain is None:  # Custom inline styles must be retained exactly.
            return False
        raw = plain
    # Some space on both sides for accents / strokes / glyph overhang.
    available_width = max(4.0, width - max(4.0, font_size * 0.4))
    if measure_width is None:
        from . import calc_box_from_font, text_render

        # Measure with the same font face used for drawing.
        family = getattr(region, "font_family", "") or text_render.DEFAULT_FONT_FAMILY
        text_render.set_font(family)

        def measure_width(text: str) -> float:
            w, _, _, _ = calc_box_from_font(
                font_size, text, True,
                getattr(region, "line_spacing", 1.0) or 1.0,
                None, getattr(region, "target_lang", None),
                letter_spacing=getattr(region, "letter_spacing", 1.0) or 1.0,
            )
            return float(w)
    wrapped = wrap_words_fixed_font(raw, available_width, measure_width)
    normalized_original = "[BR]".join(_BREAK.split(raw))
    if wrapped == normalized_original:
        return False
    # Set property only on a disposable TextBlock instance, never source JSON.
    region.translation = wrapped
    return True
