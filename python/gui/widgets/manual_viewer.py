import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl

class ManualWidget(QWidget):
    """
    A persistent side-panel widget that displays the interactive HTML manual.
    Supports context-aware jumping to specific sections using URL fragments.
    """
    def __init__(self, manual_path: str):
        super().__init__()
        self.manual_path = manual_path
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        
        # Load the base manual
        if os.path.exists(self.manual_path):
            self.browser.setUrl(QUrl.fromLocalFile(self.manual_path))
        else:
            self.browser.setHtml("<html><body style='background:#0f172a; color:white; padding:20px;'>Manual not found.</body></html>")

    def scroll_to_section(self, section_id: str):
        """Jumps to a specific section in the manual via #anchor."""
        if os.path.exists(self.manual_path):
            fragment_url = QUrl.fromLocalFile(self.manual_path)
            fragment_url.setFragment(section_id)
            self.browser.setUrl(fragment_url)
