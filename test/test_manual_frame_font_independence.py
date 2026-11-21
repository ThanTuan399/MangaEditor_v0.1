"""Manual Edition regression: typography and user frame are independent.

Resizing a dialogue rectangle must never silently change the chosen font size.
Explicitly adjusting the font size must never overwrite white-frame geometry.
Text reflows at word boundaries at its *fixed* font size in preview and export.
"""
import _bootstrap  # noqa: F401

from copy import deepcopy
from types import SimpleNamespace

import pytest

from editor.editor_controller import _sync_white_frame_size_for_font_change
from editor.geometry_commit_pipeline import build_white_frame_region_data
from editor.text_render_pipeline import build_text_block_from_region
from manga_translator.rendering.manual_typesetting import (
    custom_manual_frame_width,
    wrap_words_fixed_font,
    wrap_textblock_for_manual_frame,
)
from manga_translator.rendering.rich_text import legacy_line_breaks_to_document
from manga_translator.utils.textblock import TextBlock


def _region(**values):
    result = {
        "lines": [[[10, 10], [130, 10], [130, 110], [10, 110]]],
        "texts": ["そうだよ"],
        "translation": "Đúng rồi đó!",
        "target_lang": "VIN",
        "direction": "h",
        "font_size": 31,
        "center": [70, 60],
        "white_frame_rect_local": [-35, -35, 35, 35],
        "has_custom_white_frame": True,
    }
    result.update(values)
    return result


def test_resize_dialogue_frame_preserves_explicit_font_size():
    region = _region()
    before = deepcopy(region)
    result = build_white_frame_region_data(
        0, region,
        {"white_frame_rect_local": [-45, -40, 45, 40], "has_custom_white_frame": True},
        [-45, -40, 45, 40],
        old_white_frame_local=[-35, -35, 35, 35],
        edit_mode="white_corner",
    )
    assert result["font_size"] == 31
    assert result["white_frame_rect_local"] == [-45, -40, 45, 40]
    assert result["has_custom_white_frame"] is True
    assert region == before


def test_font_change_preserves_existing_custom_frame():
    original = _region()
    updated = {**deepcopy(original), "font_size": 54}
    _sync_white_frame_size_for_font_change(updated, original, None, None)
    assert updated["font_size"] == 54
    assert updated["white_frame_rect_local"] == original["white_frame_rect_local"]
    assert updated["has_custom_white_frame"] is True


def test_changing_translation_does_not_change_manual_frame():
    old = _region()
    updated = {**deepcopy(old), "translation": "Một câu thoại dài hơn"}
    _sync_white_frame_size_for_font_change(updated, old, None, None)
    assert updated["white_frame_rect_local"] == old["white_frame_rect_local"]


def test_word_wrap_only_breaks_between_whole_words():
    measure = lambda text: len(text) * 10.0
    wrapped = wrap_words_fixed_font("Đúng rồi đó!", 85, measure)
    assert wrapped == "Đúng rồi[BR]đó!"
    assert wrap_words_fixed_font("Yamamoto", 30, measure) == "Yamamoto"
    assert wrap_words_fixed_font("Chào[BR]bạn nhé", 80, measure) == "Chào[BR]bạn nhé"
    assert wrap_words_fixed_font("Xin chào bạn", 85, measure) == "Xin chào[BR]bạn"
    assert "xon[BR]g" not in wrap_words_fixed_font("xong bài tập", 50, measure)


def test_wrapping_textblock_does_not_change_selected_font_or_original_document():
    region = _region(translation="Đúng rồi đó!")
    original = deepcopy(region)
    block = TextBlock(**region)
    assert block.manual_frame_width == 70
    assert wrap_textblock_for_manual_frame(
        block, measure_width=lambda text: len(text) * 10
    )
    assert block.font_size == 31
    assert "[BR]" in block.translation
    assert region == original
    assert block.to_dict()["font_size"] == 31
    assert block.to_dict()["white_frame_rect_local"] == [-35, -35, 35, 35]
    assert block.to_dict()["has_custom_white_frame"] is True


def test_styled_rich_runs_are_not_silently_replaced_by_plain_wrap():
    region = _region()
    styled = legacy_line_breaks_to_document("Đúng rồi đó!").to_dict()
    styled["blocks"][0]["inlines"][0]["style"] = {"bold": True}
    region["translation_rich"] = styled
    block = TextBlock(**region)
    assert not wrap_textblock_for_manual_frame(
        block, measure_width=lambda text: len(text) * 10
    )
    assert block.translation_rich is not None
    assert block.font_size == 31


def test_no_manual_frame_means_no_forced_wrap():
    region = _region(has_custom_white_frame=False)
    assert custom_manual_frame_width(region) is None
    block = TextBlock(**region)
    assert block.manual_frame_width is None
    assert not wrap_textblock_for_manual_frame(
        block, measure_width=lambda text: len(text) * 10
    )
    assert block.translation == "Đúng rồi đó!"


def test_preview_uses_manual_frame_and_never_mutates_json(monkeypatch):
    from manga_translator.rendering import manual_typesetting as mt

    monkeypatch.setattr(
        mt, "wrap_textblock_for_manual_frame",
        lambda block: setattr(block, "translation", "Đúng rồi[BR]đó!") or True,
    )
    region = _region()
    original = deepcopy(region)
    block = build_text_block_from_region(region)
    assert block is not None
    assert block.translation == "Đúng rồi[BR]đó!"
    assert block.font_size == 31
    assert region == original


def test_export_keeps_geometry_fields_and_font_size_after_render_roundtrip():
    block = TextBlock(**_region(font_size=28))
    saved = block.to_dict()
    assert saved["font_size"] == 28
    assert saved["white_frame_rect_local"] == [-35, -35, 35, 35]
    assert saved["has_custom_white_frame"]
    reconstructed = TextBlock(**saved)
    assert reconstructed.manual_frame_width == 70



def test_fit_button_is_explicit_and_keeps_frame_geometry(monkeypatch):
    import manga_translator.rendering as renderer
    from editor.geometry_commit_pipeline import fit_font_once_to_frame

    def fake_box(font_size, text, horizontal, *args, **kwargs):
        lines = text.replace("[BR]", "\n").splitlines() or [""]
        width = max(len(line) for line in lines) * font_size * 0.55
        height = len(lines) * font_size * 1.15
        return (width, height, [], (width / 2, height / 2))

    monkeypatch.setattr(renderer, "calc_box_from_font", fake_box)
    monkeypatch.setattr(
        "editor.text_renderer_backend.apply_font_for_render", lambda font: font
    )

    params = SimpleNamespace(
        font_family="Arial", direction="h",
        line_spacing=1.0, letter_spacing=1.0,
        effective_stroke_width=0.07,
    )
    region = _region()
    before = deepcopy(region)
    fitted = fit_font_once_to_frame(
        region, region["white_frame_rect_local"], params
    )
    assert fitted is not None
    assert 8 <= fitted <= 31
    # One-shot function proposes a font size but does not alter geometry or
    # existing saved text; caller must execute an explicit undoable command.
    assert region == before


def test_render_reflow_is_idempotent_when_preview_redraws():
    block = TextBlock(**_region())
    metrics = lambda text: len(text) * 10.0
    assert wrap_textblock_for_manual_frame(block, measure_width=metrics)
    once = block.translation
    assert not wrap_textblock_for_manual_frame(block, measure_width=metrics)
    assert block.translation == once
    assert block.font_size == 31
