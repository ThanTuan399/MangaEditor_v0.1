"""Background local Ollama connection check; never block the Qt UI thread."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from manga_translator.utils.ollama_local import check_ollama_connection


class OllamaProbeThread(QThread):
    result = pyqtSignal(bool, str)

    def __init__(self, base_url: str, model: str, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.model = model

    def run(self):
        try:
            message = check_ollama_connection(self.base_url, self.model, timeout=2.5)
        except (ConnectionError, ValueError) as exc:
            self.result.emit(False, str(exc))
        else:
            self.result.emit(True, message)
