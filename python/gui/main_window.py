import sys
import os
import copy
import json
import numpy as np
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QApplication, QDockWidget, 
                             QVBoxLayout, QWidget, QStatusBar, QFileDialog,
                             QMenuBar, QDialog, QHBoxLayout, QPushButton, QMessageBox, QCheckBox)
from PyQt6.QtGui import QAction, QActionGroup, QDesktopServices, QGuiApplication
from PyQt6.QtCore import Qt, QUrl
import qdarkstyle

# Import custom widgets
from gui.widgets.phasor_plot import PhasorWidget
from gui.widgets.decay_plot import DecayWidget
from gui.widgets.image_viewer import MapWidget
from gui.widgets.controls import ControlWidget
from gui.widgets.fisher_plot import FisherWidget
from gui.widgets.mle_accuracy_plot import MLEAccuracyWidget
from gui.widgets.diagnostics_plot import DiagnosticsWidget
from gui.widgets.instrument_manager import InstrumentManager
from gui.widgets.manual_viewer import ManualWidget
from gui.widgets.custom_model_editor import CustomModelEditorDialog
from gui.automation_api import DesktopAutomationAPI
from gui.optimisation_worker import DetectionOptimisationWorker
from gui.report_export import write_precision_report_package
from backend.models import PhysicsConfig
from backend.decay_model_store import DecayModelStore
from backend.profile_store import InstrumentProfileStore
from backend.storage import storage
from metadata import get_build_label, get_full_version_label


