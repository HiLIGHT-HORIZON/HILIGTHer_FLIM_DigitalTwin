import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox
from .clipboard_export import ClipboardExportManager


class DecayWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_theme = "dark"
        self._cached_t = np.array([], dtype=float)
        self._cached_counts = np.array([], dtype=float)
        self._cached_fit_x = np.array([], dtype=float)
        self._cached_fit_y = np.array([], dtype=float)
        self._cached_residuals = np.array([], dtype=float)
        self._cached_irf_x = np.array([], dtype=float)
        self._cached_irf = np.array([], dtype=float)

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.lbl_stats = QLabel("Reduced chi2: n/a | Residual randomness p≈n/a")
        header.addWidget(self.lbl_stats)
        header.addStretch()
        self.chk_decay_log = QCheckBox("Decay log Y")
        self.chk_residual_log = QCheckBox("Residual log Y")
        self.chk_decay_log.toggled.connect(self._apply_log_modes)
        self.chk_residual_log.toggled.connect(self._apply_log_modes)
        header.addWidget(self.chk_decay_log)
        header.addWidget(self.chk_residual_log)
        self.btn_copy = QPushButton("📋")
        self.btn_copy.setToolTip("Copy screenshot to clipboard")
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        self.btn_copy.setMaximumWidth(30)
        header.addWidget(self.btn_copy)
        self.btn_export_settings = QPushButton("⚙")
        self.btn_export_settings.setToolTip("Clipboard export settings")
        self.btn_export_settings.clicked.connect(self._open_export_settings)
        self.btn_export_settings.setMaximumWidth(30)
        header.addWidget(self.btn_export_settings)
        layout.addLayout(header)

        decay_row = QHBoxLayout()
        layout.addLayout(decay_row, 3)
        self.decay_plot = pg.PlotWidget()
        self.decay_plot.setLabel("left", "Photon Counts")
        self.decay_plot.setLabel("bottom", "Time [ns]")
        self.decay_plot.showGrid(x=True, y=True, alpha=0.25)
        self.raw_curve = self.decay_plot.plot(pen=None, symbol="o", symbolSize=7)
        self.fit_curve = self.decay_plot.plot(pen=pg.mkPen("#ef4444", width=2))
        self.irf_curve = self.decay_plot.plot(pen=pg.mkPen("#22c55e", width=1.5, style=pg.QtCore.Qt.PenStyle.DashLine))
        decay_row.addWidget(self.decay_plot, 12)
        decay_legend_col = QVBoxLayout()
        self.decay_legend_obs = QLabel("● Observed decay")
        self.decay_legend_fit = QLabel("— Fitted decay")
        self.decay_legend_irf = QLabel("╌ IRF")
        decay_legend_col.addWidget(self.decay_legend_obs)
        decay_legend_col.addWidget(self.decay_legend_fit)
        decay_legend_col.addWidget(self.decay_legend_irf)
        decay_legend_col.addStretch()
        decay_row.addLayout(decay_legend_col, 2)

        residual_row = QHBoxLayout()
        layout.addLayout(residual_row, 2)
        self.residual_plot = pg.PlotWidget()
        self.residual_plot.setLabel("left", "Residuals")
        self.residual_plot.setLabel("bottom", "Time [ns]")
        self.residual_plot.showGrid(x=True, y=True, alpha=0.25)
        self.residual_curve = self.residual_plot.plot(
            pen=None,
            symbol="o",
            symbolSize=6,
        )
        self.zero_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen("#94a3b8", width=1, style=pg.QtCore.Qt.PenStyle.DashLine),
        )
        self.residual_plot.addItem(self.zero_line)
        residual_row.addWidget(self.residual_plot, 12)
        residual_legend_col = QVBoxLayout()
        self.residual_legend_label = QLabel("● Residuals")
        residual_legend_col.addWidget(self.residual_legend_label)
        residual_legend_col.addStretch()
        residual_row.addLayout(residual_legend_col, 2)

        self.set_theme("dark")
        self.clear()

    def _copy_to_clipboard(self):
        ClipboardExportManager.export_widget("decay_plot", self, parent=self, theme_target=self)

    def _open_export_settings(self):
        ClipboardExportManager.configure("decay_plot", parent=self)

    def _apply_log_modes(self):
        decay_log = self.chk_decay_log.isChecked()
        residual_log = self.chk_residual_log.isChecked()
        self.decay_plot.setLogMode(x=False, y=decay_log)
        self.residual_plot.setLogMode(x=False, y=residual_log)
        counts = np.maximum(self._cached_counts, 1e-6) if decay_log else self._cached_counts
        fit_y = np.maximum(self._cached_fit_y, 1e-6) if decay_log else self._cached_fit_y
        irf = np.maximum(self._cached_irf, 1e-6) if decay_log else self._cached_irf
        residuals = np.maximum(np.abs(self._cached_residuals), 1e-9) if residual_log else self._cached_residuals
        self.raw_curve.setData(self._cached_t, counts)
        self.fit_curve.setData(self._cached_fit_x, fit_y)
        self.irf_curve.setData(self._cached_irf_x, irf)
        self.residual_curve.setData(self._cached_t, residuals)
        self.zero_line.setVisible(not residual_log)

    def set_theme(self, theme_name):
        self.current_theme = str(theme_name).lower()
        dark = self.current_theme == "dark"
        bg = "k" if dark else "#ffffff"
        text = "#e5eefb" if dark else "#0f172a"
        raw_color = "#e5eefb" if dark else "#111827"
        residual_color = "#60a5fa" if dark else "#2563eb"
        for plot in (self.decay_plot, self.residual_plot):
            plot.setBackground(bg)
            for axis_name in ("bottom", "left"):
                axis = plot.getAxis(axis_name)
                axis.setTextPen(pg.mkPen(text))
                axis.setPen(pg.mkPen(text))
        self.lbl_stats.setStyleSheet(f"color: {text};")
        self.decay_legend_obs.setStyleSheet(f"color: {raw_color};")
        self.decay_legend_fit.setStyleSheet("color: #ef4444;")
        self.decay_legend_irf.setStyleSheet("color: #22c55e;")
        self.residual_legend_label.setStyleSheet(f"color: {residual_color};")
        self.raw_curve.setSymbolPen(pg.mkPen(raw_color))
        self.raw_curve.setSymbolBrush(pg.mkBrush(raw_color))
        self.residual_curve.setSymbolPen(pg.mkPen(residual_color))
        self.residual_curve.setSymbolBrush(pg.mkBrush(residual_color))

    def clear(self):
        self._cached_t = np.array([], dtype=float)
        self._cached_counts = np.array([], dtype=float)
        self._cached_fit_x = np.array([], dtype=float)
        self._cached_fit_y = np.array([], dtype=float)
        self._cached_residuals = np.array([], dtype=float)
        self._cached_irf_x = np.array([], dtype=float)
        self._cached_irf = np.array([], dtype=float)
        self.raw_curve.setData([], [])
        self.fit_curve.setData([], [])
        self.irf_curve.setData([], [])
        self.residual_curve.setData([], [])
        self.lbl_stats.setText("Reduced chi2: n/a | Residual randomness p≈n/a")

    def update_decay(
        self,
        t,
        counts,
        fit=None,
        fit_x=None,
        residuals=None,
        irf=None,
        irf_x=None,
        reduced_chi2=None,
        randomness=None,
        performance_summary=None,
        selected_value=None,
        truth_value=None,
    ):
        self._cached_t = np.asarray(t, dtype=float)
        self._cached_counts = np.asarray(counts, dtype=float)
        self._cached_fit_x = np.asarray(fit_x if fit_x is not None else [], dtype=float)
        self._cached_fit_y = np.asarray(fit if fit is not None else [], dtype=float)
        self._cached_residuals = np.asarray(residuals if residuals is not None else [], dtype=float)
        self._cached_irf_x = np.asarray(irf_x if irf_x is not None else [], dtype=float)
        self._cached_irf = np.asarray(irf if irf is not None else [], dtype=float)

        self.fit_curve.setVisible(self._cached_fit_x.size > 0 and self._cached_fit_y.size > 0)
        self.irf_curve.setVisible(self._cached_irf_x.size > 0 and self._cached_irf.size > 0)

        p_value = None if not randomness else randomness.get("approx_p_value")
        chi2_text = "n/a" if reduced_chi2 is None else f"{float(reduced_chi2):.3f}"
        rand_text = "n/a" if p_value is None else f"{float(p_value):.3g}"
        self.lbl_stats.setText(f"Reduced chi2: {chi2_text} | Residual randomness p≈{rand_text}")

        self._apply_log_modes()
