"""Manual-first UI, semantic text and safely cached LaMa backgrounds."""
import _bootstrap  # noqa: F401

from types import SimpleNamespace

import numpy as np
import pytest

from ui.manual_edition import (
    MANUAL_KEYS,
    filter_manual_navigation,
    initial_manual_page_key,
    manual_edition_enabled,
)
from ui.main_page.pages.manual_text import (
    manual_editor_to_text,
    manual_text_to_editor,
    translation_plain_for_ui,
    translation_input_to_plain,
    next_untranslated_region,
    translated_region_counts,
)
from manga_translator.inpainting.workspace_cache import (
    workspace_inpaint_signature,
    write_workspace_inpaint_cache,
    is_valid_workspace_inpaint_cache,
)


def fake_config(size=2048, *, solid_fill=False, per_block=False):
    return SimpleNamespace(
        inpainter=SimpleNamespace(
            inpainter="lama_large",
            inpainting_size=size,
            inpainting_precision="fp32",
            force_use_torch_inpainting=False,
            solid_fill_pure_bubbles=solid_fill,
            per_block_inpainting=per_block,
        )
    )


def test_manual_navigation_default_and_explicit_legacy_opt_in():
    assert manual_edition_enabled({}) is True
    assert manual_edition_enabled({"MANGA_EDITOR_UI": "manual"}) is True
    assert manual_edition_enabled({"MANGA_EDITOR_UI": "full"}) is False
    assert manual_edition_enabled({"MANGA_EDITOR_UI": "legacy"}) is False
    assert initial_manual_page_key(True) == "ocr_workspace"
    assert initial_manual_page_key(False) == "translation"
    pages = [
        ("translation", "AI", 1, "translate"),
        ("settings", "Settings", 2, "settings"),
        ("env", "API", 3, "API"),
        ("prompts", "Prompts", 4, "prompts"),
        ("about", "About", 5, "about"),
        ("ocr_workspace", "OCR", 6, "OCR"),
        ("batch_edit", "Batch", 7, "batch"),
        ("replacements", "Glossary", 8, "replacements"),
    ]
    result = filter_manual_navigation(pages)
    assert [row[0] for row in result] == list(MANUAL_KEYS)
    assert "translation" not in [row[0] for row in result]
    # Hide the legacy pages without mutating them for the opt-in full UI.
    assert len(pages) == 8


def test_intentional_line_breaks_do_not_include_editor_soft_wraps():
    assert manual_editor_to_text("Đúng rồi\nđó!") == "Đúng rồi[BR]đó!"
    assert manual_text_to_editor("Đúng rồi[BR]đó!") == "Đúng rồi\nđó!"
    assert manual_editor_to_text("Đúng rồi đó!") == "Đúng rồi đó!"
    assert manual_editor_to_text("Đúng\r\nrồi!\r") == "Đúng[BR]rồi![BR]"
    assert manual_text_to_editor("Đúng rồi【BR】đó!") == "Đúng rồi\nđó!"


def test_next_untranslated_wraps_without_altering_dialogue_order():
    regions = [
        {"translation": "Xin chào"},
        {"translation": ""},
        {"translation": "Đúng rồi"},
        {"translation": "   "},
    ]
    assert translated_region_counts(regions) == (2, 4)
    assert next_untranslated_region(regions, 0) == 1
    assert next_untranslated_region(regions, 2) == 3
    assert next_untranslated_region(regions, 3) == 1
    assert next_untranslated_region([{"translation": "Done"}], 0) is None
    assert next_untranslated_region([], 0) is None


