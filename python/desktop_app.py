import sys
import os
import qdarkstyle
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt

# CRITICAL: WebEngine requires AA_ShareOpenGLContexts to be set before QApplication
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    pass # Handle in dependency check if missing

# --- NEW: Splash Screen Integration ---
def main():
    # Performance boost for PyQt
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    # Initialize Core Application with necessary attributes for WebEngine
    # These MUST be set before QApplication is instantiated
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    
    app = QApplication(sys.argv)
    
    # Set App Icon
    repo_root = os.path.dirname(os.path.dirname(__file__))
    icon_path = os.path.join(repo_root, "python", "frontend", "assets", "logo_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Initialize Splash Screen
    from gui.splash_screen import HILIGHTSplashScreen
    logo_path = os.path.join(repo_root, "python", "frontend", "assets", "logo1.png")
    splash = HILIGHTSplashScreen(logo_path)
    splash.show()
    
    # 1. Loading Graphics & Styles
    splash.log("Loading Firefly Theme...")
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt6())
    
    # 2. Project Dependency Check (Optional but nice for splash)
    splash.log("Checking project dependencies...")
    try:
        req_path = os.path.join(repo_root, "python", "desktop_requirements.txt")
        if os.path.exists(req_path):
            # Run a quiet pip install to ensure everything is there, but capture output to log
            process = subprocess.Popen([sys.executable, "-m", "pip", "install", "-r", req_path, "--quiet"], 
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            splash.log("Verifying libraries (PyQt6, NumPy, etc.)...")
            # We don't want to block too long if it's already installed
            try:
                process.wait(timeout=5)
                if process.returncode == 0:
                    splash.log("All dependencies verified.")
                else:
                    splash.log("Warning: Dependency check returned non-zero code.")
            except subprocess.TimeoutExpired:
                splash.log("Dependency check taking time, continuing in background...")
    except Exception as e:
        splash.log(f"Dependency check skipped: {str(e)}")

    # 3. Importing Main Window (Heavier operation)
    splash.log("Initializing HILIGHTer GUI modules...")
    from gui.main_window import HILIGHTMainWindow
    
    # 4. Setting up Main Window
    splash.log("Building twin engine workspace...")
    window = HILIGHTMainWindow()
    
    splash.log("Startup complete. Launching...")
    window.show()
    splash.finish(window)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
