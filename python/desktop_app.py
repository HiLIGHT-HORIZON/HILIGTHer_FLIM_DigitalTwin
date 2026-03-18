import sys
import os
import qdarkstyle
from PyQt6.QtWidgets import QApplication
from gui.main_window import HILIGHTMainWindow

def main():
    # Performance boost for PyQt
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    
    # Load Firefly Theme
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt6())
    
    window = HILIGHTMainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
