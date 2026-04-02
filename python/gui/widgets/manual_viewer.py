import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, QSizePolicy
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QUrl, Qt

class ManualWidget(QWidget):
    """
    A persistent side-panel widget that displays the interactive HTML manual.
    Supports context-aware jumping to specific sections using URL fragments.
    """
    def __init__(self, manual_path: str):
        super().__init__()
        self.manual_path = manual_path
        self.manual_dir = os.path.dirname(manual_path)
        self.setWindowTitle("Interactive Manual")
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.resize(1180, 860)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._toolbar = QWidget()
        self._toolbar.setFixedHeight(46)
        self._toolbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._toolbar.setStyleSheet(
            "QWidget { background:#0b1725; border-bottom:1px solid #22384c; }"
            "QPushButton { background:#12324a; color:#e8eef7; border:1px solid #2b5877; border-radius:8px; padding:4px 10px; }"
            "QPushButton:hover { background:#184160; }"
            "QLineEdit { background:#08111b; color:#e8eef7; border:1px solid #29435b; border-radius:8px; padding:5px 10px; }"
            "QLabel { color:#dbe7f3; }"
        )
        self._toolbar_layout = QHBoxLayout(self._toolbar)
        self._toolbar_layout.setContentsMargins(10, 6, 10, 6)
        self._toolbar_layout.setSpacing(6)
        self.logo_label = QLabel()
        logo_path = os.path.abspath(
            os.path.join(self.manual_dir, "..", "..", "python", "frontend", "assets", "logo_icon.png")
        )
        if os.path.exists(logo_path):
            self.logo_label.setPixmap(QPixmap(logo_path).scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.brand_label = QLabel("<b>HILIGHTer Manual</b> <span style='color:#8fb4d8;'>support browser</span>")
        self.btn_home = QPushButton("Home")
        self.btn_back = QPushButton("Back")
        self.btn_forward = QPushButton("Forward")
        self.btn_reload = QPushButton("Reload")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search the manual...")
        self.btn_search = QPushButton("Search")
        self.lbl_hint = QLabel("<span style='color:#9eb2c8;'>Ctrl+H</span>")
        for btn in (self.btn_home, self.btn_back, self.btn_forward, self.btn_reload, self.btn_search):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(28)
        self.search_edit.setFixedHeight(28)
        self._toolbar_layout.addWidget(self.logo_label)
        self._toolbar_layout.addWidget(self.brand_label)
        self._toolbar_layout.addSpacing(10)
        self._toolbar_layout.addWidget(self.btn_home)
        self._toolbar_layout.addWidget(self.btn_back)
        self._toolbar_layout.addWidget(self.btn_forward)
        self._toolbar_layout.addWidget(self.btn_reload)
        self._toolbar_layout.addSpacing(6)
        self._toolbar_layout.addWidget(self.search_edit, 1)
        self._toolbar_layout.addWidget(self.btn_search)
        self._toolbar_layout.addSpacing(6)
        self._toolbar_layout.addWidget(self.lbl_hint)
        self._layout.addWidget(self._toolbar)
        self.browser = None
        self._pending_fragment = None
        self._section_routes = {
            "intro": ("index.html", "intro"),
            "controller": ("controller.html", "controller"),
            "simulation": ("mc-image-validation.html", "mc-image-validation"),
            "math": ("maths.html", "maths"),
            "fisher": ("run-analysis.html", "fisher-information"),
            "tutorial": ("tutorial.html", None),
            "api": ("apis.html", None),
            "mcp": ("mcp.html", None),
        }
        self.btn_home.clicked.connect(self.open_home)
        self.btn_back.clicked.connect(lambda: self.browser.back() if self.browser is not None else None)
        self.btn_forward.clicked.connect(lambda: self.browser.forward() if self.browser is not None else None)
        self.btn_reload.clicked.connect(lambda: self.browser.reload() if self.browser is not None else None)
        self.btn_search.clicked.connect(self.open_search)
        self.search_edit.returnPressed.connect(self.open_search)

    def _build_manual_url(self, filename: str, fragment: str | None = None, query: str | None = None) -> QUrl:
        url = QUrl.fromLocalFile(os.path.join(self.manual_dir, filename))
        if query:
            url.setQuery(query)
        if fragment:
            url.setFragment(fragment)
        return url

    def open_home(self):
        self._ensure_browser()
        if self.browser is not None:
            self.browser.setUrl(self._build_manual_url("index.html"))

    def open_search(self):
        query = self.search_edit.text().strip()
        self._ensure_browser()
        if self.browser is not None:
            q = f"q={QUrl.toPercentEncoding(query).data().decode('ascii')}" if query else ""
            self.browser.setUrl(self._build_manual_url("search.html", query=q))

    def _ensure_browser(self):
        if self.browser is not None:
            return
        from PyQt6.QtWebEngineWidgets import QWebEngineView

        self.browser = QWebEngineView()
        self._layout.addWidget(self.browser)
        if os.path.exists(self.manual_path):
            base_url = QUrl.fromLocalFile(self.manual_path)
            if self._pending_fragment:
                route = self._section_routes.get(self._pending_fragment)
                if route is not None:
                    base_url = self._build_manual_url(route[0], route[1])
                else:
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
            route = self._section_routes.get(section_id)
            if route is not None:
                fragment_url = self._build_manual_url(route[0], route[1])
            else:
                fragment_url = QUrl.fromLocalFile(self.manual_path)
                fragment_url.setFragment(section_id)
            if self.browser is not None:
                self.browser.setUrl(fragment_url)
