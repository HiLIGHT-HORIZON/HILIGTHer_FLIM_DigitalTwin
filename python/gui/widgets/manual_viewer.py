import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import QUrl, Qt

class ManualWidget(QWidget):
    """
    A persistent side-panel widget that displays the interactive HTML manual.
    Supports context-aware jumping to specific sections using URL fragments.
    """
    def __init__(self, manual_path: str):
        super().__init__()
        self.manual_path = manual_path
        self.setWindowTitle("Interactive Manual")
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.resize(1180, 860)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.browser = None
        self._pending_fragment = None

    def _ensure_browser(self):
        if self.browser is not None:
            return
        from PyQt6.QtWebEngineWidgets import QWebEngineView

        self.browser = QWebEngineView()
        self._layout.addWidget(self.browser)
        if os.path.exists(self.manual_path):
            base_url = QUrl.fromLocalFile(self.manual_path)
            if self._pending_fragment:
                base_url.setFragment(self._pending_fragment)
            self.browser.setUrl(base_url)
        else:
            self.browser.setHtml("<html><body style='background:#0f172a; color:white; padding:20px;'>Manual not found.</body></html>")

    def showEvent(self, event):
        self._ensure_browser()
        super().showEvent(event)

    def scroll_to_section(self, section_id: str):
        """Jumps to a specific section in the manual via #anchor."""
        self._pending_fragment = section_id
        if os.path.exists(self.manual_path):
            self._ensure_browser()
            fragment_url = QUrl.fromLocalFile(self.manual_path)
            fragment_url.setFragment(section_id)
            if self.browser is not None:
                self.browser.setUrl(fragment_url)
