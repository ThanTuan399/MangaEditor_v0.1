"""Regression tests for OCR Workspace -> multi-page editor handoff."""
import _bootstrap  # noqa: F401

from types import SimpleNamespace

import pytest

from desktop_qt_ui.editor.editor_logic import EditorLogic
from desktop_qt_ui.ui.main_page.pages.ocr_project_registry import OCRProjectRegistry
from desktop_qt_ui.ui.editor.view import EditorView
from desktop_qt_ui.ui.main_window import MainWindow


def _editor_logic_stub():
    # Follow the headless Qt tests: avoid a full EditorController and GPU load.
    logic = EditorLogic.__new__(EditorLogic)
    logic._source_paths = []
    logic._source_keys = set()
    logic._source_folders = {}
    logic._excluded_folders = set()
    logic._excluded_files = set()
    logic._source_by_key = {}
    logic._pending_load_path = None
    logic._load_first_after_snapshot = False
    requested = []
    logic._request_snapshot = lambda: requested.append(tuple(logic._source_paths))
    return logic, requested


def test_open_ocr_project_uses_only_its_registered_images(tmp_path):
    project = tmp_path / "Chapter 01"
    nested = project / "another registered project"
    nested.mkdir(parents=True)
    first, second = project / "001.webp", project / "002.webp"
    for file in (first, second, nested / "003.webp"):
        file.write_bytes(b"test")

    logic, requested = _editor_logic_stub()
    logic.open_project_folder(
        str(project), str(second), project_images=[str(first), str(second)]
    )

    assert requested == [(str(first), str(second))]
    assert logic._pending_load_path == str(second)
    assert logic._source_folders == {}
    assert not any("003.webp" in image for image in requested[0])


def test_invalid_selected_page_does_not_escape_ocr_project(tmp_path):
    project = tmp_path / "Chapter"
    outside = tmp_path / "other.webp"
    project.mkdir()
    first = project / "001.webp"
    first.write_bytes(b"image")
    outside.write_bytes(b"other")

    logic, requested = _editor_logic_stub()
    logic.open_project_folder(
        str(project), str(outside), project_images=[str(first), str(outside)]
    )

    assert requested == [(str(first),)]
    assert logic._pending_load_path == str(first)
    with pytest.raises(ValueError):
        logic.open_project_folder(str(project), project_images=[str(outside)])


def test_editor_adjacent_page_does_not_wrap(tmp_path):
    page1 = str(tmp_path / "001.webp")
    page2 = str(tmp_path / "002.webp")
    page3 = str(tmp_path / "003.webp")
    logic, _ = _editor_logic_stub()
    logic.file_model = SimpleNamespace(
        files=[SimpleNamespace(path=p) for p in (page1, page2, page3)]
    )
    current = [page2]
    logic.controller = SimpleNamespace(
        model=SimpleNamespace(get_source_image_path=lambda: current[0])
    )
    loaded = []
    logic.load_image_into_editor = loaded.append

    assert logic.adjacent_page_path(-1) == page1
    assert logic.adjacent_page_path(1) == page3
    assert logic.navigate_page(1)
    assert loaded == [page3]
    current[0] = page3
    assert logic.adjacent_page_path(1) is None
    assert not logic.navigate_page(1)


def test_last_editor_page_persists_without_rendering_again(tmp_path):
    app_root = tmp_path / "app"
    project = tmp_path / "Tập 1"
    project.mkdir()
    page = project / "006.webp"
    page.write_bytes(b"fake")
    stranger = tmp_path / "stranger.webp"
    stranger.write_bytes(b"fake")

    registry = OCRProjectRegistry(app_root)
    registry.add(project)
    registry.remember_editor_page(project, page)
    registry.remember_editor_page(project, stranger)

    restarted = OCRProjectRegistry(app_root)
    assert restarted.last_editor_page(project) == str(page)
    page.unlink()
    assert restarted.last_editor_page(project) is None


class _Label:
    def __init__(self):
        self.value = ""
    def setText(self, text):
        self.value = text


