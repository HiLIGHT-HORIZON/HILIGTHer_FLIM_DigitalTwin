import pyqtgraph as pg
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QCheckBox, QComboBox, QLabel)

class FisherWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Colors for batch sweeps
        self.colors = ['#8b5cf6', '#3b82f6', '#ec4899', '#f59e0b', '#ef4444', '#06b6d4', '#84cc16']
        self.sweep_curves = [] # List of (curves, label_widget)
        
        # Controls Header
        ctrl_layout = QHBoxLayout()
        self.chk_log_x = QCheckBox("Log X")
        self.chk_log_x.setChecked(True)
        self.chk_log_x.stateChanged.connect(self.refresh_plot)
        
        self.chk_log_y = QCheckBox("Log Y")
        self.chk_log_y.stateChanged.connect(self.refresh_plot)
        
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["F-Value (F)", "Photon Efficiency (F^-2)"])
        self.combo_mode.currentIndexChanged.connect(self.refresh_plot)
        
        ctrl_layout.addWidget(QLabel("Axes:"))
        ctrl_layout.addWidget(self.chk_log_x)
        ctrl_layout.addWidget(self.chk_log_y)

        ctrl_layout.addStretch()
        ctrl_layout.addWidget(QLabel("Metric:"))
        ctrl_layout.addWidget(self.combo_mode)
        layout.addLayout(ctrl_layout)
        
        # Main Display Layout
        display_layout = QHBoxLayout()
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#0a0a0a')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('bottom', 'Target Parameter Range')
        display_layout.addWidget(self.plot_widget, stretch=4)
        
        # Legend Panel
        from PyQt6.QtWidgets import QFrame, QScrollArea
        from PyQt6.QtCore import Qt
        self.legend_panel = QFrame()
        self.legend_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.legend_panel.setMinimumWidth(220)
        self.legend_layout = QVBoxLayout(self.legend_panel)
        self.legend_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.legend_panel)
        display_layout.addWidget(scroll, stretch=1)
        
        self.legend_layout.addWidget(QLabel("<b style='font-size: 14px; color: #fff;'>Acquisition Benchmarks</b>"))
        self.legend_layout.addSpacing(10)
        
        # Ideal Reference Curve
        self.ideal_curve = self.plot_widget.plot(
            pen=pg.mkPen(color='#10b981', width=1.5, style=pg.QtCore.Qt.PenStyle.DashLine),
            name="Ideal Case"
        )
        self._add_manual_legend("Ideal Case", self.ideal_curve, "#10b981")
        self.legend_layout.addSpacing(10)
        self.legend_layout.addWidget(QLabel("<i style='color: #888;'>Batch Curves:</i>"))
        
        layout.addLayout(display_layout)
        
        # Internal Data Store
        self.raw_tau = None
        self.batch_data = {} # label -> payload dict
        self.ideal_tau = None
        self.ideal_f = None

    def set_xaxis_label(self, text):
        self.plot_widget.setLabel('bottom', text)

    def plot_batch(self, x, results_dict, ideal_x=None, ideal_f=None):
        """
        Single atomic plot update. 
        results_dict: {label: f_values_array or {y, compatible}}
        All curves are cleared and redrawn from provided data.
        """
        # Store ideal reference
        if ideal_x is not None:
            self.ideal_tau = np.array(ideal_x, copy=True)
            self.ideal_f = np.array(ideal_f, copy=True)

        # Rebuild batch_data from provided results (all copies)
        self.batch_data = {}
        x_copy = np.array(x, copy=True)
        for label, entry in results_dict.items():
            if isinstance(entry, dict):
                self.batch_data[label] = {
                    "x": x_copy,
                    "y": np.array(entry.get("y", []), copy=True),
                    "compatible": None if entry.get("compatible") is None else np.array(entry.get("compatible"), copy=True, dtype=bool),
                }
            else:
                self.batch_data[label] = {
                    "x": x_copy,
                    "y": np.array(entry, copy=True),
                    "compatible": None,
                }

        self.refresh_plot()

    def update_data(self, x, f, label="Simulated", ideal_x=None, ideal_f=None, is_batch=False):
        """Legacy helper — delegates to plot_batch."""
        if not is_batch:
            self.batch_data = {}
        self.batch_data[label] = (np.array(x, copy=True), np.array(f, copy=True))
        if ideal_x is not None:
            self.ideal_tau = np.array(ideal_x, copy=True)
            self.ideal_f = np.array(ideal_f, copy=True)
        self.refresh_plot()

    def clear_curves(self):
        for curves, widget in self.sweep_curves:
            for curve in curves:
                self.plot_widget.removeItem(curve)
            widget.setParent(None)
            widget.deleteLater()
        self.sweep_curves = []
        self.batch_data = {}

    def _add_manual_legend(self, label, curves, color=None):
        from PyQt6.QtWidgets import QCheckBox
        from PyQt6.QtCore import Qt
        if not isinstance(curves, (list, tuple)):
            curves = [curves]
        chk = QCheckBox(label)
        chk.setChecked(True)
        if color: chk.setStyleSheet(f"color: {color}; font-weight: bold;")
        chk.stateChanged.connect(
            lambda state: [curve.setVisible(state == Qt.CheckState.Checked.value) for curve in curves]
        )
        self.legend_layout.addWidget(chk)
        return chk

    def refresh_plot(self):
        if not self.batch_data and self.ideal_tau is None:
            return

        self.plot_widget.setLogMode(x=self.chk_log_x.isChecked(), y=self.chk_log_y.isChecked())
        mode = self.combo_mode.currentIndex()
        metric = "F-Value" if mode == 0 else "Efficiency (F^-2)"
        self.plot_widget.setLabel('left', metric)

        # Remove all existing batch curves and rebuild from scratch
        for curves, widget in self.sweep_curves:
            for curve in curves:
                self.plot_widget.removeItem(curve)
            widget.setParent(None)
            widget.deleteLater()
        self.sweep_curves = []

        color_map = {}
        color_index = 0

        for i, (label, payload) in enumerate(self.batch_data.items()):
            x = payload["x"]
            f = payload["y"]
            compatible = payload.get("compatible")
            if " | " in label:
                base_label = label.split(" | ", 1)[1]
            elif label.startswith("Theory") or label.startswith("Monte Carlo"):
                base_label = "Current Configuration"
            else:
                base_label = label
            if base_label not in color_map:
                color_map[base_label] = self.colors[color_index % len(self.colors)]
                color_index += 1
            color = color_map[base_label]
            y_data = f if mode == 0 else 1.0 / (np.maximum(f, 1e-6) ** 2)
            finite_mask = np.isfinite(x) & np.isfinite(y_data)
            if not np.any(finite_mask):
                continue
            is_monte_carlo = label.startswith("Monte Carlo")
            curves = []
            if is_monte_carlo:
                compatible_mask = finite_mask.copy()
                incompatible_mask = np.zeros_like(finite_mask, dtype=bool)
                if compatible is not None and compatible.shape == x.shape:
                    compatible_mask = finite_mask & compatible
                    incompatible_mask = finite_mask & (~compatible)
                if np.any(compatible_mask):
                    curve_ok = pg.PlotDataItem(
                        x[compatible_mask], y_data[compatible_mask],
                        pen=None,
                        symbol='o', symbolSize=7, symbolBrush=pg.mkBrush(color),
                        symbolPen=pg.mkPen(color=color),
                        name=label
                    )
                    self.plot_widget.addItem(curve_ok)
                    curves.append(curve_ok)
                if np.any(incompatible_mask):
                    curve_bad = pg.PlotDataItem(
                        x[incompatible_mask], y_data[incompatible_mask],
                        pen=None,
                        symbol='o', symbolSize=7, symbolBrush=pg.mkBrush('#6b7280'),
                        symbolPen=pg.mkPen(color='#9ca3af'),
                        name=label
                    )
                    self.plot_widget.addItem(curve_bad)
                    curves.append(curve_bad)
            else:
                curve = pg.PlotDataItem(
                    x[finite_mask], y_data[finite_mask],
                    pen=pg.mkPen(color=color, width=2),
                    symbol=None, symbolSize=6, symbolBrush=None,
                    symbolPen=pg.mkPen(color=color),
                    name=label
                )
                self.plot_widget.addItem(curve)
                curves.append(curve)
            if not curves:
                continue
            chk = self._add_manual_legend(label, curves, color)
            self.sweep_curves.append((curves, chk))

        # 2. Update Ideal Curve
        if self.ideal_tau is not None and self.ideal_f is not None:
            y_i = self.ideal_f if mode == 0 else 1.0/(np.maximum(self.ideal_f,1e-6)**2)
            finite_mask = np.isfinite(self.ideal_tau) & np.isfinite(y_i)
            if np.any(finite_mask):
                self.ideal_curve.setData(self.ideal_tau[finite_mask], y_i[finite_mask])
                self.ideal_curve.show()
            else:
                self.ideal_curve.hide()
        else:
            self.ideal_curve.hide()
