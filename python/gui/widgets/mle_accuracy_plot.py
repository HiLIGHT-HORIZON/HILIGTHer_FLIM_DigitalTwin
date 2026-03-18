import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QCheckBox, QFrame, QScrollArea, QPushButton)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication


class MLEAccuracyWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.current_theme = "dark"
        self.colors = ['#8b5cf6', '#3b82f6', '#ec4899', '#f59e0b', '#ef4444', '#06b6d4', '#84cc16']
        self.series_items = [] # List of (items, legend_checkbox)
        self.series_data = {}
        self.x_label = "Ground Truth"
        self.y_offset = 0.0

        # Controls Header
        ctrl_layout = QHBoxLayout()
        self.chk_stacked = QCheckBox("Stacked View (Y-Offset)")
        self.chk_stacked.setChecked(True)
        self.chk_stacked.setToolTip("Apply an artificial offset to separate overlapping sweep curves.")
        self.chk_stacked.stateChanged.connect(self.refresh_plot)
        ctrl_layout.addWidget(self.chk_stacked)
        
        self.btn_copy = QPushButton("📋")
        self.btn_copy.setToolTip("Copy screenshot to clipboard")
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        self.btn_copy.setMaximumWidth(30)
        self.btn_copy.setStyleSheet("padding: 2px; font-size: 14px;")
        ctrl_layout.addWidget(self.btn_copy)

        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # Main Display Layout
        display_layout = QHBoxLayout()
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#0a0a0a')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('bottom', self.x_label)
        self.plot_widget.setLabel('left', 'Estimated Value')
        display_layout.addWidget(self.plot_widget, stretch=4)

        # Legend Panel
        self.legend_panel = QFrame()
        self.legend_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.legend_panel.setMinimumWidth(200)
        self.legend_layout = QVBoxLayout(self.legend_panel)
        self.legend_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.legend_panel)
        display_layout.addWidget(scroll, stretch=1)
        
        self.legend_title = QLabel("<b style='font-size: 14px; color: #fff;'>MLE Tracking (stacked)</b>")
        self.legend_layout.addWidget(self.legend_title)
        self.legend_layout.addSpacing(10)
        
        layout.addLayout(display_layout)
        self.set_theme("dark")

        self.expected_line = self.plot_widget.plot(
            pen=pg.mkPen(color='#d1d5db', width=1.5, style=Qt.PenStyle.DashLine),
            name="Expected Mean"
        )

    def _copy_to_clipboard(self):
        pixmap = self.grab()
        QGuiApplication.clipboard().setPixmap(pixmap)

    def set_theme(self, theme_name):
        self.current_theme = str(theme_name).lower()
        dark = self.current_theme == "dark"
        bg = '#0a0a0a' if dark else '#ffffff'
        text = '#e5eefb' if dark else '#0f172a'
        border = '#334155' if dark else '#cbd5e1'
        self.plot_widget.setBackground(bg)
        for axis_name in ('bottom', 'left'):
            axis = self.plot_widget.getAxis(axis_name)
            axis.setTextPen(pg.mkPen(text))
            axis.setPen(pg.mkPen(text))
        self.legend_panel.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}"
        )
        if hasattr(self, "expected_line"):
            self.refresh_plot()

    def set_xaxis_label(self, text):
        self.x_label = text
        self.plot_widget.setLabel('bottom', text)

    def clear_data(self):
        for items, widget in self.series_items:
            for item in items:
                self.plot_widget.removeItem(item)
            widget.setParent(None)
            widget.deleteLater()
        self.series_items = []
        self.series_data = {}
        self.expected_line.setData([], [])

    def _add_manual_legend(self, label, items, color=None):
        chk = QCheckBox(label)
        chk.setChecked(True)
        if color: chk.setStyleSheet(f"color: {color}; font-weight: bold;")
        chk.stateChanged.connect(
            lambda state: [item.setVisible(state == Qt.CheckState.Checked.value) for item in items]
        )
        self.legend_layout.addWidget(chk)
        return chk

    def plot_accuracy(self, x, series_dict):
        self.series_data = {}
        x_copy = np.array(x, copy=True)
        for label, payload in series_dict.items():
            self.series_data[label] = {
                "x": x_copy,
                "mean": np.array(payload["mean"], copy=True),
                "std": np.array(payload["std"], copy=True),
            }
        self.refresh_plot()

    def refresh_plot(self):
        # Clear existing items and legend widgets
        for items, widget in self.series_items:
            for item in items:
                self.plot_widget.removeItem(item)
            widget.setParent(None)
            widget.deleteLater()
        self.series_items = []

        all_x = []
        all_y = []
        stacked = self.chk_stacked.isChecked()
        title_color = "#e5eefb" if self.current_theme == "dark" else "#0f172a"
        self.legend_title.setText(
            f"<b style='font-size: 14px; color: {title_color};'>MLE Tracking (stacked)</b>"
            if stacked else
            f"<b style='font-size: 14px; color: {title_color};'>MLE Tracking</b>"
        )
        
        # Calculate offset based on range if stacked
        offset_step = 0.0
        if stacked and self.series_data:
            # Heuristic: use a fraction of the total range across all means
            all_means = [p["mean"] for p in self.series_data.values()]
            if all_means:
                flat_means = np.concatenate(all_means)
                if flat_means.size > 0:
                    span = np.nanmax(flat_means) - np.nanmin(flat_means)
                    offset_step = max(span * 0.15, 1.0) # At least 1ns or 15% span

        for idx, (label, payload) in enumerate(self.series_data.items()):
            x = payload["x"]
            mean = payload["mean"]
            std = payload["std"]
            finite_mask = np.isfinite(x) & np.isfinite(mean) & np.isfinite(std)
            if not np.any(finite_mask):
                continue

            x_f = x[finite_mask]
            mean_f = mean[finite_mask]
            
            # Apply stacking offset
            current_offset = idx * offset_step if stacked else 0.0
            mean_display = mean_f + current_offset
            
            std_f = std[finite_mask]
            color = self.colors[idx % len(self.colors)]

            curve = pg.PlotDataItem(
                x_f,
                mean_display,
                pen=pg.mkPen(color=color, width=2),
                symbol='o',
                symbolSize=6,
                symbolBrush=pg.mkBrush(color),
                symbolPen=pg.mkPen(color=color),
                name=label,
            )
            bars = pg.ErrorBarItem(
                x=x_f,
                y=mean_display,
                top=std_f,
                bottom=std_f,
                beam=0.04,
                pen=pg.mkPen(color=color, width=1),
            )
            
            # Create identity line (x=y) with offset
            identity_item = pg.PlotDataItem(
                x_f, x_f + current_offset,
                pen=pg.mkPen(color='#d1d5db', width=1.5, style=Qt.PenStyle.DashLine),
                name=f"Expected | {label}"
            )
            
            self.plot_widget.addItem(curve)
            self.plot_widget.addItem(bars)
            self.plot_widget.addItem(identity_item)
            
            # Create legend toggle
            chk = self._add_manual_legend(label, [curve, bars, identity_item], color)
            self.series_items.append(([curve, bars, identity_item], chk))
            
            all_x.append(x_f)
            all_y.append(mean_display + std_f) # Include error bars in range
            all_y.append(mean_display - std_f)

        if all_x:
            x_all = np.concatenate(all_x)
            y_all = np.concatenate(all_y)
            lo = float(np.nanmin(x_all))
            hi = float(np.nanmax(x_all))
            
            # Hide the global expected_line as we now use per-series identity lines
            self.expected_line.hide()
                
            ymin = float(np.nanmin(y_all))
            ymax = float(np.nanmax(y_all))
            self.plot_widget.setYRange(ymin, ymax, padding=0.05)
            self.plot_widget.setXRange(lo, hi, padding=0.05)
        else:
            self.expected_line.setData([], [])
