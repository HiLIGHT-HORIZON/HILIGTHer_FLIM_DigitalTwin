import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame
from PyQt6.QtGui import QGuiApplication


class DecayWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_theme = "dark"
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.lbl_stats = QLabel("Reduced chi2: n/a | Residual randomness p≈n/a")
        header.addWidget(self.lbl_stats)
        header.addStretch()
        self.btn_copy = QPushButton("📋")
        self.btn_copy.setToolTip("Copy screenshot to clipboard")
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        self.btn_copy.setMaximumWidth(30)
        header.addWidget(self.btn_copy)
        layout.addLayout(header)

        body = QHBoxLayout()
        layout.addLayout(body, 1)

        center_column = QVBoxLayout()
        body.addLayout(center_column, 4)

        decay_row = QHBoxLayout()
        center_column.addLayout(decay_row, 3)
        self.decay_legend = self._build_legend(
            [("Raw Decay", "#e5eefb"), ("Fit", "#ef4444"), ("IRF", "#22c55e")]
        )
        decay_row.addWidget(self.decay_legend, 0)

        self.plot_item = pg.PlotWidget()
        self.plot_item.setLabel("left", "Photon Counts")
        self.plot_item.setLabel("bottom", "Time [ns]")
        self.raw_curve = self.plot_item.plot(
            pen=None,
            symbol="o",
            symbolSize=7,
            symbolPen=pg.mkPen("#e5eefb"),
            symbolBrush=pg.mkBrush("#e5eefb"),
        )
        self.fit_curve = self.plot_item.plot(pen=pg.mkPen("#ef4444", width=2))
        self.irf_curve = self.plot_item.plot(pen=pg.mkPen("#22c55e", width=1.5, style=pg.QtCore.Qt.PenStyle.DashLine))
        decay_row.addWidget(self.plot_item, 1)

        residual_row = QHBoxLayout()
        center_column.addLayout(residual_row, 2)
        self.residual_legend = self._build_legend(
            [("Residuals", "#60a5fa"), ("Zero", "#94a3b8")]
        )
        residual_row.addWidget(self.residual_legend, 0)

        self.residual_plot = pg.PlotWidget()
        self.residual_plot.setLabel("left", "Residuals")
        self.residual_plot.setLabel("bottom", "Time [ns]")
        self.residual_plot.showGrid(x=True, y=True, alpha=0.25)
        self.residual_curve = self.residual_plot.plot(
            pen=None,
            symbol="o",
            symbolSize=6,
            symbolPen=pg.mkPen("#60a5fa"),
            symbolBrush=pg.mkBrush("#60a5fa"),
        )
        self.zero_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#94a3b8", width=1, style=pg.QtCore.Qt.PenStyle.DashLine))
        self.residual_plot.addItem(self.zero_line)
        residual_row.addWidget(self.residual_plot, 1)

        histogram_column = QVBoxLayout()
        body.addLayout(histogram_column, 2)
        self.lbl_hist = QLabel("Lifetime Histogram")
        histogram_column.addWidget(self.lbl_hist)
        self.hist_plot = pg.PlotWidget()
        self.hist_plot.setLabel("left", "Pixels")
        self.hist_plot.setLabel("bottom", "Lifetime [ns]")
        self.hist_plot.showGrid(x=True, y=True, alpha=0.25)
        self.hist_curve = self.hist_plot.plot(stepMode="center", fillLevel=0, brush=pg.mkBrush(96, 165, 250, 100), pen=pg.mkPen("#60a5fa", width=1.5))
        self.hist_marker = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#ef4444", width=2))
        self.truth_marker = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#22c55e", width=2, style=pg.QtCore.Qt.PenStyle.DashLine))
        self.hist_plot.addItem(self.hist_marker)
        self.hist_plot.addItem(self.truth_marker)
        histogram_column.addWidget(self.hist_plot, 1)
        self.lbl_hist_value = QLabel("Selected: n/a | Truth: n/a")
        histogram_column.addWidget(self.lbl_hist_value)

        self.set_theme("dark")
        self.clear()

    def _build_legend(self, items):
        frame = QFrame()
        frame.setMinimumWidth(110)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        for label, color in items:
            row = QHBoxLayout()
            swatch = QLabel()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(f"background:{color}; border:1px solid {color};")
            text = QLabel(label)
            row.addWidget(swatch)
            row.addWidget(text)
            row.addStretch()
            layout.addLayout(row)
        layout.addStretch()
        frame._legend_labels = frame.findChildren(QLabel)
        return frame

    def _copy_to_clipboard(self):
        QGuiApplication.clipboard().setPixmap(self.grab())

    def set_theme(self, theme_name):
        self.current_theme = str(theme_name).lower()
        dark = self.current_theme == "dark"
        bg = "k" if dark else "#ffffff"
        text = "#e5eefb" if dark else "#0f172a"
        raw_color = "#e5eefb" if dark else "#111827"
        fit_color = "#ef4444" if dark else "#b91c1c"
        irf_color = "#22c55e" if dark else "#15803d"
        residual_color = "#60a5fa" if dark else "#2563eb"
        zero_color = "#94a3b8" if dark else "#64748b"
        hist_color = "#60a5fa" if dark else "#2563eb"

        for plot in (self.plot_item, self.residual_plot, self.hist_plot):
            plot.setBackground(bg)
            for axis_name in ("bottom", "left"):
                axis = plot.getAxis(axis_name)
                axis.setTextPen(pg.mkPen(text))
                axis.setPen(pg.mkPen(text))

        for frame in (self.decay_legend, self.residual_legend):
            frame.setStyleSheet(f"QFrame {{ background: {bg}; border: 1px solid {zero_color}; border-radius: 6px; }} QLabel {{ color: {text}; }}")

        self.lbl_stats.setStyleSheet(f"color: {text};")
        self.lbl_hist.setStyleSheet(f"color: {text};")
        self.lbl_hist_value.setStyleSheet(f"color: {text};")

        self.raw_curve.setSymbolPen(pg.mkPen(raw_color))
        self.raw_curve.setSymbolBrush(pg.mkBrush(raw_color))
        self.fit_curve.setPen(pg.mkPen(fit_color, width=2))
        self.irf_curve.setPen(pg.mkPen(irf_color, width=1.5, style=pg.QtCore.Qt.PenStyle.DashLine))
        self.residual_curve.setSymbolPen(pg.mkPen(residual_color))
        self.residual_curve.setSymbolBrush(pg.mkBrush(residual_color))
        self.zero_line.setPen(pg.mkPen(zero_color, width=1, style=pg.QtCore.Qt.PenStyle.DashLine))
        self.hist_curve.setPen(pg.mkPen(hist_color, width=1.5))
        self.hist_curve.setBrush(pg.mkBrush(96, 165, 250, 100) if dark else pg.mkBrush(37, 99, 235, 80))
        self.hist_marker.setPen(pg.mkPen(fit_color, width=2))
        self.truth_marker.setPen(pg.mkPen(irf_color, width=2, style=pg.QtCore.Qt.PenStyle.DashLine))

    def clear(self):
        self.raw_curve.setData([], [])
        self.fit_curve.setData([], [])
        self.irf_curve.setData([], [])
        self.residual_curve.setData([], [])
        self.hist_curve.setData([], [])
        self.hist_marker.hide()
        self.truth_marker.hide()
        self.lbl_stats.setText("Reduced chi2: n/a | Residual randomness p≈n/a")
        self.lbl_hist_value.setText("Selected: n/a | Truth: n/a")

    def update_decay(self, t, counts, fit=None, residuals=None, irf=None, reduced_chi2=None, randomness=None,
                     histogram_values=None, selected_value=None, truth_value=None):
        self.raw_curve.setData(t, counts)

        if fit is not None:
            self.fit_curve.setData(t, fit)
            self.fit_curve.show()
        else:
            self.fit_curve.hide()

        if irf is not None:
            self.irf_curve.setData(t, irf)
            self.irf_curve.show()
        else:
            self.irf_curve.hide()

        if residuals is not None:
            self.residual_curve.setData(t, residuals)
        else:
            self.residual_curve.setData([], [])

        hist_values = np.asarray(histogram_values if histogram_values is not None else [], dtype=float)
        hist_values = hist_values[np.isfinite(hist_values)]
        if hist_values.size:
            bins = min(max(int(np.sqrt(hist_values.size)), 10), 50)
            counts_hist, edges = np.histogram(hist_values, bins=bins)
            self.hist_curve.setData(edges, counts_hist)
        else:
            self.hist_curve.setData([], [])

        if selected_value is not None and np.isfinite(selected_value):
            self.hist_marker.setPos(float(selected_value))
            self.hist_marker.show()
        else:
            self.hist_marker.hide()

        if truth_value is not None and np.isfinite(truth_value):
            self.truth_marker.setPos(float(truth_value))
            self.truth_marker.show()
        else:
            self.truth_marker.hide()

        p_value = None if not randomness else randomness.get("approx_p_value")
        chi2_text = "n/a" if reduced_chi2 is None else f"{float(reduced_chi2):.3f}"
        rand_text = "n/a" if p_value is None else f"{float(p_value):.3g}"
        self.lbl_stats.setText(f"Reduced chi2: {chi2_text} | Residual randomness p≈{rand_text}")

        selected_text = "n/a" if selected_value is None or not np.isfinite(selected_value) else f"{float(selected_value):.3f} ns"
        truth_text = "n/a" if truth_value is None or not np.isfinite(truth_value) else f"{float(truth_value):.3f} ns"
        self.lbl_hist_value.setText(f"Selected: {selected_text} | Truth: {truth_text}")
