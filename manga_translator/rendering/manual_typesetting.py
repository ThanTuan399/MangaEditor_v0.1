"""Word-like reflow for user-drawn dialogue frames.

The frame constrains available line width; it never changes the chosen font.
Wrapping is calculated on disposable TextBlock instances for both Editor and
image export. Neither semantic translation nor saved Rich Text is rewritten.
"""
from __future__ import annotations

import copy
import re
from typing import Callable

from .rich_text import (
    Paragraph,
    RichTextDocument,
    RubyRun,
    TcyRun,
    TextRun,
    ensure_rich_text_document,
    plain_equivalent_text,
)

_BREAK = re.compile(r"\[BR\]|【BR】|<br\s*/?>|\r?\n", re.IGNORECASE)
_WORD_OR_SPACE = re.compile(r"\s+|\S+")


def wrap_words_fixed_font(
    text: str,
    max_width: float,
    measure_width: Callable[[str], float],
) -> str:
    """Wrap at word boundaries, without changing font size or hard breaks."""
    if not text or max_width <= 0:
        return text
    paragraphs = _BREAK.split(text)
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


def _inline_text(inline) -> str:
    if isinstance(inline, TextRun):
        return inline.text
    if isinstance(inline, RubyRun):
        return "".join(part.text for part in inline.base)
    if isinstance(inline, TcyRun):
        return "".join(part.text for part in inline.content)
    return ""


def _slice_rich_inlines(paragraph: Paragraph, start: int, end: int):
    """Slice text spans while preserving individual styles and ruby/TCY atoms.

    Never split a ruby/TCY atom. If an exotic atom crosses a desired wrap
    boundary, the caller leaves that paragraph untouched instead.
    """
    result = []
    cursor = 0
    for inline in paragraph.inlines:
        length = len(_inline_text(inline))
        node_end = cursor + length
        a, b = max(start, cursor), min(end, node_end)
        if a < b:
            if isinstance(inline, TextRun):
                result.append(TextRun(
                    inline.text[a - cursor:b - cursor], inline.style.copy()
                ))
            elif a == cursor and b == node_end:
                result.append(copy.deepcopy(inline))
            else:
                return None
        cursor = node_end
    return result


def wrap_rich_document_fixed_font(
    rich,
    max_width: float,
    measure_width: Callable[[RichTextDocument], float],
):
    """Return (layout_document, changed), preserving every inline style.

    A Word text box may contain styled runs whose boundaries fall in the
    middle of a word. Measure a candidate as *one rich paragraph*, then slice
    the original runs only at spaces; no loss of bold/colour/font/ruby/TCY.
    The returned document exists only for the current render.
    """
    document = ensure_rich_text_document(rich)
    if max_width <= 0:
        return document, False
    new_blocks = []
    changed = False
    for paragraph in document.blocks:
        plain = "".join(_inline_text(inline) for inline in paragraph.inlines)
        words = [token for token in _WORD_OR_SPACE.finditer(plain)
                 if not token.group().isspace()]
        if len(words) < 2:
            new_blocks.append(copy.deepcopy(paragraph))
            continue

        line_start = words[0].start()
        line_end = words[0].end()
        lines = []
        failed = False
        for word in words[1:]:
            candidate = _slice_rich_inlines(paragraph, line_start, word.end())
            if candidate is None:
                failed = True
                break
            width = float(measure_width(RichTextDocument(
                blocks=[Paragraph(inlines=candidate)]
            )))
            if width <= max_width:
                line_end = word.end()
            else:
                lines.append((line_start, line_end))
                line_start = word.start()
                line_end = word.end()
        if failed:
            new_blocks.append(copy.deepcopy(paragraph))
            continue
        lines.append((line_start, line_end))
        if len(lines) == 1:
            new_blocks.append(copy.deepcopy(paragraph))
            continue

        chunks = [_slice_rich_inlines(paragraph, a, b) for a, b in lines]
        if any(chunk is None for chunk in chunks):
            new_blocks.append(copy.deepcopy(paragraph))
            continue
        changed = True
        new_blocks.extend(Paragraph(inlines=chunk) for chunk in chunks)
    return RichTextDocument(blocks=new_blocks), changed


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
    """Reflow a disposable TextBlock at the stored font size.

    For plain text, use the standard word wrapper. For rich text, preserve
    styled runs by wrapping whole rich paragraphs. A single unbreakable word
    is allowed to overflow rather than shrinking the font or splitting it.
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
    plain = plain_equivalent_text(rich) if rich else None

    # Use identical measurement configuration for preview and final export.
    if measure_width is None:
        from . import calc_box_from_font, text_render

        family = getattr(region, "font_family", "") or text_render.DEFAULT_FONT_FAMILY
        text_render.set_font(family)

        def measure_width(value) -> float:
            w, _, _, _ = calc_box_from_font(
                font_size, value, True,
                getattr(region, "line_spacing", 1.0) or 1.0,
                None, getattr(region, "target_lang", None),
                letter_spacing=getattr(region, "letter_spacing", 1.0) or 1.0,
                stroke_width=getattr(region, "stroke_width", None),
            )
            return float(w)

    available_width = max(4.0, width - max(4.0, font_size * 0.4))

    if rich and plain is None:
        wrapped, changed = wrap_rich_document_fixed_font(
            rich, available_width, measure_width
        )
        if changed:
            region.translation_rich = wrapped.to_dict()
        return changed

    if plain is not None:
        raw = plain
    wrapped = wrap_words_fixed_font(raw, available_width, measure_width)
    normalized = "[BR]".join(_BREAK.split(raw))
    if wrapped == normalized:
        return False

    # A plain Rich Text document would otherwise override translation in
    # get_translation_for_rendering(), hiding the newly wrapped paragraphs.
    if rich is not None:
        region.translation_rich = None
    region.translation = wrapped
    return True
