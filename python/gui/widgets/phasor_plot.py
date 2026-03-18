import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal, Qt

class PhasorWidget(QWidget):
    roi_changed = pyqtSignal(float, float, float, float) # g_min, g_max, s_min, s_max

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Plot Configuration
        self.plot_item = pg.PlotWidget()
        self.plot_item.setBackground('k')
        self.plot_item.setAspectLocked(True)
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.plot_item.setLabel('left', 'S (Imaginary)')
        self.plot_item.setLabel('bottom', 'G (Real)')
        self.plot_item.setXRange(0, 1)
        self.plot_item.setYRange(0, 0.6)
        
        # Theoretical Locus (Semicircle)
        t = np.linspace(0, np.pi, 100)
        lx = 0.5 + 0.5 * np.cos(t)
        ly = 0.5 * np.sin(t)
        self.locus_curve = pg.PlotCurveItem(lx, ly, pen=pg.mkPen('w', width=1, style=Qt.PenStyle.DashLine))
        self.plot_item.addItem(self.locus_curve)
        
        # Scatter for Data
        self.scatter = pg.ScatterPlotItem(size=3, pen=None, brush=pg.mkBrush(100, 150, 255, 150))
        self.plot_item.addItem(self.scatter)
        
        # ROI Selector (Square)
        self.roi = pg.RectROI([0.4, 0.2], [0.2, 0.2], pen=(0, 255, 0))
        self.plot_item.addItem(self.roi)
        self.roi.sigRegionChanged.connect(self._on_roi_change)

        layout.addWidget(self.plot_item)

    def update_data(self, g, s):
        """Update the scatter plot with new G and S maps."""
        # Flatten and filter nans
        g_flat = g.flatten()
        s_flat = s.flatten()
        mask = ~(np.isnan(g_flat) | np.isnan(s_flat))
        self.scatter.setData(x=g_flat[mask], y=s_flat[mask])

    def _on_roi_change(self):
        pos = self.roi.pos()
        size = self.roi.size()
        self.roi_changed.emit(pos.x(), pos.x() + size.x(), pos.y(), pos.y() + size.y())

# Internal helper for testing
