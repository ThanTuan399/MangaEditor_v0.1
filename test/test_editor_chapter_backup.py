"""Portable whole-folder backups must preserve all Editor state and source files."""
import _bootstrap  # noqa: F401

import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from editor.chapter_backup import save_chapter_folder

_DATE = datetime(2026, 11, 22, 1, 30, 0)


def _make_chapter(folder: Path, *, page: str = "001.png", export_dir=None):
    folder.mkdir(parents=True, exist_ok=True)
    image = folder / page
    image.write_bytes(b"original-image")
    json_path = (
        folder / "manga_translator_work" / "json"
        / (image.stem + "_translations.json")
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    region = {
        "translation": "CHỮ ĐÃ SỬA",
        "font_size": 42,
        "font_family": "Comic",
        "white_frame_rect_local": [1, 2, 80, 99],
        "has_custom_white_frame": True,
        "translation_rich": {
            "format": "richtext.v1",
            "blocks": [{
                "type": "paragraph",
                "inlines": [
                    {"type": "text", "text": "CHỮ ĐÃ SỬA", "style": {"bold": True}}
                ],
            }],
        },
    }
    page_data = {"regions": [region], "mask_raw": "base64-test-mask", "paint_overlay": "base64-test-paint"}
    if export_dir:
        page_data["last_export_dir"] = os.fspath(export_dir)
    json_path.write_text(
        json.dumps({os.fspath(image.resolve()): page_data}, ensure_ascii=False),
        encoding="utf-8",
    )
    inpaint = folder / "manga_translator_work" / "inpainted" / (image.stem + "_inpainted.png")
    inpaint.parent.mkdir(parents=True, exist_ok=True)
    inpaint.write_bytes(b"clean-background")
    return image, json_path, page_data


def test_backup_makes_one_portable_reopenable_folder_with_all_state(tmp_path):
    source = tmp_path / "nguon" / "tap 7"
    a, a_json, a_data = _make_chapter(source, page="001.png")
    b, b_json, _ = _make_chapter(source, page="002.png")
    (source / "translator_notes.txt").write_text("Do not lose my annotations", encoding="utf-8")
    target_parent = tmp_path / "backup"
    target_parent.mkdir()

    result = save_chapter_folder(
        [os.fspath(a), os.fspath(b)], os.fspath(target_parent),
        source_folders=[os.fspath(source)], created_at=_DATE,
    )
    backup = Path(result.folder)
    assert backup.name == "MangaEditor_Chapter_20261122_013000"
    assert result.pages == 2
    assert result.groups == 1
    assert (backup / "001.png").read_bytes() == b"original-image"
    assert (backup / "002.png").read_bytes() == b"original-image"
    assert (backup / "translator_notes.txt").read_text(encoding="utf-8") == "Do not lose my annotations"
    assert (backup / "manga_translator_work" / "inpainted" / "001_inpainted.png").read_bytes() == b"clean-background"

    saved_json = json.loads(
        (backup / "manga_translator_work" / "json" / "001_translations.json").read_text(encoding="utf-8")
    )
    assert saved_json == {os.fspath(backup / "001.png"): a_data}
    assert saved_json[os.fspath(backup / "001.png")]["regions"][0]["font_size"] == 42
    assert saved_json[os.fspath(backup / "001.png")]["regions"][0]["translation_rich"]["blocks"][0]["inlines"][0]["style"]["bold"]
    assert json.loads(a_json.read_text(encoding="utf-8"))[os.fspath(a.resolve())] == a_data
    assert b_json.exists()

    manifest = json.loads((backup / "mangaeditor_backup_manifest.json").read_text(encoding="utf-8"))
    assert manifest["page_count"] == 2
    assert set(manifest["pages"]) == {"001.png", "002.png"}


def test_backup_includes_recorded_external_exports_without_leaking_old_path(tmp_path):
    exported = tmp_path / "older_exports"
    exported.mkdir()
    (exported / "page.png").write_bytes(b"translated")
    source = tmp_path / "pages"
    image, _, data = _make_chapter(source, page="page.png", export_dir=exported)
    destination = tmp_path / "archive"
    destination.mkdir()

    result = save_chapter_folder([str(image)], str(destination), created_at=_DATE)
    backup = Path(result.folder)
    assert result.external_exports == 1
    output = backup / "manga_translator_work" / "result" / "page.png"
    assert output.read_bytes() == b"translated"
    stored = json.loads(
        (backup / "manga_translator_work" / "json" / "page_translations.json").read_text(encoding="utf-8")
    )
    assert stored[str(backup / "page.png")]["last_export_dir"] == str(output.parent)
    assert data["last_export_dir"] == str(exported)


def test_backup_groups_unrelated_folders_without_copying_common_drive_parent(tmp_path):
    a, _, _ = _make_chapter(tmp_path / "a", page="same.png")
    b, _, _ = _make_chapter(tmp_path / "b", page="same.png")
    (tmp_path / "unrelated-private-file.txt").write_text("not part of manga")
    output = tmp_path / "out"
    output.mkdir()
    result = save_chapter_folder([str(a), str(b)], str(output), created_at=_DATE)
    backup = Path(result.folder)
    assert result.groups == 2
    assert (backup / "chapters" / "01_a" / "same.png").is_file()
    assert (backup / "chapters" / "02_b" / "same.png").is_file()
    assert not (backup / "unrelated-private-file.txt").exists()


def test_backup_rejects_recursive_destination_without_touching_sources(tmp_path):
    image, src_json, _ = _make_chapter(tmp_path / "sources")
    original = src_json.read_bytes()
    with pytest.raises(ValueError, match="outside"):
        save_chapter_folder([str(image)], str(image.parent), created_at=_DATE)
    assert src_json.read_bytes() == original
    assert not (image.parent / "MangaEditor_Chapter_20261122_013000").exists()


def test_repeated_backups_never_replace_previous_snapshot(tmp_path):
    source = tmp_path / "manga"
    image, _, _ = _make_chapter(source)
    dest = tmp_path / "saves"
    dest.mkdir()
    first = save_chapter_folder([str(image)], str(dest), created_at=_DATE)
    first_backup = Path(first.folder)
    (first_backup / "keep.txt").write_text("first snapshot")
    second = save_chapter_folder([str(image)], str(dest), created_at=_DATE)
    assert Path(second.folder).name.endswith("_2")
    assert (first_backup / "keep.txt").read_text() == "first snapshot"


def test_failure_removes_partial_staging_not_originals(tmp_path, monkeypatch):
    from editor import chapter_backup

    source = tmp_path / "source"
    image, json_path, _ = _make_chapter(source)
    out = tmp_path / "backups"
    out.mkdir()
    original = json_path.read_bytes()

    def fail_rewrite(*_args):
        raise IOError("copy interrupted")

    monkeypatch.setattr(chapter_backup, "_relocate_json", fail_rewrite)
    with pytest.raises(IOError, match="interrupted"):
        save_chapter_folder([str(image)], str(out), created_at=_DATE)
    assert list(out.iterdir()) == []
    assert json_path.read_bytes() == original
