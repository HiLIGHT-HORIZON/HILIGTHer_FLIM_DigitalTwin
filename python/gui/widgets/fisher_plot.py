import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from .clipboard_export import ClipboardExportManager


class FisherWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.current_theme = "dark"
        self.colors = ["#8b5cf6", "#3b82f6", "#ec4899", "#f59e0b", "#ef4444", "#06b6d4", "#84cc16"]
        self.rendered_items = []
        self.series_visibility = {}
        self.series_checkboxes = {}
        self.series_groups = {}
        self.dynamic_legend_widgets = []
        self.batch_data = {}
        self.ideal_tau = None
        self.ideal_f = None
        self.ideal_conditional_f = None
        self.ideal_throughput_scale = 1.0
        self.ideal_photon_count = 0.0
        self.resolvability_default_photon_count = 0
        self._resolvability_allowed = False
        self.current_ci_level = 99.7
        self._has_mc_ci = False

        ctrl_layout = QHBoxLayout()
        self.chk_log_x = QCheckBox("Log X")
        self.chk_log_x.setChecked(True)
        self.chk_log_x.stateChanged.connect(self.refresh_plot)
        self.chk_log_x.setToolTip("Display the target-parameter axis on a logarithmic scale.")

        self.chk_log_y = QCheckBox("Log Y")
        self.chk_log_y.stateChanged.connect(self.refresh_plot)
        self.chk_log_y.setToolTip("Display the precision metric axis on a logarithmic scale.")

        self.combo_mode = QComboBox()
        self.combo_mode.addItems([
            "F-Value (F)",
            "Photon Efficiency (F^-2)",
            "Fisher Throughput",
            "Resolvability (R)",
            "Photons For R=3",
        ])
        self.combo_mode.currentIndexChanged.connect(self.refresh_plot)
        self.combo_mode.setToolTip("Choose whether to display F, photon efficiency, or Fisher throughput.")

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setToolTip("Reset the view to show all data points.")
        self.btn_reset.clicked.connect(self.reset_axes)
        self.btn_reset.setMaximumWidth(60)
        self.btn_reset.setStyleSheet("padding: 2px 5px; font-size: 11px;")

        self.btn_copy = QPushButton("📋")
        self.btn_copy.setToolTip("Copy screenshot to clipboard")
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        self.btn_copy.setMaximumWidth(30)
        self.btn_copy.setStyleSheet("padding: 2px; font-size: 14px;")
        self.btn_export_settings = QPushButton("⚙")
        self.btn_export_settings.setToolTip("Clipboard export settings")
        self.btn_export_settings.clicked.connect(self._open_export_settings)
        self.btn_export_settings.setMaximumWidth(30)
        self.btn_export_settings.setStyleSheet("padding: 2px; font-size: 14px;")

        self.lbl_resolvability_photons = QLabel("Photons:")
        self.lbl_resolvability_photons.setToolTip("Photon count used for the resolvability calculation only.")
        self.spin_resolvability_photons = QSpinBox()
        self.spin_resolvability_photons.setRange(1, 2_000_000_000)
        self.spin_resolvability_photons.setValue(1)
        self.spin_resolvability_photons.setMaximumWidth(110)
        self.spin_resolvability_photons.valueChanged.connect(self.refresh_plot)
        self.spin_resolvability_photons.setToolTip("Override the photon count used to display resolvability R.")
        self.lbl_resolvability_photons.hide()
        self.spin_resolvability_photons.hide()

        ctrl_layout.addWidget(QLabel("Axes:"))
        ctrl_layout.addWidget(self.chk_log_x)
        ctrl_layout.addWidget(self.chk_log_y)
        ctrl_layout.addWidget(self.btn_reset)
        ctrl_layout.addWidget(self.btn_copy)
        ctrl_layout.addWidget(self.btn_export_settings)
        ctrl_layout.addWidget(self.lbl_resolvability_photons)
        ctrl_layout.addWidget(self.spin_resolvability_photons)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(QLabel("Metric:"))
        ctrl_layout.addWidget(self.combo_mode)
        layout.addLayout(ctrl_layout)

        display_layout = QHBoxLayout()
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("#0a0a0a")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel("bottom", "Target Parameter Range")
        display_layout.addWidget(self.plot_widget, stretch=4)

        self.legend_panel = QFrame()
        self.legend_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.legend_panel.setMinimumWidth(220)
        self.legend_layout = QVBoxLayout(self.legend_panel)
        self.legend_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.legend_panel)
        display_layout.addWidget(scroll, stretch=1)

        self.legend_header = QLabel()
        self.legend_layout.addWidget(self.legend_header)
        self.legend_layout.addSpacing(8)

        self.ideal_curve = pg.PlotDataItem(
            pen=pg.mkPen(color="#10b981", width=1.5, style=Qt.PenStyle.DashLine)
        )
        self.plot_widget.addItem(self.ideal_curve)
        self.resolvability_limit_curve = pg.PlotDataItem(
            pen=pg.mkPen(color="#f59e0b", width=1.2, style=Qt.PenStyle.DashLine)
        )
        self.plot_widget.addItem(self.resolvability_limit_curve)

        self.chk_show_ideal = QCheckBox("Ideal Case")
        self.chk_show_ideal.setChecked(True)
        self.chk_show_ideal.setStyleSheet("color: #10b981; font-weight: bold;")
        self.chk_show_ideal.stateChanged.connect(self._apply_visibility)
        self.legend_layout.addWidget(self.chk_show_ideal)

        self.legend_layout.addSpacing(10)
        self.collections_label = QLabel()
        self.legend_layout.addWidget(self.collections_label)

        self.chk_show_theory = QCheckBox("Theory")
        self.chk_show_theory.setChecked(True)
        self.chk_show_theory.stateChanged.connect(self._apply_visibility)
        self.legend_layout.addWidget(self.chk_show_theory)

        self.chk_show_mc = QCheckBox("Monte Carlo")
        self.chk_show_mc.setChecked(True)
        self.chk_show_mc.stateChanged.connect(self._apply_visibility)
        self.legend_layout.addWidget(self.chk_show_mc)

        self.chk_show_mc_ci = QCheckBox()
        self.chk_show_mc_ci.setChecked(True)
        self.chk_show_mc_ci.stateChanged.connect(self._apply_visibility)
        self.legend_layout.addWidget(self.chk_show_mc_ci)
        self.set_ci_level(self.current_ci_level)
        self.chk_show_mc_ci.setEnabled(False)

        self.legend_layout.addSpacing(10)
        self.sweep_label = QLabel()
        self.legend_layout.addWidget(self.sweep_label)
        self.series_legend_holder = QVBoxLayout()
        self.legend_layout.addLayout(self.series_legend_holder)
        self.legend_layout.addStretch()

        layout.addLayout(display_layout)
        self.set_theme("dark")

    @staticmethod
    def _segment_indices(mask):
        idx = np.flatnonzero(mask)
        if idx.size == 0:
            return []
        splits = np.where(np.diff(idx) > 1)[0] + 1
        return [segment for segment in np.split(idx, splits) if segment.size > 0]

    def _copy_to_clipboard(self):
        ClipboardExportManager.export_widget(
            "fisher_plot",
            self,
            parent=self,
            theme_target=self,
            export_source=self.plot_widget,
            export_legend_entries=self._export_legend_entries,
        )

    def _open_export_settings(self):
        ClipboardExportManager.configure("fisher_plot", parent=self, export_source=self.plot_widget)

    def set_theme(self, theme_name):
        self.current_theme = str(theme_name).lower()
        dark = self.current_theme == "dark"
        bg = "#0a0a0a" if dark else "#ffffff"
        text = "#e5eefb" if dark else "#0f172a"
        muted = "#94a3b8" if dark else "#64748b"
        border = "#334155" if dark else "#cbd5e1"
        accent = "#10b981" if dark else "#15803d"

        self.plot_widget.setBackground(bg)
        for axis_name in ("bottom", "left"):
            axis = self.plot_widget.getAxis(axis_name)
            axis.setTextPen(pg.mkPen(text))
            axis.setPen(pg.mkPen(text))
        self.legend_panel.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}"
        )
        self.legend_header.setText(f"<b style='font-size: 14px; color: {text};'>Acquisition Benchmarks</b>")
        self.collections_label.setText(f"<i style='color: {muted};'>Collections:</i>")
        self.sweep_label.setText(f"<i style='color: {muted};'>Sweep Series:</i>")
        self.chk_show_ideal.setStyleSheet(f"color: {accent}; font-weight: bold;")
        self.chk_show_theory.setStyleSheet(f"color: {text};")
        self.chk_show_mc.setStyleSheet(f"color: {text};")
        self.chk_show_mc_ci.setStyleSheet(f"color: {text};")

    @staticmethod
    def format_ci_level(ci_level):
        text = f"{float(ci_level):.3f}".rstrip("0").rstrip(".")
        return f"{text}%"

    def set_ci_level(self, ci_level):
        self.current_ci_level = float(ci_level)
        self.chk_show_mc_ci.setText(f"MC CI {self.format_ci_level(self.current_ci_level)}")

    def set_xaxis_label(self, text):
        self.plot_widget.setLabel("bottom", text)

    @staticmethod
    def _f_to_efficiency(f_values):
        f_arr = np.asarray(f_values, dtype=float)
        return np.minimum(1.0, 1.0 / (np.maximum(f_arr, 1e-12) ** 2))

    def _metric_meta(self):
        mode = self.combo_mode.currentIndex()
        if mode == 0:
            return "F-Value (F)", "f"
        if mode == 1:
            return "Photon Efficiency (F^-2)", "efficiency"
        if mode == 2:
            return "Fisher Throughput", "throughput"
        if mode == 3:
            return "Resolvability (R)", "resolvability"
        return "Photons Required For R=3", "required_photons"

    def _display_metric_values(self, f_values, throughput_scale, conditional_f_values=None, photon_count=None):
        _metric_label, metric_key = self._metric_meta()
        if metric_key == "f":
            return np.asarray(f_values, dtype=float)
        efficiency = self._f_to_efficiency(f_values)
        if metric_key == "efficiency":
            return efficiency
        if metric_key == "throughput":
            return efficiency * float(throughput_scale)
        cond_f = np.asarray(conditional_f_values if conditional_f_values is not None else f_values, dtype=float)
        photons = float(max(photon_count if photon_count is not None else 0.0, 0.0))
        if metric_key == "resolvability":
            return np.sqrt(photons / np.maximum(8.0 * np.square(np.maximum(cond_f, 1e-12)), 1e-12))
        return 72.0 * np.square(cond_f)

    def _set_resolvability_photon_default(self, photon_count):
        new_default = int(max(round(float(photon_count)), 1.0))
        current = int(self.spin_resolvability_photons.value())
        previous_default = int(max(self.resolvability_default_photon_count, 1))
        self.resolvability_default_photon_count = new_default
        if current == previous_default or current <= 1:
            self.spin_resolvability_photons.blockSignals(True)
            self.spin_resolvability_photons.setValue(new_default)
            self.spin_resolvability_photons.blockSignals(False)

    def _resolvability_photon_count(self, fallback_count):
        _metric_label, metric_key = self._metric_meta()
        if metric_key != "resolvability":
            return float(max(fallback_count if fallback_count is not None else 0.0, 0.0))
        return float(max(self.spin_resolvability_photons.value(), 1))

    def _update_metric_controls(self, metric_key):
        show_resolvability_photons = metric_key == "resolvability"
        self.lbl_resolvability_photons.setVisible(show_resolvability_photons)
        self.spin_resolvability_photons.setVisible(show_resolvability_photons)

    def _update_metric_availability(self):
        allowed = any(bool(payload.get("resolvability_enabled", False)) for payload in self.batch_data.values())
        self._resolvability_allowed = allowed
        model = self.combo_mode.model()
        for index in (3, 4):
            item = model.item(index)
            if item is not None:
                item.setEnabled(allowed)
        if not allowed and self.combo_mode.currentIndex() in (3, 4):
            self.combo_mode.blockSignals(True)
            self.combo_mode.setCurrentIndex(0)
            self.combo_mode.blockSignals(False)

    def plot_batch(self, x, results_dict, ideal_x=None, ideal_f=None, ideal_conditional_f=None, ideal_throughput_scale=None, ideal_photon_count=None, ci_level=None):
        if ci_level is not None:
            self.set_ci_level(ci_level)
        if ideal_x is not None:
            self.ideal_tau = np.array(ideal_x, copy=True)
            self.ideal_f = np.array(ideal_f, copy=True)
            if ideal_conditional_f is None:
                self.ideal_conditional_f = np.array(ideal_f, copy=True)
            else:
                self.ideal_conditional_f = np.array(ideal_conditional_f, copy=True)
        if ideal_throughput_scale is not None:
            self.ideal_throughput_scale = float(ideal_throughput_scale)
        if ideal_photon_count is not None:
            self.ideal_photon_count = float(max(ideal_photon_count, 0.0))
            self._set_resolvability_photon_default(self.ideal_photon_count)

        self.batch_data = {}
        x_copy = np.array(x, copy=True)
        for label, entry in results_dict.items():
            if isinstance(entry, dict):
                self.batch_data[label] = {
                    "x": x_copy,
                    "y": np.array(entry.get("y", []), copy=True),
                    "compatible": None if entry.get("compatible") is None else np.array(entry.get("compatible"), copy=True, dtype=bool),
                    "f_ci_lower": None if entry.get("f_ci_lower") is None else np.array(entry.get("f_ci_lower"), copy=True),
                    "f_ci_upper": None if entry.get("f_ci_upper") is None else np.array(entry.get("f_ci_upper"), copy=True),
                    "efficiency_ci_lower": None if entry.get("efficiency_ci_lower") is None else np.array(entry.get("efficiency_ci_lower"), copy=True),
                    "efficiency_ci_upper": None if entry.get("efficiency_ci_upper") is None else np.array(entry.get("efficiency_ci_upper"), copy=True),
                    "conditional_f": None if entry.get("conditional_f") is None else np.array(entry.get("conditional_f"), copy=True),
                    "conditional_f_ci_lower": None if entry.get("conditional_f_ci_lower") is None else np.array(entry.get("conditional_f_ci_lower"), copy=True),
                    "conditional_f_ci_upper": None if entry.get("conditional_f_ci_upper") is None else np.array(entry.get("conditional_f_ci_upper"), copy=True),
                    "photon_count": float(entry.get("photon_count", 0.0)),
                    "resolvability_enabled": bool(entry.get("resolvability_enabled", False)),
                    "throughput_scale": float(entry.get("throughput_scale", 1.0)),
                }
            else:
                self.batch_data[label] = {
                    "x": x_copy,
                    "y": np.array(entry, copy=True),
                    "compatible": None,
                    "f_ci_lower": None,
                    "f_ci_upper": None,
                    "efficiency_ci_lower": None,
                    "efficiency_ci_upper": None,
                    "conditional_f": None,
                    "conditional_f_ci_lower": None,
                    "conditional_f_ci_upper": None,
                    "photon_count": 0.0,
                    "resolvability_enabled": False,
                    "throughput_scale": 1.0,
                }

        self._update_metric_availability()
        self.refresh_plot()

    def update_data(self, x, f, label="Simulated", ideal_x=None, ideal_f=None, ideal_conditional_f=None, is_batch=False):
        if not is_batch:
            self.batch_data = {}
        self.batch_data[label] = {
            "x": np.array(x, copy=True),
            "y": np.array(f, copy=True),
            "compatible": None,
            "f_ci_lower": None,
            "f_ci_upper": None,
            "efficiency_ci_lower": None,
            "efficiency_ci_upper": None,
            "conditional_f": None,
            "conditional_f_ci_lower": None,
            "conditional_f_ci_upper": None,
            "photon_count": 0.0,
            "resolvability_enabled": False,
            "throughput_scale": 1.0,
        }
        if ideal_x is not None:
            self.ideal_tau = np.array(ideal_x, copy=True)
            self.ideal_f = np.array(ideal_f, copy=True)
            if ideal_conditional_f is None:
                self.ideal_conditional_f = np.array(ideal_f, copy=True)
            else:
                self.ideal_conditional_f = np.array(ideal_conditional_f, copy=True)
        self._update_metric_availability()
        self.refresh_plot()

    def clear_curves(self):
        self._clear_rendered_items()
        self._clear_dynamic_legend()
        self.batch_data = {}
        self.series_groups = {}
        self._has_mc_ci = False
        self.ideal_curve.setData([], [])
        self.resolvability_limit_curve.setData([], [])
        self.chk_show_mc_ci.setEnabled(False)
        self._update_metric_availability()

    def clear_data(self):
        self.clear_curves()
        self.plot_widget.enableAutoRange()

    def _clear_rendered_items(self):
        for item in self.rendered_items:
            self.plot_widget.removeItem(item)
        self.rendered_items = []

    def _clear_dynamic_legend(self):
        for widget in self.dynamic_legend_widgets:
            self.series_legend_holder.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self.dynamic_legend_widgets = []
        self.series_checkboxes = {}

    def _series_identity(self, label):
        category = "theory"
        if label.startswith("Monte Carlo"):
            category = "mc"
        elif label.startswith("Theory"):
            category = "theory"

        if " | " in label:
            base_label = label.split(" | ", 1)[1]
        elif label in {"Theory", "Monte Carlo", "Simulated"}:
            base_label = "Current Configuration"
        else:
            base_label = label
        return category, base_label

    def _ensure_series_group(self, base_label, color):
        group = self.series_groups.get(base_label)
        if group is not None:
            return group

        checked = self.series_visibility.get(base_label, True)
        checkbox = QCheckBox(base_label)
        checkbox.setChecked(checked)
        checkbox.setStyleSheet(f"color: {color}; font-weight: bold;")
        checkbox.stateChanged.connect(lambda _state, key=base_label: self._on_series_toggle(key))
        self.series_legend_holder.addWidget(checkbox)
        self.dynamic_legend_widgets.append(checkbox)
        self.series_checkboxes[base_label] = checkbox
        group = {"color": color, "checkbox": checkbox, "theory": [], "mc": [], "mc_ci": []}
        self.series_groups[base_label] = group
        return group

    def _on_series_toggle(self, base_label):
        checkbox = self.series_checkboxes.get(base_label)
        if checkbox is not None:
            self.series_visibility[base_label] = checkbox.isChecked()
        self._apply_visibility()

    def _register_item(self, base_label, category, item):
        self.series_groups[base_label][category].append(item)
        self.rendered_items.append(item)
        self.plot_widget.addItem(item)

    def _set_items_visible(self, items, visible):
        for item in items:
            item.setVisible(visible)

    def _apply_visibility(self):
        self.ideal_curve.setVisible(self.chk_show_ideal.isChecked())
        show_theory = self.chk_show_theory.isChecked()
        show_mc = self.chk_show_mc.isChecked()
        show_mc_ci = self.chk_show_mc_ci.isChecked()
        for base_label, group in self.series_groups.items():
            series_enabled = self.series_checkboxes.get(base_label).isChecked()
            self._set_items_visible(group["theory"], series_enabled and show_theory)
            self._set_items_visible(group["mc"], series_enabled and show_mc)
            self._set_items_visible(group["mc_ci"], series_enabled and show_mc_ci)

    def _export_legend_entries(self):
        entries = []
        if self.chk_show_ideal.isChecked() and self.ideal_curve.xData is not None and len(self.ideal_curve.xData) > 0:
            entries.append({"label": "Ideal Case", "color": "#10b981", "style": "dash"})
        show_theory = self.chk_show_theory.isChecked()
        show_mc = self.chk_show_mc.isChecked()
        show_mc_ci = self.chk_show_mc_ci.isChecked()
        for base_label, group in self.series_groups.items():
            checkbox = self.series_checkboxes.get(base_label)
            if checkbox is None or not checkbox.isChecked():
                continue
            if show_theory and group["theory"]:
                entries.append({"label": f"{base_label} (Theory)", "color": group["color"], "style": "line"})
            if show_mc and group["mc"]:
                entries.append({"label": f"{base_label} (MC)", "color": group["color"], "style": "marker"})
            if show_mc_ci and group["mc_ci"]:
                entries.append({"label": f"{base_label} ({self.chk_show_mc_ci.text()})", "color": group["color"], "style": "line"})
        return entries

    def _create_ci_band_items(self, x, lower, upper, color):
        invisible_pen = pg.mkPen(QColor(0, 0, 0, 0), width=1)
        lower_curve = pg.PlotDataItem(x=x, y=lower, pen=invisible_pen)
        upper_curve = pg.PlotDataItem(x=x, y=upper, pen=invisible_pen)
        color_obj = pg.mkColor(color)
        fill = pg.FillBetweenItem(
            upper_curve.curve,
            lower_curve.curve,
            brush=QColor(color_obj.red(), color_obj.green(), color_obj.blue(), 70),
        )
        fill.setZValue(1)
        return [lower_curve, upper_curve, fill]

    def _valid_mask(self, x_values, y_values):
        x_arr = np.asarray(x_values, dtype=float)
        y_arr = np.asarray(y_values, dtype=float)
        mask = np.isfinite(x_arr) & np.isfinite(y_arr)
        if self.chk_log_x.isChecked():
            mask &= x_arr > 0
        if self.chk_log_y.isChecked():
            mask &= y_arr > 0
        return mask

    def _apply_tight_ranges(self, x_values, y_values):
        x_arr = np.asarray(x_values, dtype=float)
        y_arr = np.asarray(y_values, dtype=float)
        mask = self._valid_mask(x_arr, y_arr)
        if not np.any(mask):
            return

        x_valid = x_arr[mask]
        y_valid = y_arr[mask]
        x_min = float(np.min(x_valid))
        x_max = float(np.max(x_valid))
        y_min = float(np.min(y_valid))
        y_max = float(np.max(y_valid))
        _metric_label, metric_key = self._metric_meta()

        if self.chk_log_x.isChecked():
            if np.isclose(x_min, x_max):
                x_min *= 0.9
                x_max *= 1.1
            log_min = np.log10(max(x_min, 1e-300))
            log_max = np.log10(max(x_max, 1e-300))
            if np.isclose(log_min, log_max):
                pad = max(abs(log_min) * 0.05, 0.05)
                x_range_min = log_min - pad
                x_range_max = log_max + pad
            else:
                log_pad = 0.04 * max(log_max - log_min, 0.1)
                x_range_min = log_min - log_pad
                x_range_max = log_max + log_pad
        else:
            if np.isclose(x_min, x_max):
                span = max(abs(x_min) * 0.05, 1e-6)
                x_min -= span
                x_max += span
            else:
                x_pad = 0.02 * (x_max - x_min)
                x_min -= x_pad
                x_max += x_pad
            x_range_min = x_min
            x_range_max = x_max

        if self.chk_log_y.isChecked():
            if metric_key == "resolvability":
                y_min = 1.0
                y_max = max(y_max, 3.0)
            if np.isclose(y_min, y_max):
                y_min *= 0.9
                y_max *= 1.1
            log_min = np.log10(max(y_min, 1e-300))
            log_max = np.log10(max(y_max, 1e-300))
            if np.isclose(log_min, log_max):
                pad = max(abs(log_min) * 0.05, 0.05)
                y_range_min = log_min - pad
                y_range_max = log_max + pad
            else:
                log_pad = 0.05 * max(log_max - log_min, 0.1)
                y_range_min = log_min - log_pad
                y_range_max = log_max + log_pad
        else:
            if metric_key == "resolvability":
                y_min = 0.0
                y_max = max(y_max, 3.0)
            if np.isclose(y_min, y_max):
                span = max(abs(y_min) * 0.05, 1e-6)
                y_min -= span
                y_max += span
            else:
                y_pad = 0.05 * (y_max - y_min)
                y_min -= y_pad
                y_max += y_pad
            y_range_min = y_min
            y_range_max = y_max

        self.plot_widget.disableAutoRange()
        self.plot_widget.setXRange(x_range_min, x_range_max, padding=0.0)
        self.plot_widget.setYRange(y_range_min, y_range_max, padding=0.0)

    def reset_axes(self):
        self.plot_widget.enableAutoRange()
        self.refresh_plot()

    def refresh_plot(self):
        self._clear_rendered_items()
        self._clear_dynamic_legend()
        self.series_groups = {}

        metric, metric_key = self._metric_meta()
        if metric_key in {"resolvability", "required_photons"} and not self._resolvability_allowed:
            self.combo_mode.blockSignals(True)
            self.combo_mode.setCurrentIndex(0)
            self.combo_mode.blockSignals(False)
            metric, metric_key = self._metric_meta()
        self.plot_widget.setLabel("left", metric)
        self.plot_widget.setLogMode(x=self.chk_log_x.isChecked(), y=self.chk_log_y.isChecked())
        self.resolvability_limit_curve.setData([], [])
        self._update_metric_controls(metric_key)

        all_x = []
        all_y = []
        color_map = {}
        color_index = 0
        has_any_ci = False

        for label, payload in self.batch_data.items():
            category, base_label = self._series_identity(label)
            if base_label not in color_map:
                color_map[base_label] = self.colors[color_index % len(self.colors)]
                color_index += 1
            color = color_map[base_label]
            group = self._ensure_series_group(base_label, color)

            x = np.array(payload["x"], copy=False)
            f = np.array(payload["y"], copy=False)
            conditional_f = payload.get("conditional_f")
            photon_count = self._resolvability_photon_count(payload.get("photon_count", 0.0))
            throughput_scale = float(payload.get("throughput_scale", 1.0))
            if metric_key in {"resolvability", "required_photons"} and not bool(payload.get("resolvability_enabled", False)):
                continue
            y_data = self._display_metric_values(f, throughput_scale, conditional_f_values=conditional_f, photon_count=photon_count)
            mask = self._valid_mask(x, y_data)
            if not np.any(mask):
                continue

            all_x.append(np.array(x[mask], copy=True))
            all_y.append(np.array(y_data[mask], copy=True))

            if category == "mc":
                if metric_key == "f":
                    ci_lower = payload.get("f_ci_lower")
                    ci_upper = payload.get("f_ci_upper")
                elif metric_key in {"efficiency", "throughput"}:
                    ci_lower = payload.get("efficiency_ci_lower")
                    ci_upper = payload.get("efficiency_ci_upper")
                else:
                    cond_ci_lower = payload.get("conditional_f_ci_lower")
                    cond_ci_upper = payload.get("conditional_f_ci_upper")
                    if cond_ci_lower is None or cond_ci_upper is None:
                        ci_lower = None
                        ci_upper = None
                    elif metric_key == "resolvability":
                        ci_lower = np.sqrt(float(max(photon_count, 0.0)) / np.maximum(8.0 * np.square(np.maximum(np.asarray(cond_ci_upper, dtype=float), 1e-12)), 1e-12))
                        ci_upper = np.sqrt(float(max(photon_count, 0.0)) / np.maximum(8.0 * np.square(np.maximum(np.asarray(cond_ci_lower, dtype=float), 1e-12)), 1e-12))
                    else:
                        ci_lower = 72.0 * np.square(np.asarray(cond_ci_lower, dtype=float))
                        ci_upper = 72.0 * np.square(np.asarray(cond_ci_upper, dtype=float))
                has_ci = (
                    ci_lower is not None
                    and ci_upper is not None
                    and np.any(np.isfinite(ci_lower))
                    and np.any(np.isfinite(ci_upper))
                )
                if has_ci:
                    ci_lower = np.array(ci_lower, copy=True)
                    ci_upper = np.array(ci_upper, copy=True)
                    if metric_key == "efficiency":
                        ci_lower = np.minimum(1.0, ci_lower)
                        ci_upper = np.minimum(1.0, ci_upper)
                    if metric_key == "throughput":
                        ci_lower = ci_lower * throughput_scale
                        ci_upper = ci_upper * throughput_scale
                    ci_mask = mask & self._valid_mask(x, ci_lower) & self._valid_mask(x, ci_upper)
                    if np.any(ci_mask):
                        has_any_ci = True
                        all_x.append(np.array(x[ci_mask], copy=True))
                        all_y.append(np.array(ci_lower[ci_mask], copy=True))
                        all_x.append(np.array(x[ci_mask], copy=True))
                        all_y.append(np.array(ci_upper[ci_mask], copy=True))
                        for segment in self._segment_indices(ci_mask):
                            for item in self._create_ci_band_items(x[segment], ci_lower[segment], ci_upper[segment], color):
                                self._register_item(base_label, "mc_ci", item)

            compatible = payload.get("compatible")
            compatible_mask = mask.copy()
            incompatible_mask = np.zeros_like(mask, dtype=bool)
            if category == "mc" and compatible is not None and compatible.shape == x.shape:
                compatible_mask = mask & compatible
                incompatible_mask = mask & (~compatible)

            if category == "mc":
                if np.any(compatible_mask):
                    item = pg.PlotDataItem(
                        x=x[compatible_mask],
                        y=y_data[compatible_mask],
                        pen=None,
                        symbol="o",
                        symbolSize=7,
                        symbolBrush=pg.mkBrush(color),
                        symbolPen=pg.mkPen(color=color),
                    )
                    self._register_item(base_label, "mc", item)
                if np.any(incompatible_mask):
                    item = pg.PlotDataItem(
                        x=x[incompatible_mask],
                        y=y_data[incompatible_mask],
                        pen=None,
                        symbol="o",
                        symbolSize=7,
                        symbolBrush=pg.mkBrush("#6b7280"),
                        symbolPen=pg.mkPen(color="#9ca3af"),
                    )
                    self._register_item(base_label, "mc", item)
            else:
                item = pg.PlotDataItem(
                    x=x[mask],
                    y=y_data[mask],
                    pen=pg.mkPen(color=color, width=2),
                )
                self._register_item(base_label, "theory", item)

        if self.ideal_tau is not None and self.ideal_f is not None:
            ideal_y = self._display_metric_values(
                self.ideal_f,
                self.ideal_throughput_scale,
                conditional_f_values=self.ideal_conditional_f if self.ideal_conditional_f is not None else self.ideal_f,
                photon_count=self._resolvability_photon_count(self.ideal_photon_count),
            )
            ideal_mask = self._valid_mask(self.ideal_tau, ideal_y)
            if np.any(ideal_mask):
                self.ideal_curve.setData(self.ideal_tau[ideal_mask], ideal_y[ideal_mask])
                all_x.append(np.array(self.ideal_tau[ideal_mask], copy=True))
                all_y.append(np.array(ideal_y[ideal_mask], copy=True))
            else:
                self.ideal_curve.setData([], [])
        else:
            self.ideal_curve.setData([], [])

        if all_x and all_y:
            self._apply_tight_ranges(np.concatenate(all_x), np.concatenate(all_y))

        if metric_key == "resolvability" and all_x:
            x_concat = np.concatenate(all_x)
            x_mask = np.isfinite(x_concat)
            if self.chk_log_x.isChecked():
                x_mask &= x_concat > 0
            if np.any(x_mask):
                x_line = np.array([np.min(x_concat[x_mask]), np.max(x_concat[x_mask])], dtype=float)
                self.resolvability_limit_curve.setData(x_line, np.full(2, 3.0, dtype=float))

        self._has_mc_ci = has_any_ci
        self.chk_show_mc_ci.setEnabled(has_any_ci)
        self._apply_visibility()
