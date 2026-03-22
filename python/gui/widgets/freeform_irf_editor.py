import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget


class FreeFormIRFEditor(QWidget):
    points_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_theme = "dark"
        self.period_ns = 12.5
        self.selected_index = None
        self.pending_point = None
        self.dragging = False
        self.edit_mode = True
        self.points = np.array([[0.0, 0.0], [12.5, 0.0]], dtype=float)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        info_row = QHBoxLayout()
        
        
        info_row.addStretch(1)
        self.btn_add = QPushButton("Add Point")
        self.btn_delete = QPushButton("Delete Selected")
        self.btn_reset = QPushButton("Reset from Start/FWHM")
        self.btn_copy = QPushButton("📋")
        self.btn_copy.setFixedWidth(32)
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        info_row.addWidget(self.btn_add)
        info_row.addWidget(self.btn_delete)
        info_row.addWidget(self.btn_reset)
        info_row.addWidget(self.btn_copy)
        layout.addLayout(info_row)

        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "Time (ns)")
        self.plot.setLabel("left", "Amplitude")
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setMinimumHeight(130)
        layout.addWidget(self.plot, 1)

        self.curve = self.plot.plot([], [], pen=pg.mkPen("#22c55e", width=2))
        self.scatter = pg.ScatterPlotItem(size=10, brush=pg.mkBrush("#f59e0b"), pen=pg.mkPen("#0f172a", width=1))
        self.plot.addItem(self.scatter)
        self.selected_scatter = pg.ScatterPlotItem(size=14, brush=pg.mkBrush("#ef4444"), pen=pg.mkPen("#ffffff", width=1))
        self.plot.addItem(self.selected_scatter)
        self.pending_scatter = pg.ScatterPlotItem(size=12, brush=pg.mkBrush("#60a5fa"), pen=pg.mkPen("#ffffff", width=1))
        self.plot.addItem(self.pending_scatter)

        self.btn_add.clicked.connect(self.add_pending_point)
        self.btn_delete.clicked.connect(self.delete_selected_point)
        self.btn_reset.clicked.connect(self._emit_reset_requested)

        self.scatter.sigClicked.connect(self._on_point_clicked)
        self.plot.scene().sigMouseClicked.connect(self._on_scene_clicked)
        self.plot.scene().sigMouseMoved.connect(self._on_scene_moved)
        self.set_theme("dark")
        self._refresh_plot()

    def set_edit_mode(self, editable):
        self.edit_mode = bool(editable)
        self.dragging = False
        if not self.edit_mode:
            self.pending_point = None
        self.btn_add.setEnabled(self.edit_mode)
        self.btn_delete.setEnabled(self.edit_mode)
        self.btn_reset.setEnabled(self.edit_mode)
        self._refresh_plot()

    def set_theme(self, theme_name):
        self.current_theme = str(theme_name).lower()
        dark = self.current_theme == "dark"
        bg = "#0a0a0a" if dark else "#ffffff"
        text = "#e5eefb" if dark else "#0f172a"
        grid = "#334155" if dark else "#cbd5e1"
        curve = "#8b5cf6" if dark else "#2563eb"
        self.plot.setBackground(bg)
        for axis_name in ("bottom", "left"):
            axis = self.plot.getAxis(axis_name)
            axis.setTextPen(pg.mkPen(text))
            axis.setPen(pg.mkPen(text))
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.curve.setPen(pg.mkPen(curve, width=2))
        

    def _copy_to_clipboard(self):
        QGuiApplication.clipboard().setPixmap(self.grab())

    def _emit_reset_requested(self):
        self.points_changed.emit()

    def set_period(self, period_ns):
        self.period_ns = max(float(period_ns), 1e-6)
        self._ensure_sorted_points()
        self._refresh_plot()

    def set_points(self, times_ns, amplitudes):
        times = np.asarray(times_ns, dtype=float)
        amps = np.asarray(amplitudes, dtype=float)
        if times.size != amps.size or times.size < 2:
            self.points = np.array([[0.0, 0.0], [self.period_ns, 0.0]], dtype=float)
        else:
            self.points = np.column_stack([times, np.clip(amps, 0.0, 1.0)])
        self.pending_point = None
        self.selected_index = None
        self._ensure_sorted_points()
        self._refresh_plot()

    def get_points(self):
        self._ensure_sorted_points()
        return self.points[:, 0].tolist(), self.points[:, 1].tolist()

    def reset_rectangular(self, start_ns, width_ns, period_ns):
        period_ns = max(float(period_ns), 1e-6)
        start_ns = np.clip(float(start_ns), 0.0, period_ns)
        end_ns = np.clip(start_ns + max(float(width_ns), 0.0), start_ns, period_ns)
        self.period_ns = period_ns
        self.points = np.array(
            [
                [0.0, 0.0],
                [start_ns, 0.0],
                [start_ns, 1.0],
                [end_ns, 1.0],
                [end_ns, 0.0],
                [period_ns, 0.0],
            ],
            dtype=float,
        )
        self.pending_point = None
        self.selected_index = None
        self._ensure_sorted_points()
        self._refresh_plot()

    def add_pending_point(self):
        if (not self.edit_mode) or self.pending_point is None:
            return
        point = np.asarray(self.pending_point, dtype=float)
        self.points = np.vstack([self.points, point])
        self.pending_point = None
        self._ensure_sorted_points()
        self.selected_index = int(np.argmin(np.abs(self.points[:, 0] - point[0]) + np.abs(self.points[:, 1] - point[1])))
        self._refresh_plot()
        self.points_changed.emit()

    def delete_selected_point(self):
        if (not self.edit_mode) or self.selected_index is None or len(self.points) <= 2:
            return
        if self.selected_index in (0, len(self.points) - 1):
            return
        self.points = np.delete(self.points, self.selected_index, axis=0)
        self.selected_index = None
        self._ensure_sorted_points()
        self._refresh_plot()
        self.points_changed.emit()

    def _ensure_sorted_points(self):
        if self.points.size == 0:
            self.points = np.array([[0.0, 0.0], [self.period_ns, 0.0]], dtype=float)
        self.points[:, 0] = np.clip(self.points[:, 0], 0.0, self.period_ns)
        self.points[:, 1] = np.clip(self.points[:, 1], 0.0, 1.0)
        order = np.argsort(self.points[:, 0], kind="mergesort")
        self.points = self.points[order]
        self.points[0, 0] = 0.0
        self.points[-1, 0] = self.period_ns
        self.points[0, 1] = np.clip(self.points[0, 1], 0.0, 1.0)
        self.points[-1, 1] = np.clip(self.points[-1, 1], 0.0, 1.0)

    def _refresh_plot(self):
        self._ensure_sorted_points()
        x = self.points[:, 0]
        y = self.points[:, 1]
        self.curve.setData(x, y)
        self.scatter.setData(x=x, y=y, data=list(range(len(x))))
        if self.selected_index is not None and 0 <= self.selected_index < len(self.points):
            self.selected_scatter.setData(x=[x[self.selected_index]], y=[y[self.selected_index]])
        else:
            self.selected_scatter.setData([], [])
        if self.pending_point is not None:
            self.pending_scatter.setData(x=[self.pending_point[0]], y=[self.pending_point[1]])
        else:
            self.pending_scatter.setData([], [])
        self.plot.setXRange(0.0, self.period_ns, padding=0.01)
        self.plot.setYRange(-0.02, 1.05, padding=0.01)

    def _data_point_from_scene(self, scene_pos):
        if not self.plot.sceneBoundingRect().contains(scene_pos):
            return None
        view_pos = self.plot.getViewBox().mapSceneToView(scene_pos)
        x = float(np.clip(view_pos.x(), 0.0, self.period_ns))
        y = float(np.clip(view_pos.y(), 0.0, 1.0))
        return x, y

    def _on_point_clicked(self, _plot, points, _event):
        if not self.edit_mode:
            return
        if not points:
            return
        self.selected_index = int(points[0].data())
        self.pending_point = None
        self.dragging = True
        self._refresh_plot()

    def _find_nearest_point_index(self, data_point):
        if self.points is None or len(self.points) == 0:
            return None
        x, y = float(data_point[0]), float(data_point[1])
        x_tol = max(self.period_ns * 0.02, 0.02)
        y_tol = 0.05
        dx = np.abs(self.points[:, 0] - x) / x_tol
        dy = np.abs(self.points[:, 1] - y) / y_tol
        dist = np.sqrt(dx * dx + dy * dy)
        idx = int(np.argmin(dist))
        if float(dist[idx]) <= 1.0:
            return idx
        return None

    def _on_scene_clicked(self, event):
        if not self.edit_mode:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        data_point = self._data_point_from_scene(event.scenePos())
        if data_point is None:
            return
        nearest_idx = self._find_nearest_point_index(data_point)
        if nearest_idx is not None:
            self.selected_index = nearest_idx
            self.pending_point = None
            self.dragging = True
        else:
            self.pending_point = np.asarray(data_point, dtype=float)
            self.selected_index = None
            self.dragging = False
        self._refresh_plot()

    def _on_scene_moved(self, scene_pos):
        if (not self.edit_mode) or (not self.dragging) or self.selected_index is None:
            return
        if self.selected_index in (0, len(self.points) - 1):
            return
        buttons = QGuiApplication.mouseButtons()
        if not (buttons & Qt.MouseButton.LeftButton):
            self.dragging = False
            return
        data_point = self._data_point_from_scene(scene_pos)
        if data_point is None:
            return
        left_bound = self.points[self.selected_index - 1, 0] + 1e-6
        right_bound = self.points[self.selected_index + 1, 0] - 1e-6
        self.points[self.selected_index, 0] = np.clip(data_point[0], left_bound, right_bound)
        self.points[self.selected_index, 1] = data_point[1]
        self._refresh_plot()
        self.points_changed.emit()
