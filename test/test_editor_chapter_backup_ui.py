"""Editor whole-chapter backup uses UI Save, dialog and background queue safely."""
import _bootstrap  # noqa: F401

from types import SimpleNamespace

from ui.editor.view import EditorView


class _FakeToast:
    def __init__(self):
        self.errors = []

    def show_error(self, message, *_args):
        self.errors.append(message)


def _fake_editor(image, backup_func, *, save_result=True):
    calls = []
    toast = _FakeToast()
    fake = SimpleNamespace(
        logic=SimpleNamespace(
            file_model=SimpleNamespace(files=[
                SimpleNamespace(path=str(image)),
                SimpleNamespace(path=str(image.parent / "002.png")),
            ]),
            _source_folders={str(image.parent): str(image.parent)},
        ),
        model=SimpleNamespace(get_source_image_path=lambda: str(image)),
        controller=SimpleNamespace(
            get_toast_manager=lambda: toast,
            export_service=SimpleNamespace(backup_chapter_folder=backup_func),
        ),
        save_editor_state=lambda: calls.append("save-active-page") or save_result,
    )
    return fake, calls, toast


def test_user_selected_folder_saves_active_page_before_batch_copy(monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QFileDialog

    selected = tmp_path / "backup_destination"
    selected.mkdir()
    source = tmp_path / "chapter"
    source.mkdir()
    image = source / "001.png"
    image.write_bytes(b"original")
    seen = []
    fake, calls, _ = _fake_editor(
        image,
        lambda pages, target, **kwargs: seen.append(
            (list(pages), target, kwargs)
        ) or True,
    )
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory",
        lambda *_args, **_kwargs: str(selected),
    )
    assert EditorView.backup_chapter_folder(fake)
    assert calls == ["save-active-page"]
    assert seen == [(
        [str(image), str(source / "002.png")],
        str(selected),
        {"source_folders": (str(source),)},
    )]


def test_cancel_folder_picker_does_not_save_or_copy(monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QFileDialog

    image = tmp_path / "page.png"
    image.touch()
    calls = []
    fake, saved, _ = _fake_editor(
        image, lambda *_a, **_k: calls.append(True) or True,
    )
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_a, **_k: "")
    assert not EditorView.backup_chapter_folder(fake)
    assert not saved
    assert not calls


def test_failed_current_page_save_blocks_whole_folder_backup(monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QFileDialog

    image = tmp_path / "page.png"
    image.touch()
    calls = []
    fake, saved, _ = _fake_editor(
        image,
        lambda *_a, **_k: calls.append(True) or True,
        save_result=False,
    )
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory",
        lambda *_a, **_k: str(tmp_path),
    )
    assert not EditorView.backup_chapter_folder(fake)
    assert saved == ["save-active-page"]
    assert calls == []


def test_no_pages_disables_backup_gracefully():
    toast = _FakeToast()
    fake = SimpleNamespace(
        logic=SimpleNamespace(file_model=SimpleNamespace(files=[])),
        controller=SimpleNamespace(get_toast_manager=lambda: toast),
    )
    assert not EditorView.backup_chapter_folder(fake)
    assert "Không có trang" in toast.errors[0]
