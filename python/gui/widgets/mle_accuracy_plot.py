import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel


class MLEAccuracyWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.colors = ['#8b5cf6', '#3b82f6', '#ec4899', '#f59e0b', '#ef4444', '#06b6d4', '#84cc16']
        self.series_items = []
        self.series_data = {}
        self.x_label = "Ground Truth"

        header = QHBoxLayout()
        header.addWidget(QLabel("Gridded MLE Accuracy"))
        header.addStretch()
        layout.addLayout(header)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#0a0a0a')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('bottom', self.x_label)
        self.plot_widget.setLabel('left', 'Estimated Value')
        layout.addWidget(self.plot_widget)

        self.expected_line = self.plot_widget.plot(
            pen=pg.mkPen(color='#d1d5db', width=1.5, style=pg.QtCore.Qt.PenStyle.DashLine),
            name="Expected Mean"
        )

    def set_xaxis_label(self, text):
        self.x_label = text
        self.plot_widget.setLabel('bottom', text)

    def clear_data(self):
        for item in self.series_items:
            self.plot_widget.removeItem(item)
        self.series_items = []
        self.series_data = {}
        self.expected_line.setData([], [])

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
        for item in self.series_items:
            self.plot_widget.removeItem(item)
        self.series_items = []

        all_x = []
        all_y = []
        for idx, (label, payload) in enumerate(self.series_data.items()):
            x = payload["x"]
            mean = payload["mean"]
            std = payload["std"]
            finite_mask = np.isfinite(x) & np.isfinite(mean) & np.isfinite(std)
            if not np.any(finite_mask):
                continue

            x_f = x[finite_mask]
            mean_f = mean[finite_mask]
            std_f = std[finite_mask]
            color = self.colors[idx % len(self.colors)]

            curve = pg.PlotDataItem(
                x_f,
                mean_f,
                pen=pg.mkPen(color=color, width=2),
                symbol='o',
                symbolSize=6,
                symbolBrush=pg.mkBrush(color),
                symbolPen=pg.mkPen(color=color),
                name=label,
            )
            bars = pg.ErrorBarItem(
                x=x_f,
                y=mean_f,
                top=std_f,
                bottom=std_f,
                beam=0.04,
                pen=pg.mkPen(color=color, width=1),
            )
            self.plot_widget.addItem(curve)
            self.plot_widget.addItem(bars)
            self.series_items.extend([curve, bars])
            all_x.append(x_f)
            all_y.append(mean_f)

        if all_x:
            x_all = np.concatenate(all_x)
            y_all = np.concatenate(all_y)
            lo = float(np.nanmin(x_all))
            hi = float(np.nanmax(x_all))
            self.expected_line.setData([lo, hi], [lo, hi])
            ymin = min(lo, float(np.nanmin(y_all)))
            ymax = max(hi, float(np.nanmax(y_all)))
            self.plot_widget.setYRange(ymin, ymax, padding=0.05)
        else:
            self.expected_line.setData([], [])
