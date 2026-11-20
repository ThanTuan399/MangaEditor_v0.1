"""Regression: automatic BR is render-only; explicit manual breaks persist."""
import _bootstrap  # noqa: F401

import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from manga_translator.config import Config
from manga_translator.rendering.legacy_break_repair import (
    repair_legacy_auto_break_text,
    repair_legacy_image_regions,
)
from manga_translator.rendering.rich_text import legacy_line_breaks_to_document
from manga_translator.rendering.text_source_preservation import (
    dispatch_preserving_source,
    preserve_semantic_translations,
)
from manga_translator.utils.textblock import TextBlock


def block(value: str, raw: str = "") -> TextBlock:
    return TextBlock(
        [[[0, 0], [140, 0], [140, 90], [0, 90]]],
        texts=["そうだよ"],
        translation=value,
        translation_raw=raw,
        target_lang="VIN",
    )


def test_source_guard_restores_auto_wrapped_layout_and_rich_document():
    region = block("Đúng rồi đó!", "Original raw")
    with preserve_semantic_translations([region]):
        region.translation = "Đúng r[BR]ồi đó![BR]"
        region.translation_raw = "Đúng r[BR]ồi đó![BR]"
        region.ensure_translation_rich_from_legacy_breaks()
        region.font_size = 26
        region.dst_points = [1, 2, 3, 4]
    assert region.translation == "Đúng rồi đó!"
    assert region.translation_raw == "Original raw"
    assert region.translation_rich is None
    assert region.font_size == 26
    assert region.dst_points == [1, 2, 3, 4]
    assert region.to_dict()["translation"] == "Đúng rồi đó!"


def test_user_enter_br_survives_render_even_after_two_rounds():
    rich = legacy_line_breaks_to_document("Đúng rồi[BR]đó!").to_dict()
    region = block("Đúng rồi[BR]đó!", "Đúng rồi[BR]đó!")
    region.translation_rich = copy.deepcopy(rich)

    for _ in range(2):
        with preserve_semantic_translations([region]):
            region.translation = "Đúng r[BR]ồi đó![BR]"
            region.translation_raw = region.translation
            region.translation_rich = {"format": "richtext.v1", "blocks": []}
    saved = region.to_dict()
    assert saved["translation"] == "Đúng rồi[BR]đó!"
    assert saved["translation_raw"] == "Đúng rồi[BR]đó!"
    assert region.translation_rich == rich


def test_source_guard_restores_text_when_render_raises():
    region = block("Đúng rồi đó!")
    with pytest.raises(RuntimeError, match="renderer crashed"):
        with preserve_semantic_translations([region]):
            region.translation = "Đúng r[BR]ồi đó![BR]"
            region._replacement_layout_record = "temporary"
            raise RuntimeError("renderer crashed")
    assert region.translation == "Đúng rồi đó!"
    assert not hasattr(region, "_replacement_layout_record")


def test_dispatch_wrapper_still_renders_temporary_wrapping(monkeypatch):
    import manga_translator.rendering as renderer

    region = block("Đúng rồi đó!")
    seen = []

    async def fake_dispatch(img, text_regions, *args, **kwargs):
        for r in text_regions:
            r.translation = "Đúng r[BR]ồi đó![BR]"
            seen.append(r.translation)
            r.font_size = 35
        return "rendered image"

    monkeypatch.setattr(renderer, "dispatch", fake_dispatch)
    assert asyncio.run(dispatch_preserving_source("img", [region], Config())) == "rendered image"
    assert seen == ["Đúng r[BR]ồi đó![BR]"]
    assert region.translation == "Đúng rồi đó!"
    assert region.font_size == 35


def test_legacy_vietnamese_syllable_split_and_trailing_br_are_repaired():
    assert repair_legacy_auto_break_text("Đúng r[BR]ồi đó![BR]") == "Đúng rồi đó!"
    assert repair_legacy_auto_break_text("Đ[BR]úng rồi") == "Đúng rồi"


def test_manual_paragraphs_between_whole_words_are_preserved():
    assert repair_legacy_auto_break_text("Đúng rồi[BR]đó!") == "Đúng rồi[BR]đó!"
    assert repair_legacy_auto_break_text("Xin chào[BR]bạn!") == "Xin chào[BR]bạn!"


def test_legacy_repair_only_for_old_rendered_vietnamese_and_plain_rich():
    broken = "Đúng r[BR]ồi đó![BR]"
    region = {
        "translation": broken,
        "translation_raw": broken,
        "target_lang": "VIN",
        "translation_rich": legacy_line_breaks_to_document(broken).to_dict(),
    }
    image_data = {"skip_text_replacements": True, "regions": [region]}
    assert repair_legacy_image_regions(image_data) == 1
    assert region["translation"] == "Đúng rồi đó!"
    assert region["translation_raw"] == "Đúng rồi đó!"
    assert "translation_rich" not in region


@pytest.mark.parametrize("image_data", [
    {"skip_text_replacements": False},
    {"skip_text_replacements": True, "render_text_source_version": 2},
])
def test_never_migrate_new_or_unrendered_json(image_data):
    region = {"translation": "Đúng r[BR]ồi đó![BR]", "target_lang": "VIN"}
    image_data["regions"] = [region]
    assert repair_legacy_image_regions(image_data) == 0
    assert region["translation"].endswith("[BR]")


def test_preserve_styled_manual_rich_and_other_languages():
    broken = "Đúng r[BR]ồi đó![BR]"
    rich = legacy_line_breaks_to_document(broken).to_dict()
    rich["blocks"][0]["inlines"][0]["style"] = {"bold": True}
    region = {
        "translation": broken,
        "target_lang": "VIN",
        "translation_rich": rich,
    }
    japanese = {"translation": "日[BR]本語[BR]", "target_lang": "JPN"}
    image_data = {"skip_text_replacements": True, "regions": [region, japanese]}
    assert repair_legacy_image_regions(image_data) == 0
    assert region["translation"] == broken
    assert japanese["translation"].endswith("[BR]")


def test_saved_rendered_json_keeps_semantic_text_and_replay_flags(tmp_path, monkeypatch):
    from manga_translator.manga_translator import MangaTranslator
    import manga_translator.manga_translator as translator_module

    path = tmp_path / "page_translations.json"
    monkeypatch.setattr(translator_module, "get_json_path", lambda *args, **kwargs: str(path))
    region = block("Đúng rồi[BR]đó!", "Đúng rồi[BR]đó!")
    ctx = SimpleNamespace(
        text_regions=[region],
        original_size=(600, 800),
        img_rendered="image",
        mask=None,
        image_name=str(tmp_path / "page.png"),
        skip_text_replacements=False,
        render_semantic_source_preserved=True,
    )
    self = SimpleNamespace(
        text_output_file=None, font_family="Arial",
        template=False, save_text=False, translate_json_only=False,
        generate_and_export=False, save_mask=False,
        ocr_workspace_render=False,
    )
    with preserve_semantic_translations(ctx.text_regions):
        region.translation = "Đúng r[BR]ồi đó![BR]"
        region.translation_raw = region.translation
    assert MangaTranslator._save_text_to_file(self, ctx.image_name, ctx, Config()) is True
    image_data = next(iter(json.loads(path.read_text(encoding="utf-8")).values()))
    assert image_data["regions"][0]["translation"] == "Đúng rồi[BR]đó!"
    assert image_data["render_text_source_version"] == 2
    assert image_data["skip_text_replacements"] is False
