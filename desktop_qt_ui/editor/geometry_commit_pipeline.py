"""几何编辑提交管线 — 构建旋转 / 白框编辑的 region_data。"""

import copy
from typing import Optional

from manga_translator.rendering import calc_font_from_box

from editor.render_text_value import has_renderable_text, render_text_value_from_region
from services import get_render_parameter_service


def build_rotate_region_data(
    region_data: dict,
    new_angle: float,
    new_center: Optional[list] = None,
    new_lines: Optional[list] = None,
) -> dict:
    """构建旋转提交数据（可选包含 center / lines 同步）。"""
    data = copy.deepcopy(region_data)
    data["angle"] = float(new_angle)
    if new_center is not None and len(new_center) >= 2:
        data["center"] = [float(new_center[0]), float(new_center[1])]
    if new_lines is not None:
        data["lines"] = copy.deepcopy(new_lines)
    return data


def build_white_frame_region_data(
    region_index: int,
    region_data: dict,
    white_patch: dict,
    white_frame_local: Optional[list],
    old_white_frame_local: Optional[list] = None,
    edit_mode: Optional[str] = None,
) -> dict:
    """构建白框编辑提交数据（含可选字体尺寸回写）。"""
    data = copy.deepcopy(region_data)
    data.update(white_patch)

    # Manual Edition: *every* interactive frame edit switches to fixed-size
    # typography. Older JSON may still carry font_fit_mode="auto": never let
    # dragging a handle silently recalculate the user's selected font size.
    # One-shot fitting is a separate, explicit inspector command.
    data["font_fit_mode"] = "fixed"
    return data


def _white_frame_size_changed(
    old_wf_local: Optional[list],
    new_wf_local: Optional[list],
) -> bool:
    """仅当白框宽高发生变化时，才触发字号重算。"""
    old_size = _extract_white_frame_size(old_wf_local)
    new_size = _extract_white_frame_size(new_wf_local)
    if old_size is None or new_size is None:
        return True
    return tuple(round(value) for value in new_size) != tuple(
        round(value) for value in old_size
    )


def _extract_white_frame_size(
    wf_local: Optional[list],
) -> Optional[tuple[float, float]]:
    if wf_local is None or len(wf_local) != 4:
        return None
    left, top, right, bottom = wf_local
    width = float(max(0.0, right - left))
    height = float(max(0.0, bottom - top))
    if width <= 0.0 or height <= 0.0:
        return None
    return width, height


def _calc_font_size(
    region_data: dict, wf_local: Optional[list], params
) -> Optional[int]:
    size = _extract_white_frame_size(wf_local)
    if size is None:
        return None
    w, h = size
    # 反算与正算使用同一文本源（translation_rich 优先），
    # 保证拖框得到的字号与随后按字号正算的白框尺寸一致。
    text = render_text_value_from_region(region_data)
    direction = region_data.get("direction") or params.direction
    is_h = direction in ("h", "horizontal", "hr")
    if not (has_renderable_text(text) and w > 0 and h > 0):
        return None
    fs = calc_font_from_box(
        w,
        h,
        text,
        is_h,
        params.line_spacing or 1.0,
        letter_spacing=params.letter_spacing or 1.0,
        stroke_width=params.effective_stroke_width,
    )
    return int(max(8, fs))



def fit_font_once_to_frame(region_data: dict, wf_local: Optional[list], params) -> Optional[int]:
    """Explicit one-shot fitting; never called by the frame drag interaction.

    Search the largest font that fits after word-based wrapping. Do not split
    any Vietnamese word; retain manually entered [BR] paragraphs. Rich text
    with character-level styling uses the existing conservative font fitter.
    """
    size = _extract_white_frame_size(wf_local)
    if size is None:
        return None
    from manga_translator.rendering import calc_box_from_font
    from manga_translator.rendering.manual_typesetting import wrap_words_fixed_font
    from manga_translator.rendering.rich_text import (
        plain_equivalent_text, normalize_rich_linebreaks,
    )
    from editor.text_renderer_backend import apply_font_for_render

    width, height = size
    raw = render_text_value_from_region(region_data)
    if isinstance(raw, (dict,)):
        plain = plain_equivalent_text(raw)
        if plain is None:
            return _calc_font_size(region_data, wf_local, params)
        text = plain
    else:
        text = normalize_rich_linebreaks(str(raw or ""))
    if not text.strip():
        return None

    font = str(region_data.get("font_family") or getattr(params, "font_family", "") or "")
    apply_font_for_render(font)
    direction = region_data.get("direction") or getattr(params, "direction", "h")
    if direction not in ("h", "horizontal", "hr"):
        return _calc_font_size(region_data, wf_local, params)

    line_spacing = float(getattr(params, "line_spacing", 1.0) or 1.0)
    letter_spacing = float(getattr(params, "letter_spacing", 1.0) or 1.0)
    target_lang = region_data.get("target_lang") or None

    def measure_at(font_size: int, value: str):
        return calc_box_from_font(
            font_size, value, True, line_spacing, None, target_lang,
            letter_spacing=letter_spacing,
            stroke_width=params.effective_stroke_width,
        )

    def fits(font_size: int) -> bool:
        margin = max(4.0, font_size * 0.4)
        limit = max(1.0, width - margin)
        from manga_translator.rendering.rich_text import normalize_rich_linebreaks

        def measure_width(value: str) -> float:
            w, _, _, _ = measure_at(font_size, value)
            return float(w)

        wrapped = wrap_words_fixed_font(text, limit, measure_width)
        w, h, _, _ = measure_at(font_size, wrapped)
        return w <= limit and h <= max(1.0, height - margin)

    # At most ~9 expensive font measurements sequences. A manual one-shot
    # command may take longer than a normal drag, but never runs per mouse move.
    low, high, best = 8, 256, 8
    while low <= high:
        mid = (low + high) // 2
        if fits(mid):
            best = mid
            low = mid + 1
        else:
            high = mid - 1
    return best
