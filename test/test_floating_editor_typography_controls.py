"""Regression checks for explicit dialogue breaks and in-place text controls."""
import _bootstrap  # noqa: F401

from types import SimpleNamespace

from desktop_qt_ui.editor.rich_text_editor_state import RichTextEditorState
from desktop_qt_ui.ui.editor.view import EditorView
from desktop_qt_ui.ui.widgets.rich_text_floating_editor import (
    RichTextFloatingEditor,
)


class Recorder:
    def __init__(self):
        self.sent = []

    def emit(self, *args):
        self.sent.append(args)


def test_manual_break_is_saved_as_br_and_rich_paragraph():
    state = RichTextEditorState()
    state.bind_region(4, {"translation": "Đúng rồi đó!", "font_size": 23})
    assert state.apply_qt_contents_change(
        "Đúng rồi\nđó!", len("Đúng rồi"), 0, 1
    )
    payload = state.mark_document_emitted()
    assert payload is not None
    index, doc, stored_text = payload
    assert index == 4
    assert stored_text == "Đúng rồi[BR]đó!"
    assert len(doc["blocks"]) == 2
    assert state.editor_text == "Đúng rồi\nđó!"


def test_quick_font_controls_change_only_bound_bubble():
    state = RichTextEditorState()
    state.bind_region(7, {"translation": "Xin chào", "font_size": 21})
    sent = Recorder()
    editor = SimpleNamespace(
        _updating=False,
        _state=state,
        quick_font_combo=SimpleNamespace(currentFamily=lambda: "Arial"),
        region_style_changed=sent,
    )
    RichTextFloatingEditor._on_quick_font_size_changed(editor, 28)
    RichTextFloatingEditor._on_quick_font_changed(editor, 0)
    assert sent.sent == [
        (7, {"font_size": 28}),
        (7, {"font_family": "Arial"}),
    ]


def test_quick_font_controls_do_not_write_during_programmatic_refresh():
    state = RichTextEditorState()
    state.bind_region(7, {"translation": "Xin chào"})
    sent = Recorder()
    editor = SimpleNamespace(
        _updating=True,
        _state=state,
        quick_font_combo=SimpleNamespace(currentFamily=lambda: "Arial"),
        region_style_changed=sent,
    )
    RichTextFloatingEditor._on_quick_font_size_changed(editor, 30)
    RichTextFloatingEditor._on_quick_font_changed(editor, 0)
    assert sent.sent == []


def test_editor_view_rejects_font_updates_to_unselected_regions():
    sent = []
    view = SimpleNamespace(
        model=SimpleNamespace(get_selection=lambda: [2]),
        controller=SimpleNamespace(
            update_region_style_patch=lambda indices, patch: sent.append(
                (indices, patch)
            )
        ),
    )
    EditorView._on_floating_editor_style_changed(view, 5, {"font_size": 80})
    assert sent == []
    EditorView._on_floating_editor_style_changed(view, 2, {"font_size": 36})
    assert sent == [([2], {"font_size": 36})]


def test_manual_break_button_inserts_block_at_cursor_then_flushes():
    calls = []
    class DummyCursor:
        def insertBlock(self):
            calls.append("insertBlock")

    class DummyTextBox:
        def textCursor(self):
            return DummyCursor()

        def setTextCursor(self, cursor):
            calls.append("setTextCursor")

        def setFocus(self):
            calls.append("setFocus")

    state = RichTextEditorState()
    state.bind_region(1, {"translation": "Đúng rồi đó!"})
    editor = SimpleNamespace(
        _state=state,
        text_box=DummyTextBox(),
        flush_pending_changes=lambda: calls.append("flush"),
    )
    RichTextFloatingEditor._insert_manual_line_break(editor)
    assert calls == ["insertBlock", "setTextCursor", "flush", "setFocus"]