def test_inpaint_signature_ignores_translation_but_tracks_mask_and_model(tmp_path):
    source = tmp_path / "page.png"
    source.write_bytes(b"source image bytes")
    mask = np.zeros((32, 32), dtype=np.uint8)
    mask[8:14, 12:20] = 255
    cfg = fake_config()
    a = workspace_inpaint_signature(
        str(source), mask, cfg, "cpu", [{"translation": "Xin chào"}]
    )
    b = workspace_inpaint_signature(
        str(source), mask.copy(), cfg, "cpu", [{"translation": "Tạm biệt"}]
    )
    assert a == b, "Text-only revisions must reuse the same LaMa background"

    mask[8:14, 13:20] = 0
    c = workspace_inpaint_signature(str(source), mask, cfg, "cpu")
    assert c != a, "Changed erase mask must invalidate the background"

    d = workspace_inpaint_signature(str(source), mask, fake_config(1024), "cpu")
    assert d != c, "Fast mode and quality mode must not share stale inpaint"
    e = workspace_inpaint_signature(str(source), mask, fake_config(), "cuda")
    assert e != c

    source.write_bytes(b"new source data; extra bytes")
    f = workspace_inpaint_signature(str(source), mask, cfg, "cpu")
    assert f != c


def test_inpaint_disk_cache_is_safe_and_reusable(tmp_path):
    original = tmp_path / "image.png"
    original.write_bytes(b"original")
    mask = np.zeros((12, 17), dtype=np.uint8)
    mask[2:7, 5:9] = 255
    signature = workspace_inpaint_signature(str(original), mask, fake_config(), "cpu")
    inpainted = tmp_path / "image_inpainted.png"
    inpainted.write_bytes(b"correct image file")
    assert not is_valid_workspace_inpaint_cache(str(inpainted), signature)
    write_workspace_inpaint_cache(str(inpainted), signature)
    assert is_valid_workspace_inpaint_cache(str(inpainted), signature)
    assert not is_valid_workspace_inpaint_cache(str(inpainted), "other model")
    # An overwritten image no longer matches its signed metadata.
    inpainted.write_bytes(b"tampered or re-rendered image")
    assert not is_valid_workspace_inpaint_cache(str(inpainted), signature)
    assert not is_valid_workspace_inpaint_cache(str(tmp_path / "missing.png"), signature)


def test_translation_only_ui_preserves_legacy_typesetting_until_actual_edit(tmp_path):
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtWidgets import QApplication
    from ui.main_page.pages.ocr_workspace_page import OCRWorkspacePanel
    import json

    class FakeState(QObject):
        is_translating_changed = pyqtSignal(bool)
        def is_translating(self):
            return False

    class FakeController(QObject):
        file_sources_changed = pyqtSignal()
        task_completed = pyqtSignal(list)

        def __init__(self):
            super().__init__()
            self.state_manager = FakeState()
            self.source_files = []

        def get_last_open_dir(self):
            return "."

    app = QApplication.instance() or QApplication([])
    panel = OCRWorkspacePanel(
        FakeController(), t_func=lambda key, **kwargs: key.format(**kwargs)
    )
    old = "Tự hỏi Ya[BR]mamoto[BR]muốn gì."
    rich = {"format": "richtext.v1", "blocks": [{"paragraph": "manual"}]}
    try:
        regions = [
            {
                "text": "WONDER WHAT YAMAMOTO WANTS.",
                "translation": old,
                "translation_raw": old,
                "translation_rich": rich,
            },
            {"text": "何", "translation": ""},
        ]
        saved = {"page": {"regions": regions}}
        path = tmp_path / "page_translations.json"
        path.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
        original_bytes = path.read_bytes()
        panel.current_json_path = str(path)
        panel.current_data = saved
        panel.current_regions = regions
        panel._populate_table()
        assert panel.table.currentRow() == 0
        assert panel.manual_translation_edit.toPlainText() == "Tự hỏi Yamamoto muốn gì."
        assert panel.table.item(0, 2).text() == "Tự hỏi Yamamoto muốn gì."
        assert not hasattr(panel, "insert_break_button")
        assert panel._dirty is False
        # Viewing/selection/save without edits must not rewrite old JSON.
        panel._select_next_untranslated_region()
        assert panel.table.currentRow() == 1
        panel._select_next_translation_region()
        assert panel.table.currentRow() == 0
        assert panel.save_current(silent=True)
        assert path.read_bytes() == original_bytes
        assert regions[0]["translation"] == old
        assert regions[0]["translation_rich"] == rich

        field = panel.manual_translation_edit
        field.setPlainText("Tự hỏi Yamamoto muốn gì chứ?")
        assert panel.table.item(0, 2).text() == "Tự hỏi Yamamoto muốn gì chứ?"
        assert panel.current_regions[0]["translation"] == "Tự hỏi Yamamoto muốn gì chứ?"
        assert panel.current_regions[0]["translation_raw"] == "Tự hỏi Yamamoto muốn gì chứ?"
        assert "translation_rich" not in panel.current_regions[0]
        assert field.toPlainText() == "Tự hỏi Yamamoto muốn gì chứ?"
        assert panel._dirty
        assert panel.manual_translation_progress.text() == "1/2 đã dịch"
        assert panel.save_current(silent=True)
        assert not panel._dirty
        assert (tmp_path / "page_translations.json.ocr_workspace.bak").is_file()
        disk = json.loads(path.read_text(encoding="utf-8"))
        assert disk["page"]["regions"][0]["translation"] == "Tự hỏi Yamamoto muốn gì chứ?"

        panel._select_next_untranslated_region()
        assert panel.table.currentRow() == 1
        field.setPlainText("Không!")
        assert panel.current_regions[1]["translation"] == "Không!"
        assert panel.manual_translation_progress.text() == "2/2 đã dịch"
        panel._select_next_translation_region()
        assert panel.table.currentRow() == 0
        assert field.toPlainText() == "Tự hỏi Yamamoto muốn gì chứ?"
    finally:
        panel.close()
        app.processEvents()


