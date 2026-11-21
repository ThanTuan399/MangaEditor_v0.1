"""Manual Editor typography: frame and font controls are independent.

A geometry drag affects only geometry. The explicit Font Size control changes
the text's font size, including existing rich spans with absolute fontSize
settings; the ratio between deliberately different span sizes is preserved.
"""
from __future__ import annotations

import copy
import math
from typing import Any


GEOMETRY_EDIT_FIELDS = frozenset({
    "center", "angle", "lines", "white_frame_rect_local",
    "has_custom_white_frame", "render_box_rect_local",
})


def merge_geometry_without_stale_typography(
    model_region: dict, edited_region: dict
) -> dict:
    """Merge drag geometry into the freshest model region, not a stale item.

    The QGraphicsItem can hold an old font_size/translation when the user
    immediately drags after editing a font or sentence. Copying the entire item
    payload into UpdateRegionCommand would silently undo those newer edits.
    """
    merged = copy.deepcopy(model_region)
    for key in GEOMETRY_EDIT_FIELDS:
        if key in edited_region:
            merged[key] = copy.deepcopy(edited_region[key])
    merged["font_fit_mode"] = "fixed"
    return merged


def scale_rich_absolute_font_sizes(
    rich: Any, old_size: Any, new_size: Any
) -> Any:
    """Return an isolated rich doc with explicit run fontSize scaled.

    Runs using relative style.scale are already proportional to the region
    base font size and must not be touched. All other character-level style
    attributes are preserved, including ruby and bold/italic/color.
    """
    if not isinstance(rich, dict):
        return rich
    try:
        old = float(old_size)
        new = float(new_size)
    except (ValueError, TypeError):
        return rich
    if not (math.isfinite(old) and math.isfinite(new) and old > 0 and new > 0):
        return rich
    if old == new:
        return rich
    ratio = new / old
    result = copy.deepcopy(rich)
    for block in result.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for inline in block.get("inlines", []):
            if not isinstance(inline, dict):
                continue
            style = inline.get("style")
            if not isinstance(style, dict) or style.get("fontSize") is None:
                continue
            try:
                value = float(style["fontSize"])
            except (ValueError, TypeError):
                continue
            if math.isfinite(value) and value > 0:
                style["fontSize"] = max(1, round(value * ratio, 2))
    return result
