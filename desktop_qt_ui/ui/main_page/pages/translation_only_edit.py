"""A prose-only OCR translation field: not a manga typesetting surface."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QPlainTextEdit

from .manual_text import translation_input_to_plain


class TranslationOnlyEdit(QPlainTextEdit):
    """Enter advances to the next speech region; it never writes a [BR] tag."""

    next_region_requested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.next_region_requested.emit()
            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        if source.hasText():
            self.insertPlainText(translation_input_to_plain(source.text()))
            return
        super().insertFromMimeData(source)
