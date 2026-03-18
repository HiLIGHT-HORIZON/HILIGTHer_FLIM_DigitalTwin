import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtGui import QGuiApplication

class DecayWidget(QWidget):
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

        self.plot_item = pg.PlotWidget()
        self.plot_item.setBackground('k')
        self.plot_item.setLabel('left', 'Photon Counts')
        self.plot_item.setLabel('bottom', 'Time [ns]')
        self.plot_item.addLegend()
        
        # Curves
        self.decay_curve = self.plot_item.plot(pen=pg.mkPen('w', width=1.5), name='Raw Decay')
        self.fit_curve = self.plot_item.plot(pen=pg.mkPen('r', width=2), name='Analytic Fit')
        
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
        raw_color = 'w' if dark else '#111827'
        fit_color = '#ef4444' if dark else '#b91c1c'
        self.plot_item.setBackground(bg)
        for axis_name in ('bottom', 'left'):
            axis = self.plot_item.getAxis(axis_name)
            axis.setTextPen(pg.mkPen(text))
            axis.setPen(pg.mkPen(text))
        self.decay_curve.setPen(pg.mkPen(raw_color, width=1.5))
        self.fit_curve.setPen(pg.mkPen(fit_color, width=2))

    def update_decay(self, t, counts, fit=None):
        self.decay_curve.setData(t, counts)
        if fit is not None:
            self.fit_curve.setData(t, fit)
            self.fit_curve.show()
        else:
            self.fit_curve.hide()
