import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtGui import QGuiApplication

class DecayWidget(QWidget):
    def __init__(self):
        super().__init__()
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

    def _copy_to_clipboard(self):
        pixmap = self.grab()
        QGuiApplication.clipboard().setPixmap(pixmap)

    def update_decay(self, t, counts, fit=None):
        self.decay_curve.setData(t, counts)
        if fit is not None:
            self.fit_curve.setData(t, fit)
            self.fit_curve.show()
        else:
            self.fit_curve.hide()
