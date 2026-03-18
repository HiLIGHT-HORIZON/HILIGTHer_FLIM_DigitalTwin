import sys
import os
import copy
import json
import numpy as np
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QApplication, QDockWidget, 
                             QVBoxLayout, QWidget, QStatusBar, QFileDialog,
                             QMenuBar, QDialog, QHBoxLayout, QPushButton)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
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
from gui.widgets.optimizer_widget import OptimizerWidget
from gui.widgets.manual_viewer import ManualWidget
from gui.automation_api import DesktopAutomationAPI

class HILIGHTMainWindow(QMainWindow):
    LAYOUT_VERSION = 3

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HILIGHTer Digital Twin | Desktop Workspace")
        self.resize(1800, 1000) # Slightly wider for manual
        
        # Initialize Core Engine
        from backend.twin_engine import TwinEngine
        self.engine = TwinEngine()
        
        # Setup Widgets
        self.map_widget = MapWidget("Lifetime Gradient Map")
        self.phasor_widget = PhasorWidget()
        self.decay_widget = DecayWidget()
        self.control_widget = ControlWidget()
        self.fisher_widget = FisherWidget()
        self.mle_accuracy_widget = MLEAccuracyWidget()
        self.diagnostics_widget = DiagnosticsWidget()
        self.control_widget.update_from_config(self.engine.config)
        self.control_widget.btn_export.setEnabled(False)
        self.last_precision_run = None
        self.desktop_api = DesktopAutomationAPI(self)
        
        # Setup Manual (Persistent Sidepanel)
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        manual_path = os.path.join(repo_root, "docs", "digital_twin_manual.html")
        manual_fallback = os.path.join(repo_root, "python", "frontend", "public", "manual.html")
        self.manual_widget = ManualWidget(manual_path if os.path.exists(manual_path) else manual_fallback)
        
        # Setup Layout
        self.init_menu()
        self.setup_docks()
        self.connect_signals()
        
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
        self.refresh_diagnostics()

    def save_layout(self):
        self.settings.setValue("layoutVersion", self.LAYOUT_VERSION)
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

    def restore_layout(self):
        saved_version = self.settings.value("layoutVersion", 0, int)
        if saved_version != self.LAYOUT_VERSION:
            return
        geo = self.settings.value("geometry")
        if geo: self.restoreGeometry(geo)
        state = self.settings.value("windowState")
        if state: self.restoreState(state)

    def closeEvent(self, event):
        self.save_layout()
        super().closeEvent(event)

    def init_menu(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("&File")
        self.export_precision_act = QAction("Export Precision Report...", self)
        self.export_precision_act.setEnabled(False)
        self.export_precision_act.triggered.connect(self.export_last_precision_report)
        file_menu.addAction(self.export_precision_act)

        exit_act = QAction("❌ Exit", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)
        
        help_menu = menubar.addMenu("&Help")
        about_act = QAction("ℹ️ About", self)
        about_act.triggered.connect(self.show_about)
        help_menu.addAction(about_act)

        view_menu = menubar.addMenu("&View")
        self.theme_act = QAction("🌞 Light Mode", self)
        self.theme_act.triggered.connect(self.toggle_theme)
        view_menu.addAction(self.theme_act)

    def apply_theme(self):
        """Applies the current theme from settings."""
        theme = self.settings.value("theme", "dark")
        app = QApplication.instance()
        if theme == "dark":
            app.setStyleSheet(qdarkstyle.load_stylesheet())
            self.theme_act.setText("🌞 Light Mode")
        else:
            app.setStyleSheet("") # Default bright theme
            self.theme_act.setText("🌙 Dark Mode")

    def toggle_theme(self):
        """Switches between dark and light themes."""
        current = self.settings.value("theme", "dark")
        new_theme = "light" if current == "dark" else "dark"
        self.settings.setValue("theme", new_theme)
        self.apply_theme()

    def setup_docks(self):
        placeholder = QWidget()
        placeholder.setLayout(QVBoxLayout())
        placeholder.layout().setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(placeholder)

        # Left: Controls
        c_dock = QDockWidget("Digital Twin Controller", self)
        c_dock.setObjectName("dock_params")
        c_dock.setWidget(self.control_widget)
        # Allow floating but persistent top-left placement
        c_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | 
                           QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, c_dock)

        # Right Top: Phasor
        p_dock = QDockWidget("Phasor Space (G vs S)", self)
        p_dock.setObjectName("dock_phasor")
        p_dock.setWidget(self.phasor_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, p_dock)

        # Right Bottom: Fisher
        f_dock = QDockWidget("Precision (Fisher Info)", self)
        f_dock.setObjectName("dock_fisher")
        f_dock.setWidget(self.fisher_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, f_dock)

        acc_dock = QDockWidget("Gridded MLE Accuracy", self)
        acc_dock.setObjectName("dock_mle_accuracy")
        acc_dock.setWidget(self.mle_accuracy_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, acc_dock)

        # Right Center: Diagnostics
        dia_dock = QDockWidget("Instrument Diagnostics", self)
        dia_dock.setObjectName("dock_diagnostics")
        dia_dock.setWidget(self.diagnostics_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dia_dock)

        # Bottom: Decay
        d_dock = QDockWidget("Single Pixel Decay / Fit", self)
        d_dock.setObjectName("dock_decay")
        d_dock.setWidget(self.decay_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, d_dock)

        # Bottom Left: Image / Map
        map_dock = QDockWidget("Lifetime Gradient Map", self)
        map_dock.setObjectName("dock_map")
        map_dock.setWidget(self.map_widget)
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

    def connect_signals(self):
        # Context-aware Manual
        self.control_widget.context_changed.connect(self.manual_widget.scroll_to_section)

        # Simulation controls
        self.control_widget.btn_precision.clicked.connect(self.run_precision_analysis)
        self.control_widget.btn_simulate.clicked.connect(self.run_image_gen)
        self.control_widget.btn_export.clicked.connect(self.preview_last_precision_report)
        self.control_widget.btn_interrupt.clicked.connect(self.interrupt_simulation)
        self.control_widget.btn_manage_inst.clicked.connect(self.open_instrument_manager)
        self.control_widget.btn_optimize.clicked.connect(self.open_optimizer)
        
        # Auto-refresh diagnostics on any param change
        from PyQt6.QtWidgets import QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox, QLineEdit
        for widget in self.control_widget.findChildren((QDoubleSpinBox, QSpinBox)):
            widget.valueChanged.connect(self.refresh_diagnostics)
        for widget in self.control_widget.findChildren((QComboBox, QCheckBox)):
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self.refresh_diagnostics)
            else:
                widget.clicked.connect(self.refresh_diagnostics)

        self.map_widget.pixel_selected.connect(self.on_pixel_select)
        self.phasor_widget.roi_changed.connect(self.on_phasor_roi)

    def open_instrument_manager(self):
        # Pass engine config to manager
        dlg = InstrumentManager(self, self.engine.config)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # If applied, sync UI back from config
            self.control_widget.update_from_config(self.engine.config)
            self.refresh_diagnostics()
            self.statusBar().showMessage("Instrument profile applied successfully.")

    def open_optimizer(self):
        """Opens the Gate Optimizer dialog."""
        self.sync_ui_to_config() # Push current settings to engine
        dlg = QDialog(self)
        dlg.setWindowTitle("Gate Optimization")
        dlg.setLayout(QVBoxLayout())
        
        opt_widget = OptimizerWidget(self.engine)
        dlg.layout().addWidget(opt_widget)
        
        # Connect the export signal
        opt_widget.gates_optimized.connect(self.on_gates_optimized)
        opt_widget.gates_optimized.connect(dlg.accept)
        
        dlg.exec()

    def on_gates_optimized(self, edges):
        """Callback for when new gate edges are decided by the optimizer."""
        self.engine.config.gate_type = "custom"
        self.engine.config.gate_edges = edges
        
        # Calculate widths for the UI
        widths = np.diff(edges).tolist()
        self.engine.config.gate_widths = widths
        
        # Sync back to Control UI
        self.control_widget.update_from_config(self.engine.config)
        self.refresh_diagnostics()
        self.statusBar().showMessage("Optimized gates applied successfully.")

    def sync_ui_to_config(self):
        cfg = self.engine.config
        cw = self.control_widget
        
        # Model Parameters (Dynamic row logic)
        cfg.decay_model = cw.combo_decay_model.currentText().lower()
        cfg.n_components = cw.spin_n_comp.value()
        cfg.taus[0] = cw.param_rows["tau1"]['val'].value()
        cfg.taus[1] = cw.param_rows["tau2"]['val'].value()
        cfg.amplitudes[0] = cw.param_rows["alpha"]['val'].value()
        cfg.background_level = cw.param_rows["background"]['val'].value()
        cfg.beta = cw.param_rows["beta"]['val'].value()
        
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
        coarse_step = (cfg.f_x_max - cfg.f_x_min) / max(1, cfg.f_x_steps - 1)
        cfg.grid_tau_min = max(1e-6, cfg.f_x_min - coarse_step)
        cfg.grid_tau_max = cfg.f_x_max + coarse_step
        cfg.grid_steps = max(3, ((cfg.f_x_steps - 1) + 2) * cfg.grid_fine_factor + 1)
        scale_map = {"log": "log", "linear": "linear", "exponential": "exp"}
        cfg.f_x_scale = scale_map.get(cw.combo_fx_scale.currentText().lower(), "log")
        cfg.precision_validate_mc = cw.chk_validate_mc.isChecked()
        cfg.precision_photons = cw.spin_precision_photons.value()
        cfg.precision_mc_repeats = cw.spin_mc_repeats.value()
        cfg.precision_accuracy_pvalue = cw.spin_accuracy_pvalue.value()
        cfg.sweep_autoplay = self.diagnostics_widget.chk_autoplay.isChecked()

        # Laser & IRF
        cfg.period = cw.spin_period.value()
        cfg.b_decay_wrapping = cw.chk_decay_wrap.isChecked()
        cfg.irf_profile = cw.combo_profile.currentText().lower()
        cfg.irf_fwhm = cw.spin_fwhm.value()
        cfg.irf_position = cw.spin_irf_pos.value()
        cfg.irf_rise_time = cw.spin_rise.value()
        cfg.irf_fall_time = cw.spin_fall.value()
        
        # Burst Excitation
        cfg.burst_enabled = cw.group_burst.isChecked()
        cfg.burst_sub_period = cw.spin_burst_period.value()
        cfg.burst_sub_fwhm = cw.spin_burst_fwhm.value()
        
        # Instrument & Noise
        cfg.a_photons = cw.spin_photons.value()
        cfg.sim_mode = cw.combo_sim_mode.currentText().lower()
        cfg.timing_jitter = cw.spin_jitter.value()
        cfg.detector_deadtime = cw.spin_deadtime.value()
        cfg.b_multihit_mode = cw.chk_multihit.isChecked()
        cfg.n_repeats = cw.spin_repeats.value()

        # Gating
        gate_type = cw.combo_gate_type.currentText().lower()
        cfg.gate_type = gate_type
        cfg.gate_rise = cw.spin_gate_rise.value()
        cfg.gate_fall = cw.spin_gate_fall.value()
        cfg.gate_stick_to_end = cw.chk_gate_stick.isChecked()
        
        if cw.radio_gate_irf.isChecked(): cfg.gate_start_mode = "irf_3sigma"
        elif cw.radio_gate_start.isChecked(): cfg.gate_start_mode = "start"
        else: cfg.gate_start_mode = "free"
        cfg.gate_first_start = cw.spin_gate_first.value()

        num_gates = cw.spin_num_gates.value()
        
        # Calculate dynamic edges for 'equal' or count mismatch
        if gate_type == "equal" or (len(cfg.gate_edges)-1 != num_gates):
            t_start = 0.0
            if cfg.gate_start_mode == "irf_3sigma":
                # Find 3-sigma point of IRF including jitter
                jitter_ns = cfg.timing_jitter / 1000.0
                if cfg.irf_profile == "gaussian":
                    sigma_base = cfg.irf_fwhm / 2.35482
                    sigma_total = np.sqrt(sigma_base**2 + jitter_ns**2)
                    t_start = cfg.irf_position + 3.0 * sigma_total
                elif cfg.irf_profile == "ideal (dirac)":
                    t_start = cfg.irf_position + 3.0 * jitter_ns
                else: # rectangular
                    # Rect with jitter tails
                    t_start = cfg.irf_position + cfg.irf_fwhm + 3.0 * jitter_ns
            elif cfg.gate_start_mode == "free":
                t_start = cfg.gate_first_start
            
            t_end = cfg.period if cfg.gate_stick_to_end else cfg.gate_edges[-1]
            if t_end <= t_start: t_end = t_start + 5.0 # Safety
            
            edges = np.linspace(t_start, t_end, num_gates + 1)
            cfg.gate_edges = edges.tolist()
            cfg.gate_widths = [edges[1]-edges[0]] * num_gates
            
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
        try:
            cfg.instr_sweep_fixed_countrate_kcps = float(cw.sweep_options["deadtime_fixed_countrate_ns"]["extra"].text().strip())
        except Exception:
            cfg.instr_sweep_fixed_countrate_kcps = 100.0
        try:
            cfg.instr_sweep_fixed_deadtime_ns = float(cw.sweep_options["countrate_fixed_deadtime_kcps"]["extra"].text().strip())
        except Exception:
            cfg.instr_sweep_fixed_deadtime_ns = 45.0
        cfg.instr_sweep_vals = self._parse_sweep_values(cfg.instr_sweep_param, cw.get_selected_sweep_values_text())

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
            irf_ref = self.engine.dt_excitation(self.engine.time_vector)
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
            self.diagnostics_widget.update_plot(
                frame["time_vec"],
                frame["gate_shapes"],
                irf=frame.get("irf"),
                pdf=frame.get("pdf"),
                label=frame.get("label"),
            )

    def refresh_diagnostics(self):
        """Forces a re-distillation of gates and updates the physics plots."""
        self.sync_ui_to_config()
        frame = self._create_diagnostics_frame(self.engine.config)
        self._show_diagnostics_frame(frame, use_frames=False)

    def interrupt_simulation(self):
        self.engine.config.b_interrupt = True
        self.statusBar().showMessage("⌛ Interrupt Request Received...")

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
                    _, f_val = self.engine.compute_fisher_info(x_range, int(sweep_cfg.a_photons))
                    batch_results[self._format_sweep_label(param, val, sweep_cfg)] = np.array(f_val, copy=True)
                    print(f"  DEBUG: [{param}={val}] f_val[0]={f_val[0]:.6f}, f_val[mid]={f_val[len(f_val)//2]:.6f}")
                finally:
                    self.engine.config = baseline_cfg  # Always restore baseline

            # ---- SINGLE PLOT UPDATE WITH ALL CURVES ----
            self.fisher_widget.plot_batch(x_range, batch_results,
                                          ideal_x=x_range, ideal_f=f_ideal)
            self.statusBar().showMessage("✅ Batch Sweep Complete.")
        else:
            # Single curve
            _, f_val = self.engine.compute_fisher_info(x_range, int(cfg.a_photons))
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
        x_min = float(cfg.f_x_min)
        x_max = float(cfg.f_x_max)
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

    def _parse_sweep_values(self, param, raw_text):
        tokens = [token.strip() for token in raw_text.split(",") if token.strip()]
        if not tokens:
            return []
        if param == "multihit_capabilities":
            values = []
            for token in tokens:
                normalized = token.lower()
                if normalized in {"1", "true", "on", "yes", "enabled", "multi"}:
                    values.append(1.0)
                elif normalized in {"0", "false", "off", "no", "disabled", "single"}:
                    values.append(0.0)
                else:
                    try:
                        values.append(1.0 if float(token) >= 0.5 else 0.0)
                    except Exception:
                        continue
            return values
        try:
            return [float(token) for token in tokens]
        except Exception:
            return []

    def _format_sweep_label(self, param, value, cfg):
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
        if param == "countrate_fixed_deadtime_kcps":
            return f"Countrate = {value:g} Kphotons/s @ {cfg.instr_sweep_fixed_deadtime_ns:g} ns"
        if param == "multihit_capabilities":
            return f"Multihit = {'On' if value >= 0.5 else 'Off'}"
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
                sigma_total = np.sqrt((cfg.irf_fwhm / 2.355) ** 2 + jitter_ns ** 2)
                t_start = cfg.irf_position + 3.0 * sigma_total
            elif cfg.gate_start_mode == "free":
                t_start = cfg.gate_first_start
            t_end = cfg.period if cfg.gate_stick_to_end else cfg.gate_edges[-1]
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
            cfg.metadata["countrate_kcps"] = float(cfg.instr_sweep_fixed_countrate_kcps)
        elif param == "countrate_fixed_deadtime_kcps":
            cfg.detector_deadtime = float(cfg.instr_sweep_fixed_deadtime_ns)
            cfg.metadata["force_precision_deadtime_mc"] = True
            cfg.metadata["countrate_kcps"] = float(value)
        elif param == "multihit_capabilities":
            cfg.metadata["force_precision_deadtime_mc"] = True
            cfg.b_multihit_mode = bool(value >= 0.5)
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
        self.sync_ui_to_config()
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
                self._show_diagnostics_frame(frame, use_frames=True)
                self.diagnostics_widget.pause_playback()
                QApplication.processEvents()

                self.engine.config = sweep_cfg
                self.engine.grid_templates = None
                self.engine.grid_tau_axis = None

                theory_f = np.full(len(x_range), np.nan)
                theory_fi = np.full(len(x_range), np.nan)
                theory_label = "Theory" if raw_value is None else f"Theory | {label}"

                def theory_callback(point_idx, fisher_val, f_val):
                    nonlocal completed_steps
                    theory_fi[point_idx] = fisher_val
                    theory_f[point_idx] = f_val
                    plot_results[theory_label] = np.array(theory_f, copy=True)
                    completed_steps += 1
                    self._set_progress(completed_steps, max(total_steps, 1), f"Precision theory: {label} ({point_idx + 1}/{len(x_range)})")
                    is_last = point_idx == len(x_range) - 1
                    if is_last or ((point_idx + 1) % plot_update_interval == 0):
                        self.fisher_widget.plot_batch(x_range, plot_results, ideal_x=x_range, ideal_f=f_ideal)
                        QApplication.processEvents()

                _, theory_final = self.engine.compute_fisher_info(
                    x_range,
                    int(sweep_cfg.precision_photons),
                    point_callback=theory_callback,
                )
                theory_f = np.array(theory_final, copy=True)
                plot_results[theory_label] = theory_f
                self.fisher_widget.plot_batch(x_range, plot_results, ideal_x=x_range, ideal_f=f_ideal)

                mc_payload = None
                if run_mc and not self.engine.config.b_interrupt:
                    mc_f = np.full(len(x_range), np.nan)
                    mc_mean = np.full(len(x_range), np.nan)
                    mc_std = np.full(len(x_range), np.nan)
                    mc_compatible = np.full(len(x_range), True, dtype=bool)
                    mc_label = "Monte Carlo" if raw_value is None else f"Monte Carlo | {label}"

                    def mc_callback(point_idx, mean_tau, std_tau, f_val, p_eff, p_value, compatible):
                        nonlocal completed_steps
                        mc_mean[point_idx] = mean_tau
                        mc_std[point_idx] = std_tau
                        mc_f[point_idx] = f_val
                        mc_compatible[point_idx] = bool(compatible)
                        plot_results[mc_label] = {
                            "y": np.array(mc_f, copy=True),
                            "compatible": np.array(mc_compatible, copy=True),
                        }
                        accuracy_results[label] = {
                            "mean": np.array(mc_mean, copy=True),
                            "std": np.array(mc_std, copy=True),
                        }
                        completed_steps += 1
                        self._set_progress(completed_steps, max(total_steps, 1), f"Monte Carlo validation: {label} ({point_idx + 1}/{len(x_range)})")
                        is_last = point_idx == len(x_range) - 1
                        if is_last or ((point_idx + 1) % plot_update_interval == 0):
                            self.fisher_widget.plot_batch(x_range, plot_results, ideal_x=x_range, ideal_f=f_ideal)
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
                        "compatible": np.array(mc_payload["compatible"], copy=True),
                    }
                    accuracy_results[label] = {
                        "mean": np.array(mc_payload["mean_tau"], copy=True),
                        "std": np.array(mc_payload["std_tau"], copy=True),
                    }
                    self.fisher_widget.plot_batch(x_range, plot_results, ideal_x=x_range, ideal_f=f_ideal)
                    self.mle_accuracy_widget.plot_accuracy(x_range, accuracy_results)

                run_series.append({
                    "label": label,
                    "theory_fisher": np.array(theory_fi, copy=True),
                    "theory_f": np.array(theory_f, copy=True),
                    "mc": mc_payload,
                    "diagnostics_frame": frame,
                    "config": copy.deepcopy(sweep_cfg),
                })

            self.last_precision_run = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "x_range": np.array(x_range, copy=True),
                "ideal_f": np.array(f_ideal, copy=True),
                "series": run_series,
                "x_label": target_label,
                "config": copy.deepcopy(baseline_cfg),
            }
            self.export_precision_act.setEnabled(bool(run_series))
            self.control_widget.btn_export.setEnabled(bool(run_series))
            self.statusBar().showMessage("Precision analysis complete.")
        finally:
            self.engine.config = baseline_cfg
            self.control_widget.btn_precision.setEnabled(True)
            self.control_widget.btn_interrupt.setEnabled(False)
            self.progress.hide()
            if self.diagnostics_widget.chk_autoplay.isChecked():
                self.diagnostics_widget.resume_playback()

    def run_image_gen(self):
        """Runs the actual Monte Carlo photon image simulation."""
        self.engine.config.b_interrupt = False
        self.control_widget.btn_simulate.setEnabled(False)
        self.control_widget.btn_interrupt.setEnabled(True)
        
        self.sync_ui_to_config()
        self.statusBar().showMessage("🖼️ Generating Synthetic FLIM Image...")
        self.progress.show()
        
        res = self.control_widget.spin_res.value()
        # Spatial gradient logic...
        tau_grid = np.tile(np.linspace(0.5, 5.0, res), (res, 1))
        
        num_gates = len(self.engine.config.gate_edges) - 1
        self.engine.raw_data = np.zeros((res, res, num_gates))
        
        # Fast simulated image (reduced repeats for UI responsiveness)
        for y in range(res):
            if self.engine.config.b_interrupt: break
            for x in range(res):
                counts = self.engine.simulate_photons_with_deadtime(tau_grid[y,x], self.engine.config.a_photons)
                self.engine.raw_data[y,x,:] = counts
            if y % 10 == 0:
                self.progress.setValue(int(100 * y / res))
                self.map_widget.set_image(np.sum(self.engine.raw_data, axis=2))
                QApplication.processEvents()
        
        self.statusBar().showMessage("🎨 Imaging Complete.")
        self.control_widget.btn_simulate.setEnabled(True)
        self.control_widget.btn_interrupt.setEnabled(False)
        self.progress.hide()
        QApplication.restoreOverrideCursor()


    def on_pixel_select(self, y, x):
        if self.engine.raw_data is None: return
        
        decay = self.engine.raw_data[y, x, :]
        edges = np.array(self.engine.config.gate_edges)
        centers = 0.5 * (edges[:-1] + edges[1:])
        
        # Generate fit curve if available
        fit = None
        if self.engine.tau_map is not None:
             # Basic implementation from main.py logic
             tau = self.engine.tau_map[y, x]
             if not np.isnan(tau):
                 # Recalculate theoretical decay...
                 t_vec = self.engine.time_vector
                 sig = np.exp(-t_vec / tau)
                 # Simpler visualization for desktop for now
                 pj = self.engine.gate_shapes @ sig
                 pj /= np.sum(pj)
                 # Scaled to match raw data height
                 fit = pj * np.sum(decay)
        
        self.decay_widget.update_decay(centers, decay, fit)

    def on_phasor_roi(self, gmin, gmax, smin, smax):
        # Filtering logic for mask
        if self.engine.raw_data is None: return
        # Mocking masking feedback for now
        pass

    def export_last_precision_report(self):
        self.preview_last_precision_report()

    def preview_last_precision_report(self):
        if not self.last_precision_run:
            self.statusBar().showMessage("No precision run is available to export.")
            return

        html = self._build_precision_report_html()
        dlg = QDialog(self)
        dlg.setWindowTitle("Precision Report Preview")
        dlg.resize(1200, 850)
        dlg_layout = QVBoxLayout(dlg)

        from PyQt6.QtWebEngineWidgets import QWebEngineView
        browser = QWebEngineView(dlg)
        browser.setHtml(html)
        dlg_layout.addWidget(browser)

        button_row = QHBoxLayout()
        button_row.addStretch()
        save_btn = QPushButton("Save HTML...", dlg)
        close_btn = QPushButton("Close", dlg)
        button_row.addWidget(save_btn)
        button_row.addWidget(close_btn)
        dlg_layout.addLayout(button_row)

        def save_report():
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Precision Report",
                "hilighter_precision_report.html",
                "HTML Files (*.html)",
            )
            if not file_path:
                return
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(html)
            self.statusBar().showMessage(f"Precision report exported to {file_path}")

        save_btn.clicked.connect(save_report)
        close_btn.clicked.connect(dlg.accept)
        dlg.exec()

    def _build_precision_report_html(self):
        report = self.last_precision_run
        x_range = report["x_range"].tolist()
        ideal_f = report["ideal_f"].tolist()
        config_dump = report["config"].model_dump() if hasattr(report["config"], "model_dump") else {}

        series_payload = []
        frame_payload = []
        for item in report["series"]:
            entry = {
                "label": item["label"],
                "theory_f": item["theory_f"].tolist(),
                "theory_eff": (1.0 / np.maximum(item["theory_f"], 1e-12) ** 2).tolist(),
            }
            if item["mc"] is not None:
                entry["mc_f"] = item["mc"]["f_value"].tolist()
                entry["mc_eff"] = item["mc"]["efficiency"].tolist()
                entry["mc_mean"] = item["mc"]["mean_tau"].tolist()
                entry["mc_std"] = item["mc"]["std_tau"].tolist()
            series_payload.append(entry)

            frame = item["diagnostics_frame"]
            frame_payload.append({
                "label": frame["label"],
                "time": frame["time_vec"].tolist(),
                "gates": frame["gate_shapes"].tolist(),
                "irf": frame["irf"].tolist(),
                "pdf": frame["pdf"].tolist(),
            })

        payload = {
            "timestamp": report["timestamp"],
            "x_label": report["x_label"],
            "x_range": x_range,
            "ideal_f": ideal_f,
            "ideal_eff": (1.0 / np.maximum(report["ideal_f"], 1e-12) ** 2).tolist(),
            "series": series_payload,
            "frames": frame_payload,
            "config": config_dump,
        }
        payload_json = json.dumps(payload)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HILIGHTer Precision Report</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      --bg: #07111f;
      --panel: #10233d;
      --text: #e5eefb;
      --muted: #9fb3ca;
      --accent: #38bdf8;
      --line: #1f3a5a;
    }}
    body {{ margin: 0; font-family: "Segoe UI", sans-serif; background: linear-gradient(180deg, #07111f 0%, #0b1728 100%); color: var(--text); }}
    main {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    .panel {{ background: rgba(16, 35, 61, 0.92); border: 1px solid var(--line); border-radius: 16px; padding: 18px; margin-bottom: 18px; }}
    .grid {{ display: grid; grid-template-columns: 2fr 1fr; gap: 18px; }}
    .controls {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }}
    button, select {{ background: #173559; color: var(--text); border: 1px solid #29507d; border-radius: 8px; padding: 8px 12px; }}
    input[type="checkbox"] {{ transform: scale(1.1); }}
    pre {{ white-space: pre-wrap; color: var(--muted); }}
    #diagPlot {{ height: 420px; }}
    #precisionPlot, #mcPlot {{ height: 460px; }}
  </style>
</head>
<body>
  <main>
    <div class="panel">
      <h1>HILIGHTer Precision Report</h1>
      <div>Generated: {report["timestamp"]}</div>
      <div>X-Axis: {report["x_label"]}</div>
    </div>
    <div class="grid">
      <div>
        <div class="panel">
          <div class="controls">
            <label><input type="checkbox" id="showEfficiency"> Show Photon Efficiency</label>
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

    function precisionTraces(showEfficiency) {{
      const metricKey = showEfficiency ? "theory_eff" : "theory_f";
      const idealKey = showEfficiency ? "ideal_eff" : "ideal_f";
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
          y: series[metricKey],
          mode: "lines",
          name: `Theory | ${{series.label}}`,
          line: {{ width: 2, color }}
        }});
        if (series.mc_f) {{
          traces.push({{
            x: report.x_range,
            y: showEfficiency ? series.mc_eff : series.mc_f,
            mode: "markers",
            name: `Monte Carlo | ${{series.label}}`,
            marker: {{ size: 8, color, symbol: "circle" }}
          }});
        }}
      }});
      return traces;
    }}

    function renderPrecision() {{
      const showEfficiency = document.getElementById("showEfficiency").checked;
      Plotly.newPlot("precisionPlot", precisionTraces(showEfficiency), {{
        paper_bgcolor: "#10233d",
        plot_bgcolor: "#10233d",
        font: {{ color: "#e5eefb" }},
        xaxis: {{ title: report.x_label, type: "log", gridcolor: "#1f3a5a" }},
        yaxis: {{ title: showEfficiency ? "Photon Efficiency (1/F²)" : "F-Value", gridcolor: "#1f3a5a" }},
        legend: {{ orientation: "h" }},
        margin: {{ t: 30, r: 20, b: 60, l: 70 }}
      }}, {{ responsive: true }});
    }}

    function renderMonteCarloSummary() {{
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
        paper_bgcolor: "#10233d",
        plot_bgcolor: "#10233d",
        font: {{ color: "#e5eefb" }},
        xaxis: {{ title: report.x_label, type: "log", gridcolor: "#1f3a5a" }},
        yaxis: {{ title: "Monte Carlo mean τ ± std", gridcolor: "#1f3a5a" }},
        margin: {{ t: 30, r: 20, b: 60, l: 70 }}
      }}, {{ responsive: true }});
    }}

    function renderFrame() {{
      if (!report.frames.length) return;
      const frame = report.frames[frameIndex];
      document.getElementById("frameLabel").textContent = frame.label;
      const traces = frame.gates.map((gate, idx) => ({{
        x: frame.time,
        y: gate,
        mode: "lines",
        name: `Gate ${{idx + 1}}`
      }}));
      traces.push({{ x: frame.time, y: frame.irf, mode: "lines", name: "IRF", line: {{ color: "#22d3ee", width: 3 }} }});
      traces.push({{ x: frame.time, y: frame.pdf, mode: "lines", name: "PDF", line: {{ color: "#ffffff", width: 3, dash: "dash" }} }});
      Plotly.newPlot("diagPlot", traces, {{
        paper_bgcolor: "#10233d",
        plot_bgcolor: "#10233d",
        font: {{ color: "#e5eefb" }},
        xaxis: {{ title: "Time (ns)", gridcolor: "#1f3a5a" }},
        yaxis: {{ title: "Relative amplitude", gridcolor: "#1f3a5a" }},
        margin: {{ t: 30, r: 20, b: 60, l: 70 }}
      }}, {{ responsive: true }});
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

    document.getElementById("showEfficiency").addEventListener("change", renderPrecision);
    document.getElementById("prevFrame").addEventListener("click", () => stepFrame(-1));
    document.getElementById("nextFrame").addEventListener("click", () => stepFrame(1));
    document.getElementById("autoplay").addEventListener("change", updateAutoplay);

    renderPrecision();
    renderMonteCarloSummary();
    renderFrame();
    updateAutoplay();
  </script>
</body>
</html>"""

    def show_about(self):
        from PyQt6.QtWidgets import QMessageBox
        about_text = """
        <h2>HILIGHTer Digital Twin</h2>
        <p>A full-spectrum modeling environment for high-speed time-gated imaging.</p>
        <hr>
        <b>Powered by:</b>
        <ul>
            <li><b>PhasorPy</b>: High-precision fit-free analysis.</li>
            <li><b>PyQt6 & PyQtGraph</b>: High-performance UI and plotting.</li>
            <li><b>NumPy & SciPy</b>: Core numerical and signal processing.</li>
            <li><b>QDarkStyle</b>: Sleek, research-ready aesthetics.</li>
        </ul>
        <p><i>Special thanks to the PhasorPy contributors for their standard-setting phasor approach implementation.</i></p>
        """
        QMessageBox.about(self, "About HILIGHTer", about_text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HILIGHTMainWindow()
    window.show()
    sys.exit(app.exec())
