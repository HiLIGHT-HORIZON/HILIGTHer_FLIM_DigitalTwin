import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Add python directory to path so imports work
repo_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(repo_root, "python"))

from gui.splash_screen import HILIGHTSplashScreen

app = QApplication(sys.argv)
logo_path = os.path.join(repo_root, "python", "frontend", "assets", "logo1.png")

splash = HILIGHTSplashScreen(logo_path)
splash.show()
splash.log("Splash Screen Demo Mode...")
splash.log("Testing interactive links!")

# Automatically close after 15 seconds so it doesn't hang forever
QTimer.singleShot(15000, app.quit)

print("Splash screen launched! It will automatically close in 15 seconds.")
app.exec()
print("Splash screen visual test finished.")