class _Button:
    def __init__(self):
        self.enabled = None
    def setEnabled(self, enabled):
        self.enabled = enabled


def test_editor_page_navigation_controls_show_position(tmp_path):
    paths = [str(tmp_path / f"{n:03d}.webp") for n in range(1, 4)]
    fake = SimpleNamespace(
        logic=SimpleNamespace(
            file_model=SimpleNamespace(files=[SimpleNamespace(path=p) for p in paths])
        ),
        model=SimpleNamespace(get_source_image_path=lambda: paths[1]),
        page_position_label=_Label(),
        previous_page_button=_Button(),
        next_page_button=_Button(),
    )
    EditorView._refresh_page_navigation(fake)
    assert fake.page_position_label.value == "2 / 3"
    assert fake.previous_page_button.enabled is True
    assert fake.next_page_button.enabled is True


def test_leaving_editor_saves_dirty_state_and_preserves_clean_state():
    saved = []
    remembered = []
    committed = []
    dirty = [True]
    model = SimpleNamespace(get_source_image_path=lambda: "001.webp")
    controller = SimpleNamespace(
        export_service=SimpleNamespace(has_unsaved_changes=lambda: dirty[0]),
        save_editor_state=lambda: saved.append(True) or True,
        commit_pending_edits=lambda: committed.append(True),
    )
    view = SimpleNamespace(
        force_save_property_panel_edits=lambda: None,
        rich_text_editor=SimpleNamespace(flush_pending_changes=lambda: None),
    )
    window = SimpleNamespace(
        editor_model=model,
        editor_controller=controller,
        editor_view=view,
        _remember_ocr_editor_page=lambda: remembered.append(True),
    )
    assert MainWindow._save_editor_if_modified(window)
    assert len(saved) == len(remembered) == 1

    dirty[0] = False
    assert MainWindow._save_editor_if_modified(window)
    assert len(saved) == 1  # Avoid needlessly rewriting JSON and invalidating cache.
    assert len(remembered) == 2
    assert len(committed) == 2


def test_editor_reopen_uses_last_project_page_not_initial_ocr_selection(tmp_path):
    project = tmp_path / "chapter"
    project.mkdir()
    first = project / "001.webp"
    last = project / "006.webp"
    first.touch()
    last.touch()

    calls = []
    panel = SimpleNamespace(
        projects=SimpleNamespace(
            active=str(project),
            last_editor_page=lambda folder: str(last),
        ),
        image_paths=[str(first), str(last)],
        current_image_path=str(first),
    )
    fake = SimpleNamespace(
        main_view=SimpleNamespace(ocr_workspace_panel=panel),
        _save_editor_if_modified=lambda: True,
        _ensure_editor_initialized=lambda: None,
        editor_logic=SimpleNamespace(
            open_project_folder=lambda *a, **kw: calls.append((a, kw))
        ),
        editor_view=object(),
        switchTo=lambda view: None,
    )
    MainWindow._open_ocr_project_in_editor(fake)
    assert calls == [
        ((str(project), str(last)), {"project_images": [str(first), str(last)]})
    ]
    assert fake._active_ocr_editor_project == str(project)


def test_editor_explicit_selection_takes_priority_over_resume(tmp_path):
    project = tmp_path / "chapter"
    project.mkdir()
    first = project / "001.webp"
    last = project / "006.webp"
    first.touch()
    last.touch()
    selected = []
    panel = SimpleNamespace(
        projects=SimpleNamespace(
            active=str(project),
            last_editor_page=lambda folder: str(last),
        ),
        image_paths=[str(first), str(last)],
        current_image_path=str(last),
    )
    fake = SimpleNamespace(
        main_view=SimpleNamespace(ocr_workspace_panel=panel),
        _save_editor_if_modified=lambda: True,
        _ensure_editor_initialized=lambda: None,
        editor_logic=SimpleNamespace(
            open_project_folder=lambda _folder, page, **kw: selected.append(page)
        ),
        editor_view=object(),
        switchTo=lambda view: None,
    )
    MainWindow._open_ocr_project_in_editor(fake, str(project), str(first))
    assert selected == [str(first)]