def test_plain_translation_entry_does_not_inject_layout_breaks():
    assert translation_plain_for_ui("Đúng r[BR]ồi đó![BR]") == "Đúng rồi đó!"
    assert translation_plain_for_ui(
        "Tự hỏi Ya[BR]mamoto[BR]muốn gì.",
        "WONDER WHAT YAMAMOTO WANTS.",
    ) == "Tự hỏi Yamamoto muốn gì."
    assert translation_plain_for_ui(
        "Chắc cũng chỉ là[BR]mấy trò nhảm nhí[BR]thường thấy của[BR]mấy gã trai tán thôi."
    ) == "Chắc cũng chỉ là mấy trò nhảm nhí thường thấy của mấy gã trai tán thôi."
    assert translation_plain_for_ui("Đúng rồi[BR]đó!") == "Đúng rồi đó!"
    assert translation_input_to_plain("Đúng rồi\nđó!") == "Đúng rồi đó!"
    assert translation_input_to_plain("Đúng rồi[BR]đó!") == "Đúng rồi đó!"
    assert translation_input_to_plain("Xin  chào\tbạn") == "Xin chào bạn"


def test_legacy_manual_break_helpers_remain_available_to_editor():
    assert manual_editor_to_text("Đúng rồi\nđó!") == "Đúng rồi[BR]đó!"
    assert manual_text_to_editor("Đúng rồi[BR]đó!") == "Đúng rồi\nđó!"



def test_manual_autosave_is_debounced_and_never_saves_while_busy():
    from ui.main_page.pages.ocr_workspace_page import OCRWorkspacePanel

    starts = []
    saves = []
    checkbox = SimpleNamespace(isChecked=lambda: True)
    view = SimpleNamespace(
        manual_autosave_checkbox=checkbox,
        current_json_path="existing.json",
        _manual_autosave_timer=SimpleNamespace(start=lambda: starts.append(True)),
        _dirty=True,
        controller=SimpleNamespace(
            state_manager=SimpleNamespace(is_translating=lambda: False)
        ),
        save_current=lambda silent=False: saves.append(silent) or True,
    )
    OCRWorkspacePanel._schedule_manual_autosave(view)
    assert starts == [True]
    OCRWorkspacePanel._autosave_manual_translation(view)
    assert saves == [True]
    view.controller.state_manager.is_translating = lambda: True
    OCRWorkspacePanel._autosave_manual_translation(view)
    assert saves == [True]
    view.manual_autosave_checkbox = SimpleNamespace(isChecked=lambda: False)
    OCRWorkspacePanel._schedule_manual_autosave(view)
    assert starts == [True]
