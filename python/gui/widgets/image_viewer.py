import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton


class MapWidget(QWidget):
    pixel_selected = pyqtSignal(int, int)  # y, x

    def __init__(self, title="Image Validation"):
        super().__init__()
        self.current_theme = "dark"
        self._intensity_data = None
        self._lifetime_data = None

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.btn_copy = QPushButton("📋")
        self.btn_copy.setToolTip("Copy screenshot to clipboard")
        self.btn_copy.setMaximumWidth(30)
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        header.addStretch()
        header.addWidget(self.btn_copy)
        layout.addLayout(header)

        row = QHBoxLayout()
        self.intensity_view = self._build_panel("Intensity", self._grey_cmap())
        self.lifetime_view = self._build_panel("Fitted Lifetime", self._lifetime_cmap())
        row.addWidget(self.intensity_view["container"])
        row.addWidget(self.lifetime_view["container"])
        layout.addLayout(row)
        self.set_theme("dark")

    def _grey_cmap(self):
        colors = [(0, 0, 0), (64, 64, 64), (128, 128, 128), (192, 192, 192), (255, 255, 255)]
        return pg.ColorMap(pos=np.linspace(0.0, 1.0, 5), color=colors)

    def _lifetime_cmap(self):
        try:
            return pg.colormap.get("CET-C6")
        except Exception:
            colors = [
                (0, 8, 35),
                (18, 55, 122),
                (46, 125, 50),
                (255, 193, 7),
                (180, 4, 38),
            ]
            return pg.ColorMap(pos=np.linspace(0.0, 1.0, 5), color=colors)

    def _make_view(self, label, cmap):
        view = pg.ImageView()
        view.ui.menuBtn.hide()
        view.ui.roiBtn.hide()
        view.setColorMap(cmap)
        v_line = pg.InfiniteLine(angle=90, movable=False, pen="w")
        h_line = pg.InfiniteLine(angle=0, movable=False, pen="w")
        view.addItem(v_line, ignoreBounds=True)
        view.addItem(h_line, ignoreBounds=True)
        view._cross_v = v_line
        view._cross_h = h_line
        view._panel_label = label
        view.scene.sigMouseClicked.connect(lambda ev, panel=view: self._on_click(panel, ev))
        return view

    def _build_panel(self, label, cmap):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        title = QLabel(label)
        layout.addWidget(title)
        view = self._make_view(label, cmap)
        layout.addWidget(view, 1)
        return {"container": container, "label": title, "view": view}

    def _copy_to_clipboard(self):
        QGuiApplication.clipboard().setPixmap(self.grab())

    def set_theme(self, theme_name):
        self.current_theme = str(theme_name).lower()
        dark = self.current_theme == "dark"
        crosshair_color = "w" if dark else "#111827"
        bg = "#111827" if dark else "#ffffff"
        text = "#e5eefb" if dark else "#0f172a"
        for panel in (self.intensity_view, self.lifetime_view):
            view = panel["view"]
            panel["label"].setStyleSheet(f"color: {text}; font-weight: 600;")
            view.getView().setBackgroundColor(bg)
            view._cross_v.setPen(pg.mkPen(crosshair_color))
            view._cross_h.setPen(pg.mkPen(crosshair_color))

    def set_image(self, data):
        self.set_images(data, data)

    def set_images(self, intensity, lifetime):
        self._intensity_data = None if intensity is None else np.asarray(intensity, dtype=float)
        self._lifetime_data = None if lifetime is None else np.asarray(lifetime, dtype=float)
        if self._intensity_data is not None:
            self.intensity_view["view"].setImage(self._intensity_data.T)
        else:
            self.intensity_view["view"].setImage(np.zeros((1, 1), dtype=float))
        if self._lifetime_data is not None:
            self.lifetime_view["view"].setImage(self._lifetime_data.T)
        else:
            self.lifetime_view["view"].setImage(np.zeros((1, 1), dtype=float))

    def clear_image(self):
        self._intensity_data = None
        self._lifetime_data = None
        self.intensity_view["view"].setImage(np.zeros((1, 1), dtype=float))
        self.lifetime_view["view"].setImage(np.zeros((1, 1), dtype=float))

    def _on_click(self, panel, ev):
        if ev.button() != pg.QtCore.Qt.MouseButton.LeftButton:
            return
        pos = ev.scenePos()
        if not panel.view.sceneBoundingRect().contains(pos):
            return
        mouse_point = panel.view.mapSceneToView(pos)
        x, y = int(mouse_point.x()), int(mouse_point.y())
        if panel is self.intensity_view["view"]:
            active = self._intensity_data
        else:
            active = self._lifetime_data
        if active is None:
            return
        if 0 <= x < active.shape[0] and 0 <= y < active.shape[1]:
            for view in (self.intensity_view["view"], self.lifetime_view["view"]):
                view._cross_v.setPos(mouse_point.x())
                view._cross_h.setPos(mouse_point.y())
            self.pixel_selected.emit(y, x)
