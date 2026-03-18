import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout

class DecayWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        self.plot_item = pg.PlotWidget()
        self.plot_item.setBackground('k')
        self.plot_item.setLabel('left', 'Photon Counts')
        self.plot_item.setLabel('bottom', 'Time [ns]')
        self.plot_item.addLegend()
        
        # Curves
        self.decay_curve = self.plot_item.plot(pen=pg.mkPen('w', width=1.5), name='Raw Decay')
        self.fit_curve = self.plot_item.plot(pen=pg.mkPen('r', width=2), name='Analytic Fit')
        
        layout.addWidget(self.plot_item)

    def update_decay(self, t, counts, fit=None):
        self.decay_curve.setData(t, counts)
        if fit is not None:
            self.fit_curve.setData(t, fit)
            self.fit_curve.show()
        else:
            self.fit_curve.hide()
