"""Whole-chapter Save must include freshly rendered, translated page images."""
import _bootstrap  # noqa: F401

import json
from pathlib import Path

import pytest
from PIL import Image

from editor.chapter_backup import save_chapter_folder
from editor.chapter_render import render_saved_chapter_page


def _page(source: Path, name: str, *, translated: bool = True) -> Path:
    source.mkdir(parents=True, exist_ok=True)
    path = source / name
    Image.new("RGB", (16, 12), "white").save(path)
    if translated:
        work = source / "manga_translator_work" / "json"
        work.mkdir(parents=True, exist_ok=True)
        (work / f"{path.stem}_translations.json").write_text(
            json.dumps({
                str(path.resolve()): {
                    "regions": [{"translation": "ĐÃ DỊCH", "font_size": 30}],
                }
            }, ensure_ascii=False), encoding="utf-8",
        )
    return path


def _fake_render_calls():
    calls = []

    def render(image, target, config, *, image_key=None):
        assert config["render"]["font_family"] == "Comic"
        assert image_key
        calls.append((image, target, image_key))
        with Image.open(image) as original:
            result = original.convert("RGB")
            result.putpixel((0, 0), (255, 0, 0))
            result.save(target)
        return target

    return calls, render


def test_save_entire_chapter_contains_freshly_rendered_edited_images(tmp_path):
    chapter = tmp_path / "chapter"
    a = _page(chapter, "001.png")
    b = _page(chapter, "002.jpg")
    destination = tmp_path / "backup"
    destination.mkdir()
    calls, fake_renderer = _fake_render_calls()
    result = save_chapter_folder(
        [str(a), str(b)], str(destination),
        source_folders=[str(chapter)],
        render_config={"render": {"font_family": "Comic"}},
        render_page=fake_renderer,
    )
    assert len(calls) == 2
    assert result.rendered_pages == 2
    assert result.unchanged_pages == 0
    rendered = Path(result.rendered_directory)
    assert rendered == Path(result.folder) / "manga_translator_work" / "anh_da_chinh_sua"
    assert (rendered / "001.png").exists()
    assert (rendered / "002.png").exists()
    for path in [rendered / "001.png", rendered / "002.png"]:
        with Image.open(path) as final:
            assert final.getpixel((0, 0)) == (255, 0, 0)
    with Image.open(a) as raw:
        assert raw.getpixel((0, 0)) == (255, 255, 255)
    with Image.open(Path(result.folder) / "001.png") as backed_up_raw:
        assert backed_up_raw.getpixel((0, 0)) == (255, 255, 255)
    manifest = json.loads(
        (Path(result.folder) / "mangaeditor_backup_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["rendered_count"] == 2
    assert len(manifest["rendered_pages"]) == 2
    assert {p["status"] for p in manifest["rendered_pages"]} == {"rendered"}
    assert all((Path(result.folder) / p["output"]).exists() for p in manifest["rendered_pages"])
    assert all(image_key.startswith(result.folder) for _, _, image_key in calls)


def test_page_without_saved_project_is_explicitly_marked_unedited(tmp_path):
    folder = tmp_path / "source"
    edited = _page(folder, "a.png")
    untouched = _page(folder, "b.png", translated=False)
    destination = tmp_path / "backup"
    destination.mkdir()
    calls, renderer = _fake_render_calls()
    result = save_chapter_folder(
        [str(edited), str(untouched)], str(destination),
        render_config={"render": {"font_family": "Comic"}},
        render_page=renderer,
    )
    assert len(calls) == 1
    assert result.rendered_pages == 1
    assert result.unchanged_pages == 1
    with Image.open(Path(result.rendered_directory) / "b.png") as image:
        assert image.getpixel((0, 0)) == (255, 255, 255)
    manifest = json.loads(
        (Path(result.folder) / "mangaeditor_backup_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["unchanged_count"] == 1
    assert sorted(p["status"] for p in manifest["rendered_pages"]) == ["rendered", "unchanged"]


def test_render_error_aborts_full_backup_without_publishing_originals(tmp_path):
    folder = tmp_path / "chapter"
    image = _page(folder, "001.png")
    destination = tmp_path / "backup"
    destination.mkdir()

    def fail(*_args, **_kwargs):
        raise RuntimeError("Renderer failed to draw the text")

    with pytest.raises(RuntimeError, match="Renderer failed"):
        save_chapter_folder(
            [str(image)], str(destination),
            render_config={"render": {}}, render_page=fail,
        )
    assert list(destination.iterdir()) == []
    assert image.is_file()


def test_same_image_stem_different_extensions_do_not_overwrite(tmp_path):
    folder = tmp_path / "source"
    a = _page(folder, "same.png")
    b = _page(folder, "same.jpg")
    destination = tmp_path / "backup"
    destination.mkdir()
    _, renderer = _fake_render_calls()
    result = save_chapter_folder(
        [str(a), str(b)], str(destination),
        render_config={"render": {"font_family": "Comic"}},
        render_page=renderer,
    )
    image_names = sorted(p.name for p in Path(result.rendered_directory).glob("*.png"))
    assert image_names == ["same.png", "same_jpg.png"]


def test_actual_editor_job_is_constructed_from_saved_edits(tmp_path, monkeypatch):
    """Exercise the real loader / job construction, mocking only expensive GPU render."""
    from editor import chapter_render
    from services.export_service import BackendExportResult, ExportService

    source = tmp_path / "page.png"
    Image.new("RGB", (16, 12), "white").save(source)
    target = tmp_path / "output.png"
    region = {
        "translation": "BẢN ĐÃ SỬA",
        "font_size": 33,
        "font_family": "Comic",
        "center": [8, 6],
        "white_frame_rect_local": [-6, -5, 6, 5],
        "has_custom_white_frame": True,
    }
    seen = {}

    def load_json(_self, image_path, image=None, *, image_key_override=None):
        seen["key"] = image_key_override
        return [region], None, None, {}

    def no_repair(_regions, _size, mask):
        return mask, False

    def fake_execute(self, job):
        assert job.regions[0]["translation"] == "BẢN ĐÃ SỬA"
        assert job.regions[0]["font_size"] == 33
        assert job.regions[0]["font_family"] == "Comic"
        assert job.export_base.kind == "source"
        assert job.output_path == str(target)
        with Image.open(job.source_path) as image:
            colored = image.convert("RGB")
            colored.putpixel((1, 1), (200, 50, 25))
            colored.save(job.output_path)
        return BackendExportResult()

    monkeypatch.setattr(chapter_render.FileService, "load_translation_json", load_json)
    from manga_translator.mask_refinement import region_polygon_mask
    monkeypatch.setattr(region_polygon_mask, "repair_missing_translation_masks", no_repair)
    monkeypatch.setattr(ExportService, "execute_export_job", fake_execute)
    render_saved_chapter_page(
        str(source), str(target),
        {"render": {"font_family": "Comic"}}, image_key=str(tmp_path / "final" / "page.png"),
    )
    assert seen["key"] == str(tmp_path / "final" / "page.png")
    assert target.is_file()
    with Image.open(target) as result:
        assert result.getpixel((1, 1)) == (200, 50, 25)