LIGHT_APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #f3f6fb;
    color: #0f172a;
}
QDockWidget::title {
    background: #e5edf6;
    color: #0f172a;
    padding: 6px 10px;
    border: 1px solid #cbd5e1;
}
QMenuBar, QMenu, QStatusBar {
    background: #ffffff;
    color: #0f172a;
}
QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QLineEdit {
    background: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px 8px;
}
QCheckBox, QLabel, QGroupBox, QRadioButton {
    color: #0f172a;
}
QGroupBox {
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 10px;
    background: #ffffff;
}
QScrollArea, QTabWidget::pane {
    background: #f8fafc;
    border: 1px solid #dbe4ef;
}
"""

class HILIGHTMainWindow(QMainWindow):
    LAYOUT_VERSION = 5

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"HILIGHTer Digital Twin v{get_full_version_label()} | Desktop Workspace")
        self._apply_startup_geometry()
        
        # Initialize Core Engine
        from backend.twin_engine import TwinEngine
        self.engine = TwinEngine()
        self.decay_model_store = DecayModelStore()
        self.profile_store = InstrumentProfileStore()
        
        # Setup Widgets
        self.map_widget = MapWidget("Lifetime Gradient Map")
        self.phasor_widget = PhasorWidget()
        self.decay_widget = DecayWidget()
        self.control_widget = ControlWidget()
        self.control_widget.decay_model_store = self.decay_model_store
        self.control_widget.custom_model_editor_requested.connect(self.open_custom_model_editor)
        self.fisher_widget = FisherWidget()
        self.mle_accuracy_widget = MLEAccuracyWidget()
        self.diagnostics_widget = DiagnosticsWidget()
        self.control_widget.update_from_config(self.engine.config)
        self.control_widget.btn_export.setEnabled(False)
        self.last_precision_run = None
        self.last_optimization_run = None
        self.optimization_results_saved = False
        self.optimization_results_imported = False
        self.optimization_mode_active = False
        self.optimization_running = False
        self.optimization_toggle_suppressed = False
        self.loading_config_into_ui = False
        self.optimization_worker = None
        self.optimization_baseline_snapshot = None
        self.optimization_x_range = None
        self.optimization_ideal_f = None
        self.optimization_ideal_f_conditional = None
        self.optimization_autoplay_previous = None
        self.last_validation_run = None
        self.validation_fit_summary = None
        self.workspace_mode = None
        self.desktop_api = DesktopAutomationAPI(self)
        self.simulation_core_prompted_session = False
        self.event_driven_warning_shown_session = False
        self.startup_complete = False
        
        # Security & API State (Default open)
        self.gui_api_locked = False
        self.backend_api_locked = False
        self.mcp_server_stopped = False
        self._sync_locks_to_disk()
        
        # Setup Manual (Persistent Sidepanel)
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        manual_path = os.path.join(repo_root, "docs", "manual", "index.html")
        manual_fallback = os.path.join(repo_root, "python", "frontend", "public", "manual.html")
        self.manual_widget = ManualWidget(manual_path if os.path.exists(manual_path) else manual_fallback)
        
        # Setup Layout
        self.init_menu()
        self.setup_docks()
        self.connect_signals()
        self._update_primary_action_buttons()
        
        # Status Bar with Progress
        from PyQt6.QtWidgets import QProgressBar
        self.progress = QProgressBar()
        self.progress.setMaximumHeight(15)
        self.progress.setMaximumWidth(200)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)
        
        # Initial State
        self.statusBar().showMessage("Ready.")
        
        # Persistence: Restore Layout
        from PyQt6.QtCore import QSettings
        self.settings = QSettings("HILIGHT", "DigitalTwin")
        self.apply_theme() # Apply theme before restoring layout/state
        self.restore_layout()
        
        # Initial Plot Refresh
        self._update_simulation_mode_badge()
        self.refresh_diagnostics()
        self.startup_complete = True

    def _sync_locks_to_disk(self):
        """Persist lock state for access by the MCP server and other sub-processes."""
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(data_dir, exist_ok=True)
        lock_file = os.path.join(data_dir, "app_locks.json")
        try:
            with open(lock_file, "w") as f:
                json.dump({
                    "gui_api_locked": bool(self.gui_api_locked),
                    "backend_api_locked": bool(self.backend_api_locked),
                    "mcp_server_stopped": bool(self.mcp_server_stopped)
                }, f)
        except Exception:
            pass

    def save_layout(self):
        self.settings.setValue("layoutVersion", self.LAYOUT_VERSION)
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        screen = self._available_screen_geometry()
        if screen is not None:
            self.settings.setValue("screenWidth", screen.width())
            self.settings.setValue("screenHeight", screen.height())

    def restore_layout(self):
        saved_version = self.settings.value("layoutVersion", 0, int)
        if saved_version != self.LAYOUT_VERSION:
            self._apply_default_dock_sizes()
            self._fit_window_to_screen()
            return
        current_screen = self._available_screen_geometry()
        saved_width = self.settings.value("screenWidth", 0, int)
        saved_height = self.settings.value("screenHeight", 0, int)
        if current_screen is not None and saved_width and saved_height:
            if saved_width > current_screen.width() or saved_height > current_screen.height():
                self._clear_saved_layout()
                self._apply_default_dock_sizes()
                self._fit_window_to_screen()
                return
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)
        self._fit_window_to_screen()
        if current_screen is not None:
            min_hint = self.minimumSizeHint()
            if min_hint.width() > current_screen.width() or min_hint.height() > current_screen.height():
                self._clear_saved_layout()
                self._apply_default_dock_sizes()
                self._fit_window_to_screen()

    def closeEvent(self, event):
        self.save_layout()
        super().closeEvent(event)

    def _available_screen_geometry(self):
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return None
        return screen.availableGeometry()

    def _apply_startup_geometry(self):
        available = self._available_screen_geometry()
        if available is None:
            self.resize(1600, 900)
            return
        width = min(1800, max(1100, int(available.width() * 0.92)))
        height = min(1000, max(780, int(available.height() * 0.90)))
        width = min(width, available.width())
        height = min(height, available.height())
        self.resize(width, height)
        self.move(
            available.x() + max((available.width() - width) // 2, 0),
            available.y() + max((available.height() - height) // 2, 0),
        )

    def _fit_window_to_screen(self):
        available = self._available_screen_geometry()
        if available is None:
            return
        width = min(self.width(), available.width())
        height = min(self.height(), available.height())
        self.resize(width, height)
        frame = self.frameGeometry()
        x = min(max(frame.x(), available.x()), available.right() - frame.width() + 1)
        y = min(max(frame.y(), available.y()), available.bottom() - frame.height() + 1)
        self.move(x, y)

    def _apply_default_dock_sizes(self):
        available = self._available_screen_geometry()
        if available is None:
            width = 1600
            height = 900
        else:
            width = available.width()
            height = available.height()
        left_width = max(360, int(width * 0.28))
        right_width = max(640, width - left_width)
        top_height = max(420, int(height * 0.62))
        bottom_height = max(220, height - top_height)
        right_stack = max(180, int(top_height / 3))
        self.resizeDocks([self.dock_params, self.dock_fisher], [left_width, right_width], Qt.Orientation.Horizontal)
        self.resizeDocks([self.dock_params, self.dock_map], [top_height, bottom_height], Qt.Orientation.Vertical)
        self.resizeDocks([self.dock_fisher, self.dock_mle_accuracy, self.dock_diagnostics], [right_stack, right_stack, right_stack], Qt.Orientation.Vertical)
        self.resizeDocks([self.dock_map, self.dock_decay, self.dock_phasor], [max(280, int(right_width * 0.36)), max(280, int(right_width * 0.34)), max(220, int(right_width * 0.30))], Qt.Orientation.Horizontal)

    def _clear_saved_layout(self):
        self.settings.remove("geometry")
        self.settings.remove("windowState")
        self.settings.remove("screenWidth")
        self.settings.remove("screenHeight")

    def init_menu(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("&File")
        self.load_workspace_act = QAction("Load Workspace...", self)
        self.load_workspace_act.triggered.connect(self.load_workspace)
        file_menu.addAction(self.load_workspace_act)

        self.save_workspace_act = QAction("Save Workspace...", self)
        self.save_workspace_act.triggered.connect(self.save_workspace)
        file_menu.addAction(self.save_workspace_act)

        self.clear_workspace_act = QAction("Clear Workspace", self)
        self.clear_workspace_act.triggered.connect(lambda: self.clear_workspace(confirm=True))
        file_menu.addAction(self.clear_workspace_act)

        file_menu.addSeparator()
        self.export_precision_act = QAction("Save Report As...", self)
        self.export_precision_act.setEnabled(False)
        self.export_precision_act.triggered.connect(self.export_last_precision_report)
        file_menu.addAction(self.export_precision_act)

        file_menu.addSeparator()
        exit_act = QAction("Exit", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)
        
        view_menu = menubar.addMenu("&View")
        theme_menu = view_menu.addMenu("Theme")
        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_dark_act = QAction("Dark", self, checkable=True)
        self.theme_light_act = QAction("Light", self, checkable=True)
        self.theme_group.addAction(self.theme_dark_act)
        self.theme_group.addAction(self.theme_light_act)
        self.theme_dark_act.triggered.connect(lambda: self.set_theme_mode("dark"))
        self.theme_light_act.triggered.connect(lambda: self.set_theme_mode("light"))
        theme_menu.addAction(self.theme_dark_act)
        theme_menu.addAction(self.theme_light_act)

        view_menu.addSeparator()
        self.view_simulations_act = QAction("Simulation Workspace", self)
        self.view_simulations_act.triggered.connect(self.apply_simulation_view)
        view_menu.addAction(self.view_simulations_act)
        self.view_testing_act = QAction("Image Validation Workspace", self)
        self.view_testing_act.triggered.connect(self.apply_testing_view)
        view_menu.addAction(self.view_testing_act)

        tools_menu = menubar.addMenu("&Tools")
        
        self.profile_mgr_act = QAction("Profiles...", self)
        self.profile_mgr_act.triggered.connect(self.open_instrument_manager)
        tools_menu.addAction(self.profile_mgr_act)

        self.custom_model_act = QAction("Custom model...", self)
        self.custom_model_act.triggered.connect(self.open_custom_model_editor)
        tools_menu.addAction(self.custom_model_act)
        
        tools_menu.addSeparator()
        
        self.lock_gui_act = QAction("Lock GUI APIs", self)
        self.lock_gui_act.triggered.connect(self.toggle_gui_api_lock)
        tools_menu.addAction(self.lock_gui_act)
        
        self.lock_backend_act = QAction("Lock backend APIs", self)
        self.lock_backend_act.triggered.connect(self.toggle_backend_api_lock)
        tools_menu.addAction(self.lock_backend_act)
        
        self.api_docs_act = QAction("API docs...", self)
        self.api_docs_act.triggered.connect(lambda: self.show_manual("api"))
        tools_menu.addAction(self.api_docs_act)
        
        tools_menu.addSeparator()
        
        self.stop_mcp_act = QAction("Stop MCP server", self)
        self.stop_mcp_act.triggered.connect(self.toggle_mcp_lock)
        tools_menu.addAction(self.stop_mcp_act)
        
        self.mcp_docs_act = QAction("MCP docs...", self)
        self.mcp_docs_act.triggered.connect(lambda: self.show_manual("mcp"))
        tools_menu.addAction(self.mcp_docs_act)
        
        tools_menu.addSeparator()
        
        self.app_lockdown_act = QAction("App safety lockdown", self)
        self.app_lockdown_act.triggered.connect(self.app_safety_lockdown)
        tools_menu.addAction(self.app_lockdown_act)

        help_menu = menubar.addMenu("&Help")
        
        self.tutorial_act = QAction("Interactive Tutorial", self)
        self.tutorial_act.setShortcut("Ctrl+T")
        self.tutorial_act.triggered.connect(lambda: self.show_manual("tutorial"))
        help_menu.addAction(self.tutorial_act)

        self.manual_act = QAction("See Manual", self)
        self.manual_act.setShortcut("Ctrl+H")
        self.manual_act.triggered.connect(self.show_manual)
        help_menu.addAction(self.manual_act)
        
        help_menu.addSeparator()
        
        about_act = QAction("About", self)
        about_act.triggered.connect(self.show_about)
        help_menu.addAction(about_act)

    def toggle_gui_api_lock(self):
        self.gui_api_locked = not self.gui_api_locked
        self._sync_locks_to_disk()
        self.lock_gui_act.setText("Unlock GUI APIs" if self.gui_api_locked else "Lock GUI APIs")
        self.statusBar().showMessage(f"GUI API {'locked' if self.gui_api_locked else 'unlocked'}.")

    def toggle_backend_api_lock(self):
        self.backend_api_locked = not self.backend_api_locked
        self._sync_locks_to_disk()
        self.lock_backend_act.setText("Unlock Backend APIs" if self.backend_api_locked else "Lock Backend APIs")
        self.statusBar().showMessage(f"Backend API {'locked' if self.backend_api_locked else 'unlocked'}.")

    def toggle_mcp_lock(self):
        self.mcp_server_stopped = not self.mcp_server_stopped
        self._sync_locks_to_disk()
        self.stop_mcp_act.setText("Start MCP server" if self.mcp_server_stopped else "Stop MCP server")
        self.statusBar().showMessage(f"MCP server {'stopped' if self.mcp_server_stopped else 'started'}.")

    def app_safety_lockdown(self):
        """Global override for all API and MCP access."""
        if not (self.gui_api_locked and self.backend_api_locked and self.mcp_server_stopped):
            self.gui_api_locked = True
            self.backend_api_locked = True
            self.mcp_server_stopped = True
            self.app_lockdown_act.setText("App safety unlock")
        else:
            self.gui_api_locked = False
            self.backend_api_locked = False
            self.mcp_server_stopped = False
            self.app_lockdown_act.setText("App safety lockdown")
        
        self._sync_locks_to_disk()
        # Update other menu texts
        self.lock_gui_act.setText("Unlock GUI APIs" if self.gui_api_locked else "Lock GUI APIs")
        self.lock_backend_act.setText("Unlock Backend APIs" if self.backend_api_locked else "Lock Backend APIs")
        self.stop_mcp_act.setText("Start MCP server" if self.mcp_server_stopped else "Stop MCP server")
        self.statusBar().showMessage("Safety Lockdown: " + ("ACTIVATED" if self.gui_api_locked else "DEACTIVATED"))

    def apply_theme(self):
        """Applies the current theme from settings."""
        theme = self.settings.value("theme", "dark")
        app = QApplication.instance()
        if theme == "dark":
            app.setStyleSheet(qdarkstyle.load_stylesheet())
            self.theme_dark_act.setChecked(True)
        else:
            app.setStyleSheet(LIGHT_APP_STYLESHEET)
            self.theme_light_act.setChecked(True)

        for widget in (
            self.control_widget,
            self.map_widget,
            self.phasor_widget,
            self.decay_widget,
            self.fisher_widget,
            self.mle_accuracy_widget,
            self.diagnostics_widget,
        ):
            if hasattr(widget, "set_theme"):
                widget.set_theme(theme)
        self._apply_optimization_dock_highlight()

    def set_theme_mode(self, theme_name):
        self.settings.setValue("theme", str(theme_name).lower())
        self.apply_theme()

    def setup_docks(self):
        placeholder = QWidget()
        placeholder.setLayout(QVBoxLayout())
        placeholder.layout().setContentsMargins(0, 0, 0, 0)
        placeholder.setMinimumWidth(0)
        placeholder.setMaximumWidth(0)
        self.setCentralWidget(placeholder)
        self.setDockNestingEnabled(True)

        # Left: Controls
        c_dock = QDockWidget("Digital Twin Controller", self)
        c_dock.setObjectName("dock_params")
        c_dock.setWidget(self.control_widget)
        self.dock_params = c_dock
        # Allow floating but persistent top-left placement
        c_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | 
                           QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, c_dock)

        # Right Top: Phasor
        p_dock = QDockWidget("Phasor Space (G vs S)", self)
        p_dock.setObjectName("dock_phasor")
        p_dock.setWidget(self.phasor_widget)
        self.dock_phasor = p_dock
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, p_dock)

        # Right Bottom: Fisher
        f_dock = QDockWidget("Precision (Fisher Info)", self)
        f_dock.setObjectName("dock_fisher")
        f_dock.setWidget(self.fisher_widget)
        self.dock_fisher = f_dock
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, f_dock)

        acc_dock = QDockWidget("Gridded MLE Accuracy", self)
        acc_dock.setObjectName("dock_mle_accuracy")
        acc_dock.setWidget(self.mle_accuracy_widget)
        self.dock_mle_accuracy = acc_dock
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, acc_dock)

        # Right Center: Diagnostics
        dia_dock = QDockWidget("Instrument Diagnostics", self)
        dia_dock.setObjectName("dock_diagnostics")
        dia_dock.setWidget(self.diagnostics_widget)
        self.dock_diagnostics = dia_dock
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dia_dock)

        # Bottom: Decay
        d_dock = QDockWidget("Pixel Inspector", self)
        d_dock.setObjectName("dock_decay")
        d_dock.setWidget(self.decay_widget)
        self.dock_decay = d_dock
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, d_dock)

        # Bottom Left: Image / Map
        map_dock = QDockWidget("MC Image Validation", self)
        map_dock.setObjectName("dock_map")
        map_dock.setWidget(self.map_widget)
        self.dock_map = map_dock
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, map_dock)

        self.splitDockWidget(c_dock, f_dock, Qt.Orientation.Horizontal)
        self.splitDockWidget(c_dock, map_dock, Qt.Orientation.Vertical)
        self.splitDockWidget(f_dock, acc_dock, Qt.Orientation.Vertical)
        self.splitDockWidget(acc_dock, dia_dock, Qt.Orientation.Vertical)
        self.splitDockWidget(map_dock, d_dock, Qt.Orientation.Horizontal)
        self.splitDockWidget(d_dock, p_dock, Qt.Orientation.Horizontal)

        self.resizeDocks([c_dock, f_dock], [540, 1180], Qt.Orientation.Horizontal)
        self.resizeDocks([c_dock, map_dock], [720, 420], Qt.Orientation.Vertical)
        self.resizeDocks([f_dock, acc_dock, dia_dock], [300, 300, 340], Qt.Orientation.Vertical)
        self.resizeDocks([map_dock, d_dock, p_dock], [760, 720, 420], Qt.Orientation.Horizontal)

    def apply_simulation_view(self):
        for dock in (self.dock_params, self.dock_fisher, self.dock_mle_accuracy, self.dock_diagnostics):
            dock.show()
        for dock in (self.dock_map, self.dock_decay, self.dock_phasor):
            dock.hide()
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_params)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_fisher)
        self.splitDockWidget(self.dock_fisher, self.dock_mle_accuracy, Qt.Orientation.Vertical)
        self.splitDockWidget(self.dock_mle_accuracy, self.dock_diagnostics, Qt.Orientation.Vertical)
        self.resizeDocks([self.dock_params, self.dock_fisher], [420, 900], Qt.Orientation.Horizontal)
        self.resizeDocks([self.dock_fisher, self.dock_mle_accuracy, self.dock_diagnostics], [320, 320, 320], Qt.Orientation.Vertical)

    def apply_testing_view(self):
        for dock in (self.dock_params, self.dock_map, self.dock_decay, self.dock_phasor):
            dock.show()
        for dock in (self.dock_fisher, self.dock_mle_accuracy, self.dock_diagnostics):
            dock.hide()
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_params)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_map)
        self.splitDockWidget(self.dock_map, self.dock_decay, Qt.Orientation.Vertical)
        self.splitDockWidget(self.dock_decay, self.dock_phasor, Qt.Orientation.Vertical)
        self.resizeDocks([self.dock_params, self.dock_map], [420, 900], Qt.Orientation.Horizontal)
        self.resizeDocks([self.dock_map, self.dock_decay, self.dock_phasor], [320, 320, 320], Qt.Orientation.Vertical)

    def connect_signals(self):
        # Context-aware Manual
        self.control_widget.context_changed.connect(self.manual_widget.scroll_to_section)

        # Simulation controls
        self.control_widget.btn_precision.clicked.connect(self.run_precision_analysis)
        self.control_widget.btn_simulate.clicked.connect(self.run_image_gen)
        self.control_widget.btn_fit_image.clicked.connect(self.fit_validation_image)
        self.control_widget.btn_export.clicked.connect(self.preview_last_precision_report)
        self.control_widget.btn_interrupt.clicked.connect(self.interrupt_simulation)
        self.control_widget.btn_manage_inst.clicked.connect(self.open_instrument_manager)
        self.control_widget.chk_opt_detection.toggled.connect(self._on_optimization_scope_toggled)
        self.control_widget.chk_opt_excitation.toggled.connect(self._on_optimization_scope_toggled)
        self.control_widget.radio_f_basis_period.toggled.connect(self._on_f_basis_changed)
        self.control_widget.radio_f_basis_all.toggled.connect(self._on_f_basis_changed)
        self.control_widget.radio_f_basis_collected.toggled.connect(self._on_f_basis_changed)
        self.control_widget.advanced_config_changed.connect(self.refresh_diagnostics)
        
        # Auto-refresh diagnostics on any param change
        from PyQt6.QtWidgets import QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox, QLineEdit
        for widget in self.control_widget.findChildren((QDoubleSpinBox, QSpinBox)):
            widget.valueChanged.connect(self.refresh_diagnostics)
        for widget in self.control_widget.findChildren((QComboBox, QCheckBox)):
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self.refresh_diagnostics)
            else:
                widget.clicked.connect(self.refresh_diagnostics)
        self.control_widget.group_burst.toggled.connect(self.refresh_diagnostics)
        for widget in self.control_widget.findChildren(QLineEdit):
            widget.textChanged.connect(self.refresh_diagnostics)
        self.control_widget.btn_freeform_mode.toggled.connect(self.refresh_diagnostics)

        self.map_widget.pixel_selected.connect(self.on_pixel_select)

    def _update_primary_action_buttons(self):
        optimisation_running = bool(self.optimization_running)
        self.control_widget.btn_manage_inst.setEnabled(True)
        self.control_widget.btn_precision.setEnabled(True)
        self.control_widget.btn_simulate.setEnabled(True)
        self.control_widget.btn_interrupt.setEnabled(optimisation_running)
        if self.optimization_mode_active:
            self.control_widget.btn_precision.setText("Run Optimisation")
            self.control_widget.btn_precision.setToolTip("Run the active optimisation workflow.")
        else:
            self.control_widget.btn_precision.setText("Run Analysis")
            self.control_widget.btn_precision.setToolTip("Run the current analysis workflow, including precision calculations and active result views.")

    def _update_simulation_mode_badge(self):
        status = self.engine.get_simulation_mode_status()
        self.control_widget._update_simulation_mode_badge(status)

    def _detector_event_effects_active(self, cfg=None):
        cfg = cfg or self.engine.config
        if float(getattr(cfg, "detector_deadtime", 0.0)) > 0.0:
            return True
        if float(getattr(cfg, "detector_afterpulsing_probability", 0.0)) > 0.0:
            return True
        if float(getattr(cfg, "detector_dark_count_rate_cps", 0.0)) > 0.0:
            return True
        if not bool(getattr(cfg, "b_multihit_mode", True)):
            return True
        capacity = getattr(cfg, "event_multihit_capacity", None)
        if capacity is None:
            return False
        try:
            capacity_val = int(capacity)
        except (TypeError, ValueError):
            return False
        return capacity_val < 1_000_000

    def _resolve_simulation_core_session_choice(self):
        if not self.startup_complete:
            return

        cfg = self.engine.config
        preference = str(getattr(cfg, "simulation_mode_preference", "auto")).lower()
        if self._detector_event_effects_active(cfg) and preference == "auto" and not self.simulation_core_prompted_session:
            box = QMessageBox(self)
            box.setWindowTitle("Detector Effects Enabled")
            box.setIcon(QMessageBox.Icon.Information)
            box.setText("Detector event effects are active.")
            box.setInformativeText(
                "Choose which computational core to use for these effects.\n\n"
                "Use Ideal Poisson (recommended) to apply the fast detector-transfer approximation.\n"
                "Use Event-driven for chronological detection physics.\n\n"
                "The event-driven core is still under development and is slow. Use few pixels and few MC repeats."
            )
            btn_poisson = box.addButton("Use Ideal Poisson (recommended)", QMessageBox.ButtonRole.AcceptRole)
            btn_event = box.addButton("Use Event-driven", QMessageBox.ButtonRole.ActionRole)
            box.setDefaultButton(btn_poisson)
            box.exec()
            chosen = "event_driven" if box.clickedButton() is btn_event else "ideal_poisson"
            self.control_widget.simulation_mode_preference = chosen
            self.engine.config.simulation_mode_preference = chosen
            self.simulation_core_prompted_session = True
            if chosen == "event_driven":
                self.event_driven_warning_shown_session = True
            self._update_simulation_mode_badge()

        status = self.engine.get_simulation_mode_status()
        if (
            self.startup_complete
            and str(status.get("effective_mode", "ideal_poisson")).lower() == "event_driven"
            and not self.event_driven_warning_shown_session
        ):
            QMessageBox.warning(
                self,
                "Event-driven Core",
                "The event-driven computational core is still under development. Use with caution.\n\n"
                "It is also significantly slower than the Ideal Poisson core. Prefer few pixels and few MC repeats.",
            )
            self.event_driven_warning_shown_session = True

    def open_instrument_manager(self):
        # Pass engine config to manager
        dlg = InstrumentManager(self, self.engine.config)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if dlg.applied_config is not None:
                self._apply_config_to_workspace(dlg.applied_config)
                self.statusBar().showMessage("Instrument profile applied successfully.")

    def open_custom_model_editor(self):
        dlg = CustomModelEditorDialog(self.engine.config, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected_key = dlg.selected_model_key()
            self.decay_model_store = DecayModelStore()
            self.engine.decay_model_store = self.decay_model_store
            self.engine.config.decay_model = selected_key
            self.engine.config.decay_model_sweep_defaults = dlg.cfg.decay_model_sweep_defaults
            self.control_widget.decay_model_store = self.decay_model_store
            self.control_widget.refresh_decay_model_options(selected_key)
            self.control_widget.update_param_visibility()
            self.control_widget.update_from_config(self.engine.config)
            self.engine.invalidate_grid()
            self.refresh_diagnostics()
            self.statusBar().showMessage(f"Decay model '{selected_key}' loaded.")

    def _apply_config_to_workspace(self, config):
        self.engine.config = self.engine.config.__class__(
            **(config.model_dump() if hasattr(config, "model_dump") else config.dict())
        )
        self.decay_model_store = DecayModelStore()
        self.engine.decay_model_store = self.decay_model_store
        self.control_widget.decay_model_store = self.decay_model_store
        self.loading_config_into_ui = True
        try:
            self.control_widget.update_from_config(self.engine.config)
        finally:
            self.loading_config_into_ui = False
        self._update_simulation_mode_badge()
        self.refresh_diagnostics()

    def _set_export_enabled(self):
        enabled = bool(self.last_precision_run or self.last_optimization_run or self.last_validation_run)
        self.export_precision_act.setEnabled(enabled)
        self.control_widget.btn_export.setEnabled(enabled)

    def _current_target_label(self):
        return self.control_widget.param_rows[self.engine.config.f_x_param]['label'].text().replace(":", "")

    def _predicted_accuracy_from_theory(self, x_range, f_values, n_photons):
        x_arr = np.asarray(x_range, dtype=float)
        denom = np.maximum(np.abs(x_arr), 1e-12)
        sigma = np.asarray(f_values, dtype=float) * denom / np.sqrt(max(int(n_photons), 1))
        return {
            "mean": np.array(x_arr, copy=True),
            "std": np.array(sigma, copy=True),
        }

    def _coerce_physics_config(self, cfg_like):
        if isinstance(cfg_like, PhysicsConfig):
            return copy.deepcopy(cfg_like)
        if isinstance(cfg_like, dict):
            return PhysicsConfig(**copy.deepcopy(cfg_like))
        raise TypeError(f"Unsupported configuration payload: {type(cfg_like).__name__}")

    def _precision_throughput_scale(self, cfg_like, reference_excitation_area):
        cfg = self._coerce_physics_config(cfg_like)
        return float(self.engine._throughput_metric(cfg, float(reference_excitation_area)))

    def _resolvability_enabled(self, cfg_like):
        cfg = self._coerce_physics_config(cfg_like)
        return (
            str(getattr(cfg, "decay_model", "exponential")).lower() == "exponential"
            and int(getattr(cfg, "n_components", 1)) == 1
            and str(getattr(cfg, "f_x_param", "tau1")).lower() == "tau1"
        )

    def _current_f_basis_mode(self):
        cw = self.control_widget
        if cw.radio_f_basis_collected.isChecked():
            return "collected"
        if cw.radio_f_basis_all.isChecked():
            return "all"
        return "period"

    def _selected_photon_budget(self, cfg_like, collected_budget):
        cfg = self._coerce_physics_config(cfg_like)
        total_budget = float(max(getattr(cfg, "precision_photons", 0), 0.0))
        mode = self._current_f_basis_mode()
        collected = np.asarray(collected_budget, dtype=float)
        if mode == "collected":
            return np.maximum(collected, 0.0)
        if mode == "all":
            return total_budget
        return total_budget * float(self.engine._acquisition_period_fraction(cfg))

    def _rescale_f_from_conditional(self, x_range, f_conditional, collected_budget, cfg_like):
        x_arr = np.asarray(x_range, dtype=float)
        f_cond = np.asarray(f_conditional, dtype=float)
        collected = np.asarray(collected_budget, dtype=float)
        target_budget = np.asarray(self._selected_photon_budget(cfg_like, collected), dtype=float)
        if target_budget.ndim == 0:
            target_budget = np.full_like(collected, float(target_budget))
        scale = np.full_like(f_cond, np.nan, dtype=float)
        valid = np.isfinite(f_cond) & np.isfinite(collected) & (collected > 0.0) & np.isfinite(target_budget) & (target_budget >= 0.0)
        scale[valid] = np.sqrt(target_budget[valid] / collected[valid])
        out = np.full_like(f_cond, np.nan, dtype=float)
        out[valid] = f_cond[valid] * scale[valid]
        return out

    def _theory_conditional_curve(self, snapshot, x_range):
        if snapshot.get("theory_f_conditional") is not None:
            return np.asarray(snapshot["theory_f_conditional"], dtype=float)
        return np.asarray(snapshot.get("theory_f", np.full(len(x_range), np.nan)), dtype=float)

    def _theory_collected_budget(self, snapshot, x_range):
        theory_cond = self._theory_conditional_curve(snapshot, x_range)
        fisher = np.asarray(snapshot.get("theory_fisher", np.full(len(x_range), np.nan)), dtype=float)
        x_arr = np.asarray(x_range, dtype=float)
        denom = np.maximum(np.abs(x_arr), 1e-12)
        budget = fisher * np.square(theory_cond * denom)
        budget[~np.isfinite(budget)] = np.nan
        return budget

    def _display_theory_curve(self, snapshot, x_range):
        theory_cond = self._theory_conditional_curve(snapshot, x_range)
        collected_budget = self._theory_collected_budget(snapshot, x_range)
        return self._rescale_f_from_conditional(x_range, theory_cond, collected_budget, snapshot.get("config", self.engine.config))

    def _display_mc_payload(self, mc_payload, cfg_like):
        if mc_payload is None:
            return None
        payload = copy.deepcopy(mc_payload)
        f_cond = payload.get("f_value_conditional")
        survival = payload.get("survival_eta")
        if f_cond is None or survival is None:
            return payload
        f_cond_arr = np.asarray(f_cond, dtype=float)
        survival_arr = np.asarray(survival, dtype=float)
        total_budget = float(max(getattr(self._coerce_physics_config(cfg_like), "precision_photons", 0), 0.0))
        collected_budget = total_budget * survival_arr
        f_eff = self._rescale_f_from_conditional(np.arange(len(f_cond_arr), dtype=float), f_cond_arr, collected_budget, cfg_like)
        payload["f_value"] = f_eff
        payload["f_value_effective"] = np.array(f_eff, copy=True)
        with np.errstate(divide="ignore", invalid="ignore"):
            payload["efficiency"] = np.clip(1.0 / np.square(np.maximum(f_eff, 1e-12)), 0.0, 1.0)
        if payload.get("f_ci_lower") is not None and payload.get("f_ci_upper") is not None:
            f_ci_lower = np.asarray(payload["f_ci_lower"], dtype=float)
            f_ci_upper = np.asarray(payload["f_ci_upper"], dtype=float)
            cond_lower = np.asarray(payload.get("f_value_conditional", f_ci_lower), dtype=float)
            valid = np.isfinite(cond_lower) & np.isfinite(f_cond_arr) & (f_cond_arr > 0)
            scale = np.full_like(f_cond_arr, np.nan, dtype=float)
            scale[valid] = f_eff[valid] / f_cond_arr[valid]
            payload["f_ci_lower"] = f_ci_lower * scale
            payload["f_ci_upper"] = f_ci_upper * scale
            with np.errstate(divide="ignore", invalid="ignore"):
                payload["efficiency_ci_lower"] = np.clip(1.0 / np.square(np.maximum(np.asarray(payload["f_ci_upper"], dtype=float), 1e-12)), 0.0, 1.0)
                payload["efficiency_ci_upper"] = np.clip(1.0 / np.square(np.maximum(np.asarray(payload["f_ci_lower"], dtype=float), 1e-12)), 0.0, 1.0)
        return payload

    def _redisplay_last_precision_run(self):
        report = self.last_precision_run
        if not report:
            return
        x_range = np.asarray(report["x_range"], dtype=float)
        ideal_f = np.asarray(report["ideal_f"], dtype=float)
        ideal_f_conditional = np.asarray(report.get("ideal_f_conditional", report["ideal_f"]), dtype=float)
        target_label = report.get("x_label", self._current_target_label())
        self.fisher_widget.set_xaxis_label(target_label)
        self.mle_accuracy_widget.set_xaxis_label(f"Ground Truth {target_label}")
        reference_excitation_area = self.engine._excitation_area_and_peak(self._coerce_physics_config(report["config"]))[0]
        plot_results = {}
        accuracy_results = {}
        frames = []
        for item in report.get("series", []):
            label = item["label"]
            throughput_scale = self._precision_throughput_scale(item.get("config", report["config"]), reference_excitation_area)
            theory_f = self._display_theory_curve(item, x_range)
            plot_results[f"Theory | {label}"] = {
                "y": theory_f,
                "conditional_f": np.asarray(item.get("theory_f_conditional", item["theory_f"]), dtype=float),
                "photon_count": float(getattr(self._coerce_physics_config(item.get("config", report["config"])), "precision_photons", 0.0)),
                "resolvability_enabled": self._resolvability_enabled(item.get("config", report["config"])),
                "throughput_scale": throughput_scale,
            }
            mc_payload = self._display_mc_payload(item.get("mc"), item.get("config", report["config"]))
            if mc_payload is not None:
                plot_results[f"Monte Carlo | {label}"] = {
                    "y": np.asarray(mc_payload["f_value"], dtype=float),
                    "conditional_f": np.asarray(mc_payload.get("f_value_conditional", mc_payload["f_value"]), dtype=float),
                    "conditional_f_ci_lower": None if mc_payload.get("f_ci_lower_conditional") is None else np.asarray(mc_payload["f_ci_lower_conditional"], dtype=float),
                    "conditional_f_ci_upper": None if mc_payload.get("f_ci_upper_conditional") is None else np.asarray(mc_payload["f_ci_upper_conditional"], dtype=float),
                    "photon_count": float(getattr(self._coerce_physics_config(item.get("config", report["config"])), "precision_photons", 0.0)),
                    "resolvability_enabled": self._resolvability_enabled(item.get("config", report["config"])),
                    "compatible": np.asarray(mc_payload["compatible"], dtype=bool),
                    "f_ci_lower": np.asarray(mc_payload["f_ci_lower"], dtype=float),
                    "f_ci_upper": np.asarray(mc_payload["f_ci_upper"], dtype=float),
                    "efficiency_ci_lower": np.asarray(mc_payload["efficiency_ci_lower"], dtype=float),
                    "efficiency_ci_upper": np.asarray(mc_payload["efficiency_ci_upper"], dtype=float),
                    "throughput_scale": throughput_scale,
                }
                accuracy_results[label] = {
                    "mean": np.asarray(mc_payload["mean_tau"], dtype=float),
                    "std": np.asarray(mc_payload["std_tau"], dtype=float),
                }
            frames.append(copy.deepcopy(item["diagnostics_frame"]))
        self.fisher_widget.plot_batch(
            x_range,
            plot_results,
            ideal_x=x_range,
            ideal_f=ideal_f,
            ideal_conditional_f=ideal_f_conditional,
            ideal_throughput_scale=1.0,
            ideal_photon_count=float(getattr(self._coerce_physics_config(report["config"]), "precision_photons", 0.0)),
            ci_level=float(getattr(self._coerce_physics_config(report["config"]), "precision_ci_level", 99.7)),
        )
        if accuracy_results:
            self.mle_accuracy_widget.plot_accuracy(x_range, accuracy_results)
        self.diagnostics_widget.set_sweep_frames(frames)

    def _on_f_basis_changed(self, checked=False):
        if not checked or self.loading_config_into_ui:
            return
        self.engine.config.optimization_f_photon_basis = self._current_f_basis_mode()
        if self.last_precision_run and not self.optimization_mode_active:
            self._redisplay_last_precision_run()
        elif self.last_optimization_run:
            self._display_optimization_snapshots(
                self.last_optimization_run["x_range"],
                self.last_optimization_run["ideal_f"],
                self.last_optimization_run["snapshots"],
                focus_last=True,
                resume_autoplay=False,
                ideal_f_conditional=self.last_optimization_run.get("ideal_f_conditional", self.last_optimization_run["ideal_f"]),
            )

    def _build_optimization_snapshot(self, cfg, label, objective=None, min_f=None):
        original_config = self.engine.config
        try:
            self.engine.config = copy.deepcopy(cfg)
            self.engine.invalidate_grid()
            x_range = self._build_precision_x_range(self.engine.config)
            _, ideal_f = self.engine.compute_ideal_reference(x_range, int(self.engine.config.precision_photons))
            if str(getattr(self.engine.config, "optimization_f_photon_basis", "collected")).lower() == "collected":
                ideal_f_conditional = np.array(ideal_f, copy=True)
            else:
                _, ideal_f_conditional = self.engine.compute_ideal_reference(
                    x_range,
                    int(self.engine.config.precision_photons),
                    photon_basis_mode="collected",
                )
            theory_fi, theory_f = self.engine.compute_fisher_info(
                x_range,
                int(self.engine.config.precision_photons),
                photon_basis_mode=getattr(self.engine.config, "optimization_f_photon_basis", "period"),
            )
            if str(getattr(self.engine.config, "optimization_f_photon_basis", "collected")).lower() == "collected":
                theory_f_conditional = np.array(theory_f, copy=True)
            else:
                _, theory_f_conditional = self.engine.compute_fisher_info(
                    x_range,
                    int(self.engine.config.precision_photons),
                    photon_basis_mode="collected",
                )
            frame = self._create_diagnostics_frame(self.engine.config, label)
            frame["background_curves"] = self._build_precision_pdf_ensemble(self.engine.config, x_range)
            gate_edges = np.asarray(self.engine.config.gate_edges, dtype=float)
            return {
                "label": label,
                "objective": float(objective if objective is not None else np.nanmean(theory_f)),
                "min_f": float(min_f if min_f is not None else np.nanmin(theory_f)),
                "gate_count": int(max(0, gate_edges.size - 1)),
                "x_range": np.array(x_range, copy=True),
                "ideal_f": np.array(ideal_f, copy=True),
                "ideal_f_conditional": np.array(ideal_f_conditional, copy=True),
                "theory_f": np.array(theory_f, copy=True),
                "theory_f_conditional": np.array(theory_f_conditional, copy=True),
                "theory_fisher": np.array(theory_fi, copy=True),
                "accuracy": self._predicted_accuracy_from_theory(x_range, theory_f, int(self.engine.config.precision_photons)),
                "diagnostics_frame": frame,
                "config": copy.deepcopy(self.engine.config.model_dump() if hasattr(self.engine.config, "model_dump") else self.engine.config.dict()),
            }
        finally:
            self.engine.config = original_config
            self.engine.invalidate_grid()

    def _resolve_optimization_start_snapshot_cfg(self, cfg):
        snapshot_cfg = copy.deepcopy(cfg)
        algorithm = str(getattr(snapshot_cfg, "detection_optimization_algorithm", "fisher_compression")).lower()
        auto_compress = bool(getattr(snapshot_cfg, "detection_opt_fc_auto_compress", False))
        if algorithm != "fisher_compression" or not auto_compress:
            return snapshot_cfg

        start = 0.0
        start_anchor = str(getattr(snapshot_cfg, "detection_opt_start_anchor", "zero")).lower()
        if start_anchor == "irf":
            jitter_ns = float(getattr(snapshot_cfg, "timing_jitter", 0.0)) / 1000.0
            irf_profile = str(getattr(snapshot_cfg, "irf_profile", "gaussian")).lower()
            if irf_profile == "gaussian":
                sigma_total = np.sqrt((float(snapshot_cfg.irf_fwhm) / 2.355) ** 2 + jitter_ns ** 2)
                start = float(snapshot_cfg.irf_position) + 3.0 * sigma_total
            elif irf_profile == "ideal (dirac)":
                start = float(snapshot_cfg.irf_position) + 3.0 * jitter_ns
            else:
                start = float(snapshot_cfg.irf_position) + float(snapshot_cfg.irf_fwhm) + 3.0 * jitter_ns
        elif start_anchor == "custom":
            start = float(getattr(snapshot_cfg, "detection_opt_start_time", 0.0))

        end_anchor = str(getattr(snapshot_cfg, "detection_opt_end_anchor", "period")).lower()
        if end_anchor == "custom":
            end = float(getattr(snapshot_cfg, "detection_opt_end_time", snapshot_cfg.period))
        else:
            end = float(snapshot_cfg.period)
        if end <= start:
            end = start + 1e-3

        n_gates = max(1, int(getattr(snapshot_cfg, "detection_opt_fc_initial_gates", max(2, len(snapshot_cfg.gate_edges) - 1))))
        edges = np.linspace(start, end, n_gates + 1)
        snapshot_cfg.gate_type = "custom"
        snapshot_cfg.gate_edges = edges.tolist()
        snapshot_cfg.gate_widths = np.diff(edges).tolist()
        return snapshot_cfg

    def _build_optimization_current_text(self, snapshot):
        if snapshot is None:
            return "Current simulated value: baseline configuration"
        edges = np.asarray(snapshot.get("config", {}).get("gate_edges", []), dtype=float)
        edge_text = ", ".join(f"{edge:.3f}" for edge in edges[:6])
        if edges.size > 6:
            edge_text += ", ..."
        objective = snapshot.get("objective", np.nan)
        min_f = snapshot.get("min_f", np.nan)
        gate_count = int(snapshot.get("gate_count", max(0, len(edges) - 1)))
        return (
            f"Current simulated value: {snapshot.get('label', 'Current')} | "
            f"Objective J = {objective:.6g} | Minimum F = {min_f:.6g} | Gate count = {gate_count} | Gates = [{edge_text}]"
        )

    def _disable_diagnostics_autoplay_for_optimization(self):
        if self.optimization_autoplay_previous is None:
            self.optimization_autoplay_previous = bool(self.diagnostics_widget.chk_autoplay.isChecked())
        if self.diagnostics_widget.chk_autoplay.isChecked():
            self.diagnostics_widget.chk_autoplay.setChecked(False)
        else:
            self.diagnostics_widget.pause_playback()

    def _restore_diagnostics_autoplay_after_optimization(self, checked=None):
        restore_checked = self.optimization_autoplay_previous if checked is None else bool(checked)
        if restore_checked is None:
            restore_checked = bool(self.diagnostics_widget.chk_autoplay.isChecked())
        self.diagnostics_widget.chk_autoplay.setChecked(bool(restore_checked))
        if restore_checked:
            self.diagnostics_widget.resume_playback()
        else:
            self.diagnostics_widget.pause_playback()
        self.optimization_autoplay_previous = None

    def _display_optimization_snapshots(self, x_range, ideal_f, snapshots, focus_last=False, resume_autoplay=False, ideal_f_conditional=None):
        if not snapshots:
            return
        x_arr = np.asarray(x_range, dtype=float)
        ideal_arr = np.asarray(ideal_f, dtype=float)
        ideal_cond_arr = np.asarray(ideal_f if ideal_f_conditional is None else ideal_f_conditional, dtype=float)
        reference_excitation_area = self.engine._excitation_area_and_peak(self.engine.config)[0]
        target_label = self.control_widget.param_rows[self.engine.config.f_x_param]['label'].text().replace(":", "")
        self.fisher_widget.set_xaxis_label(target_label)
        self.mle_accuracy_widget.set_xaxis_label(f"Ground Truth {target_label}")

        plot_results = {}
        accuracy_results = {}
        frames = []
        for snapshot in snapshots:
            label = snapshot["label"]
            throughput_scale = self._precision_throughput_scale(snapshot.get("config", self.engine.config), reference_excitation_area)
            plot_results[f"Theory | {label}"] = {
                "y": self._display_theory_curve(snapshot, x_arr),
                "conditional_f": np.asarray(snapshot.get("theory_f_conditional", snapshot["theory_f"]), dtype=float),
                "photon_count": float(getattr(self._coerce_physics_config(snapshot.get("config", self.engine.config)), "precision_photons", 0.0)),
                "resolvability_enabled": self._resolvability_enabled(snapshot.get("config", self.engine.config)),
                "throughput_scale": throughput_scale,
            }
            mc_payload = self._display_mc_payload(snapshot.get("mc"), snapshot.get("config", self.engine.config))
            if mc_payload is not None:
                plot_results[f"Monte Carlo | {label}"] = {
                    "y": np.asarray(mc_payload["f_value"], dtype=float),
                    "conditional_f": np.asarray(mc_payload.get("f_value_conditional", mc_payload["f_value"]), dtype=float),
                    "conditional_f_ci_lower": None if mc_payload.get("f_ci_lower_conditional") is None else np.asarray(mc_payload["f_ci_lower_conditional"], dtype=float),
                    "conditional_f_ci_upper": None if mc_payload.get("f_ci_upper_conditional") is None else np.asarray(mc_payload["f_ci_upper_conditional"], dtype=float),
                    "photon_count": float(getattr(self._coerce_physics_config(snapshot.get("config", self.engine.config)), "precision_photons", 0.0)),
                    "resolvability_enabled": self._resolvability_enabled(snapshot.get("config", self.engine.config)),
                    "compatible": np.asarray(mc_payload["compatible"], dtype=bool),
                    "f_ci_lower": np.asarray(mc_payload["f_ci_lower"], dtype=float),
                    "f_ci_upper": np.asarray(mc_payload["f_ci_upper"], dtype=float),
                    "efficiency_ci_lower": np.asarray(mc_payload["efficiency_ci_lower"], dtype=float),
                    "efficiency_ci_upper": np.asarray(mc_payload["efficiency_ci_upper"], dtype=float),
                    "throughput_scale": throughput_scale,
                }
            accuracy_results[label] = {
                "mean": np.asarray(snapshot["accuracy"]["mean"], dtype=float),
                "std": np.asarray(snapshot["accuracy"]["std"], dtype=float),
            }
            frame = copy.deepcopy(snapshot["diagnostics_frame"])
            frames.append(frame)

        self.fisher_widget.plot_batch(
            x_arr,
            plot_results,
            ideal_x=x_arr,
            ideal_f=ideal_arr,
            ideal_conditional_f=ideal_cond_arr,
            ideal_throughput_scale=1.0,
            ideal_photon_count=float(getattr(self._coerce_physics_config(self.engine.config), "precision_photons", 0.0)),
            ci_level=float(getattr(self.engine.config, "precision_ci_level", 99.7)),
        )
        self.mle_accuracy_widget.plot_accuracy(x_arr, accuracy_results)
        self.diagnostics_widget.set_sweep_frames(frames)
        if focus_last and frames:
            self.diagnostics_widget.set_frame(len(frames) - 1)
        if resume_autoplay and self.diagnostics_widget.chk_autoplay.isChecked():
            self.diagnostics_widget.resume_playback()
        else:
            self.diagnostics_widget.pause_playback()

    def _apply_optimization_results_to_instrument(self):
        if not self.last_optimization_run:
            return
        final_cfg = copy.deepcopy(self.last_optimization_run["final_config"])
        self.engine.config = self.engine.config.__class__(**final_cfg)
        self.loading_config_into_ui = True
        try:
            self.control_widget.update_from_config(self.engine.config)
        finally:
            self.loading_config_into_ui = False
        self.optimization_results_imported = True
        self.refresh_diagnostics()
        self.statusBar().showMessage("Optimised detection gates imported into the current instrument.")

    def _prompt_optimization_exit_actions(self):
        if not self.last_optimization_run:
            return
        if not self.optimization_results_imported:
            reply = QMessageBox.question(
                self,
                "Import Optimisation Results",
                "Do you want to import the optimisation results into the current instrument definition?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._apply_optimization_results_to_instrument()
        if not self.optimization_results_saved:
            reply = QMessageBox.question(
                self,
                "Save Optimisation Results",
                "Optimisation results have not been saved yet. Do you want to save them now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.preview_last_precision_report()

    def _apply_optimization_dock_highlight(self):
        if not hasattr(self, "dock_fisher"):
            return
        theme = self.settings.value("theme", "dark") if hasattr(self, "settings") else "dark"
        if self.optimization_mode_active:
            bg = "#7f1d1d" if theme == "dark" else "#b91c1c"
            border = "#ef4444" if theme == "dark" else "#991b1b"
            text = "#ffffff"
            style = (
                "QDockWidget::title {"
                f"background: {bg}; color: {text}; padding: 6px 10px; border: 1px solid {border};"
                "}"
            )
        else:
            style = ""
        for dock in (
            getattr(self, "dock_params", None),
            getattr(self, "dock_fisher", None),
            getattr(self, "dock_mle_accuracy", None),
            getattr(self, "dock_diagnostics", None),
        ):
            if dock is not None:
                dock.setStyleSheet(style)

    def _set_optimization_mode_ui(self, active, running=False):
        self.optimization_mode_active = bool(active)
        self.optimization_running = bool(running)
        if self.optimization_mode_active:
            self._disable_diagnostics_autoplay_for_optimization()
            self.diagnostics_widget.chk_autoplay.setEnabled(not self.optimization_running)
        else:
            self.diagnostics_widget.chk_autoplay.setEnabled(len(getattr(self.diagnostics_widget, "frames", [])) > 1)
        self.control_widget.set_optimization_mode_active(active, running=running)
        self._apply_optimization_dock_highlight()
        self._update_primary_action_buttons()

    def _show_optimization_baseline(self):
        self.sync_ui_to_config()
        cfg = copy.deepcopy(self.engine.config)
        if not (cfg.optimize_detection_gates or cfg.optimize_excitation_profile):
            return
        cfg = self._resolve_optimization_start_snapshot_cfg(cfg)
        baseline = self._build_optimization_snapshot(cfg, "Step 1: Start")
        self.optimization_baseline_snapshot = copy.deepcopy(baseline)
        self.optimization_x_range = np.array(baseline["x_range"], copy=True)
        self.optimization_ideal_f = np.array(baseline["ideal_f"], copy=True)
        self.optimization_ideal_f_conditional = np.array(baseline.get("ideal_f_conditional", baseline["ideal_f"]), copy=True)
        self.control_widget.clear_optimization_progress()
        self.control_widget.set_optimization_status(
            "Optimisation mode uses numerical theory only during the run. "
            "Monte Carlo validation is optionally applied to the displayed intermediate states at the end."
        )
        self.control_widget.set_optimization_current_value(self._build_optimization_current_text(baseline))
        self._display_optimization_snapshots(
            baseline["x_range"],
            baseline["ideal_f"],
            [baseline],
            focus_last=True,
            resume_autoplay=False,
            ideal_f_conditional=baseline.get("ideal_f_conditional", baseline["ideal_f"]),
        )

    def _on_optimization_scope_toggled(self, _checked):
        if self.optimization_toggle_suppressed:
            return
        active = self.control_widget.chk_opt_detection.isChecked() or self.control_widget.chk_opt_excitation.isChecked()
        if active and not self.optimization_mode_active:
            self._disable_diagnostics_autoplay_for_optimization()
            self._set_optimization_mode_ui(True, running=False)
            self._show_optimization_baseline()
            self.statusBar().showMessage("Optimisation mode active.")
        elif not active and self.optimization_mode_active:
            self.exit_optimization_mode()

    def exit_optimization_mode(self):
        if self.optimization_running:
            QMessageBox.information(
                self,
                "Optimisation",
                "Wait for the current optimisation run to finish before exiting optimisation mode.",
            )
            return
        self._prompt_optimization_exit_actions()
        self.optimization_toggle_suppressed = True
        try:
            self.control_widget.chk_opt_detection.setChecked(False)
            self.control_widget.chk_opt_excitation.setChecked(False)
        finally:
            self.optimization_toggle_suppressed = False
        self._set_optimization_mode_ui(False, running=False)
        self.optimization_baseline_snapshot = None
        self.optimization_x_range = None
        self.optimization_ideal_f = None
        self.optimization_ideal_f_conditional = None
        self.control_widget.clear_optimization_progress()
        self._restore_diagnostics_autoplay_after_optimization()
        self.refresh_diagnostics()
        self.statusBar().showMessage("Optimisation mode exited.")

    def run_optimization_workflow(self):
        self.sync_ui_to_config()
        self._resolve_simulation_core_session_choice()
        cfg = self.engine.config
        cfg.b_interrupt = False

        run_detection = bool(getattr(cfg, "optimize_detection_gates", False))
        run_excitation = bool(getattr(cfg, "optimize_excitation_profile", False))

        if not run_detection and not run_excitation:
            QMessageBox.information(
                self,
                "Optimisation",
                "Enable at least one optimisation target in the Optimisation tab.",
            )
            return

        if self.optimization_running:
            return

        # Force a fresh baseline build before launching the worker so optimisation
        # does not depend on any previous simulation/diagnostics run.
        self.engine.invalidate_grid()
        self._show_optimization_baseline()
        cfg = copy.deepcopy(self.engine.config)
        cfg.b_interrupt = False
        self._disable_diagnostics_autoplay_for_optimization()
        self._set_optimization_mode_ui(True, running=True)
        self.control_widget.clear_optimization_progress()
        self.control_widget.set_optimization_status("Optimisation started. Numerical theory only is used during the live run.")
        self.control_widget.set_optimization_current_value("Current simulated value: optimisation running...")
        self.control_widget.btn_export.setEnabled(False)
        self.optimization_results_saved = False
        self.optimization_results_imported = False
        self.last_optimization_run = None
        self.export_precision_act.setEnabled(False)

        self.optimization_worker = DetectionOptimisationWorker(copy.deepcopy(cfg))
        self.optimization_worker.baseline_ready.connect(self._on_optimization_baseline_ready)
        self.optimization_worker.progress_ready.connect(self._on_optimization_progress_ready)
        self.optimization_worker.result_ready.connect(self._on_optimization_finished)
        self.optimization_worker.failed.connect(self._on_optimization_failed)
        self.optimization_worker.start()
        self.statusBar().showMessage("Optimisation running...")

    def _on_optimization_baseline_ready(self, payload):
        baseline = payload["baseline"]
        self.optimization_baseline_snapshot = copy.deepcopy(baseline)
        self.optimization_x_range = np.array(payload["x_range"], copy=True)
        self.optimization_ideal_f = np.array(payload["ideal_f"], copy=True)
        self.optimization_ideal_f_conditional = np.array(payload.get("ideal_f_conditional", payload["ideal_f"]), copy=True)
        baseline_eff = np.minimum(1.0, 1.0 / np.maximum(np.square(np.asarray(baseline["theory_f"], dtype=float)), 1e-12))
        self.control_widget.update_optimization_progress(
            [0],
            [baseline["objective"]],
            {
                "min_f": [baseline["min_f"]],
                "min_eff": [float(np.nanmax(baseline_eff)) if np.any(np.isfinite(baseline_eff)) else np.nan],
                "auc_eff": [float(np.trapezoid(baseline_eff) if hasattr(np, "trapezoid") else np.trapz(baseline_eff))],
                "throughput": [float(np.nanmax(baseline_eff)) if np.any(np.isfinite(baseline_eff)) else np.nan],
                "gate_count": [int(baseline.get("gate_count", 0))],
            },
        )
        self.control_widget.set_optimization_current_value(self._build_optimization_current_text(baseline))
        if self.control_widget.chk_optimization_realtime.isChecked():
            self._display_optimization_snapshots(
                payload["x_range"],
                payload["ideal_f"],
                [baseline],
                focus_last=True,
                resume_autoplay=False,
                ideal_f_conditional=payload.get("ideal_f_conditional", payload["ideal_f"]),
            )

    def _on_optimization_progress_ready(self, payload):
        iterations = np.asarray(payload["iterations"], dtype=float)
        objectives = np.asarray(payload["objective_history"], dtype=float)
        min_f = np.asarray(payload["min_f_history"], dtype=float)
        self.control_widget.update_optimization_progress(
            iterations,
            objectives,
            {
                "min_f": np.asarray(payload.get("min_f_history", []), dtype=float),
                "min_eff": np.asarray(payload.get("min_eff_history", []), dtype=float),
                "auc_eff": np.asarray(payload.get("auc_eff_history", []), dtype=float),
                "throughput": np.asarray(payload.get("throughput_history", []), dtype=float),
                "throughput_auc": np.asarray(payload.get("throughput_auc_history", []), dtype=float),
                "gate_count": np.asarray(payload.get("gate_count_history", []), dtype=float),
            },
        )
        current = payload.get("current")
        if current is not None:
            self.control_widget.set_optimization_current_value(self._build_optimization_current_text(current))
            self.control_widget.set_optimization_status(
                f"Optimisation running.\n\nCurrent step: {current.get('step', 0)}\n"
                f"Objective J: {current.get('objective', np.nan):.6g}\n"
                f"Minimum F: {current.get('min_f', np.nan):.6g}\n"
                f"Gate count: {int(current.get('gate_count', max(0, len(current.get('config', {}).get('gate_edges', [])) - 1)))}"
            )
            if self.control_widget.chk_optimization_realtime.isChecked():
                snapshots = [current]
                if self.optimization_baseline_snapshot is not None:
                    snapshots = [self.optimization_baseline_snapshot, current]
                self._display_optimization_snapshots(
                    self.optimization_x_range if self.optimization_x_range is not None else current["accuracy"]["mean"],
                    self.optimization_ideal_f if self.optimization_ideal_f is not None else current["theory_f"],
                    snapshots,
                    focus_last=True,
                    resume_autoplay=False,
                    ideal_f_conditional=self.optimization_ideal_f_conditional if self.optimization_ideal_f_conditional is not None else (self.optimization_ideal_f if self.optimization_ideal_f is not None else current["theory_f"]),
                )

    def _on_optimization_finished(self, payload):
        self.optimization_running = False
        self.optimization_x_range = np.array(payload["x_range"], copy=True)
        self.optimization_ideal_f = np.array(payload["ideal_f"], copy=True)
        self.optimization_ideal_f_conditional = np.array(payload.get("ideal_f_conditional", payload["ideal_f"]), copy=True)
        self._set_optimization_mode_ui(True, running=False)
        self.last_optimization_run = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "x_range": np.array(payload["x_range"], copy=True),
            "ideal_f": np.array(payload["ideal_f"], copy=True),
            "ideal_f_conditional": np.array(payload.get("ideal_f_conditional", payload["ideal_f"]), copy=True),
            "snapshots": copy.deepcopy(payload["snapshots"]),
            "final_snapshot": copy.deepcopy(payload["final_snapshot"]),
            "final_config": copy.deepcopy(payload["final_config"]),
            "final_excitation_summary": copy.deepcopy(payload.get("final_excitation_summary", {})),
            "objective_history": np.array(payload["objective_history"], copy=True),
            "min_f_history": np.array(payload["min_f_history"], copy=True),
            "min_eff_history": np.array(payload.get("min_eff_history", []), copy=True),
            "auc_eff_history": np.array(payload.get("auc_eff_history", []), copy=True),
            "throughput_history": np.array(payload.get("throughput_history", []), copy=True),
            "throughput_auc_history": np.array(payload.get("throughput_auc_history", []), copy=True),
            "gate_count_history": np.array(payload.get("gate_count_history", []), copy=True),
            "final_gate_count": int(payload.get("final_gate_count", max(0, len(payload.get("best_edges", [])) - 1))),
            "x_label": self._current_target_label(),
            "config": copy.deepcopy(self.engine.config.model_dump() if hasattr(self.engine.config, "model_dump") else self.engine.config.dict()),
        }
        self.control_widget.update_optimization_progress(
            np.arange(len(payload["objective_history"]), dtype=float),
            payload["objective_history"],
            {
                "min_f": np.asarray(payload.get("min_f_history", []), dtype=float),
                "min_eff": np.asarray(payload.get("min_eff_history", []), dtype=float),
                "auc_eff": np.asarray(payload.get("auc_eff_history", []), dtype=float),
                "throughput": np.asarray(payload.get("throughput_history", []), dtype=float),
                "throughput_auc": np.asarray(payload.get("throughput_auc_history", []), dtype=float),
                "gate_count": np.asarray(payload.get("gate_count_history", []), dtype=float),
            },
        )
        excitation_summary = payload.get("final_excitation_summary", {})
        excitation_text = ""
        if excitation_summary:
            width_text = ""
            if "width_ns" in excitation_summary:
                width_text = f"\nExcitation width: {float(excitation_summary['width_ns']):.6g} ns"
            elif excitation_summary.get("control_points"):
                width_text = f"\nExcitation control points: {len(excitation_summary['control_points'])}"
            excitation_text = (
                f"\nBest excitation profile: {excitation_summary.get('profile', 'n/a')}"
                f"\nExcitation constraint: {excitation_summary.get('constraint', 'n/a')}"
                f"{width_text}"
                f"\nEquivalent width: {float(excitation_summary.get('equivalent_width_ns', np.nan)):.6g} ns"
            )
        self.control_widget.set_optimization_current_value(self._build_optimization_current_text(payload["final_snapshot"]))
        self.control_widget.set_optimization_status(
            f"Optimisation complete.\n\nBest objective J: {payload['best_objective']:.6g}\n"
            f"Displayed optimisation states: {len(payload['snapshots'])}\n"
            f"Final gate count: {int(payload.get('final_gate_count', max(0, len(payload.get('best_edges', [])) - 1)))}"
            f"{excitation_text}"
        )
        self._display_optimization_snapshots(
            payload["x_range"],
            payload["ideal_f"],
            payload["snapshots"],
            focus_last=True,
            resume_autoplay=False,
            ideal_f_conditional=payload.get("ideal_f_conditional", payload["ideal_f"]),
        )
        self._disable_diagnostics_autoplay_for_optimization()
        self.diagnostics_widget.chk_autoplay.setEnabled(True)
        self.optimization_results_saved = False
        self.optimization_results_imported = False
        self._update_primary_action_buttons()
        self._set_export_enabled()
        self.statusBar().showMessage("Optimisation complete.")
        self.optimization_worker = None

    def _on_optimization_failed(self, message):
        self.optimization_running = False
        self._set_optimization_mode_ui(self.optimization_mode_active, running=False)
        self.control_widget.set_optimization_status(f"Optimisation failed.\n\n{message}")
        self._restore_diagnostics_autoplay_after_optimization()
        self._update_primary_action_buttons()
        self._set_export_enabled()
        QMessageBox.warning(self, "Optimisation Failed", message)
        self.statusBar().showMessage("Optimisation failed.")
        self.optimization_worker = None

    def sync_ui_to_config(self):
        cfg = self.engine.config
        cw = self.control_widget
        
        # Model Parameters (Dynamic row logic)
        cfg.decay_model = cw.get_selected_decay_model_key()
        cfg.n_components = cw.spin_n_comp.value()
        if "tau1" in cw.param_rows:
            cfg.taus[0] = cw.param_rows["tau1"]['val'].value()
        if "tau2" in cw.param_rows:
            cfg.taus[1] = cw.param_rows["tau2"]['val'].value()
        if "alpha" in cw.param_rows:
            cfg.amplitudes[0] = cw.param_rows["alpha"]['val'].value()
            if len(cfg.amplitudes) > 1:
                cfg.amplitudes[1] = max(0.0, 1.0 - cfg.amplitudes[0])
        dark_count_rate = float(getattr(cw, "spin_dark_count_rate", None).value()) if hasattr(cw, "spin_dark_count_rate") else 0.0
        cfg.background_level = 0.0 if dark_count_rate > 0.0 else cw.param_rows["background"]['val'].value() / 100.0
        if "beta" in cw.param_rows:
            cfg.beta = cw.param_rows["beta"]['val'].value()
        cfg.custom_model_params = {
            name: row["val"].value()
            for name, row in cw.param_rows.items()
            if name not in getattr(cw, "base_param_names", set())
        }
        
        # Fix Flags & F-Value X Selection
        selected_x = None
        for name, row in cw.param_rows.items():
            if row['x'].isChecked():
                selected_x = name
        if selected_x is None:
            selected_x = "tau1"
            if "tau1" in cw.param_rows:
                cw.param_rows["tau1"]['x'].setChecked(True)
        cfg.f_x_param = selected_x
        for name, row in cw.param_rows.items():
            forced_fixed = name != selected_x
            row['fix'].setChecked(forced_fixed)
            cfg.fixed_params[name] = forced_fixed
        cfg.f_x_min = cw.spin_fx_min.value()
        cfg.f_x_max = cw.spin_fx_max.value()
        cfg.f_x_steps = cw.spin_fx_steps.value()
        cfg.grid_fine_factor = cw.spin_grid_fine_factor.value()
        scale_map = {"log": "log", "linear": "linear", "exponential": "exp"}
        cfg.f_x_scale = scale_map.get(cw.combo_fx_scale.currentText().lower(), "log")
        runtime_defs = self.decay_model_store.runtime_param_defs(cfg)
        selected_meta = next((item for item in runtime_defs if item.get("name") == cfg.f_x_param), {})
        use_log_grid = cfg.f_x_scale == "log" and cfg.f_x_min > 0 and cfg.f_x_max > 0 and str(selected_meta.get("scale", "")).lower() == "log"
        if use_log_grid:
            step_ratio = (cfg.f_x_max / cfg.f_x_min) ** (1.0 / max(1, cfg.f_x_steps - 1))
            pad_factor = max(step_ratio, 1.25)
            cfg.grid_tau_min = max(1e-6, cfg.f_x_min / pad_factor)
            cfg.grid_tau_max = max(cfg.grid_tau_min * 1.0001, cfg.f_x_max * pad_factor)
        else:
            coarse_step = (cfg.f_x_max - cfg.f_x_min) / max(1, cfg.f_x_steps - 1)
            cfg.grid_tau_min = max(1e-6, cfg.f_x_min - coarse_step)
            cfg.grid_tau_max = cfg.f_x_max + coarse_step
        cfg.grid_steps = max(3, ((cfg.f_x_steps - 1) + 2) * cfg.grid_fine_factor + 1)
        cfg.precision_validate_mc = cw.chk_validate_mc.isChecked()
        cfg.precision_compute_ci = cw.chk_compute_ci.isChecked()
        cfg.precision_photons = cw.spin_precision_photons.value()
        cfg.precision_mc_repeats = cw.spin_mc_repeats.value()
        cfg.precision_accuracy_pvalue = cw.spin_accuracy_pvalue.value()
        cfg.precision_bootstrap_samples = cw.spin_bootstrap_samples.value()
        cfg.precision_ci_level = cw.spin_ci_level.value()
        cfg.sweep_autoplay = self.diagnostics_widget.chk_autoplay.isChecked()

        # Optimization
        cfg.optimize_detection_gates = cw.chk_opt_detection.isChecked()
        cfg.optimize_excitation_profile = cw.chk_opt_excitation.isChecked()
        cfg.optimization_mode = "sequential"
        optimization_first_map = {"detection first": "detection", "excitation first": "excitation"}
        cfg.optimization_first = optimization_first_map.get(cw.combo_optimization_first.currentText().lower(), "detection")
        cfg.optimization_iterations = cw.spin_optimization_iterations.value()
        if cw.radio_f_basis_collected.isChecked():
            cfg.optimization_f_photon_basis = "collected"
        elif cw.radio_f_basis_all.isChecked():
            cfg.optimization_f_photon_basis = "all"
        else:
            cfg.optimization_f_photon_basis = "period"
        optimization_objective_map = {
            "fisher information": "fisher_information",
            "fisher throughput": "fisher_throughput",
            "photon efficiency auc": "photon_efficiency_auc",
            "throughput auc": "throughput_auc",
        }
        cfg.optimization_objective = optimization_objective_map.get(
            cw.combo_optimization_objective.currentText().lower(),
            "fisher_throughput",
        )
        cfg.optimization_max_fi_loss_pct = cw.spin_optimization_fi_loss.value()
        cfg.optimization_realtime_visualization = cw.chk_optimization_realtime.isChecked()
        cfg.optimization_realtime_interval_s = cw.spin_optimization_realtime_interval.value()
        cfg.optimization_intermediate_steps = cw.spin_optimization_steps_to_show.value()
        cfg.optimization_validate_mc_intermediates = cw.chk_optimization_validate_mc.isChecked()

        detection_algorithm_map = {
            "direct mean f minimisation": "direct_slsqp",
            "partition theorem bottom-up": "partition_bottom_up",
            "partition theorem top-down": "partition_top_down",
            "fisher compression": "fisher_compression",
        }
        cfg.detection_optimization_algorithm = detection_algorithm_map.get(
            cw.combo_detection_algorithm.currentText().lower(),
            "fisher_compression",
        )
        detection_start_map = {"stick to 0": "zero", "start after irf": "irf", "custom": "custom"}
        cfg.detection_opt_start_anchor = detection_start_map.get(
            cw.combo_detection_start_anchor.currentText().lower(),
            "zero",
        )
        cfg.detection_opt_restarts = int(getattr(cw, "detection_opt_restarts", 20))
        cfg.detection_opt_ftol = float(getattr(cw, "detection_opt_ftol", 1e-4))
        cfg.detection_opt_maxiter = int(getattr(cw, "detection_opt_maxiter", 50))
        cfg.detection_opt_fine_bins_per_gate = int(getattr(cw, "detection_opt_fine_bins_per_gate", 12))
        cfg.detection_opt_fine_bin_cap = int(getattr(cw, "detection_opt_fine_bin_cap", 256))
        cfg.detection_opt_fc_nuisance_aware = bool(getattr(cw, "detection_opt_fc_nuisance_aware", True))
        cfg.detection_opt_fc_auto_compress = bool(getattr(cw, "detection_opt_fc_auto_compress", False))
        cfg.detection_opt_fc_initial_gates = int(getattr(cw, "detection_opt_fc_initial_gates", 16))
        cfg.detection_opt_fc_min_gates = int(getattr(cw, "detection_opt_fc_min_gates", 2))
        cfg.detection_opt_fc_max_f_loss_pct = float(getattr(cw, "detection_opt_fc_max_f_loss_pct", 5.0))
        cfg.detection_opt_start_time = cw.spin_detection_start_anchor.value()
        detection_end_map = {"stick to period": "period", "custom": "custom"}
        cfg.detection_opt_end_anchor = detection_end_map.get(
            cw.combo_detection_end_anchor.currentText().lower(),
            "period",
        )
        cfg.detection_opt_end_time = cw.spin_detection_end_anchor.value()

        excitation_profile_map = {
            "gaussian": "gaussian",
            "square": "rectangular",
            "free form": "free_form",
        }
        cfg.excitation_optimization_profile = excitation_profile_map.get(
            cw.combo_excitation_optimization_profile.currentText().lower(),
            "gaussian",
        )
        excitation_constraint_map = {
            "fixed dose (area)": "fixed_dose",
            "fixed peak": "fixed_peak",
        }
        cfg.excitation_optimization_constraint = excitation_constraint_map.get(
            cw.combo_excitation_constraint.currentText().lower(),
            "fixed_dose",
        )
        cfg.excitation_optimization_width_min = cw.spin_excitation_width_min.value()
        cfg.excitation_optimization_width_max = cw.spin_excitation_width_max.value()
        cfg.excitation_optimization_control_points = cw.spin_excitation_control_points.value()

        # Laser & IRF
        cfg.period = cw.spin_period.value()
        cfg.b_decay_wrapping = cw.chk_pulse_train_decay.isChecked()
        irf_profile_map = {
            "gaussian": "gaussian",
            "rectangular": "rectangular",
            "free form": "free_form",
            "ideal (dirac)": "ideal (dirac)",
        }
        cfg.irf_profile = irf_profile_map.get(cw.combo_profile.currentText().lower(), "gaussian")
        cfg.irf_fwhm = cw.spin_fwhm.value()
        cfg.irf_position = cw.spin_irf_pos.value()
        cfg.irf_rise_time = cw.spin_rise.value()
        cfg.irf_fall_time = cw.spin_fall.value()
        freeform_times, freeform_points = cw.freeform_editor.get_points()
        cfg.irf_freeform_times = [float(v) for v in freeform_times]
        cfg.irf_freeform_points = [float(v) for v in freeform_points]
        cfg.irf_freeform_edit_mode = bool(cw.btn_freeform_mode.isChecked())
        
        # Burst Excitation
        cfg.burst_enabled = cw.group_burst.isChecked()
        cfg.burst_sub_period = cw.spin_burst_period.value() / 1000.0 # From ps to ns
        cfg.burst_sub_fwhm = cw.spin_burst_fwhm.value() / 1000.0 # From ps to ns
        
        # Instrument & Noise
        cfg.a_photons = float(cw.spin_precision_photons.value())
        cfg.image_mc_repeats = int(cw.spin_image_repeats.value())
        image_fit_map = {
            "gridded mle": "gridded_mle",
            "iterative reconvolution": "mle",
            "tail fitting": "tail",
        }
        cfg.image_fit_method = image_fit_map.get(cw.combo_image_fit_method.currentText().lower(), "gridded_mle")
        cfg.timing_jitter = cw.spin_jitter.value()
        cfg.detector_deadtime = cw.spin_deadtime.value()
        cfg.detector_afterpulsing_probability = float(getattr(cw, "spin_afterpulsing", None).value()) / 100.0 if hasattr(cw, "spin_afterpulsing") else 0.0
        cfg.detector_dark_count_rate_cps = dark_count_rate
        cfg.b_multihit_mode = cw.chk_multihit.isChecked()
        cfg.simulation_mode_preference = str(getattr(cw, "simulation_mode_preference", "auto")).lower()
        cfg.event_deadtime_mode = "none" if cfg.detector_deadtime <= 0 else "nonparalyzable"
        cfg.event_multihit_capacity = getattr(cw, "event_multihit_capacity", None)
        cfg.event_routing_mode = "exclusive"
        cfg.event_arbitration_rule = "random"
        cfg.event_share_resource_group = True
        cfg.event_return_timestamps = False
        cfg.event_pixel_dwell_time_s = float(getattr(cw, "event_pixel_dwell_time_s", 1e-3))
        cfg.n_repeats = int(cw.spin_image_repeats.value())

        # Gating
        gate_type = cw.combo_gate_type.currentText().lower()
        cfg.gate_type = gate_type
        cfg.gate_rise = cw.spin_gate_rise.value()
        cfg.gate_fall = cw.spin_gate_fall.value()
        
        if cw.radio_gate_irf.isChecked(): cfg.gate_start_mode = "irf_3sigma"
        elif cw.radio_gate_start.isChecked(): cfg.gate_start_mode = "start"
        else: cfg.gate_start_mode = "free"
        cfg.gate_first_start = cw.spin_gate_first.value()
        cfg.gate_end_mode = "free" if cw.radio_gate_end_free.isChecked() else "period"
        cfg.gate_last_end = cw.spin_gate_last.value()
        cfg.gate_collection_mode = "sequential" if cw.radio_gate_collection_seq.isChecked() else "histogram"
        if cw.radio_overlap_never.isChecked():
            cfg.gate_overlap_mode = "never"
        elif cw.radio_overlap_yes.isChecked():
            cfg.gate_overlap_mode = "allow"
        else:
            cfg.gate_overlap_mode = "jitter_only"
        cfg.gate_overlap_ns = cw.spin_gate_overlap.value()
        if cw.radio_overlap_effect_duplicate.isChecked():
            cfg.gate_overlap_effect = "duplicate_events"
        elif cw.radio_overlap_effect_independent.isChecked():
            cfg.gate_overlap_effect = "independent_duplicates"
        else:
            cfg.gate_overlap_effect = "exclusive"
        cfg.gate_wraparound = cw.chk_gate_wraparound.isChecked()

        edges, _ = cw.validate_gate_definition()
        if edges is not None:
            cfg.gate_edges = list(edges)
            cfg.gate_widths = np.diff(np.asarray(edges, dtype=float)).tolist()
            
        # Optional Instrument Sweep
        cfg.instr_sweep_active = not cw.radio_sweep_off.isChecked()
        cfg.instr_sweep_param = cw.get_selected_sweep_param()
        cfg.instr_sweep_gate_sharp_edge = (
            "sharp_rise"
            if cw.sweep_options["gate_edge_one_sharp_ps"]["extra"].currentText().startswith("Sharp Rise")
            else "sharp_fall"
        )
        cfg.instr_sweep_burst_sharp_edge = (
            "sharp_rise"
            if cw.sweep_options["burst_edge_one_sharp_ns"]["extra"].currentText().startswith("Sharp Rise")
            else "sharp_fall"
        )
        if "deadtime_fixed_countrate_ns" in cw.sweep_options and cw.sweep_options["deadtime_fixed_countrate_ns"]["extra"] is not None:
            try:
                cfg.instr_sweep_fixed_countrate_kcps = float(cw.sweep_options["deadtime_fixed_countrate_ns"]["extra"].text().strip())
            except Exception:
                cfg.instr_sweep_fixed_countrate_kcps = 100.0
        else:
            cfg.instr_sweep_fixed_countrate_kcps = 100.0
        cfg.instr_sweep_fixed_deadtime_ns = float(getattr(cfg, "instr_sweep_fixed_deadtime_ns", 45.0))
        cfg.instr_sweep_vals = self._parse_sweep_values(cfg.instr_sweep_param, cw.get_selected_sweep_values_text())
        if cfg.instr_sweep_active and cfg.instr_sweep_param == "countrate_via_dwell_hz":
            cfg.precision_photons = 1000

    def _create_diagnostics_frame(self, config=None, label="Instrument snapshot"):
        original_config = self.engine.config
        if config is not None:
            self.engine.config = copy.deepcopy(config)
        try:
            self.engine.grid_templates = None
            self.engine.grid_tau_axis = None
            self.engine.distill_gates()
            tau_ref = self.engine.config.taus[0] if self.engine.config.taus else 2.5
            pdf_ref = self.engine.dt_pdf(self.engine.time_vector, tau_ref)
            pdf_ref = self.engine._effective_detected_pdf(
                pdf_ref,
                float(getattr(self.engine.config, "a_photons", 0.0)),
                self.engine.config,
            )
            irf_cfg = copy.deepcopy(self.engine.config)
            irf_cfg.simulation_mode_preference = "ideal_poisson"
            irf_cfg.background_level = 0.0
            irf_cfg.decay_model = "exponential"
            irf_cfg.n_components = 1
            irf_cfg.taus = [1e-9]
            irf_cfg.amplitudes = [1.0]
            self.engine.config = irf_cfg
            irf_ref = self.engine.dt_pdf(self.engine.time_vector, tau=1e-9)
            return {
                "time_vec": np.array(self.engine.time_vector, copy=True),
                "gate_shapes": np.array(self.engine.gate_shapes, copy=True),
                "irf": np.array(irf_ref, copy=True),
                "pdf": np.array(pdf_ref, copy=True),
                "label": label,
            }
        finally:
            self.engine.config = original_config

    def _show_diagnostics_frame(self, frame, use_frames=False):
        if use_frames:
            self.diagnostics_widget.append_frame(frame, focus=True)
        else:
            self.diagnostics_widget.clear_frames()
            # Build name for the legend: parameter=value
            x_param = self.engine.config.f_x_param
            # We assume f_x_param is something like "tau1"
            val = getattr(self.engine.config, "taus", [2.5])[0] if x_param=="tau1" else getattr(self.engine.config, x_param, 2.5)
            # Use label from control widget for better display
            try:
                display_label = self.control_widget.param_rows[x_param]['label'].text().split("(")[0].strip()
            except:
                display_label = x_param
            
            pdf_label = f"Ref PDF: {display_label} = {val:g} ns"
            
            self.diagnostics_widget.update_plot(
                frame["time_vec"],
                frame["gate_shapes"],
                irf=frame.get("irf"),
                pdf=frame.get("pdf"),
                label=pdf_label
            )

    def refresh_diagnostics(self):
        """Forces a re-distillation of gates and updates the physics plots."""
        if self.loading_config_into_ui:
            return
        if self.optimization_running:
            return
        self.sync_ui_to_config()
        self._resolve_simulation_core_session_choice()
        self._update_simulation_mode_badge()
        if self.optimization_mode_active and not self.optimization_running:
            self._show_optimization_baseline()
            return
        frame = self._create_diagnostics_frame(self.engine.config)
        self._show_diagnostics_frame(frame, use_frames=False)

    def interrupt_simulation(self):
        self.engine.config.b_interrupt = True
        if self.optimization_worker is not None:
            self.optimization_worker.request_interrupt()
        self.statusBar().showMessage("⌛ Interrupt Request Received...")

    def _serialise_workspace_value(self, value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, dict):
            return {k: self._serialise_workspace_value(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._serialise_workspace_value(v) for v in value]
        return value

    def _has_precision_workspace(self):
        return bool(self.last_precision_run or self.last_optimization_run)

    def _has_validation_workspace(self):
        return bool(self.engine.raw_data is not None or self.last_validation_run)

    def _confirm_workspace_transition(self, target_mode):
        if target_mode == "precision" and self.workspace_mode == "validation" and self._has_validation_workspace():
            reply = QMessageBox.question(
                self,
                "Clear Validation Workspace",
                "TEST data is currently loaded. Clear the workspace before running RUN?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
            self.clear_workspace(confirm=False)
        if target_mode == "validation" and self.workspace_mode == "precision" and self._has_precision_workspace():
            reply = QMessageBox.question(
                self,
                "Clear Precision Workspace",
                "RUN results are currently loaded. Clear the workspace before running TEST?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
            self.clear_workspace(confirm=False)
        return True

    def clear_workspace(self, confirm=False):
        if confirm and not (self._has_precision_workspace() or self._has_validation_workspace()):
            return
        if confirm:
            reply = QMessageBox.question(
                self,
                "Clear Workspace",
                "Clear all generated data while keeping the controller settings?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.engine.clear_workspace_data()
        self.last_precision_run = None
        self.last_optimization_run = None
        self.last_validation_run = None
        self.validation_fit_summary = None
        self.workspace_mode = None
        self.export_precision_act.setEnabled(False)
        self.control_widget.btn_export.setEnabled(False)
        self.map_widget.clear_image()
        self.phasor_widget.update_data(np.array([]), np.array([]))
        self.decay_widget.clear()
        self.fisher_widget.clear_data()
        self.mle_accuracy_widget.clear_data()
        self.diagnostics_widget.clear_frames()
        self.statusBar().showMessage("Workspace cleared.")

    def save_workspace(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Workspace", "hilighter_workspace.h5", "HDF5 Files (*.h5)")
        if not file_path:
            return
        self.sync_ui_to_config()
        metadata = {
            "schema_version": 2,
            "theme": self.settings.value("theme", "dark"),
            "workspace_mode": self.workspace_mode,
            "config": self.engine.config.model_dump() if hasattr(self.engine.config, "model_dump") else self.engine.config.dict(),
            "last_precision_run": self._serialise_workspace_value(self.last_precision_run),
            "last_optimization_run": self._serialise_workspace_value(self.last_optimization_run),
            "last_validation_run": self._serialise_workspace_value(self.last_validation_run),
            "validation_metadata": self._serialise_workspace_value(self.engine.validation_metadata),
        }
        arrays = {
            "raw_data": self.engine.raw_data,
            "tau_map": self.engine.tau_map,
            "a_map": self.engine.a_map,
            "b_map": self.engine.b_map,
            "chi2_map": self.engine.chi2_map,
            "validation_param_map": self.engine.validation_param_map,
            "validation_truth_map": self.engine.validation_truth_map,
        }
        try:
            storage.save_workspace(file_path, metadata, arrays)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Save Workspace", str(exc))
            return
        self.statusBar().showMessage(f"Workspace saved to {file_path}")

    def load_workspace(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Workspace", "", "HDF5 Files (*.h5)")
        if not file_path:
            return
        try:
            metadata, arrays = storage.load_workspace(file_path)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Load Workspace", str(exc))
            return
        self.engine.config = PhysicsConfig(**metadata.get("config", {}))
        self.loading_config_into_ui = True
        try:
            self.control_widget.update_from_config(self.engine.config)
        finally:
            self.loading_config_into_ui = False
        self.settings.setValue("theme", metadata.get("theme", "dark"))
        self.apply_theme()
        self._update_simulation_mode_badge()
        self.engine.raw_data = arrays.get("raw_data")
        self.engine.tau_map = arrays.get("tau_map")
        self.engine.a_map = arrays.get("a_map")
        self.engine.b_map = arrays.get("b_map")
        self.engine.chi2_map = arrays.get("chi2_map")
        self.engine.validation_param_map = arrays.get("validation_param_map")
        self.engine.validation_truth_map = arrays.get("validation_truth_map")
        self.engine.validation_metadata = metadata.get("validation_metadata", {})
        self.last_precision_run = metadata.get("last_precision_run")
        self.last_optimization_run = metadata.get("last_optimization_run")
        self.last_validation_run = metadata.get("last_validation_run")
        self.workspace_mode = metadata.get("workspace_mode")
        self.engine.distill_gates()
        if self.engine.raw_data is not None:
            self._refresh_validation_views()
            self.apply_testing_view()
        elif self.engine.validation_param_map is not None:
            self.map_widget.set_images(None, self.engine.validation_param_map)
            self.apply_testing_view()
        self._set_export_enabled()
        self.statusBar().showMessage(f"Workspace loaded from {file_path}")

    def _run_precision_analysis_legacy(self):
        """Exclusively runs the theoretical Fisher/F-value evaluation."""
        self.sync_ui_to_config()
        cfg = self.engine.config

        # === DIAGNOSTICS ===
        print(f"[PRECISION] instr_sweep_active={cfg.instr_sweep_active}")
        print(f"[PRECISION] instr_sweep_param={cfg.instr_sweep_param}")
        print(f"[PRECISION] instr_sweep_vals={cfg.instr_sweep_vals}")
        # ===================
        
        # Generate X-axis range
        x_range = self._build_precision_x_range(cfg)
            
        # Update X-Axis Label from UI
        target_label = self.control_widget.param_rows[cfg.f_x_param]['label'].text().replace(":", "")
        self.fisher_widget.set_xaxis_label(target_label)
        self.mle_accuracy_widget.set_xaxis_label(f"Ground Truth {target_label}")
        self.mle_accuracy_widget.clear_data()
        
        self.statusBar().showMessage("📈 Computing Theoretical Precision Map...")
        
        # Ideal Reference
        _, f_ideal = self.engine.compute_ideal_reference(x_range, int(cfg.a_photons))
        
        if cfg.instr_sweep_active and cfg.instr_sweep_vals:
            # ---- COLLECT ALL RESULTS FIRST, THEN PLOT ONCE ----
            # Take a clean snapshot of the config before any sweep mutation
            baseline_cfg = copy.deepcopy(cfg)
            param = cfg.instr_sweep_param
            batch_results = {}  # label -> f_values array

            for i, val in enumerate(cfg.instr_sweep_vals):
                self.statusBar().showMessage(f"📈 Batch Sweep: {param} = {val} ({i+1}/{len(cfg.instr_sweep_vals)})")
                
                # Build a fresh mutated config from the baseline each iteration
                sweep_cfg = copy.deepcopy(baseline_cfg)
                try:
                    self._apply_sweep_value(sweep_cfg, param, val)
                except ValueError:
                    print(f"Warning: Param '{param}' not found in PhysicsConfig")
                    continue
                
                # Temporarily assign to engine, compute, restore
                self.engine.config = sweep_cfg
                try:
                    _, f_val = self.engine.compute_fisher_info(
                        x_range,
                        int(sweep_cfg.a_photons),
                        photon_basis_mode=getattr(sweep_cfg, "optimization_f_photon_basis", "period"),
                    )
                    batch_results[self._format_sweep_label(param, val, sweep_cfg)] = np.array(f_val, copy=True)
                finally:
                    self.engine.config = baseline_cfg  # Always restore baseline

            sweep_pdfs = self._build_precision_pdf_ensemble(cfg, x_range)

            # Update Diagnostics with the ensemble
            frame = self._create_diagnostics_frame(cfg)
            frame["background_curves"] = sweep_pdfs
            self.diagnostics_widget.update_plot(
                frame["time_vec"], frame["gate_shapes"], 
                irf=frame["irf"], pdf=frame["pdf"], 
                background_curves=sweep_pdfs
            )

            # ---- SINGLE PLOT UPDATE WITH ALL CURVES ----
            self.fisher_widget.plot_batch(x_range, batch_results,
                                          ideal_x=x_range, ideal_f=f_ideal)
            self.statusBar().showMessage("✅ Batch Sweep Complete.")
        else:
            # Single curve
            _, f_val = self.engine.compute_fisher_info(
                x_range,
                int(cfg.a_photons),
                photon_basis_mode=getattr(cfg, "optimization_f_photon_basis", "period"),
            )
            
            sweep_pdfs = self._build_precision_pdf_ensemble(cfg, x_range)

            frame = self._create_diagnostics_frame(cfg)
            frame["background_curves"] = sweep_pdfs
            self.diagnostics_widget.update_plot(
                frame["time_vec"], frame["gate_shapes"], 
                irf=frame["irf"], pdf=frame["pdf"], 
                background_curves=sweep_pdfs
            )

            self.fisher_widget.plot_batch(x_range, {"Simulated": np.array(f_val, copy=True)},
                                          ideal_x=x_range, ideal_f=f_ideal)
                                           
        self.statusBar().showMessage("✅ Precision Analysis Complete.")

    def _set_progress(self, completed, total, message):
        if total <= 0:
            self.progress.hide()
            return
        self.progress.show()
        self.progress.setValue(int(100 * completed / total))
        self.statusBar().showMessage(message)

    def _build_precision_x_range(self, cfg):
        lower_bound, upper_bound = self.engine._get_cfg_param_bounds(getattr(cfg, "f_x_param", "tau1"))
        x_min = float(cfg.f_x_min)
        x_max = float(cfg.f_x_max)
        if lower_bound is not None:
            x_min = max(x_min, float(lower_bound))
            x_max = max(x_max, float(lower_bound))
        if upper_bound is not None:
            x_min = min(x_min, float(upper_bound))
            x_max = min(x_max, float(upper_bound))
        n_steps = max(int(cfg.f_x_steps), 2)
        scale = str(cfg.f_x_scale).lower()

        if x_max < x_min:
            x_min, x_max = x_max, x_min
        if np.isclose(x_max, x_min):
            return np.full(n_steps, x_min, dtype=float)
        if scale in {"log", "exp"} and (x_min <= 0 or x_max <= 0):
            scale = "linear"

        if scale == "log":
            return np.logspace(np.log10(x_min), np.log10(x_max), n_steps)
        if scale == "linear":
            return np.linspace(x_min, x_max, n_steps)
        return np.geomspace(x_min, x_max, n_steps)

    def _build_precision_pdf_ensemble(self, cfg, x_range):
        original_config = self.engine.config
        try:
            curves = []
            for x_val in x_range:
                pdf_cfg = copy.deepcopy(cfg)
                self.engine.config = pdf_cfg
                self.engine._set_cfg_param(pdf_cfg.f_x_param, float(x_val))
                self.engine.distill_gates()
                pdf = np.array(self.engine.dt_pdf(self.engine.time_vector), copy=True)
                pdf = self.engine._effective_detected_pdf(
                    pdf,
                    float(getattr(pdf_cfg, "a_photons", 0.0)),
                    pdf_cfg,
                )
                curves.append(pdf)
            return curves
        finally:
            self.engine.config = original_config

    def _parse_sweep_values(self, param, raw_text):
        if param == "instrument_profile":
            return [token.strip() for token in raw_text.split(",") if token.strip()]
        tokens = [token.strip() for token in raw_text.split(",") if token.strip()]
        if not tokens:
            return []
        try:
            return [float(token) for token in tokens]
        except Exception:
            return []

    def _format_sweep_label(self, param, value, cfg):
        def _format_rate_hz(rate_hz):
            rate = float(rate_hz)
            if rate >= 1e9:
                return f"{rate / 1e9:g} GHz"
            if rate >= 1e6:
                return f"{rate / 1e6:g} MHz"
            if rate >= 1e3:
                return f"{rate / 1e3:g} kHz"
            return f"{rate:g} Hz"

        if param == "laser_pulse_fwhm_ns":
            return f"Laser Pulse = {value:g} ns"
        if param == "detector_jitter_ps":
            return f"Detector Jitter = {value:g} ps"
        if param == "gate_edge_symmetric_ps":
            return f"Gate Rise/Fall = {value:g} ps"
        if param == "gate_edge_one_sharp_ps":
            mode = "sharp rise" if cfg.instr_sweep_gate_sharp_edge == "sharp_rise" else "sharp fall"
            return f"Gate Edge = {value:g} ps ({mode})"
        if param == "number_of_gates":
            return f"Number of Gates = {int(round(value))}"
        if param == "deadtime_fixed_countrate_ns":
            return f"Deadtime = {value:g} ns @ {cfg.instr_sweep_fixed_countrate_kcps:g} Kphotons/s"
        if param == "countrate_via_dwell_hz":
            return f"Count Rate = {_format_rate_hz(value)}"
        if param == "countrate_fixed_deadtime_kcps":
            return f"Countrate = {value:g} Kphotons/s @ {cfg.instr_sweep_fixed_deadtime_ns:g} ns"
        if param == "multihit_capabilities":
            return f"Max events/period = {int(round(value))}"
        if param == "afterpulsing_probability_pct":
            return f"Afterpulsing = {value:g}%"
        if param == "dark_count_rate_cps":
            return f"Dark count rate = {value:g} cps"
        if param == "instrument_profile":
            return f"Profile = {value}"
        if param == "burst_edge_symmetric_ns":
            return f"Burst Rise/Fall = {value:g} ns"
        if param == "burst_edge_one_sharp_ns":
            mode = "sharp rise" if cfg.instr_sweep_burst_sharp_edge == "sharp_rise" else "sharp fall"
            return f"Burst Edge = {value:g} ns ({mode})"
        return f"{param} = {value:g}"

    def _apply_sweep_value(self, cfg, param, value):
        cfg.metadata = dict(getattr(cfg, "metadata", {}))
        cfg.metadata.pop("force_precision_deadtime_mc", None)
        if param == "number_of_gates":
            t_start = 0.0
            if cfg.gate_start_mode == "irf_3sigma":
                jitter_ns = cfg.timing_jitter / 1000.0
                if cfg.irf_profile == "gaussian":
                    sigma_total = np.sqrt((cfg.irf_fwhm / 2.355) ** 2 + jitter_ns ** 2)
                    t_start = cfg.irf_position + 3.0 * sigma_total
                elif cfg.irf_profile == "ideal (dirac)":
                    t_start = cfg.irf_position + 3.0 * jitter_ns
                else:
                    t_start = cfg.irf_position + cfg.irf_fwhm + 3.0 * jitter_ns
            elif cfg.gate_start_mode == "free":
                t_start = cfg.gate_first_start
            t_end = cfg.period if getattr(cfg, "gate_end_mode", "period") == "period" else getattr(cfg, "gate_last_end", cfg.gate_edges[-1])
            edges = np.linspace(t_start, t_end, int(value) + 1)
            cfg.gate_edges = edges.tolist()
            cfg.gate_widths = np.diff(edges).tolist()
        elif param == "laser_pulse_fwhm_ns":
            cfg.irf_fwhm = float(value)
        elif param == "detector_jitter_ps":
            cfg.timing_jitter = float(value)
        elif param == "gate_edge_symmetric_ps":
            edge_ns = float(value) / 1000.0
            cfg.gate_rise = edge_ns
            cfg.gate_fall = edge_ns
        elif param == "gate_edge_one_sharp_ps":
            edge_ns = float(value) / 1000.0
            if cfg.instr_sweep_gate_sharp_edge == "sharp_rise":
                cfg.gate_rise = 0.0
                cfg.gate_fall = edge_ns
            else:
                cfg.gate_rise = edge_ns
                cfg.gate_fall = 0.0
        elif param == "deadtime_fixed_countrate_ns":
            cfg.detector_deadtime = float(value)
            cfg.metadata["force_precision_deadtime_mc"] = True
            target_rate_hz = max(float(cfg.instr_sweep_fixed_countrate_kcps) * 1000.0, 1.0)
            cfg.event_pixel_dwell_time_s = float(cfg.precision_photons) / target_rate_hz
            cfg.metadata["countrate_kcps"] = float(cfg.instr_sweep_fixed_countrate_kcps)
            cfg.metadata["target_countrate_hz"] = target_rate_hz
        elif param == "countrate_via_dwell_hz":
            target_rate_hz = max(float(value), 1.0)
            cfg.precision_photons = 1000
            cfg.a_photons = 1000.0
            cfg.event_pixel_dwell_time_s = float(cfg.precision_photons) / target_rate_hz
            cfg.metadata["target_countrate_hz"] = target_rate_hz
        elif param == "countrate_fixed_deadtime_kcps":
            cfg.detector_deadtime = float(cfg.instr_sweep_fixed_deadtime_ns)
            cfg.metadata["force_precision_deadtime_mc"] = True
            target_rate_hz = max(float(value) * 1000.0, 1.0)
            cfg.event_pixel_dwell_time_s = float(cfg.precision_photons) / target_rate_hz
            cfg.metadata["countrate_kcps"] = float(value)
            cfg.metadata["target_countrate_hz"] = target_rate_hz
        elif param == "multihit_capabilities":
            cfg.metadata["force_precision_deadtime_mc"] = True
            capacity = max(int(round(value)), 1)
            cfg.event_multihit_capacity = capacity
            cfg.b_multihit_mode = capacity > 1
        elif param == "afterpulsing_probability_pct":
            cfg.detector_afterpulsing_probability = max(float(value), 0.0) / 100.0
        elif param == "dark_count_rate_cps":
            cfg.detector_dark_count_rate_cps = max(float(value), 0.0)
        elif param == "instrument_profile":
            loaded = self.profile_store.load_profile(str(value), sanitize=True)
            loaded_cfg = loaded["config"]
            preserved = {
                "f_x_param": cfg.f_x_param,
                "f_x_min": cfg.f_x_min,
                "f_x_max": cfg.f_x_max,
                "f_x_steps": cfg.f_x_steps,
                "f_x_scale": cfg.f_x_scale,
                "precision_photons": cfg.precision_photons,
                "precision_validate_mc": cfg.precision_validate_mc,
                "precision_mc_repeats": cfg.precision_mc_repeats,
                "precision_compute_ci": cfg.precision_compute_ci,
                "precision_accuracy_pvalue": cfg.precision_accuracy_pvalue,
                "precision_bootstrap_samples": cfg.precision_bootstrap_samples,
                "precision_ci_level": cfg.precision_ci_level,
                "instr_sweep_active": cfg.instr_sweep_active,
                "instr_sweep_param": cfg.instr_sweep_param,
                "instr_sweep_vals": list(cfg.instr_sweep_vals),
            }
            new_cfg = PhysicsConfig(**(loaded_cfg.model_dump() if hasattr(loaded_cfg, "model_dump") else loaded_cfg.dict()))
            for key, val in preserved.items():
                setattr(new_cfg, key, val)
            new_cfg.active_instrument_profile = str(value)
            cfg.__dict__.update(new_cfg.__dict__)
        elif param == "burst_edge_symmetric_ns":
            cfg.burst_enabled = True
            cfg.burst_sub_rise_time = float(value)
            cfg.burst_sub_fall_time = float(value)
        elif param == "burst_edge_one_sharp_ns":
            cfg.burst_enabled = True
            edge_ns = float(value)
            if cfg.instr_sweep_burst_sharp_edge == "sharp_rise":
                cfg.burst_sub_rise_time = 0.0
                cfg.burst_sub_fall_time = edge_ns
            else:
                cfg.burst_sub_rise_time = edge_ns
                cfg.burst_sub_fall_time = 0.0
        elif hasattr(cfg, param):
            setattr(cfg, param, value)
        else:
            raise ValueError(f"Unsupported sweep parameter: {param}")
        return cfg

    def run_precision_analysis(self):
        """Runs the theoretical precision evaluation and optional Monte Carlo validation."""
        if self.optimization_mode_active:
            self.run_optimization_workflow()
            return
        if not self._confirm_workspace_transition("precision"):
            return
        self.sync_ui_to_config()
        self._resolve_simulation_core_session_choice()
        self.apply_simulation_view()
        self.workspace_mode = "precision"
        baseline_cfg = copy.deepcopy(self.engine.config)
        cfg = baseline_cfg
        cfg.b_interrupt = False

        print(f"[PRECISION] instr_sweep_active={cfg.instr_sweep_active}")
        print(f"[PRECISION] instr_sweep_param={cfg.instr_sweep_param}")
        print(f"[PRECISION] instr_sweep_vals={cfg.instr_sweep_vals}")

        x_range = self._build_precision_x_range(cfg)

        target_label = self.control_widget.param_rows[cfg.f_x_param]['label'].text().replace(":", "")
        self.fisher_widget.set_xaxis_label(target_label)

        sweep_values = cfg.instr_sweep_vals if (cfg.instr_sweep_active and cfg.instr_sweep_vals) else [None]
        run_mc = cfg.precision_validate_mc

        total_steps = len(sweep_values) * len(x_range) * (1 + (1 if run_mc else 0))
        completed_steps = 0
        plot_update_interval = max(1, len(x_range) // 12)

        self.control_widget.btn_precision.setEnabled(False)
        self.control_widget.btn_interrupt.setEnabled(True)
        self.diagnostics_widget.chk_autoplay.setChecked(cfg.sweep_autoplay)
        self.diagnostics_widget.pause_playback()
        self.diagnostics_widget.clear_frames()
        self._set_progress(0, max(total_steps, 1), "Preparing precision analysis...")

        try:
            self.engine.config = copy.deepcopy(baseline_cfg)
            self.engine.grid_templates = None
            self.engine.grid_tau_axis = None
            _, f_ideal = self.engine.compute_ideal_reference(x_range, int(cfg.precision_photons))
            if str(getattr(cfg, "optimization_f_photon_basis", "collected")).lower() == "collected":
                f_ideal_conditional = np.array(f_ideal, copy=True)
            else:
                _, f_ideal_conditional = self.engine.compute_ideal_reference(
                    x_range,
                    int(cfg.precision_photons),
                    photon_basis_mode="collected",
                )
            baseline_reference_area, _ = self.engine._excitation_area_and_peak(baseline_cfg)

            plot_results = {}
            accuracy_results = {}
            run_series = []
            for raw_value in sweep_values:
                if self.engine.config.b_interrupt:
                    break

                sweep_cfg = copy.deepcopy(baseline_cfg)
                if raw_value is None:
                    label = "Current Configuration"
                else:
                    self._apply_sweep_value(sweep_cfg, cfg.instr_sweep_param, raw_value)
                    label = self._format_sweep_label(cfg.instr_sweep_param, raw_value, sweep_cfg)

                frame = self._create_diagnostics_frame(sweep_cfg, label)
                frame["background_curves"] = self._build_precision_pdf_ensemble(sweep_cfg, x_range)
                self.diagnostics_widget.append_frame(frame, focus=True)

                self.diagnostics_widget.update_plot(
                    frame["time_vec"],
                    frame["gate_shapes"],
                    irf=frame.get("irf"),
                    pdf=frame.get("pdf"),
                    label=frame.get("label"),
                    background_curves=frame["background_curves"]
                )
                
                self.diagnostics_widget.pause_playback()
                QApplication.processEvents()

                self.engine.config = sweep_cfg
                self.engine.grid_templates = None
                self.engine.grid_tau_axis = None

                theory_f = np.full(len(x_range), np.nan)
                theory_fi = np.full(len(x_range), np.nan)
                throughput_scale = self._precision_throughput_scale(sweep_cfg, baseline_reference_area)
                theory_label = "Theory" if raw_value is None else f"Theory | {label}"

                def theory_callback(point_idx, fisher_val, f_val):
                    nonlocal completed_steps
                    theory_fi[point_idx] = fisher_val
                    theory_f[point_idx] = f_val
                    plot_results[theory_label] = {
                        "y": np.array(theory_f, copy=True),
                        "conditional_f": np.array(theory_f, copy=True),
                        "photon_count": float(getattr(self._coerce_physics_config(sweep_cfg), "precision_photons", 0.0)),
                        "resolvability_enabled": self._resolvability_enabled(sweep_cfg),
                        "throughput_scale": throughput_scale,
                    }
                    completed_steps += 1
                    self._set_progress(completed_steps, max(total_steps, 1), f"Precision theory: {label} ({point_idx + 1}/{len(x_range)})")
                    is_last = point_idx == len(x_range) - 1
                    if is_last or ((point_idx + 1) % plot_update_interval == 0):
                        self.fisher_widget.plot_batch(
                            x_range,
                            plot_results,
                            ideal_x=x_range,
                            ideal_f=f_ideal,
                            ideal_conditional_f=f_ideal_conditional,
                            ideal_throughput_scale=1.0,
                            ideal_photon_count=float(getattr(self._coerce_physics_config(sweep_cfg), "precision_photons", 0.0)),
                            ci_level=float(getattr(self._coerce_physics_config(sweep_cfg), "precision_ci_level", 99.7)),
                        )
                        QApplication.processEvents()

                _, theory_final = self.engine.compute_fisher_info(
                    x_range,
                    int(sweep_cfg.precision_photons),
                    point_callback=theory_callback,
                    photon_basis_mode=getattr(sweep_cfg, "optimization_f_photon_basis", "period"),
                )
                theory_f = np.array(theory_final, copy=True)
                if str(getattr(sweep_cfg, "optimization_f_photon_basis", "collected")).lower() == "collected":
                    theory_f_conditional = np.array(theory_f, copy=True)
                else:
                    _, theory_conditional = self.engine.compute_fisher_info(
                        x_range,
                        int(sweep_cfg.precision_photons),
                        photon_basis_mode="collected",
                    )
                    theory_f_conditional = np.array(theory_conditional, copy=True)
                plot_results[theory_label] = {
                    "y": theory_f,
                    "conditional_f": np.array(theory_f_conditional, copy=True),
                    "photon_count": float(getattr(self._coerce_physics_config(sweep_cfg), "precision_photons", 0.0)),
                    "resolvability_enabled": self._resolvability_enabled(sweep_cfg),
                    "throughput_scale": throughput_scale,
                }
                self.fisher_widget.plot_batch(
                    x_range,
                    plot_results,
                    ideal_x=x_range,
                    ideal_f=f_ideal,
                    ideal_conditional_f=f_ideal_conditional,
                    ideal_throughput_scale=1.0,
                    ideal_photon_count=float(getattr(self._coerce_physics_config(sweep_cfg), "precision_photons", 0.0)),
                    ci_level=float(getattr(self._coerce_physics_config(sweep_cfg), "precision_ci_level", 99.7)),
                )

                mc_payload = None
                if run_mc and not self.engine.config.b_interrupt:
                    mc_f = np.full(len(x_range), np.nan)
                    mc_mean = np.full(len(x_range), np.nan)
                    mc_std = np.full(len(x_range), np.nan)
                    mc_compatible = np.full(len(x_range), True, dtype=bool)
                    mc_f_ci_lower = np.full(len(x_range), np.nan)
                    mc_f_ci_upper = np.full(len(x_range), np.nan)
                    mc_eff_ci_lower = np.full(len(x_range), np.nan)
                    mc_eff_ci_upper = np.full(len(x_range), np.nan)
                    mc_label = "Monte Carlo" if raw_value is None else f"Monte Carlo | {label}"

                    def mc_callback(point_idx, mean_tau, std_tau, f_val, p_eff, p_value, compatible,
                                    f_ci_low, f_ci_high, eff_ci_low, eff_ci_high):
                        nonlocal completed_steps
                        mc_mean[point_idx] = mean_tau
                        mc_std[point_idx] = std_tau
                        mc_f[point_idx] = f_val
                        mc_compatible[point_idx] = bool(compatible)
                        mc_f_ci_lower[point_idx] = f_ci_low
                        mc_f_ci_upper[point_idx] = f_ci_high
                        mc_eff_ci_lower[point_idx] = eff_ci_low
                        mc_eff_ci_upper[point_idx] = eff_ci_high
                        basis_is_collected = str(getattr(sweep_cfg, "optimization_f_photon_basis", "collected")).lower() == "collected"
                        plot_results[mc_label] = {
                            "y": np.array(mc_f, copy=True),
                            "conditional_f": np.array(mc_f, copy=True) if basis_is_collected else None,
                            "conditional_f_ci_lower": np.array(mc_f_ci_lower, copy=True) if basis_is_collected else None,
                            "conditional_f_ci_upper": np.array(mc_f_ci_upper, copy=True) if basis_is_collected else None,
                            "compatible": np.array(mc_compatible, copy=True),
                            "f_ci_lower": np.array(mc_f_ci_lower, copy=True),
                            "f_ci_upper": np.array(mc_f_ci_upper, copy=True),
                            "efficiency_ci_lower": np.array(mc_eff_ci_lower, copy=True),
                            "efficiency_ci_upper": np.array(mc_eff_ci_upper, copy=True),
                            "photon_count": float(getattr(self._coerce_physics_config(sweep_cfg), "precision_photons", 0.0)),
                            "resolvability_enabled": self._resolvability_enabled(sweep_cfg),
                            "throughput_scale": throughput_scale,
                        }
                        accuracy_results[label] = {
                            "mean": np.array(mc_mean, copy=True),
                            "std": np.array(mc_std, copy=True),
                        }
                        completed_steps += 1
                        self._set_progress(completed_steps, max(total_steps, 1), f"Monte Carlo validation: {label} ({point_idx + 1}/{len(x_range)})")
                        is_last = point_idx == len(x_range) - 1
                        if is_last or ((point_idx + 1) % plot_update_interval == 0):
                            self.fisher_widget.plot_batch(
                                x_range,
                                plot_results,
                                ideal_x=x_range,
                                ideal_f=f_ideal,
                                ideal_conditional_f=f_ideal_conditional,
                                ideal_throughput_scale=1.0,
                                ideal_photon_count=float(getattr(self._coerce_physics_config(sweep_cfg), "precision_photons", 0.0)),
                                ci_level=float(getattr(self._coerce_physics_config(sweep_cfg), "precision_ci_level", 99.7)),
                            )
                            self.mle_accuracy_widget.plot_accuracy(x_range, accuracy_results)
                            QApplication.processEvents()

                    mc_payload = self.engine.monte_carlo_precision_curve(
                        x_range,
                        int(sweep_cfg.precision_photons),
                        int(sweep_cfg.precision_mc_repeats),
                        point_callback=mc_callback,
                    )
                    plot_results[mc_label] = {
                        "y": np.array(mc_payload["f_value"], copy=True),
                        "conditional_f": np.array(mc_payload.get("f_value_conditional", mc_payload["f_value"]), copy=True),
                        "conditional_f_ci_lower": np.array(mc_payload.get("f_ci_lower_conditional", np.full(len(x_range), np.nan)), copy=True),
                        "conditional_f_ci_upper": np.array(mc_payload.get("f_ci_upper_conditional", np.full(len(x_range), np.nan)), copy=True),
                        "photon_count": float(getattr(self._coerce_physics_config(sweep_cfg), "precision_photons", 0.0)),
                        "resolvability_enabled": self._resolvability_enabled(sweep_cfg),
                        "compatible": np.array(mc_payload["compatible"], copy=True),
                        "f_ci_lower": np.array(mc_payload["f_ci_lower"], copy=True),
                        "f_ci_upper": np.array(mc_payload["f_ci_upper"], copy=True),
                        "efficiency_ci_lower": np.array(mc_payload["efficiency_ci_lower"], copy=True),
                        "efficiency_ci_upper": np.array(mc_payload["efficiency_ci_upper"], copy=True),
                        "throughput_scale": throughput_scale,
                    }
                    accuracy_results[label] = {
                        "mean": np.array(mc_payload["mean_tau"], copy=True),
                        "std": np.array(mc_payload["std_tau"], copy=True),
                    }
                    self.fisher_widget.plot_batch(
                        x_range,
                        plot_results,
                        ideal_x=x_range,
                        ideal_f=f_ideal,
                        ideal_conditional_f=f_ideal_conditional,
                        ideal_throughput_scale=1.0,
                        ideal_photon_count=float(getattr(self._coerce_physics_config(sweep_cfg), "precision_photons", 0.0)),
                        ci_level=float(getattr(self._coerce_physics_config(sweep_cfg), "precision_ci_level", 99.7)),
                    )
                    self.mle_accuracy_widget.plot_accuracy(x_range, accuracy_results)

                run_series.append({
                    "label": label,
                    "theory_fisher": np.array(theory_fi, copy=True),
                    "theory_f": np.array(theory_f, copy=True),
                    "theory_f_conditional": np.array(theory_f_conditional, copy=True),
                    "throughput_scale": throughput_scale,
                    "mc": mc_payload,
                    "diagnostics_frame": frame,
                    "config": copy.deepcopy(sweep_cfg),
                })

            self.last_precision_run = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "x_range": np.array(x_range, copy=True),
                "ideal_f": np.array(f_ideal, copy=True),
                "ideal_f_conditional": np.array(f_ideal_conditional, copy=True),
                "series": run_series,
                "x_label": target_label,
                "config": copy.deepcopy(baseline_cfg),
            }
            self._set_export_enabled()
            self.statusBar().showMessage("Precision analysis complete.")
        finally:
            self.engine.config = baseline_cfg
            self.control_widget.btn_precision.setEnabled(True)
            self.control_widget.btn_interrupt.setEnabled(False)
            self.progress.hide()
            if self.diagnostics_widget.chk_autoplay.isChecked():
                self.diagnostics_widget.resume_playback()

    def run_image_gen(self):
        """Generate the synthetic validation image."""
        if not self._confirm_workspace_transition("validation"):
            return
        self.engine.config.b_interrupt = False
        self.control_widget.btn_simulate.setEnabled(False)
        self.control_widget.btn_interrupt.setEnabled(True)
        self.sync_ui_to_config()
        self._resolve_simulation_core_session_choice()
        self.apply_testing_view()
        self.workspace_mode = "validation"
        self.statusBar().showMessage("Generating synthetic validation image...")
        self.progress.show()
        self.progress.setValue(0)
        try:
            payload = self.engine.generate_validation_image(
                n_photons=int(self.engine.config.a_photons),
                target_repeats=int(self.engine.config.image_mc_repeats),
                progress_callback=lambda done, total: self.progress.setValue(int((done / max(total, 1)) * 45)),
            )
            self.last_validation_run = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "geometry": copy.deepcopy(payload["geometry"]),
                "fit_method": self.engine.config.image_fit_method,
                "x_values": np.asarray(payload["x_values"], dtype=float).tolist(),
            }
            self._refresh_validation_views()
            QApplication.processEvents()
            self.progress.setValue(50)
            self.fit_validation_image(update_buttons=False)
            self.statusBar().showMessage("Validation image generated and fitted.")
            self._set_export_enabled()
        finally:
            self.control_widget.btn_simulate.setEnabled(True)
            self.control_widget.btn_interrupt.setEnabled(False)
            self.progress.hide()
            QApplication.restoreOverrideCursor()

    def fit_validation_image(self, update_buttons=True):
        if self.engine.raw_data is None:
            self.statusBar().showMessage("Generate a validation image before fitting.")
            return
        self.sync_ui_to_config()
        self._resolve_simulation_core_session_choice()
        self.statusBar().showMessage("Fitting validation image...")
        if update_buttons:
            self.progress.show()
            self.progress.setValue(0)
        QApplication.processEvents()
        try:
            self.engine.run_fit(
                method=self.engine.config.image_fit_method,
                progress_callback=lambda done, total: self.progress.setValue(50 + int((done / max(total, 1)) * 50)) if not update_buttons else self.progress.setValue(int((done / max(total, 1)) * 100)),
            )
            self._refresh_validation_views()
            if self.last_validation_run is None:
                self.last_validation_run = {"timestamp": datetime.utcnow().isoformat() + "Z"}
            self.last_validation_run["fit_method"] = self.engine.config.image_fit_method
            self.last_validation_run["analysis_warnings"] = list(getattr(self.engine, "last_analysis_warnings", []))
            warnings = list(getattr(self.engine, "last_analysis_warnings", []))
            self.statusBar().showMessage("Validation image fitted." if not warnings else warnings[0])
            self._set_export_enabled()
        finally:
            if update_buttons:
                self.progress.hide()

    def _refresh_validation_views(self):
        intensity = None if self.engine.raw_data is None else np.sum(self.engine.raw_data, axis=2)
        lifetime = self.engine.tau_map if self.engine.tau_map is not None else self.engine.validation_param_map
        self.validation_fit_summary = self.engine.summarize_validation_performance(lifetime, photon_map=intensity)
        self.map_widget.set_images(intensity, lifetime)
        g_map, s_map = self.engine.calculate_phasor()
        if g_map is not None and s_map is not None:
            self.phasor_widget.update_data(
                g_map,
                s_map,
                performance_summary=self.validation_fit_summary,
                universal_locus=self.engine.get_theoretical_locus(),
                actual_locus=self.engine.get_discrete_single_exponential_arc(),
            )
        self.on_pixel_select(0, 0)


    def on_pixel_select(self, y, x):
        if self.engine.raw_data is None:
            return
        payload = self.engine.get_pixel_fit_payload(y, x, fit_method=self.engine.config.image_fit_method)
        if payload.get("status") != "ok":
            return
        self.decay_widget.update_decay(
            payload["centers"],
            payload["counts"],
            fit=payload.get("fit_values"),
            fit_x=payload.get("fit_centers"),
            residuals=payload.get("residuals"),
            irf=payload.get("irf_values"),
            irf_x=payload.get("irf_time"),
            reduced_chi2=payload.get("reduced_chi2"),
            randomness=payload.get("randomness"),
            performance_summary=self.validation_fit_summary,
            selected_value=payload.get("estimate"),
            truth_value=payload.get("truth"),
        )
        g_map, s_map = self.engine.calculate_phasor()
        if g_map is not None and s_map is not None:
            selected_phasor = None
            try:
                selected_phasor = (float(g_map[y, x]), float(s_map[y, x]))
            except Exception:
                selected_phasor = None
            self.phasor_widget.update_data(
                g_map,
                s_map,
                performance_summary=self.validation_fit_summary,
                selected_value=payload.get("estimate"),
                truth_value=payload.get("truth"),
                selected_phasor=selected_phasor,
                universal_locus=self.engine.get_theoretical_locus(),
                actual_locus=self.engine.get_discrete_single_exponential_arc(),
            )

    def on_phasor_roi(self, gmin, gmax, smin, smax):
        return

    def export_last_precision_report(self):
        self.preview_last_precision_report()

    def preview_last_precision_report(self):
        if self.workspace_mode == "validation" and self.last_validation_run:
            self.save_workspace()
            return
        if not self.last_precision_run and not self.last_optimization_run:
            self.statusBar().showMessage("No reportable precision or optimisation run is available to export.")
            return

        html = self._build_precision_report_html()
        dlg = QDialog(self)
        dlg.setWindowTitle("Report Preview")
        dlg.resize(1200, 850)
        dlg_layout = QVBoxLayout(dlg)

        from PyQt6.QtWebEngineWidgets import QWebEngineView
        browser = QWebEngineView(dlg)
        browser.setHtml(html)
        dlg_layout.addWidget(browser)

        button_row = QHBoxLayout()
        button_row.addStretch()
        open_after_save_chk = QCheckBox("Open saved report", dlg)
        open_after_save_chk.setChecked(True)
        save_btn = QPushButton("Save As...", dlg)
        close_btn = QPushButton("Close", dlg)
        button_row.addWidget(open_after_save_chk)
        button_row.addWidget(save_btn)
        button_row.addWidget(close_btn)
        dlg_layout.addLayout(button_row)

        def save_report():
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Report As",
                "hilighter_report.html",
                "HTML Files (*.html)",
            )
            if not file_path:
                return
            html_path, asset_dir = self._save_precision_report_package(file_path)
            self.optimization_results_saved = bool(self.last_optimization_run)
            self.statusBar().showMessage(f"Report saved to {html_path} with assets in {asset_dir}")
            if open_after_save_chk.isChecked():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(html_path)))

        save_btn.clicked.connect(save_report)
        close_btn.clicked.connect(dlg.accept)
        dlg.exec()

    def _serialise_snapshot_series(self, label, theory_f, mc_payload=None, cfg_like=None, reference_excitation_area=1.0):
        theory_arr = np.asarray(theory_f, dtype=float)
        theory_eff = np.minimum(1.0, 1.0 / (np.maximum(theory_arr, 1e-12) ** 2))
        throughput_scale = self._precision_throughput_scale(cfg_like, reference_excitation_area) if cfg_like is not None else 1.0
        entry = {
            "label": label,
            "theory_f": theory_arr.tolist(),
            "theory_eff": theory_eff.tolist(),
            "theory_throughput": (theory_eff * throughput_scale).tolist(),
            "throughput_scale": float(throughput_scale),
        }
        if mc_payload is not None:
            mc_f = np.asarray(mc_payload["f_value"], dtype=float)
            mc_eff = np.asarray(mc_payload["efficiency"], dtype=float)
            entry["mc_f"] = mc_f.tolist()
            entry["mc_eff"] = mc_eff.tolist()
            entry["mc_throughput"] = (mc_eff * throughput_scale).tolist()
            entry["mc_mean"] = np.asarray(mc_payload["mean_tau"], dtype=float).tolist()
            entry["mc_std"] = np.asarray(mc_payload["std_tau"], dtype=float).tolist()
            mc_f_ci_lower = np.asarray(mc_payload["f_ci_lower"], dtype=float)
            mc_f_ci_upper = np.asarray(mc_payload["f_ci_upper"], dtype=float)
            mc_eff_ci_lower = np.asarray(mc_payload["efficiency_ci_lower"], dtype=float)
            mc_eff_ci_upper = np.asarray(mc_payload["efficiency_ci_upper"], dtype=float)
            entry["mc_f_ci_lower"] = mc_f_ci_lower.tolist()
            entry["mc_f_ci_upper"] = mc_f_ci_upper.tolist()
            entry["mc_eff_ci_lower"] = mc_eff_ci_lower.tolist()
            entry["mc_eff_ci_upper"] = mc_eff_ci_upper.tolist()
            entry["mc_throughput_ci_lower"] = (mc_eff_ci_lower * throughput_scale).tolist()
            entry["mc_throughput_ci_upper"] = (mc_eff_ci_upper * throughput_scale).tolist()
        return entry

    def _serialise_frame(self, frame):
        return {
            "label": frame.get("label", "Instrument snapshot"),
            "time": np.array(frame["time_vec"], copy=True).tolist(),
            "gates": np.array(frame["gate_shapes"], copy=True).tolist(),
            "irf": np.array(frame.get("irf"), copy=True).tolist() if frame.get("irf") is not None else [],
            "pdf": np.array(frame.get("pdf"), copy=True).tolist() if frame.get("pdf") is not None else [],
        }

    def _build_precision_report_payload(self):
        primary_optimisation = bool(self.last_optimization_run) and (
            self.optimization_mode_active
            or not self.last_precision_run
            or self.last_optimization_run.get("timestamp", "") >= self.last_precision_run.get("timestamp", "")
        )
        report = self.last_optimization_run if primary_optimisation else self.last_precision_run
        if report is None:
            raise RuntimeError("No reportable run is available.")

        if primary_optimisation:
            config_dump = copy.deepcopy(report["config"])
            reference_excitation_area = self.engine._excitation_area_and_peak(self._coerce_physics_config(config_dump))[0]
            x_range = np.asarray(report["x_range"], dtype=float).tolist()
            ideal_f = np.asarray(report["ideal_f"], dtype=float).tolist()
            series_payload = []
            frame_payload = []
            accuracy_payload = []
            for snapshot in report["snapshots"]:
                series_payload.append(
                    self._serialise_snapshot_series(
                        snapshot["label"],
                        self._display_theory_curve(snapshot, np.asarray(report["x_range"], dtype=float)),
                        self._display_mc_payload(snapshot.get("mc"), snapshot.get("config")),
                        cfg_like=snapshot.get("config"),
                        reference_excitation_area=reference_excitation_area,
                    )
                )
                frame_payload.append(self._serialise_frame(snapshot["diagnostics_frame"]))
                accuracy_payload.append({
                    "label": snapshot["label"],
                    "mean": np.asarray(snapshot["accuracy"]["mean"], dtype=float).tolist(),
                    "std": np.asarray(snapshot["accuracy"]["std"], dtype=float).tolist(),
                })
            timestamp = report["timestamp"]
            x_label = report["x_label"]
        else:
            config_dump = report["config"].model_dump() if hasattr(report["config"], "model_dump") else {}
            reference_excitation_area = self.engine._excitation_area_and_peak(self._coerce_physics_config(config_dump))[0]
            x_range = np.asarray(report["x_range"], dtype=float).tolist()
            ideal_f = np.asarray(report["ideal_f"], dtype=float).tolist()
            series_payload = []
            frame_payload = []
            for item in report["series"]:
                series_payload.append(
                    self._serialise_snapshot_series(
                        item["label"],
                        self._display_theory_curve(item, np.asarray(report["x_range"], dtype=float)),
                        self._display_mc_payload(item.get("mc"), item.get("config")),
                        cfg_like=item.get("config"),
                        reference_excitation_area=reference_excitation_area,
                    )
                )
                frame_payload.append(self._serialise_frame(item["diagnostics_frame"]))
            accuracy_payload = []
            for label, values in self.mle_accuracy_widget.series_data.items():
                accuracy_payload.append({
                    "label": label,
                    "mean": np.array(values["mean"], copy=True).tolist(),
                    "std": np.array(values["std"], copy=True).tolist(),
                })
            timestamp = report["timestamp"]
            x_label = report["x_label"]

        combo_index = self.fisher_widget.combo_mode.currentIndex()
        metric_options = {
            0: ("F-Value (F)", "f"),
            1: ("Photon Efficiency (F^-2)", "efficiency"),
            2: ("Fisher Throughput", "throughput"),
        }
        metric_label, metric_key = metric_options.get(combo_index, metric_options[0])
        ci_level = float(config_dump.get("precision_ci_level", 99.7))
        ideal_eff = np.minimum(1.0, 1.0 / (np.maximum(np.asarray(ideal_f, dtype=float), 1e-12) ** 2))
        payload = {
            "timestamp": timestamp,
            "x_label": x_label,
            "x_range": x_range,
            "ideal_f": ideal_f,
            "ideal_eff": ideal_eff.tolist(),
            "ideal_throughput": ideal_eff.tolist(),
            "series": series_payload,
            "frames": frame_payload,
            "config": config_dump,
            "precision_display": {
                "log_x": self.fisher_widget.chk_log_x.isChecked(),
                "log_y": self.fisher_widget.chk_log_y.isChecked(),
                "metric": metric_key,
                "metric_label": metric_label,
                "ci_level": ci_level,
                "ci_label": FisherWidget.format_ci_level(ci_level),
            },
            "accuracy": {
                "stacked": self.mle_accuracy_widget.chk_stacked.isChecked(),
                "series": accuracy_payload,
            },
        }
        if self.last_optimization_run is not None:
            optimisation_cfg = self.last_optimization_run["config"]
            payload["optimization"] = {
                "active_export": primary_optimisation,
                "options": {
                    "optimize_detection_gates": bool(optimisation_cfg.get("optimize_detection_gates", False)),
                    "optimize_excitation_profile": bool(optimisation_cfg.get("optimize_excitation_profile", False)),
                    "optimization_mode": "sequential",
                    "optimization_first": str(optimisation_cfg.get("optimization_first", "detection")),
                    "optimization_iterations": int(optimisation_cfg.get("optimization_iterations", 20)),
                    "optimization_objective": str(optimisation_cfg.get("optimization_objective", "fisher_throughput")),
                    "optimization_max_fi_loss_pct": float(optimisation_cfg.get("optimization_max_fi_loss_pct", 5.0)),
                    "optimization_realtime_visualization": bool(optimisation_cfg.get("optimization_realtime_visualization", False)),
                    "optimization_realtime_interval_s": float(optimisation_cfg.get("optimization_realtime_interval_s", 5.0)),
                    "optimization_intermediate_steps": int(optimisation_cfg.get("optimization_intermediate_steps", 6)),
                    "optimization_validate_mc_intermediates": bool(optimisation_cfg.get("optimization_validate_mc_intermediates", False)),
                    "detection_optimization_algorithm": str(optimisation_cfg.get("detection_optimization_algorithm", "fisher_compression")),
                    "detection_opt_restarts": int(optimisation_cfg.get("detection_opt_restarts", 20)),
                    "detection_opt_ftol": float(optimisation_cfg.get("detection_opt_ftol", 1e-4)),
                    "detection_opt_maxiter": int(optimisation_cfg.get("detection_opt_maxiter", 50)),
                    "detection_opt_fine_bins_per_gate": int(optimisation_cfg.get("detection_opt_fine_bins_per_gate", 12)),
                    "detection_opt_fine_bin_cap": int(optimisation_cfg.get("detection_opt_fine_bin_cap", 256)),
                    "detection_opt_fc_nuisance_aware": bool(optimisation_cfg.get("detection_opt_fc_nuisance_aware", True)),
                    "detection_opt_fc_auto_compress": bool(optimisation_cfg.get("detection_opt_fc_auto_compress", False)),
                    "detection_opt_fc_initial_gates": int(optimisation_cfg.get("detection_opt_fc_initial_gates", 16)),
                    "detection_opt_fc_min_gates": int(optimisation_cfg.get("detection_opt_fc_min_gates", 2)),
                    "detection_opt_fc_max_f_loss_pct": float(optimisation_cfg.get("detection_opt_fc_max_f_loss_pct", 5.0)),
                    "detection_opt_start_anchor": str(optimisation_cfg.get("detection_opt_start_anchor", "zero")),
                    "detection_opt_start_time": float(optimisation_cfg.get("detection_opt_start_time", 0.0)),
                    "detection_opt_end_anchor": str(optimisation_cfg.get("detection_opt_end_anchor", "period")),
                    "detection_opt_end_time": float(optimisation_cfg.get("detection_opt_end_time", optimisation_cfg.get("period", 12.5))),
                    "excitation_optimization_profile": str(optimisation_cfg.get("excitation_optimization_profile", "gaussian")),
                    "excitation_optimization_constraint": str(optimisation_cfg.get("excitation_optimization_constraint", "fixed_dose")),
                },
                "objective_history": np.asarray(self.last_optimization_run["objective_history"], dtype=float).tolist(),
                "min_f_history": np.asarray(self.last_optimization_run["min_f_history"], dtype=float).tolist(),
                "min_eff_history": np.asarray(self.last_optimization_run.get("min_eff_history", []), dtype=float).tolist(),
                "auc_eff_history": np.asarray(self.last_optimization_run.get("auc_eff_history", []), dtype=float).tolist(),
                "throughput_history": np.asarray(self.last_optimization_run.get("throughput_history", []), dtype=float).tolist(),
                "throughput_auc_history": np.asarray(self.last_optimization_run.get("throughput_auc_history", []), dtype=float).tolist(),
                "gate_count_history": np.asarray(self.last_optimization_run.get("gate_count_history", []), dtype=float).tolist(),
                "final_gate_count": int(self.last_optimization_run.get("final_gate_count", max(0, len(self.last_optimization_run.get("final_config", {}).get("gate_edges", [])) - 1))),
                "snapshots": [
                    {
                        "label": snapshot["label"],
                        "objective": float(snapshot["objective"]),
                        "min_f": float(snapshot["min_f"]),
                        "gate_count": int(snapshot.get("gate_count", max(0, len(snapshot.get("config", {}).get("gate_edges", [])) - 1))),
                        "config": copy.deepcopy(snapshot["config"]),
                    }
                    for snapshot in self.last_optimization_run["snapshots"]
                ],
                "final_config": copy.deepcopy(self.last_optimization_run["final_config"]),
                "final_excitation_summary": copy.deepcopy(self.last_optimization_run.get("final_excitation_summary", {})),
            }
        return payload

    def _save_precision_report_package(self, file_path):
        payload = self._build_precision_report_payload()
        html_path, asset_dir = write_precision_report_package(file_path, payload)
        if self.last_optimization_run is not None:
            self.optimization_results_saved = True
        return html_path, asset_dir

    def _build_precision_report_html(self):
        payload = self._build_precision_report_payload()
        x_range = payload["x_range"]
        ideal_f = payload["ideal_f"]
        config_dump = payload["config"]

        payload_json = json.dumps(payload)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HILIGHTer Precision and Optimisation Report</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      --bg: #07111f;
      --bg2: #0b1728;
      --panel: #10233d;
      --text: #e5eefb;
      --muted: #9fb3ca;
      --accent: #38bdf8;
      --line: #1f3a5a;
      --btn-bg: #173559;
      --btn-line: #29507d;
    }}
    body[data-theme="light"] {{
      --bg: #f5f7fb;
      --bg2: #eef4fb;
      --panel: #ffffff;
      --text: #0f172a;
      --muted: #475569;
      --accent: #2563eb;
      --line: #d7dee8;
      --btn-bg: #ffffff;
      --btn-line: #cbd5e1;
    }}
    body {{ margin: 0; font-family: "Segoe UI", sans-serif; background: linear-gradient(180deg, var(--bg) 0%, var(--bg2) 100%); color: var(--text); }}
    main {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 18px; margin-bottom: 18px; }}
    .grid {{ display: grid; grid-template-columns: 2fr 1fr; gap: 18px; }}
    .controls {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }}
    .topbar {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }}
    button, select {{ background: var(--btn-bg); color: var(--text); border: 1px solid var(--btn-line); border-radius: 8px; padding: 8px 12px; }}
    input[type="checkbox"] {{ transform: scale(1.1); }}
    pre {{ white-space: pre-wrap; color: var(--muted); }}
    #diagPlot {{ height: 420px; }}
    #precisionPlot, #mcPlot {{ height: 460px; }}
  </style>
</head>
<body>
  <main>
    <div class="panel">
      <div class="topbar">
        <div>
          <h1>HILIGHTer Precision and Optimisation Report</h1>
          <div>Generated: {payload["timestamp"]}</div>
          <div>X-Axis: {payload["x_label"]}</div>
        </div>
        <button id="themeToggle" type="button">Switch to Light Theme</button>
      </div>
    </div>
    <div class="grid">
        <div>
        <div class="panel">
          <div class="controls">
            <label for="metricSelect">Metric</label>
            <select id="metricSelect">
              <option value="f">F-Value (F)</option>
              <option value="efficiency">Photon Efficiency (F^-2)</option>
              <option value="throughput">Fisher Throughput</option>
            </select>
          </div>
          <div id="precisionPlot"></div>
        </div>
        <div class="panel">
          <div id="mcPlot"></div>
        </div>
      </div>
      <div>
        <div class="panel">
          <h2>Configuration</h2>
          <pre id="configBlock"></pre>
        </div>
        <div class="panel">
          <div class="controls">
            <button id="prevFrame">Prev</button>
            <button id="nextFrame">Next</button>
            <label><input type="checkbox" id="autoplay" checked> Auto-play</label>
          </div>
          <div id="frameLabel"></div>
          <div id="diagPlot"></div>
        </div>
      </div>
    </div>
  </main>
  <script>
    const report = {payload_json};
    document.getElementById("configBlock").textContent = JSON.stringify(report.config, null, 2);
    let frameIndex = 0;
    let timer = null;
    let currentTheme = "dark";
    const themeConfig = {{
      dark: {{ paperBg: "#10233d", plotBg: "#10233d", font: "#e5eefb", grid: "#1f3a5a" }},
      light: {{ paperBg: "#ffffff", plotBg: "#ffffff", font: "#0f172a", grid: "#d7dee8" }},
    }};

    function hexToRgba(hex, alpha) {{
      const normalized = hex.replace("#", "");
      const value = normalized.length === 3
        ? normalized.split("").map((ch) => ch + ch).join("")
        : normalized;
      const r = parseInt(value.slice(0, 2), 16);
      const g = parseInt(value.slice(2, 4), 16);
      const b = parseInt(value.slice(4, 6), 16);
      return `rgba(${{r}}, ${{g}}, ${{b}}, ${{alpha}})`;
    }}

    function precisionTraces(metricKey) {{
      const theoryKey = metricKey === "throughput" ? "theory_throughput" : (metricKey === "efficiency" ? "theory_eff" : "theory_f");
      const idealKey = metricKey === "throughput" ? "ideal_throughput" : (metricKey === "efficiency" ? "ideal_eff" : "ideal_f");
      const ciLegend = report.precision_display.ci_label ? "Monte Carlo " + report.precision_display.ci_label + " CI" : "Monte Carlo CI";
      const palette = ["#8b5cf6", "#3b82f6", "#ec4899", "#f59e0b", "#ef4444", "#06b6d4", "#84cc16"];
      const traces = [{{
        x: report.x_range,
        y: report[idealKey],
        mode: "lines",
        name: "Ideal Reference",
        line: {{ dash: "dash", width: 2, color: "#34d399" }}
      }}];
      report.series.forEach((series, idx) => {{
        const color = palette[idx % palette.length];
        traces.push({{
          x: report.x_range,
          y: series[theoryKey],
          mode: "lines",
          name: `Theory | ${{series.label}}`,
          line: {{ width: 2, color }}
        }});
        if (series.mc_f) {{
          const mcKey = metricKey === "throughput" ? "mc_throughput" : (metricKey === "efficiency" ? "mc_eff" : "mc_f");
          const ciLowerKey = metricKey === "throughput" ? "mc_throughput_ci_lower" : (metricKey === "efficiency" ? "mc_eff_ci_lower" : "mc_f_ci_lower");
          const ciUpperKey = metricKey === "throughput" ? "mc_throughput_ci_upper" : (metricKey === "efficiency" ? "mc_eff_ci_upper" : "mc_f_ci_upper");
          const ciLower = series[ciLowerKey];
          const ciUpper = series[ciUpperKey];
          const hasCi = Array.isArray(ciLower) && Array.isArray(ciUpper)
            && ciLower.some((v) => Number.isFinite(v))
            && ciUpper.some((v) => Number.isFinite(v));
          if (hasCi) {{
            traces.push({{
              x: report.x_range,
              y: ciLower,
              mode: "lines",
              line: {{ width: 0, color }},
              hoverinfo: "skip",
              showlegend: false
            }});
            traces.push({{
              x: report.x_range,
              y: ciUpper,
              mode: "lines",
              line: {{ width: 0, color }},
              fill: "tonexty",
              fillcolor: hexToRgba(color, 0.18),
              name: `${{ciLegend}} | ${{series.label}}`
            }});
            traces.push({{
              x: report.x_range,
              y: series[mcKey],
              mode: "markers",
              name: `Monte Carlo | ${{series.label}}`,
              marker: {{ size: 8, color, symbol: "circle" }}
            }});
          }} else {{
            traces.push({{
              x: report.x_range,
              y: series[mcKey],
              mode: "markers",
              name: `Monte Carlo | ${{series.label}}`,
              marker: {{ size: 8, color, symbol: "circle" }}
            }});
          }}
        }}
      }});
      return traces;
    }}

    function renderPrecision() {{
      const metricKey = document.getElementById("metricSelect").value;
      const theme = themeConfig[currentTheme];
      const yTitle = metricKey === "throughput"
        ? "Fisher Throughput"
        : (metricKey === "efficiency" ? "Photon Efficiency (F^-2)" : "F-Value");
      Plotly.newPlot("precisionPlot", precisionTraces(metricKey), {{
        paper_bgcolor: theme.paperBg,
        plot_bgcolor: theme.plotBg,
        font: {{ color: theme.font }},
        xaxis: {{ title: report.x_label, type: report.precision_display.log_x ? "log" : "linear", gridcolor: theme.grid }},
        yaxis: {{ title: yTitle, type: report.precision_display.log_y ? "log" : "linear", gridcolor: theme.grid }},
        legend: {{ orientation: "h" }},
        margin: {{ t: 30, r: 20, b: 60, l: 70 }}
      }}, {{ responsive: true }});
    }}

    function renderMonteCarloSummary() {{
      const theme = themeConfig[currentTheme];
      const traces = [];
      report.series.forEach((series) => {{
        if (series.mc_mean) {{
          traces.push({{
            x: report.x_range,
            y: series.mc_mean,
            error_y: {{ type: "data", array: series.mc_std, visible: true }},
            mode: "lines+markers",
            name: series.label
          }});
        }}
      }});
      Plotly.newPlot("mcPlot", traces, {{
        paper_bgcolor: theme.paperBg,
        plot_bgcolor: theme.plotBg,
        font: {{ color: theme.font }},
        xaxis: {{ title: report.x_label, type: report.precision_display.log_x ? "log" : "linear", gridcolor: theme.grid }},
        yaxis: {{ title: "Monte Carlo mean τ ± std", gridcolor: theme.grid }},
        margin: {{ t: 30, r: 20, b: 60, l: 70 }}
      }}, {{ responsive: true }});
    }}

    function renderFrame() {{
      if (!report.frames.length) return;
      const theme = themeConfig[currentTheme];
      const frame = report.frames[frameIndex];
      document.getElementById("frameLabel").textContent = frame.label;
      const traces = frame.gates.map((gate, idx) => ({{
        x: frame.time,
        y: gate,
        mode: "lines",
        name: `Gate ${{idx + 1}}`
      }}));
      traces.push({{ x: frame.time, y: frame.irf, mode: "lines", name: "IRF", line: {{ color: "#22d3ee", width: 3 }} }});
      traces.push({{ x: frame.time, y: frame.pdf, mode: "lines", name: "PDF", line: {{ color: currentTheme === "dark" ? "#ffffff" : "#111827", width: 3, dash: "dash" }} }});
      Plotly.newPlot("diagPlot", traces, {{
        paper_bgcolor: theme.paperBg,
        plot_bgcolor: theme.plotBg,
        font: {{ color: theme.font }},
        xaxis: {{ title: "Time (ns)", gridcolor: theme.grid }},
        yaxis: {{ title: "Relative amplitude", gridcolor: theme.grid }},
        margin: {{ t: 30, r: 20, b: 60, l: 70 }}
      }}, {{ responsive: true }});
    }}

    function applyTheme(themeName) {{
      currentTheme = themeName;
      document.body.dataset.theme = themeName;
      document.getElementById("themeToggle").textContent = themeName === "dark"
        ? "Switch to Light Theme"
        : "Switch to Dark Theme";
      renderPrecision();
      renderMonteCarloSummary();
      renderFrame();
    }}

    function stepFrame(step) {{
      if (!report.frames.length) return;
      frameIndex = (frameIndex + step + report.frames.length) % report.frames.length;
      renderFrame();
    }}

    function updateAutoplay() {{
      if (timer) clearInterval(timer);
      if (document.getElementById("autoplay").checked && report.frames.length > 1) {{
        timer = setInterval(() => stepFrame(1), 1000);
      }}
    }}

    document.getElementById("metricSelect").value = report.precision_display.metric || "f";
    document.getElementById("metricSelect").addEventListener("change", renderPrecision);
    document.getElementById("themeToggle").addEventListener("click", () => {{
      applyTheme(currentTheme === "dark" ? "light" : "dark");
    }});
    document.getElementById("prevFrame").addEventListener("click", () => stepFrame(-1));
    document.getElementById("nextFrame").addEventListener("click", () => stepFrame(1));
    document.getElementById("autoplay").addEventListener("change", updateAutoplay);

    applyTheme("dark");
    updateAutoplay();
  </script>
</body>
</html>"""

    def show_about(self):
        from PyQt6.QtWidgets import QMessageBox
        about_text = """
        <h2 style='color: #22d3ee;'>HILIGHTer Digital Twin | Desktop Workspace</h2>
        <p>A full-spectrum modeling environment for high-speed time-gated imaging.</p>
        <hr>
        <p><b>Version:</b> v{get_full_version_label()}<br>
        <b>Build:</b> {get_build_label()}</p>
        
        <hr>
        <p><b>Project funded by EU HORIZON and UKRI</b><br>
        <a href='https://hilighthorizon.eu/'>https://hilighthorizon.eu/</a></p>
        
        <p><b>Created by:</b><br>
        Dr Alessandro Esposito (Brunel University London)</p>

        <p><b>Contributors:</b><br>
        Alessandro Esposito (@ae275)<br>
        Conor Treacy (@c-treacy)</p>

        <hr>
        <b>Powered by:</b>
        <ul>
            <li><b>HILIGHTer backend</b>: Internal phasor analysis and lifetime-fitting backend used for validation-image analysis paths.</li>
            <li><b>PyQt6 & PyQtGraph</b>: High-performance UI and plotting.</li>
            <li><b>NumPy, SciPy & Numba</b>: Numerical processing kernels.</li>
            <li><b>QDarkStyle</b>: Sleek, research-ready aesthetics.</li>
        </ul>
        <p><i>The validation-analysis workflow is implemented directly within the HILIGHTer backend.</i></p>
        """
        QMessageBox.about(self, "About HILIGHTer", about_text)

    def show_manual(self, section_id: str | None = None):
        """Displays the interactive manual as a floating window."""
        self.manual_widget.show()
        self.manual_widget.raise_()
        self.manual_widget.activateWindow()
        if section_id:
            self.manual_widget.scroll_to_section(section_id)
        if section_id == "tutorial":
            self.statusBar().showMessage("Displaying Interactive Tutorial (Ctrl+T).")
        else:
            self.statusBar().showMessage("Displaying Interactive Manual (Ctrl+H).")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HILIGHTMainWindow()
    window.show()
    sys.exit(app.exec())
