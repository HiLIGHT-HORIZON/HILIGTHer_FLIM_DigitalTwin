import sys
import os
import subprocess
import importlib
import qdarkstyle
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt

# CRITICAL: WebEngine requires AA_ShareOpenGLContexts to be set before QApplication
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    pass # Handle in dependency check if missing

REQUIRED_DESKTOP_MODULES = [
    "PyQt6",
    "PyQt6.QtWebEngineWidgets",
    "pyqtgraph",
    "qdarkstyle",
    "numpy",
    "scipy",
    "pydantic",
    "numba",
    "h5py",
]


def _missing_desktop_modules():
    missing = []
    for module_name in REQUIRED_DESKTOP_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            missing.append((module_name, str(exc)))
    return missing


def _stream_dependency_update(repo_root, splash):
    req_path = os.path.join(repo_root, "python", "desktop_requirements.txt")
    if not os.path.exists(req_path):
        message = "Dependency file not found: desktop_requirements.txt"
        print(message, flush=True)
        splash.log(message)
        return

    missing_before = _missing_desktop_modules()
    if not missing_before:
        message = "Desktop dependencies already available locally; skipping online update."
        print(message, flush=True)
        splash.log(message)
        return

    commands = [
        ("Checking pip version...", [sys.executable, "-m", "pip", "--version"]),
        (
            "Installing missing desktop dependencies...",
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--upgrade",
                "-r",
                req_path,
            ],
        ),
    ]

    for title, command in commands:
        print(title, flush=True)
        splash.log(title)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        try:
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                print(line, flush=True)
                splash.log(line)
            process.wait()
        finally:
            if process.stdout is not None:
                process.stdout.close()
        if process.returncode != 0:
            break

    missing_after = _missing_desktop_modules()
    if missing_after:
        if missing_before == missing_after:
            details = "; ".join(f"{name}: {err}" for name, err in missing_after)
            raise RuntimeError(f"Required desktop modules are still unavailable: {details}")
        details = "; ".join(f"{name}: {err}" for name, err in missing_after)
        raise RuntimeError(f"Desktop dependency install did not complete successfully: {details}")

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
    
    # 2. Project Dependency Check and Update
    try:
        splash.log("Checking and updating desktop dependencies...")
        _stream_dependency_update(repo_root, splash)
        splash.log("All dependencies are up to date.")
    except Exception as e:
        message = f"Dependency update failed: {str(e)}"
        print(message, flush=True)
        splash.log(message)
        raise

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
