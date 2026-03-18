import pyqtgraph as pg
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal

class MapWidget(QWidget):
    pixel_selected = pyqtSignal(int, int) # y, x

    def __init__(self, title="Gradient Map"):
        super().__init__()
        layout = QVBoxLayout(self)
        
        self.view = pg.ImageView()
        # Remove menu button for cleaner look
        self.view.ui.menuBtn.hide()
        self.view.ui.roiBtn.hide()
        
        # Color Map (Firefly-like thermal)
        colors = [
            (0, 0, 0),
            (0, 0, 150),
            (255, 0, 0),
            (255, 255, 0),
            (255, 255, 255)
        ]
        cmap = pg.ColorMap(pos=np.linspace(0.0, 1.0, 5), color=colors)
        self.view.setColorMap(cmap)
        
        # Crosshair for selection
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen='w')
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen='w')
        self.view.addItem(self.v_line, ignoreBounds=True)
        self.view.addItem(self.h_line, ignoreBounds=True)
        
        # Event Handling
        self.view.scene.sigMouseClicked.connect(self._on_click)
        
        layout.addWidget(self.view)

    def set_image(self, data):
        """Expects 2D numpy array."""
        self.view.setImage(data.T) # Transpose for pyqtgraph (x,y)

    def _on_click(self, ev):
        if ev.button() == pg.QtCore.Qt.MouseButton.LeftButton:
            pos = ev.scenePos()
            if self.view.view.sceneBoundingRect().contains(pos):
                mouse_point = self.view.view.mapSceneToView(pos)
                x, y = int(mouse_point.x()), int(mouse_point.y())
                # Bound checking
                img = self.view.image
                if img is not None:
                    if 0 <= x < img.shape[0] and 0 <= y < img.shape[1]:
                        self.v_line.setPos(mouse_point.x())
                        self.h_line.setPos(mouse_point.y())
                        self.pixel_selected.emit(y, x)
