"""Regression tests for Vietnamese vertical OCR text and unpainted source glyphs."""
import _bootstrap  # noqa: F401

import json
import logging
import os
from types import SimpleNamespace

import numpy as np

from manga_translator.mask_refinement.region_polygon_mask import (
    mask_from_text_regions,
    repair_missing_translation_masks,
)
from manga_translator.rendering import _resolve_region_render_horizontal
from manga_translator.utils.textblock import TextBlock


def _quad(x, y, w=20, h=46):
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


def _region(x, *, translation="nè nè, vẫn chưa làm xong bài tập à?", direction="v"):
    return {
        "lines": [_quad(x, 10)],
        "texts": ["何をしているの？"],
        "translation": translation,
        "direction": direction,
        "target_lang": "VIN",
        "font_size": 22,
    }


def test_inherited_vertical_japanese_ocr_becomes_horizontal_vietnamese():
    data = _region(12)
    block = TextBlock(**data)
    assert block.horizontal is True
    assert _resolve_region_render_horizontal(block) is True
    saved = block.to_dict()
    assert saved["direction"] == "h"
    assert saved["direction_user_override"] is False


def test_editor_text_block_uses_same_vietnamese_orientation():
    from editor.text_render_pipeline import build_text_block_from_region

    block = build_text_block_from_region(_region(10))
    assert block is not None
    assert block.horizontal is True


def test_explicit_manual_vertical_remains_vertical_after_save():
    data = _region(12)
    data["direction_user_override"] = True
    block = TextBlock(**data)
    assert block.vertical is True
    assert _resolve_region_render_horizontal(block) is False
    serialized = block.to_dict()
    assert serialized["direction"] == "v"
    assert serialized["direction_user_override"] is True
    assert TextBlock(**serialized).vertical is True


def test_untranslated_source_or_non_vietnamese_region_keeps_direction():
    untranslated = TextBlock(**_region(10, translation=""))
    assert untranslated.vertical is True
    region = _region(10)
    region["target_lang"] = "JPN"
    assert TextBlock(**region).vertical is True


def test_editor_file_service_normalizes_saved_vietnamese_orientation(tmp_path, monkeypatch):
    from services.file_service import FileService

    image = os.path.abspath(str(tmp_path / "chapter.png"))
    json_path = tmp_path / "page.json"
    written = {
        image: {"regions": [_region(10), _region(40, translation="")]}
    }
    json_path.write_text(json.dumps(written, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr("services.file_service.find_json_path", lambda path: str(json_path))
    service = FileService.__new__(FileService)
    service.logger = logging.getLogger("test_vietnamese_mask")
    service.config_service = SimpleNamespace(
        get_config=lambda: SimpleNamespace(
            translator=SimpleNamespace(target_lang="VIN")
        )
    )
    regions, mask, _size, _overlays = service.load_translation_json(image)
    assert mask is None
    assert regions[0]["direction"] == "h"
    assert regions[1]["direction"] == "v"  # untranslated source is untouched


def test_missing_mask_is_recreated_only_for_translated_polygons():
    regions = [_region(10), _region(70, translation="")]
    fixed, updated = repair_missing_translation_masks(regions, (80, 120), None)
    assert updated is True
    assert fixed.dtype == np.uint8
    assert fixed[20, 15] == 255
    assert fixed[20, 75] == 0


def test_missing_second_translated_region_is_recovered_without_erasing_unrelated_pixels():
    regions = [_region(10), _region(65)]
    source_mask = mask_from_text_regions([regions[0]], (80, 120))
    source_mask[2, 2] = 255
    original = source_mask.copy()
    repaired, changed = repair_missing_translation_masks(
        regions, (80, 120), source_mask
    )
    assert changed is True
    assert repaired[20, 14] == 255
    assert repaired[20, 75] == 255
    assert repaired[2, 2] == 255
    assert np.array_equal(original, source_mask)  # never mutate input


def test_complete_mask_is_not_changed_or_invalidated():
    regions = [_region(10), _region(70)]
    full = mask_from_text_regions(regions, (80, 120))
    repaired, changed = repair_missing_translation_masks(regions, (80, 120), full)
    assert changed is False
    assert np.array_equal(full, repaired)


def test_invalid_polygons_do_not_damage_mask():
    broken = _region(10)
    broken["lines"] = [[[float("nan"), 1], [2, 3], [4, 5]]]
    repaired, changed = repair_missing_translation_masks(
        [broken], (80, 120), None
    )
    assert changed is False
    assert not np.any(repaired)


def test_editor_document_worker_marks_missing_mask_as_repaired():
    from editor.document_load_worker import DocumentLoadWorker

    fake_file_service = SimpleNamespace(
        load_translation_json=lambda path: ([_region(10)], None, (120, 80), {})
    )
    fake_service = SimpleNamespace(
        controller=None,
        file_service=fake_file_service,
        logger=logging.getLogger("test_editor_document_worker"),
    )
    worker = DocumentLoadWorker(fake_service, "page.png", None)
    regions, mask, overlays, repaired = worker._load_regions_and_mask(
        "page.png", "page.json", (120, 80)
    )
    assert len(regions) == 1
    assert repaired
    assert mask[20, 15] == 255
    assert overlays == {}
