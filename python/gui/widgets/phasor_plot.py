import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QGuiApplication


class PlainAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        labels = []
        for value in values:
            if abs(value) < 1e-12:
                value = 0.0
            if spacing >= 1.0:
                labels.append(f"{value:.0f}" if abs(value - round(value)) < 1e-9 else f"{value:.2f}")
            elif spacing >= 0.1:
                labels.append(f"{value:.2f}")
            else:
                labels.append(f"{value:.3f}")
        return labels


class PhasorWidget(QWidget):
    roi_changed = pyqtSignal(float, float, float, float) # g_min, g_max, s_min, s_max

    def __init__(self):
        super().__init__()
        self.current_theme = "dark"
        layout = QVBoxLayout(self)
        
        # Clipboard Support
        header = QHBoxLayout()
        header.addStretch()
        self.btn_copy = QPushButton("📋")
        self.btn_copy.setToolTip("Copy screenshot to clipboard")
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        self.btn_copy.setMaximumWidth(30)
        header.addWidget(self.btn_copy)
        layout.addLayout(header)

        # Plot Configuration
        self.plot_item = pg.PlotWidget(
            axisItems={
                "bottom": PlainAxisItem(orientation="bottom"),
                "left": PlainAxisItem(orientation="left"),
            }
        )
        self.plot_item.setBackground('k')
        self.plot_item.setAspectLocked(True)
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.plot_item.setLabel('left', 'S (Imaginary)')
        self.plot_item.setLabel('bottom', 'G (Real)')
        self.plot_item.setXRange(-0.02, 1.02, padding=0.0)
        self.plot_item.setYRange(-0.02, 0.52, padding=0.0)
        self.plot_item.getAxis('left').enableAutoSIPrefix(False)
        self.plot_item.getAxis('bottom').enableAutoSIPrefix(False)
        
        # Theoretical Locus (Semicircle)
        t = np.linspace(0, np.pi, 100)
        lx = 0.5 + 0.5 * np.cos(t)
        ly = 0.5 * np.sin(t)
        self.locus_curve = pg.PlotCurveItem(lx, ly, pen=pg.mkPen('w', width=1, style=Qt.PenStyle.DashLine))
        self.plot_item.addItem(self.locus_curve)
        
        # Scatter for Data
        self.scatter = pg.ScatterPlotItem(size=3, pen=None, brush=pg.mkBrush(100, 150, 255, 150))
        self.plot_item.addItem(self.scatter)
        
        # ROI Selector (Square)
        self.roi = pg.RectROI([0.4, 0.2], [0.2, 0.2], pen=(0, 255, 0))
        self.plot_item.addItem(self.roi)
        self.roi.sigRegionChanged.connect(self._on_roi_change)

        layout.addWidget(self.plot_item)
        self.set_theme("dark")

    def _copy_to_clipboard(self):
        pixmap = self.grab()
        QGuiApplication.clipboard().setPixmap(pixmap)

    def set_theme(self, theme_name):
        self.current_theme = str(theme_name).lower()
        dark = self.current_theme == "dark"
        bg = 'k' if dark else '#ffffff'
        text = '#e5eefb' if dark else '#0f172a'
        locus = 'w' if dark else '#475569'
        scatter = (100, 150, 255, 150) if dark else (31, 119, 180, 160)
        self.plot_item.setBackground(bg)
        for axis_name in ('bottom', 'left'):
            axis = self.plot_item.getAxis(axis_name)
            axis.setTextPen(pg.mkPen(text))
            axis.setPen(pg.mkPen(text))
        self.locus_curve.setPen(pg.mkPen(locus, width=1, style=Qt.PenStyle.DashLine))
        self.scatter.setBrush(pg.mkBrush(*scatter))

    def update_data(self, g, s):
        """Update the scatter plot with new G and S maps."""
        g_arr = np.asarray(g, dtype=float).reshape(-1)
        s_arr = np.asarray(s, dtype=float).reshape(-1)
        mask = np.isfinite(g_arr) & np.isfinite(s_arr)
        if not np.any(mask):
            self.scatter.setData(x=[], y=[])
            self.plot_item.setXRange(-0.02, 1.02, padding=0.0)
            self.plot_item.setYRange(-0.02, 0.52, padding=0.0)
            return

        x_vals = g_arr[mask]
        y_vals = s_arr[mask]
        self.scatter.setData(x=x_vals, y=y_vals)

        x_min = float(np.min(x_vals))
        x_max = float(np.max(x_vals))
        y_min = float(np.min(y_vals))
        y_max = float(np.max(y_vals))
        x_pad = max((x_max - x_min) * 0.08, 0.02)
        y_pad = max((y_max - y_min) * 0.08, 0.02)
        self.plot_item.setXRange(min(-0.02, x_min - x_pad), max(1.02, x_max + x_pad), padding=0.0)
        self.plot_item.setYRange(min(-0.02, y_min - y_pad), max(0.52, y_max + y_pad), padding=0.0)

    def _on_roi_change(self):
        pos = self.roi.pos()
        size = self.roi.size()
        self.roi_changed.emit(pos.x(), pos.x() + size.x(), pos.y(), pos.y() + size.y())

# Internal helper for testing
