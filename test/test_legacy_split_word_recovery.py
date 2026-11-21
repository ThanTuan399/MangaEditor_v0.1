"""Regression coverage: removing [BR] must not leave broken Vietnamese words."""
import _bootstrap  # noqa: F401

from copy import deepcopy

from manga_translator.rendering.legacy_word_recovery import (
    recover_split_words,
    repair_editor_region_list,
    repair_editor_region_split_words,
)
from manga_translator.rendering.rich_text import legacy_line_breaks_to_document
from desktop_qt_ui.editor.rich_text_editing import document_from_region
from desktop_qt_ui.ui.main_page.pages.manual_text import translation_plain_for_ui


def test_translation_list_recovers_spaces_left_by_old_br_removal():
    assert translation_plain_for_ui("nè nè, vẫn chưa làm xon g bài tập à?") == (
        "nè nè, vẫn chưa làm xong bài tập à?"
    )
    assert translation_plain_for_ui("chụp giúp ch ị đây mấy bức ảnh nhé!") == (
        "chụp giúp chị đây mấy bức ảnh nhé!"
    )


def test_editor_joins_multiple_split_syllables_and_retains_full_word_breaks():
    value = "còn phần hu[BR]ấn luyện ch[BR]o hôm nay thì sao nhỉ?"
    assert recover_split_words(value) == (
        "còn phần huấn luyện cho hôm nay thì sao nhỉ?"
    )
    assert translation_plain_for_ui(value) == (
        "còn phần huấn luyện cho hôm nay thì sao nhỉ?"
    )
    assert recover_split_words("Đúng rồi[BR]đó!") == "Đúng rồi[BR]đó!"
    assert recover_split_words("Tôi[BR]ở đây") == "Tôi[BR]ở đây"
    assert recover_split_words("tôi đang học") == "tôi đang học"


def test_legacy_named_person_joined_using_original_ocr():
    assert translation_plain_for_ui(
        "Tự hỏi Ya[BR]mamoto[BR]muốn gì.",
        "WONDER WHAT YAMAMOTO WANTS.",
    ) == "Tự hỏi Yamamoto muốn gì."


def test_editor_cleans_plain_rich_paragraphs_only_when_split_is_certain():
    old = "còn phần hu[BR]ấn luyện ch[BR]o hôm nay thì sao nhỉ?"
    rich = legacy_line_breaks_to_document(old).to_dict()
    region = {
        "translation": old,
        "translation_raw": old,
        "translation_rich": rich,
        "target_lang": "VIN",
        "text": "ねえ",
    }
    assert repair_editor_region_split_words(region)
    assert region["translation"] == (
        "còn phần huấn luyện cho hôm nay thì sao nhỉ?"
    )
    assert region["translation_raw"] == region["translation"]
    assert "translation_rich" not in region
    # The floating Rich Text editor must no longer show the old paragraphs.
    document = document_from_region(region)
    assert len(document["blocks"]) == 1


def test_editor_recovers_space_corruption_without_br_and_no_styled_document():
    region = {
        "target_lang": "VIN",
        "translation": "nè nè, vẫn chưa làm xon g bài tập à?",
    }
    assert repair_editor_region_split_words(region)
    assert region["translation"] == "nè nè, vẫn chưa làm xong bài tập à?"


def test_editor_does_not_discard_intentional_breaks_or_styled_runs():
    manual = {
        "target_lang": "VIN",
        "translation": "Đúng rồi[BR]đó!",
        "translation_rich": legacy_line_breaks_to_document("Đúng rồi[BR]đó!").to_dict(),
    }
    untouched = deepcopy(manual)
    assert not repair_editor_region_split_words(manual)
    assert manual == untouched

    styled = {
        "target_lang": "VIN",
        "translation": "hu[BR]ấn luyện",
        "translation_rich": legacy_line_breaks_to_document("hu[BR]ấn luyện").to_dict(),
    }
    styled["translation_rich"]["blocks"][0]["inlines"][0]["style"] = {"bold": True}
    original = deepcopy(styled)
    assert not repair_editor_region_split_words(styled)
    assert styled == original

    japanese = {"target_lang": "JPN", "translation": "hu[BR]ấn luyện"}
    assert not repair_editor_region_split_words(japanese)


def test_editor_repair_list_is_idempotent():
    cases = [
        {"target_lang": "VIN", "translation": "xon g"},
        {"target_lang": "VIN", "translation": "ch ị"},
        {"target_lang": "VIN", "translation": "Đúng rồi[BR]đó!"},
    ]
    assert repair_editor_region_list(cases) == 2
    assert repair_editor_region_list(cases) == 0
    assert [r["translation"] for r in cases] == [
        "xong", "chị", "Đúng rồi[BR]đó!"
    ]
