import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtCore import Qt


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
    def __init__(self):
        super().__init__()
        self.current_theme = "dark"
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addStretch()
        self.btn_copy = QPushButton("📋")
        self.btn_copy.setToolTip("Copy screenshot to clipboard")
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        self.btn_copy.setMaximumWidth(30)
        header.addWidget(self.btn_copy)
        layout.addLayout(header)

        body = QHBoxLayout()
        layout.addLayout(body, 1)

        self.plot_item = pg.PlotWidget(
            axisItems={
                "bottom": PlainAxisItem(orientation="bottom"),
                "left": PlainAxisItem(orientation="left"),
            }
        )
        self.plot_item.setAspectLocked(True)
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.plot_item.setLabel("left", "S (Imaginary)")
        self.plot_item.setLabel("bottom", "G (Real)")
        self.plot_item.setXRange(-0.02, 1.02, padding=0.0)
        self.plot_item.setYRange(-0.02, 0.52, padding=0.0)
        self.plot_item.getAxis("left").enableAutoSIPrefix(False)
        self.plot_item.getAxis("bottom").enableAutoSIPrefix(False)
        self.legend = self.plot_item.addLegend(offset=(10, 10))
        body.addWidget(self.plot_item, 3)

        t = np.linspace(0, np.pi, 100)
        lx = 0.5 + 0.5 * np.cos(t)
        ly = 0.5 * np.sin(t)
        self.universal_curve = self.plot_item.plot(
            lx,
            ly,
            pen=pg.mkPen("w", width=1, style=Qt.PenStyle.DashLine),
            name="Universal semicircle",
        )
        self.actual_curve = self.plot_item.plot(
            [],
            [],
            pen=pg.mkPen("#f59e0b", width=2),
            name="Discrete single-exp arc",
        )
        self.scatter = pg.ScatterPlotItem(size=3, pen=None, brush=pg.mkBrush(100, 150, 255, 150))
        self.plot_item.addItem(self.scatter)
        self.selected_marker = pg.ScatterPlotItem(size=12, pen=pg.mkPen("#ef4444", width=2), brush=pg.mkBrush(239, 68, 68, 120))
        self.plot_item.addItem(self.selected_marker)

        side = QVBoxLayout()
        body.addLayout(side, 2)

        self.lbl_precision = QLabel("Precision (F^-2)")
        side.addWidget(self.lbl_precision)
        self.precision_plot = pg.PlotWidget()
        self.precision_plot.setLabel("left", "F^-2")
        self.precision_plot.setLabel("bottom", "Truth [ns]")
        self.precision_plot.showGrid(x=True, y=True, alpha=0.25)
        self.precision_curve = self.precision_plot.plot(pen=pg.mkPen("#38bdf8", width=2), symbol="o", symbolSize=6)
        self.precision_marker = pg.ScatterPlotItem(size=10, pen=pg.mkPen("#ef4444"), brush=pg.mkBrush("#ef4444"))
        self.precision_plot.addItem(self.precision_marker)
        side.addWidget(self.precision_plot, 1)

        self.lbl_accuracy = QLabel("Accuracy")
        side.addWidget(self.lbl_accuracy)
        self.accuracy_plot = pg.PlotWidget()
        self.accuracy_plot.setLabel("left", "Estimated [ns]")
        self.accuracy_plot.setLabel("bottom", "Truth [ns]")
        self.accuracy_plot.showGrid(x=True, y=True, alpha=0.25)
        self.accuracy_identity = self.accuracy_plot.plot(pen=pg.mkPen("#94a3b8", width=1.5, style=Qt.PenStyle.DashLine))
        self.accuracy_curve = self.accuracy_plot.plot(pen=pg.mkPen("#22c55e", width=2), symbol="o", symbolSize=6)
        self.accuracy_marker = pg.ScatterPlotItem(size=10, pen=pg.mkPen("#ef4444"), brush=pg.mkBrush("#ef4444"))
        self.accuracy_plot.addItem(self.accuracy_marker)
        side.addWidget(self.accuracy_plot, 1)

        self.set_theme("dark")

    def _copy_to_clipboard(self):
        QGuiApplication.clipboard().setPixmap(self.grab())

    def set_theme(self, theme_name):
        self.current_theme = str(theme_name).lower()
        dark = self.current_theme == "dark"
        bg = "k" if dark else "#ffffff"
        text = "#e5eefb" if dark else "#0f172a"
        locus = "w" if dark else "#475569"
        scatter = (100, 150, 255, 150) if dark else (31, 119, 180, 160)
        for plot in (self.plot_item, self.precision_plot, self.accuracy_plot):
            plot.setBackground(bg)
            for axis_name in ("bottom", "left"):
                axis = plot.getAxis(axis_name)
                axis.setTextPen(pg.mkPen(text))
                axis.setPen(pg.mkPen(text))
        self.lbl_precision.setStyleSheet(f"color: {text};")
        self.lbl_accuracy.setStyleSheet(f"color: {text};")
        self.universal_curve.setPen(pg.mkPen(locus, width=1, style=Qt.PenStyle.DashLine))
        self.scatter.setBrush(pg.mkBrush(*scatter))

    def update_data(
        self,
        g,
        s,
        performance_summary=None,
        selected_value=None,
        truth_value=None,
        selected_phasor=None,
        universal_locus=None,
        actual_locus=None,
    ):
        g_arr = np.asarray(g, dtype=float).reshape(-1)
        s_arr = np.asarray(s, dtype=float).reshape(-1)
        mask = np.isfinite(g_arr) & np.isfinite(s_arr)
        if np.any(mask):
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
        else:
            self.scatter.setData(x=[], y=[])

        if selected_phasor is not None:
            try:
                sg, ss = selected_phasor
                if np.isfinite(float(sg)) and np.isfinite(float(ss)):
                    self.selected_marker.setData([float(sg)], [float(ss)])
                else:
                    self.selected_marker.setData([], [])
            except Exception:
                self.selected_marker.setData([], [])
        else:
            self.selected_marker.setData([], [])

        if universal_locus is not None:
            ug, us = universal_locus
            self.universal_curve.setData(np.asarray(ug, dtype=float), np.asarray(us, dtype=float))
        if actual_locus is not None:
            ag, a_s = actual_locus
            self.actual_curve.setData(np.asarray(ag, dtype=float), np.asarray(a_s, dtype=float))

        summary = performance_summary or {}
        truth = np.asarray(summary.get("truth", []), dtype=float)
        mean = np.asarray(summary.get("mean", []), dtype=float)
        eff = np.asarray(summary.get("f_inv2", []), dtype=float)
        self.precision_curve.setData(truth, eff)
        self.accuracy_curve.setData(truth, mean)
        if truth.size:
            lo = float(np.nanmin(truth))
            hi = float(np.nanmax(truth))
            self.accuracy_identity.setData([lo, hi], [lo, hi])
        else:
            self.accuracy_identity.setData([], [])
        if truth_value is not None and np.isfinite(truth_value) and selected_value is not None and np.isfinite(selected_value):
            match = np.argmin(np.abs(truth - float(truth_value))) if truth.size else None
            if match is not None and truth.size:
                self.precision_marker.setData([truth[match]], [eff[match]])
            else:
                self.precision_marker.setData([], [])
            self.accuracy_marker.setData([float(truth_value)], [float(selected_value)])
        else:
            self.precision_marker.setData([], [])
            self.accuracy_marker.setData([], [])
