from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QDoubleSpinBox, QSpinBox, QPushButton,
                             QComboBox, QLabel, QGroupBox, QTabWidget,
                             QCheckBox, QLineEdit, QRadioButton, QButtonGroup,
                             QStackedWidget, QTextEdit, QToolButton, QDialog,
                             QScrollArea,
                             QDialogButtonBox)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QGuiApplication
import numpy as np
import pyqtgraph as pg

class ControlWidget(QWidget):
    context_changed = pyqtSignal(str) # Emits section ID for manual

    def __init__(self):
        super().__init__()
        self.current_theme = "dark"
        self.optimization_running_state = False
        layout = QVBoxLayout(self)
        
        # Main Tab Container
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        def two_column_row(left_label, left_widget, right_label, right_widget):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(QLabel(left_label))
            row_layout.addWidget(left_widget, 1)
            row_layout.addSpacing(8)
            row_layout.addWidget(QLabel(right_label))
            row_layout.addWidget(right_widget, 1)
            return row
        
        # --- TAB 0: DECAY MODEL (NOW FIRST) ---
        decay_tab = QWidget()
        decay_layout = QVBoxLayout(decay_tab)
        
        model_group = QGroupBox("Model Architecture")
        model_form = QFormLayout(model_group)
        self.combo_decay_model = QComboBox()
        self.combo_decay_model.addItems(["Exponential", "Stretched", "Custom"])
        self.combo_decay_model.setToolTip("Select the mathematical model for fluorescence decay.")
        model_form.addRow("Mode:", self.combo_decay_model)
        
        self.spin_n_comp = QSpinBox()
        self.spin_n_comp.setRange(1, 10)
        self.spin_n_comp.setValue(1)
        model_form.addRow("N Components:", self.spin_n_comp)

        self.chk_pulse_train_decay = QCheckBox("Enable PDF Wrapping (Pulse Train)")
        self.chk_pulse_train_decay.setToolTip("Handles long-lived decay 'wraparound' by modulo-summing the PDF over Trep.")
        model_form.addRow(self.chk_pulse_train_decay)
        
        decay_layout.addWidget(model_group)

        # Precision Parameters Table/Matrix
        param_group = QGroupBox("Fit Parameters & Precision Targeting")
        param_vbox = QVBoxLayout(param_group)
        self.param_grid = QFormLayout()
        
        # Row storage for dynamic visibility
        self.param_rows = {} # name -> {label, widgets}

        def add_param_row(name, label_text, tooltip):
            h = QHBoxLayout()
            val = QDoubleSpinBox()
            val.setRange(0, 1000); val.setDecimals(3)
            fix_chk = QCheckBox("Fix")
            x_chk = QCheckBox("X-Axis")
            x_chk.setToolTip("Use this parameter as the X-axis for F-plots.")
            h.addWidget(val, 2)
            h.addWidget(fix_chk, 1)
            h.addWidget(x_chk, 1)
            
            label = QLabel(label_text)
            self.param_grid.addRow(label, h)
            self.param_rows[name] = {'label': label, 'layout': h, 'val': val, 'fix': fix_chk, 'x': x_chk}
            return val, fix_chk, x_chk

        self.p_tau1, self.f_tau1, self.x_tau1 = add_param_row("tau1", "Tau 1 (ns):", "Primary lifetime")
        self.p_tau2, self.f_tau2, self.x_tau2 = add_param_row("tau2", "Tau 2 (ns):", "Secondary lifetime")
        self.p_alpha, self.f_alpha, self.x_alpha = add_param_row("alpha", "Alpha 1 (frac):", "Fractional contribution")
        self.p_bg, self.f_bg, self.x_bg = add_param_row("background", "Background:", "Constant offset")
        self.p_beta, self.f_beta, self.x_beta = add_param_row("beta", "Beta (KWW):", "Stretching factor")
        
        # Single selection logic for X-axis (Radio-style)
        self.x_group = {
            "tau1": self.x_tau1, "tau2": self.x_tau2, 
            "alpha": self.x_alpha, "background": self.x_bg, "beta": self.x_beta
        }
        self.default_x_ranges = {
            "tau1": (0.5, 7.5),
            "tau2": (0.5, 7.5),
            "alpha": (0.0, 1.0),
            "background": (0.0, 0.25),
        }
        self.default_x_scales = {
            "tau1": "Log",
            "tau2": "Log",
            "alpha": "Linear",
            "background": "Linear",
            "beta": "Linear",
        }
        for name, chk in self.x_group.items():
            chk.setProperty("param_name", name)
            chk.clicked.connect(self._handle_x_selection)
            
        param_vbox.addLayout(self.param_grid)
        decay_layout.addWidget(param_group)

        # Connect architecture changes to visibility
        self.combo_decay_model.currentIndexChanged.connect(self.update_param_visibility)
        self.spin_n_comp.valueChanged.connect(self.update_param_visibility)
        self.update_param_visibility()

        # F-Value Curve Resolution
        sweep_grid_group = QGroupBox("Precision Sweep Configuration (X-Axis)")
        sweep_grid_form = QFormLayout(sweep_grid_group)
        self.spin_fx_min = QDoubleSpinBox()
        self.spin_fx_min.setRange(0.0, 1000)
        self.spin_fx_min.setValue(0.5)

        self.spin_fx_max = QDoubleSpinBox()
        self.spin_fx_max.setRange(0.0, 1000)
        self.spin_fx_max.setValue(7.5)
        sweep_grid_form.addRow(two_column_row("Min Value:", self.spin_fx_min, "Max Value:", self.spin_fx_max))

        self.spin_fx_steps = QSpinBox()
        self.spin_fx_steps.setRange(10, 500)
        self.spin_fx_steps.setValue(30)

        self.spin_grid_fine_factor = QSpinBox()
        self.spin_grid_fine_factor.setRange(1, 1000)
        self.spin_grid_fine_factor.setValue(100)
        sweep_grid_form.addRow(two_column_row("Steps:", self.spin_fx_steps, "MLE Fine Factor:", self.spin_grid_fine_factor))

        self.combo_fx_scale = QComboBox()
        self.combo_fx_scale.addItems(["Log", "Linear", "Exponential"])
        sweep_grid_form.addRow("Grid Scale:", self.combo_fx_scale)
        decay_layout.addWidget(sweep_grid_group)

        mle_group = QGroupBox("Gridded MLE Definition")
        mle_form = QFormLayout(mle_group)
        self.lbl_grid_min = QLabel("0.100")
        self.lbl_grid_max = QLabel("10.000")
        self.lbl_grid_steps = QLabel("5000")
        self.lbl_grid_scale = QLabel("Linear")
        mle_form.addRow(two_column_row("Grid Min:", self.lbl_grid_min, "Grid Max:", self.lbl_grid_max))
        mle_form.addRow(two_column_row("Grid Steps:", self.lbl_grid_steps, "Grid Scale:", self.lbl_grid_scale))
        decay_layout.addWidget(mle_group)

        exec_group = QGroupBox("Precision Execution")
        exec_form = QFormLayout(exec_group)
        self.chk_validate_mc = QCheckBox("Validate with Monte Carlo")
        self.chk_validate_mc.setChecked(True)
        self.chk_compute_ci = QCheckBox("Compute 95% CI")
        self.chk_compute_ci.setChecked(False)
        mc_toggle_row = QWidget()
        mc_toggle_layout = QHBoxLayout(mc_toggle_row)
        mc_toggle_layout.setContentsMargins(0, 0, 0, 0)
        mc_toggle_layout.addWidget(self.chk_validate_mc)
        mc_toggle_layout.addWidget(self.chk_compute_ci)
        mc_toggle_layout.addStretch()
        exec_form.addRow(mc_toggle_row)

        self.spin_precision_photons = QSpinBox()
        self.spin_precision_photons.setRange(1, 10_000_000)
        self.spin_precision_photons.setValue(2000)

        self.spin_mc_repeats = QSpinBox()
        self.spin_mc_repeats.setRange(10, 5000)
        self.spin_mc_repeats.setValue(400)
        exec_form.addRow(two_column_row("Precision Photons:", self.spin_precision_photons, "MC Repeats:", self.spin_mc_repeats))

        self.spin_accuracy_pvalue = QDoubleSpinBox()
        self.spin_accuracy_pvalue.setRange(0.00000001, 0.5)
        self.spin_accuracy_pvalue.setDecimals(8)
        self.spin_accuracy_pvalue.setSingleStep(0.000001)
        self.spin_accuracy_pvalue.setValue(0.0000001)
        exec_form.addRow("Estimator Accuracy p-value:", self.spin_accuracy_pvalue)

        self.spin_bootstrap_samples = QSpinBox()
        self.spin_bootstrap_samples.setRange(200, 100000)
        self.spin_bootstrap_samples.setSingleStep(100)
        self.spin_bootstrap_samples.setValue(2000)

        self.spin_ci_level = QDoubleSpinBox()
        self.spin_ci_level.setRange(50.0, 99.999)
        self.spin_ci_level.setDecimals(3)
        self.spin_ci_level.setSingleStep(0.5)
        self.spin_ci_level.setValue(95.0)
        exec_form.addRow(two_column_row("Bootstrap Resamples:", self.spin_bootstrap_samples, "CI Level (%):", self.spin_ci_level))
        self.chk_validate_mc.toggled.connect(self._sync_precision_execution_ui)
        self.chk_compute_ci.toggled.connect(lambda _: self._sync_precision_execution_ui(self.chk_validate_mc.isChecked()))
        self._sync_precision_execution_ui(self.chk_validate_mc.isChecked())
        decay_layout.addWidget(exec_group)

        self.spin_fx_min.valueChanged.connect(self.update_gridded_mle_summary)
        self.spin_fx_max.valueChanged.connect(self.update_gridded_mle_summary)
        self.spin_fx_steps.valueChanged.connect(self.update_gridded_mle_summary)
        self.spin_grid_fine_factor.valueChanged.connect(self.update_gridded_mle_summary)
        self.update_gridded_mle_summary()
        
        decay_layout.addStretch()
        self.tabs.addTab(decay_tab, "Decay Model")

        # --- TAB 1: IMAGES / VALIDATION ---
        acq_tab = QWidget()
        acq_layout = QVBoxLayout(acq_tab)
        
        stat_group = QGroupBox("Image Synthesis")
        stat_layout = QFormLayout(stat_group)
        self.spin_photons = QSpinBox()
        self.spin_photons.setRange(1, 10_000_000)
        self.spin_photons.setSingleStep(100)
        self.spin_photons.setValue(2000)
        stat_layout.addRow("Avg Photons:", self.spin_photons)

        self.spin_image_repeats = QSpinBox()
        self.spin_image_repeats.setRange(1, 100000)
        self.spin_image_repeats.setValue(200)
        stat_layout.addRow("Target repeats:", self.spin_image_repeats)

        self.lbl_image_param = QLabel("tau1")
        self.lbl_image_x_summary = QLabel("Min 0.500 | Max 7.500 | Steps 30")
        stat_layout.addRow("Swept parameter:", self.lbl_image_param)
        stat_layout.addRow("X-axis source:", self.lbl_image_x_summary)
        acq_layout.addWidget(stat_group)

        res_group = QGroupBox("Derived Validation Geometry")
        res_layout = QFormLayout(res_group)
        self.lbl_image_x_pixels = QLabel("90")
        self.lbl_image_y_pixels = QLabel("70")
        self.lbl_image_band_width = QLabel("3")
        self.lbl_image_effective_repeats = QLabel("210")
        res_layout.addRow(two_column_row("X pixels:", self.lbl_image_x_pixels, "Y pixels:", self.lbl_image_y_pixels))
        res_layout.addRow(two_column_row("Band width:", self.lbl_image_band_width, "Replicates/value:", self.lbl_image_effective_repeats))
        acq_layout.addWidget(res_group)

        analysis_group = QGroupBox("Image Analysis")
        analysis_form = QFormLayout(analysis_group)
        self.combo_image_fit_method = QComboBox()
        self.combo_image_fit_method.addItems(["Gridded MLE", "MLE", "Tail Fitting"])
        analysis_form.addRow("Lifetime fitting:", self.combo_image_fit_method)
        self.lbl_image_backends = QLabel("Phasors: PhasorPy | Lifetime fitting: FLIMfit")
        self.lbl_image_backends.setWordWrap(True)
        analysis_form.addRow("Backends:", self.lbl_image_backends)
        self.btn_fit_image = QPushButton("FIT IMAGE")
        analysis_form.addRow(self.btn_fit_image)
        acq_layout.addWidget(analysis_group)

        self.spin_fx_min.valueChanged.connect(self.update_image_validation_summary)
        self.spin_fx_max.valueChanged.connect(self.update_image_validation_summary)
        self.spin_fx_steps.valueChanged.connect(self.update_image_validation_summary)
        self.spin_image_repeats.valueChanged.connect(self.update_image_validation_summary)
        acq_layout.addStretch()
        self.update_image_validation_summary()
        self.tabs.addTab(acq_tab, "Images")

        # --- TAB 2: LASER / IRF (REFACTORED) ---
        laser_tab = QWidget()
        laser_layout = QFormLayout(laser_tab)
        
        self.spin_period = QDoubleSpinBox(); self.spin_period.setRange(0.1, 1000); self.spin_period.setValue(12.5)
        laser_layout.addRow("Period (ns):", self.spin_period)
        
        self.chk_decay_wrap = QCheckBox("Decay wrapping")
        self.chk_decay_wrap.setChecked(True)
        laser_layout.addRow(self.chk_decay_wrap)

        self.combo_profile = QComboBox()
        self.combo_profile.addItems(["Gaussian", "Rectangular", "Free Form", "Ideal (Dirac)"])
        laser_layout.addRow("IRF Profile:", self.combo_profile)
        
        self.spin_fwhm = QDoubleSpinBox(); self.spin_fwhm.setValue(0.25)
        laser_layout.addRow("FWHM / Duration (ns):", self.spin_fwhm)
        
        self.spin_irf_pos = QDoubleSpinBox(); self.spin_irf_pos.setRange(-10, 1000); self.spin_irf_pos.setValue(0.0)
        self.label_irf_pos = QLabel("Position (Center):")
        laser_layout.addRow(self.label_irf_pos, self.spin_irf_pos)
        
        self.spin_rise = QDoubleSpinBox(); self.spin_rise.setValue(0.05)
        self.label_rise = QLabel("Rise Time (ns):")
        laser_layout.addRow(self.label_rise, self.spin_rise)
        
        self.spin_fall = QDoubleSpinBox(); self.spin_fall.setValue(0.05)
        self.label_fall = QLabel("Fall Time (ns):")
        laser_layout.addRow(self.label_fall, self.spin_fall)
        
        # Burst Excitation Sub-group
        self.group_burst = QGroupBox("Burst Excitation")
        self.group_burst.setCheckable(True)
        self.group_burst.setChecked(False)
        burst_l = QFormLayout(self.group_burst)
        
        self.spin_burst_period = QDoubleSpinBox()
        self.spin_burst_period.setRange(1.0, 100000.0)
        self.spin_burst_period.setValue(1000.0)
        self.spin_burst_period.setToolTip("Peak-to-peak distance between sub-pulses in the burst (ps).")
        burst_l.addRow("Pulse distance (ps):", self.spin_burst_period)
        
        self.spin_burst_fwhm = QDoubleSpinBox()
        self.spin_burst_fwhm.setRange(1.0, 100000.0)
        self.spin_burst_fwhm.setValue(100.0)
        self.spin_burst_fwhm.setToolTip("Pulse-width (FWHM) of each sub-pulse in the burst (ps).")
        burst_l.addRow("Burst FWHM (ps):", self.spin_burst_fwhm)
        
        laser_layout.addRow(self.group_burst)
        
        self.tabs.addTab(laser_tab, "Excitation")
        
        # Connect IRF profile changes for the excitation-specific controls
        self.combo_profile.currentIndexChanged.connect(self._update_irf_ui)
        self._update_irf_ui()

        # Detection
        detection_tab = QWidget()
        detection_layout = QVBoxLayout(detection_tab)

        detector_group = QGroupBox("Detector")
        hw_layout = QFormLayout(detector_group)
        self.spin_jitter = QSpinBox(); self.spin_jitter.setValue(150)
        self.spin_deadtime = QSpinBox(); self.spin_deadtime.setValue(45)
        hw_layout.addRow(two_column_row("Jitter (ps):", self.spin_jitter, "Deadtime (ns):", self.spin_deadtime))
        self.chk_multihit = QCheckBox("Multihit Detection"); self.chk_multihit.setChecked(True)
        hw_layout.addRow(self.chk_multihit)
        detection_layout.addWidget(detector_group)

        # Gating
        gating_group = QGroupBox("Gating")
        gate_layout = QFormLayout(gating_group)
        self.spin_num_gates = QSpinBox(); self.spin_num_gates.setRange(2, 512); self.spin_num_gates.setValue(4)
        self.combo_gate_type = QComboBox(); self.combo_gate_type.addItems(["Equal", "Custom"])
        gate_layout.addRow(two_column_row("Num Gates:", self.spin_num_gates, "Gate Type:", self.combo_gate_type))
        self.label_gate_definition = QLabel("Gate Edges (ns):")
        self.edit_gate_widths = QLineEdit()
        gate_layout.addRow(self.label_gate_definition, self.edit_gate_widths)
        self.lbl_gate_error = QLabel("")
        self.lbl_gate_error.setStyleSheet("color: #dc2626; font-weight: bold;")
        gate_layout.addRow("", self.lbl_gate_error)
        self.spin_gate_rise = QDoubleSpinBox(); self.spin_gate_rise.setValue(0.1)
        self.spin_gate_fall = QDoubleSpinBox(); self.spin_gate_fall.setValue(0.1)
        gate_layout.addRow(two_column_row("Edge Rise (ns):", self.spin_gate_rise, "Edge Fall (ns):", self.spin_gate_fall))

        # Radio button group for gate start mode
        start_group = QGroupBox("Gate Start Alignment")
        start_layout = QVBoxLayout(start_group)
        
        self.radio_gate_irf = QRadioButton("Stick to IRF (3σ decay)")
        self.radio_gate_start = QRadioButton("Stick to start (0)")
        self.radio_gate_free = QRadioButton("Free")
        self.radio_gate_start.setChecked(True)
        
        self.gate_start_bg = QButtonGroup()
        self.gate_start_bg.addButton(self.radio_gate_irf)
        self.gate_start_bg.addButton(self.radio_gate_start)
        self.gate_start_bg.addButton(self.radio_gate_free)
        
        start_layout.addWidget(self.radio_gate_irf)
        start_layout.addWidget(self.radio_gate_start)
        
        free_layout = QHBoxLayout()
        free_layout.addWidget(self.radio_gate_free)
        self.spin_gate_first = QDoubleSpinBox()
        self.spin_gate_first.setRange(0, 1000)
        self.spin_gate_first.setValue(0.0)
        self.spin_gate_first.setEnabled(False)
        free_layout.addWidget(self.spin_gate_first)
        start_layout.addLayout(free_layout)
        
        gate_layout.addRow(start_group)

        end_group = QGroupBox("Gate End Alignment")
        end_layout = QVBoxLayout(end_group)

        self.radio_gate_end_period = QRadioButton("Stick to end of period")
        self.radio_gate_end_free = QRadioButton("Free")
        self.radio_gate_end_period.setChecked(True)

        self.gate_end_bg = QButtonGroup()
        self.gate_end_bg.addButton(self.radio_gate_end_period)
        self.gate_end_bg.addButton(self.radio_gate_end_free)

        end_layout.addWidget(self.radio_gate_end_period)
        end_free_layout = QHBoxLayout()
        end_free_layout.addWidget(self.radio_gate_end_free)
        self.spin_gate_last = QDoubleSpinBox()
        self.spin_gate_last.setRange(0, 1000)
        self.spin_gate_last.setValue(12.5)
        self.spin_gate_last.setEnabled(False)
        end_free_layout.addWidget(self.spin_gate_last)
        end_layout.addLayout(end_free_layout)
        gate_layout.addRow(end_group)

        collection_group = QGroupBox("Gate Collection")
        collection_layout = QVBoxLayout(collection_group)
        self.radio_gate_collection_hist = QRadioButton("Histogram bin")
        self.radio_gate_collection_seq = QRadioButton("Sequential (under development)")
        self.radio_gate_collection_hist.setChecked(True)
        self.gate_collection_bg = QButtonGroup()
        self.gate_collection_bg.addButton(self.radio_gate_collection_hist)
        self.gate_collection_bg.addButton(self.radio_gate_collection_seq)
        collection_layout.addWidget(self.radio_gate_collection_hist)
        collection_layout.addWidget(self.radio_gate_collection_seq)
        gate_layout.addRow(collection_group)

        overlap_group = QGroupBox("Gate Overlap")
        overlap_layout = QVBoxLayout(overlap_group)
        self.radio_overlap_jitter = QRadioButton("Only for jittering/skewness")
        self.radio_overlap_never = QRadioButton("Never")
        self.radio_overlap_yes = QRadioButton("Yes (under development)")
        self.radio_overlap_jitter.setChecked(True)
        self.gate_overlap_bg = QButtonGroup()
        self.gate_overlap_bg.addButton(self.radio_overlap_jitter)
        self.gate_overlap_bg.addButton(self.radio_overlap_never)
        self.gate_overlap_bg.addButton(self.radio_overlap_yes)
        overlap_layout.addWidget(self.radio_overlap_jitter)
        overlap_layout.addWidget(self.radio_overlap_never)
        overlap_yes_row = QHBoxLayout()
        overlap_yes_row.addWidget(self.radio_overlap_yes)
        self.spin_gate_overlap = QDoubleSpinBox()
        self.spin_gate_overlap.setRange(0.0, 1000.0)
        self.spin_gate_overlap.setDecimals(3)
        self.spin_gate_overlap.setSingleStep(0.01)
        self.spin_gate_overlap.setValue(0.0)
        self.spin_gate_overlap.setEnabled(False)
        overlap_yes_row.addWidget(self.spin_gate_overlap)
        overlap_layout.addLayout(overlap_yes_row)
        gate_layout.addRow(overlap_group)

        overlap_effect_group = QGroupBox("Overlap Effect")
        overlap_effect_layout = QVBoxLayout(overlap_effect_group)
        self.radio_overlap_effect_exclusive = QRadioButton("Exclusive")
        self.radio_overlap_effect_duplicate = QRadioButton("Duplicate events (under development)")
        self.radio_overlap_effect_independent = QRadioButton("Independent duplicates (under development)")
        self.radio_overlap_effect_exclusive.setChecked(True)
        self.gate_overlap_effect_bg = QButtonGroup()
        self.gate_overlap_effect_bg.addButton(self.radio_overlap_effect_exclusive)
        self.gate_overlap_effect_bg.addButton(self.radio_overlap_effect_duplicate)
        self.gate_overlap_effect_bg.addButton(self.radio_overlap_effect_independent)
        overlap_effect_layout.addWidget(self.radio_overlap_effect_exclusive)
        overlap_effect_layout.addWidget(self.radio_overlap_effect_duplicate)
        overlap_effect_layout.addWidget(self.radio_overlap_effect_independent)
        gate_layout.addRow(overlap_effect_group)

        self.chk_gate_wraparound = QCheckBox("Wrap around")
        self.chk_gate_wraparound.setChecked(True)
        gate_layout.addRow(self.chk_gate_wraparound)
        
        # Connect radio buttons
        self.radio_gate_free.toggled.connect(self.spin_gate_first.setEnabled)
        self.radio_gate_end_free.toggled.connect(self.spin_gate_last.setEnabled)
        self.radio_overlap_yes.toggled.connect(self.spin_gate_overlap.setEnabled)

        detection_layout.addWidget(gating_group)
        detection_layout.addStretch()
        self.tabs.addTab(detection_tab, "Detection")

        # --- TAB 5: OPTIMISATION ---
        optimization_tab = QWidget()
        optimization_layout = QVBoxLayout(optimization_tab)

        self.lbl_optimization_banner = QLabel("Optimisation mode inactive")
        self.lbl_optimization_banner.setStyleSheet(
            "padding: 8px 10px; border-radius: 8px; background: #334155; color: white; font-weight: bold;"
        )
        optimization_layout.addWidget(self.lbl_optimization_banner)

        optimization_scope_group = QGroupBox("Optimisation Setup")
        optimization_scope_form = QFormLayout(optimization_scope_group)
        self.chk_opt_detection = QCheckBox("Optimise detection gates")
        self.chk_opt_excitation = QCheckBox("Optimise excitation profile")
        scope_row = QWidget()
        scope_row_layout = QHBoxLayout(scope_row)
        scope_row_layout.setContentsMargins(0, 0, 0, 0)
        scope_row_layout.addWidget(self.chk_opt_detection)
        scope_row_layout.addWidget(self.chk_opt_excitation)
        scope_row_layout.addStretch()
        optimization_scope_form.addRow(scope_row)

        self.combo_optimization_mode = QComboBox()
        self.combo_optimization_mode.addItems(["Sequential"])
        self.combo_optimization_mode.hide()

        self.combo_optimization_first = QComboBox()
        self.combo_optimization_first.addItems(["Detection First", "Excitation First"])
        self.spin_optimization_iterations = QSpinBox()
        self.spin_optimization_iterations.setRange(1, 50)
        self.spin_optimization_iterations.setValue(20)
        optimization_scope_form.addRow(two_column_row("Run Order:", self.combo_optimization_first, "Max iterations:", self.spin_optimization_iterations))
        optimization_layout.addWidget(optimization_scope_group)

        optimization_view_group = QGroupBox("Optimisation Visualisation")
        optimization_view_form = QFormLayout(optimization_view_group)
        self.chk_optimization_realtime = QCheckBox("Real-time display")
        self.chk_optimization_realtime.setChecked(False)
        self.spin_optimization_steps_to_show = QSpinBox()
        self.spin_optimization_steps_to_show.setRange(2, 24)
        self.spin_optimization_steps_to_show.setValue(6)
        self.chk_optimization_validate_mc = QCheckBox("Run MC")
        self.chk_optimization_validate_mc.setChecked(False)
        optimization_view_row = QWidget()
        optimization_view_row_layout = QHBoxLayout(optimization_view_row)
        optimization_view_row_layout.setContentsMargins(0, 0, 0, 0)
        optimization_view_row_layout.addWidget(self.chk_optimization_realtime)
        optimization_view_row_layout.addSpacing(10)
        optimization_view_row_layout.addWidget(QLabel("Stored steps:"))
        optimization_view_row_layout.addWidget(self.spin_optimization_steps_to_show)
        optimization_view_row_layout.addSpacing(10)
        optimization_view_row_layout.addWidget(self.chk_optimization_validate_mc)
        optimization_view_row_layout.addStretch()
        optimization_view_form.addRow(optimization_view_row)
        optimization_layout.addWidget(optimization_view_group)

        detection_opt_group = QGroupBox("Detection Gate Optimisation")
        detection_opt_form = QFormLayout(detection_opt_group)
        self.combo_detection_algorithm = QComboBox()
        self.combo_detection_algorithm.addItems([
            "Fisher Compression",
            "Direct Mean F Minimisation",
            "Partition Theorem Bottom-Up",
            "Partition Theorem Top-Down",
        ])
        self.btn_detection_algorithm_settings = QToolButton()
        self.btn_detection_algorithm_settings.setText("⚙")
        self.btn_detection_algorithm_settings.setAutoRaise(True)
        self.btn_detection_algorithm_settings.setFixedWidth(28)
        self.btn_detection_algorithm_settings.clicked.connect(self._open_detection_algorithm_settings)
        self.detection_opt_restarts = 20
        self.detection_opt_ftol = 1e-4
        self.detection_opt_maxiter = 50
        self.detection_opt_fine_bins_per_gate = 12
        self.detection_opt_fine_bin_cap = 256
        self.detection_opt_fc_nuisance_aware = True
        self.detection_opt_fc_auto_compress = False
        self.detection_opt_fc_initial_gates = 16
        self.detection_opt_fc_min_gates = 2
        self.detection_opt_fc_max_f_loss_pct = 5.0
        algorithm_row = QWidget()
        algorithm_row_layout = QHBoxLayout(algorithm_row)
        algorithm_row_layout.setContentsMargins(0, 0, 0, 0)
        algorithm_row_layout.addWidget(self.combo_detection_algorithm, 1)
        algorithm_row_layout.addWidget(self.btn_detection_algorithm_settings)
        detection_opt_form.addRow("Algorithm:", algorithm_row)

        self.combo_detection_start_anchor = QComboBox()
        self.combo_detection_start_anchor.addItems(["Stick to 0", "Start after IRF", "Custom"])
        self.spin_detection_start_anchor = QDoubleSpinBox()
        self.spin_detection_start_anchor.setRange(0.0, 1000.0)
        self.spin_detection_start_anchor.setEnabled(False)
        detection_opt_form.addRow(two_column_row("First Gate Start:", self.combo_detection_start_anchor, "Custom Start (ns):", self.spin_detection_start_anchor))

        self.combo_detection_end_anchor = QComboBox()
        self.combo_detection_end_anchor.addItems(["Stick to period", "Custom"])
        self.spin_detection_end_anchor = QDoubleSpinBox()
        self.spin_detection_end_anchor.setRange(0.1, 1000.0)
        self.spin_detection_end_anchor.setValue(12.5)
        self.spin_detection_end_anchor.setEnabled(False)
        detection_opt_form.addRow(two_column_row("Last Gate End:", self.combo_detection_end_anchor, "Custom End (ns):", self.spin_detection_end_anchor))
        optimization_layout.addWidget(detection_opt_group)

        excitation_opt_group = QGroupBox("Excitation Optimisation")
        excitation_opt_form = QFormLayout(excitation_opt_group)
        self.combo_excitation_optimization_profile = QComboBox()
        self.combo_excitation_optimization_profile.addItems(["Gaussian", "Square", "Free Form"])
        self.combo_excitation_constraint = QComboBox()
        self.combo_excitation_constraint.addItems(["Fixed dose (area)", "Fixed peak"])
        self.combo_optimization_objective = QComboBox()
        self.combo_optimization_objective.addItems(["Fisher Information", "Fisher Throughput"])
        self.combo_optimization_objective.setCurrentText("Fisher Throughput")
        self.spin_optimization_fi_loss = QDoubleSpinBox()
        self.spin_optimization_fi_loss.setRange(0.0, 100.0)
        self.spin_optimization_fi_loss.setDecimals(2)
        self.spin_optimization_fi_loss.setSingleStep(0.5)
        self.spin_optimization_fi_loss.setValue(5.0)
        excitation_opt_form.addRow(
            two_column_row("Type:", self.combo_excitation_optimization_profile, "Constraint:", self.combo_excitation_constraint)
        )
        excitation_opt_form.addRow(
            two_column_row("Objective:", self.combo_optimization_objective, "Max F^-2 loss (%):", self.spin_optimization_fi_loss)
        )

        self.spin_excitation_width_min = QDoubleSpinBox()
        self.spin_excitation_width_min.setRange(0.0001, 1000.0)
        self.spin_excitation_width_min.setDecimals(6)
        self.spin_excitation_width_min.setSingleStep(0.0001)
        self.spin_excitation_width_min.setValue(0.05)
        self.spin_excitation_width_max = QDoubleSpinBox()
        self.spin_excitation_width_max.setRange(0.0001, 1000.0)
        self.spin_excitation_width_max.setDecimals(6)
        self.spin_excitation_width_max.setSingleStep(0.0001)
        self.spin_excitation_width_max.setValue(10.0)
        self.spin_excitation_control_points = QSpinBox()
        self.spin_excitation_control_points.setRange(3, 64)
        self.spin_excitation_control_points.setValue(8)
        excitation_row = QWidget()
        excitation_row_layout = QHBoxLayout(excitation_row)
        excitation_row_layout.setContentsMargins(0, 0, 0, 0)
        excitation_row_layout.addWidget(QLabel("Width min (ns):"))
        excitation_row_layout.addWidget(self.spin_excitation_width_min, 1)
        excitation_row_layout.addSpacing(8)
        excitation_row_layout.addWidget(QLabel("Max (ns):"))
        excitation_row_layout.addWidget(self.spin_excitation_width_max, 1)
        excitation_row_layout.addSpacing(8)
        excitation_row_layout.addWidget(QLabel("Control pts:"))
        excitation_row_layout.addWidget(self.spin_excitation_control_points, 1)
        excitation_opt_form.addRow(excitation_row)
        optimization_layout.addWidget(excitation_opt_group)

        self.lbl_optimization_current = QLabel("Current simulated value: baseline configuration")
        self.lbl_optimization_current.setWordWrap(True)
        optimization_layout.addWidget(self.lbl_optimization_current)

        self.txt_optimization_hint = QTextEdit()
        self.txt_optimization_hint.setReadOnly(True)
        self.txt_optimization_hint.setMaximumHeight(110)
        self.txt_optimization_hint.setPlainText(
            "Optimisation mode uses the Precision, MLE Accuracy, and Instrument Diagnostics widgets as the live "
            "workspace. Detection, excitation, throughput-aware selection, and joint sequential or iterative "
            "optimisation all run from this tab."
        )
        optimization_layout.addWidget(self.txt_optimization_hint)

        button_row = QWidget()
        button_row_layout = QHBoxLayout(button_row)
        button_row_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_run_optimization = QPushButton("RUN OPTIMISATION")
        self.btn_run_optimization.setStyleSheet("background-color: #166534; color: white; font-weight: bold;")
        button_row_layout.addWidget(self.btn_run_optimization)
        self.btn_exit_optimization = QPushButton("EXIT OPTIMISATION MODE")
        self.btn_exit_optimization.setStyleSheet("background-color: #991b1b; color: white; font-weight: bold;")
        self.btn_exit_optimization.setEnabled(False)
        button_row_layout.addWidget(self.btn_exit_optimization)
        optimization_layout.addWidget(button_row)

        objective_header = QWidget()
        objective_header_layout = QHBoxLayout(objective_header)
        objective_header_layout.setContentsMargins(0, 0, 0, 0)
        objective_header_layout.addWidget(QLabel("Objective History"))
        objective_header_layout.addStretch()
        self.btn_copy_optimization_objective = QPushButton("📋")
        self.btn_copy_optimization_objective.setToolTip("Copy objective-history plot to clipboard")
        self.btn_copy_optimization_objective.setMaximumWidth(30)
        self.btn_copy_optimization_objective.setStyleSheet("padding: 2px; font-size: 14px;")
        self.btn_copy_optimization_objective.clicked.connect(
            lambda: self._copy_widget_to_clipboard(self.optimization_objective_plot)
        )
        objective_header_layout.addWidget(self.btn_copy_optimization_objective)
        optimization_layout.addWidget(objective_header)

        self.optimization_objective_plot = pg.PlotWidget()
        self.optimization_objective_plot.setMinimumHeight(180)
        self.optimization_objective_plot.showGrid(x=True, y=True, alpha=0.25)
        self.optimization_objective_plot.setLabel("left", "Objective")
        self.optimization_objective_plot.setLabel("bottom", "Iteration")
        self.optimization_objective_plot.setLogMode(x=False, y=True)
        self.optimization_objective_curve = self.optimization_objective_plot.plot(
            pen=pg.mkPen("#ef4444", width=2),
            symbol="o",
            symbolSize=5,
            symbolBrush=pg.mkBrush("#ef4444"),
            symbolPen=pg.mkPen("#ef4444"),
        )
        optimization_layout.addWidget(self.optimization_objective_plot)

        best_f_header = QWidget()
        best_f_header_layout = QHBoxLayout(best_f_header)
        best_f_header_layout.setContentsMargins(0, 0, 0, 0)
        best_f_header_layout.addWidget(QLabel("Minimum F History"))
        best_f_header_layout.addStretch()
        self.btn_copy_optimization_best_f = QPushButton("📋")
        self.btn_copy_optimization_best_f.setToolTip("Copy minimum-F plot to clipboard")
        self.btn_copy_optimization_best_f.setMaximumWidth(30)
        self.btn_copy_optimization_best_f.setStyleSheet("padding: 2px; font-size: 14px;")
        self.btn_copy_optimization_best_f.clicked.connect(
            lambda: self._copy_widget_to_clipboard(self.optimization_best_f_plot)
        )
        best_f_header_layout.addWidget(self.btn_copy_optimization_best_f)
        optimization_layout.addWidget(best_f_header)

        self.optimization_best_f_plot = pg.PlotWidget()
        self.optimization_best_f_plot.setMinimumHeight(180)
        self.optimization_best_f_plot.showGrid(x=True, y=True, alpha=0.25)
        self.optimization_best_f_plot.setLabel("left", "Minimum F")
        self.optimization_best_f_plot.setLabel("bottom", "Iteration")
        self.optimization_best_f_plot.setLogMode(x=False, y=True)
        self.optimization_best_f_curve = self.optimization_best_f_plot.plot(
            pen=pg.mkPen("#22c55e", width=2),
            symbol="o",
            symbolSize=5,
            symbolBrush=pg.mkBrush("#22c55e"),
            symbolPen=pg.mkPen("#22c55e"),
        )
        optimization_layout.addWidget(self.optimization_best_f_plot)

        optimization_layout.addStretch()
        self.tabs.addTab(optimization_tab, "Optimisation")

        self.combo_detection_start_anchor.currentIndexChanged.connect(self._sync_optimization_ui)
        self.combo_detection_end_anchor.currentIndexChanged.connect(self._sync_optimization_ui)
        self.combo_detection_algorithm.currentIndexChanged.connect(self._sync_optimization_ui)
        self.combo_optimization_mode.currentIndexChanged.connect(self._sync_optimization_ui)
        self.combo_optimization_objective.currentIndexChanged.connect(self._sync_optimization_ui)
        self.combo_excitation_optimization_profile.currentIndexChanged.connect(self._sync_optimization_ui)
        self.chk_opt_detection.toggled.connect(self._sync_optimization_ui)
        self.chk_opt_excitation.toggled.connect(self._sync_optimization_ui)
        self._sync_optimization_ui()

        # --- TAB 6: BATCH SWEEP ---
        instr_tab = QWidget()
        instr_layout = QVBoxLayout(instr_tab)
        self.sweep_button_group = QButtonGroup(self)
        self.sweep_button_group.setExclusive(True)
        self.sweep_options = {}
        self.radio_sweep_off = QRadioButton("Off")
        self.sweep_button_group.addButton(self.radio_sweep_off)
        self.radio_sweep_off.toggled.connect(self._update_sweep_inputs_enabled)

        sweep_list_group = QGroupBox("Sweep Mode")
        sweep_list_layout = QVBoxLayout(sweep_list_group)
        sweep_list_layout.setContentsMargins(8, 8, 8, 8)
        sweep_list_layout.addWidget(self.radio_sweep_off)
        instr_layout.addWidget(sweep_list_group)

        self.sweep_detail_group = QGroupBox("Sweep Values")
        self.sweep_detail_form = QFormLayout(self.sweep_detail_group)
        self.lbl_sweep_detail_title = QLabel("Batch sweep disabled")
        self.sweep_detail_form.addRow("Mode:", self.lbl_sweep_detail_title)
        self.sweep_detail_stack = QStackedWidget()
        self.sweep_detail_form.addRow(self.sweep_detail_stack)
        instr_layout.addWidget(self.sweep_detail_group)

        def add_sweep_option(key, title, values_default, values_label="Values:",
                             extra_widget=None, extra_label=None):
            radio = QRadioButton(title)
            values_edit = QLineEdit(values_default)
            detail = QWidget()
            detail_layout = QFormLayout(detail)
            detail_layout.setContentsMargins(0, 0, 0, 0)
            detail_layout.addRow(values_label, values_edit)
            widgets = [values_edit]
            if extra_widget is not None and extra_label is not None:
                detail_layout.addRow(extra_label, extra_widget)
                widgets.append(extra_widget)
            sweep_list_layout.addWidget(radio)
            self.sweep_detail_stack.addWidget(detail)
            self.sweep_button_group.addButton(radio)
            self.sweep_options[key] = {
                "radio": radio,
                "title": title,
                "values": values_edit,
                "extra": extra_widget,
                "widgets": widgets,
                "detail": detail,
            }
            radio.toggled.connect(self._update_sweep_inputs_enabled)

        add_sweep_option("laser_pulse_fwhm_ns", "Laser Pulse (FWHM, ns)", "0.1, 0.2, 0.5")
        add_sweep_option("gate_edge_symmetric_ps", "Gate Rise/Fall Time (ps) - Symmetric Values", "25, 50, 100")
        gate_sharp_mode = QComboBox()
        gate_sharp_mode.addItems(["Sharp Rise, Sweep Fall", "Sharp Fall, Sweep Rise"])
        add_sweep_option(
            "gate_edge_one_sharp_ps",
            "Gate Rise/Fall Time (ps) - One Fixed to Sharp Rise or Fall",
            "25, 50, 100",
            extra_widget=gate_sharp_mode,
            extra_label="Mode:",
        )
        add_sweep_option("number_of_gates", "Number of Gates", "2, 4, 8, 16")
        add_sweep_option("burst_edge_symmetric_ns", "Burst Rise/Fall Time (ns) - Symmetric Values", "0.05, 0.1, 0.2")
        burst_sharp_mode = QComboBox()
        burst_sharp_mode.addItems(["Sharp Rise, Sweep Fall", "Sharp Fall, Sweep Rise"])
        add_sweep_option(
            "burst_edge_one_sharp_ns",
            "Burst Rise/Fall Time (ns) - One Fixed to Sharp Rise or Fall",
            "0.05, 0.1, 0.2",
            extra_widget=burst_sharp_mode,
            extra_label="Mode:",
        )

        self.radio_sweep_off.setChecked(True)
        self._update_sweep_inputs_enabled()

        instr_layout.addStretch()
        self.tabs.addTab(instr_tab, "Batch Sweep")

        tabs_container = QWidget()
        tabs_container_layout = QVBoxLayout(tabs_container)
        tabs_container_layout.setContentsMargins(0, 0, 0, 0)
        tabs_container_layout.addWidget(self.tabs)

        tabs_scroll = QScrollArea()
        tabs_scroll.setWidgetResizable(True)
        tabs_scroll.setWidget(tabs_container)
        layout.addWidget(tabs_scroll, 1)
        
        # --- UNIFIED ACTION AREA ---
        action_layout = QHBoxLayout()
        btn_height = 40
        
        self.btn_manage_inst = QPushButton("🔬 Profiles")
        self.btn_manage_inst.setMinimumHeight(btn_height)
        self.btn_manage_inst.setStyleSheet(
            "QPushButton { background-color: #374151; color: white; font-weight: bold; }"
            "QPushButton:disabled { background-color: #1f2937; color: #6b7280; }"
        )
        
        self.btn_precision = QPushButton("RUN")
        self.btn_precision.setStyleSheet(
            "QPushButton { background-color: #1e3a8a; color: white; font-weight: bold; }"
            "QPushButton:disabled { background-color: #1f2937; color: #6b7280; }"
        )
        self.btn_precision.setMinimumHeight(btn_height)
        
        self.btn_export = QPushButton("SAVE AS")
        self.btn_export.setStyleSheet("background-color: #334155; color: white; font-weight: bold;")
        self.btn_export.setMinimumHeight(btn_height)

        self.btn_simulate = QPushButton("TEST")
        self.btn_simulate.setStyleSheet(
            "QPushButton { background-color: #0d9488; color: white; font-weight: bold; }"
            "QPushButton:disabled { background-color: #1f2937; color: #6b7280; }"
        )
        self.btn_simulate.setMinimumHeight(btn_height)
        self.btn_simulate.setMinimumWidth(90)
        
        self.btn_interrupt = QPushButton("🛑")
        self.btn_interrupt.setFixedWidth(40)
        self.btn_interrupt.setMinimumHeight(btn_height)
        self.btn_interrupt.setStyleSheet("background-color: #7f1d1d; color: white;")
        
        action_layout.addWidget(self.btn_manage_inst, 1)
        action_layout.addWidget(self.btn_precision, 2)
        action_layout.addWidget(self.btn_interrupt, 0)
        action_layout.addWidget(self.btn_export, 1)
        action_layout.addWidget(self.btn_simulate, 1)
        
        layout.addLayout(action_layout)
        self._apply_tooltips()
        self.set_theme("dark")
        self.combo_gate_type.currentIndexChanged.connect(self._sync_gate_controls)
        self.spin_num_gates.valueChanged.connect(self._sync_gate_controls)
        self.edit_gate_widths.textChanged.connect(self._sync_gate_controls)
        self.radio_gate_irf.toggled.connect(self._sync_gate_controls)
        self.radio_gate_start.toggled.connect(self._sync_gate_controls)
        self.radio_gate_free.toggled.connect(self._sync_gate_controls)
        self.spin_gate_first.valueChanged.connect(self._sync_gate_controls)
        self.radio_gate_end_period.toggled.connect(self._sync_gate_controls)
        self.radio_gate_end_free.toggled.connect(self._sync_gate_controls)
        self.spin_gate_last.valueChanged.connect(self._sync_gate_controls)
        self.spin_period.valueChanged.connect(self._sync_gate_controls)
        self.combo_profile.currentIndexChanged.connect(self._sync_gate_controls)
        self.spin_fwhm.valueChanged.connect(self._sync_gate_controls)
        self.spin_irf_pos.valueChanged.connect(self._sync_gate_controls)
        self.spin_jitter.valueChanged.connect(self._sync_gate_controls)
        self.radio_overlap_jitter.toggled.connect(self._sync_gate_controls)
        self.radio_overlap_never.toggled.connect(self._sync_gate_controls)
        self.radio_overlap_yes.toggled.connect(self._sync_gate_controls)
        self._sync_gate_controls()

    def _compute_gate_anchor_start(self):
        t_start = 0.0
        jitter_ns = max(float(self.spin_jitter.value()), 0.0) / 1000.0
        if self.radio_gate_irf.isChecked():
            profile = self.combo_profile.currentText().lower()
            if profile == "gaussian":
                sigma_base = max(float(self.spin_fwhm.value()), 0.0) / 2.35482
                sigma_total = np.sqrt((sigma_base ** 2) + (jitter_ns ** 2))
                t_start = float(self.spin_irf_pos.value()) + (3.0 * sigma_total)
            elif profile == "ideal (dirac)":
                t_start = float(self.spin_irf_pos.value()) + (3.0 * jitter_ns)
            else:
                t_start = float(self.spin_irf_pos.value()) + float(self.spin_fwhm.value()) + (3.0 * jitter_ns)
        elif self.radio_gate_free.isChecked():
            t_start = float(self.spin_gate_first.value())
        return max(0.0, t_start)

    def _compute_gate_anchor_end(self):
        if self.radio_gate_end_free.isChecked():
            return max(float(self.spin_gate_last.value()), 0.0)
        return max(float(self.spin_period.value()), 0.0)

    @staticmethod
    def _parse_float_list(text):
        values = []
        raw = str(text).replace(";", ",").strip()
        if not raw:
            return values
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            values.append(float(token))
        return values

    def validate_gate_definition(self):
        gate_type = self.combo_gate_type.currentText().lower()
        start = self._compute_gate_anchor_start()
        end = self._compute_gate_anchor_end()
        if end <= start:
            return None, "The last gate edge must be larger than the first gate edge."

        if gate_type == "equal":
            n_gates = max(int(self.spin_num_gates.value()), 1)
            edges = np.linspace(start, end, n_gates + 1)
            return edges.tolist(), ""

        try:
            edges = self._parse_float_list(self.edit_gate_widths.text())
        except Exception:
            return None, "Gate edges must be a comma-separated list of numbers."

        if len(edges) < 2:
            return None, "Define at least two edges to create one or more custom gates."
        if any(edges[idx + 1] <= edges[idx] for idx in range(len(edges) - 1)):
            return None, "Gate edges must be strictly increasing."

        adjusted = list(edges)
        if not self.radio_gate_free.isChecked():
            adjusted[0] = start
        if not self.radio_gate_end_free.isChecked():
            adjusted[-1] = end
        if any(adjusted[idx + 1] <= adjusted[idx] for idx in range(len(adjusted) - 1)):
            return None, "Custom edges conflict with the selected start/end anchors."
        return adjusted, ""

    def _sync_gate_controls(self):
        gate_type = self.combo_gate_type.currentText().lower()
        edges, error = self.validate_gate_definition()
        self.lbl_gate_error.setText(error)

        is_custom = gate_type == "custom"
        self.spin_num_gates.setEnabled(not is_custom)
        self.edit_gate_widths.setReadOnly(not is_custom)
        self.label_gate_definition.setText("Gate Edges (ns):")

        if gate_type == "equal":
            self.edit_gate_widths.blockSignals(True)
            self.edit_gate_widths.setText(", ".join(f"{edge:g}" for edge in (edges or [])))
            self.edit_gate_widths.blockSignals(False)
        elif edges is not None:
            self.spin_num_gates.blockSignals(True)
            self.spin_num_gates.setValue(max(1, len(edges) - 1))
            self.spin_num_gates.blockSignals(False)
            if (not self.radio_gate_free.isChecked()) or (not self.radio_gate_end_free.isChecked()):
                self.edit_gate_widths.blockSignals(True)
                self.edit_gate_widths.setText(", ".join(f"{edge:g}" for edge in edges))
                self.edit_gate_widths.blockSignals(False)

        allow_overlap = not self.radio_overlap_never.isChecked()
        self.spin_gate_overlap.setVisible(self.radio_overlap_yes.isChecked())
        self.spin_gate_overlap.setEnabled(self.radio_overlap_yes.isChecked())
        for widget in (
            self.radio_overlap_effect_exclusive,
            self.radio_overlap_effect_duplicate,
            self.radio_overlap_effect_independent,
        ):
            widget.setEnabled(allow_overlap)
        if not allow_overlap:
            self.radio_overlap_effect_exclusive.setChecked(True)

    def _handle_x_selection(self):
        """Ensures exclusive selection (Radio button behavior)."""
        sender = self.sender()
        if not sender.isChecked():
            # If user tries to uncheck the ONLY checked box, turn it back on
            sender.setChecked(True)
            return
        
        # Uncheck all others
        selected_name = sender.property("param_name")
        for name, chk in self.x_group.items():
            if chk != sender:
                chk.setChecked(False)
            if name in self.param_rows:
                self.param_rows[name]['fix'].setChecked(name != selected_name)
        self._apply_default_x_range(selected_name)
        self._apply_default_x_scale(selected_name)

    def _apply_default_x_range(self, param_name):
        if param_name not in self.default_x_ranges:
            return
        min_val, max_val = self.default_x_ranges[param_name]
        self.spin_fx_min.setValue(min_val)
        self.spin_fx_max.setValue(max_val)

    def _apply_default_x_scale(self, param_name):
        if param_name not in self.default_x_scales:
            return
        self.combo_fx_scale.setCurrentText(self.default_x_scales[param_name])

    def _apply_tooltips(self):
        self.tabs.setTabToolTip(0, "Decay model, precision target, Monte Carlo validation, and bootstrap settings.")
        self.tabs.setTabToolTip(1, "Synthetic image generation settings.")
        self.tabs.setTabToolTip(2, "Excitation and IRF definition.")
        self.tabs.setTabToolTip(3, "Detector and gating settings.")
        self.tabs.setTabToolTip(4, "Detection and excitation optimisation settings.")
        self.tabs.setTabToolTip(5, "Instrument batch sweeps for comparative precision runs.")

        tooltips = {
            self.spin_n_comp: "Number of decay components used in the forward and inverse model.",
            self.spin_fx_min: "Minimum value of the swept target parameter.",
            self.spin_fx_max: "Maximum value of the swept target parameter.",
            self.spin_fx_steps: "Number of points in the precision sweep.",
            self.spin_grid_fine_factor: "Refinement factor used to build the gridded MLE lookup axis.",
            self.combo_fx_scale: "Spacing of the target-parameter sweep values.",
            self.chk_validate_mc: "Run Monte Carlo validation alongside the theoretical Fisher calculation.",
            self.chk_compute_ci: "Bootstrap the Monte Carlo repeats to estimate a confidence interval for F or F^-2.",
            self.spin_precision_photons: "Photon count used in Fisher and Monte Carlo precision analysis.",
            self.spin_mc_repeats: "Number of Monte Carlo repeats per point on the precision sweep.",
            self.spin_accuracy_pvalue: "Bootstrap-based p-value threshold used to judge estimator accuracy.",
            self.spin_bootstrap_samples: "Number of bootstrap resamples used for p-values and confidence intervals.",
            self.spin_ci_level: "Confidence level used for the Monte Carlo interval display.",
            self.spin_photons: "Average photon budget for synthetic image generation.",
            self.spin_image_repeats: "Requested number of Monte Carlo-style repeats represented for each swept x-axis value.",
            self.combo_image_fit_method: "Lifetime-fitting backend for the validation image.",
            self.btn_fit_image: "Fit the generated validation image using the selected algorithm.",
            self.spin_period: "Measurement repetition period in nanoseconds.",
            self.chk_decay_wrap: "Include decay wrapping from previous periods in the model.",
            self.combo_profile: "Excitation or IRF profile used in the forward model.",
            self.spin_fwhm: "IRF width for Gaussian mode or pulse duration for rectangular mode.",
            self.spin_irf_pos: "IRF temporal position within the period.",
            self.spin_rise: "Rising edge time for rectangular excitation profiles.",
            self.spin_fall: "Falling edge time for rectangular excitation profiles.",
            self.group_burst: "Enable and configure burst excitation sub-pulses.",
            self.spin_burst_period: "Peak-to-peak distance between sub-pulses in the burst (ps).",
            self.spin_burst_fwhm: "Pulse-width (FWHM) of each sub-pulse in the burst (ps).",
            self.spin_jitter: "Detector timing jitter in picoseconds.",
            self.spin_deadtime: "Detector deadtime in nanoseconds.",
            self.chk_multihit: "Allow more than one detected photon per excitation cycle.",
            self.spin_num_gates: "Number of detector gates across the measurement period.",
            self.combo_gate_type: "Gate construction mode.",
            self.edit_gate_widths: "Comma-separated gate edges in nanoseconds. In Equal mode this field shows the generated edges; in Custom mode you can edit them directly.",
            self.lbl_gate_error: "Inline validation message for the custom gate-edge definition.",
            self.spin_gate_rise: "Gate opening edge transition width, defined as the standard deviation (sigma) of a Gaussian transition.",
            self.spin_gate_fall: "Gate closing edge transition width, defined as the standard deviation (sigma) of a Gaussian transition.",
            self.radio_gate_irf: "Start the first gate after the IRF tail.",
            self.radio_gate_start: "Start the first gate at time zero.",
            self.radio_gate_free: "Use a user-defined first gate start time.",
            self.spin_gate_first: "Manual start time for the first gate when Free is selected.",
            self.radio_gate_end_period: "Force the final gate edge to coincide with the measurement period.",
            self.radio_gate_end_free: "Use a user-defined final gate edge.",
            self.spin_gate_last: "Manual end time for the last gate when Free is selected.",
            self.radio_gate_collection_hist: "Histogram-style gating: photons are binned into gates without being discarded.",
            self.radio_gate_collection_seq: "Sequential gating: each gate is acquired in a separate pass and photons outside the active gate are lost in that pass.",
            self.radio_overlap_jitter: "Allow only the natural overlap caused by jittered or skewed gate tails.",
            self.radio_overlap_never: "Do not allow gate overlap. Overlapping tails are clipped and can create photon-loss gaps between gates.",
            self.radio_overlap_yes: "Allow user-specified geometric overlap between adjacent gates.",
            self.spin_gate_overlap: "Overlap added to each gate in nanoseconds when explicit overlap is enabled.",
            self.radio_overlap_effect_exclusive: "Overlapped photons contribute to only one gate.",
            self.radio_overlap_effect_duplicate: "Overlapped photons can appear in more than one gate, but do not improve photon statistics.",
            self.radio_overlap_effect_independent: "Overlapped photons are treated as independent duplicated counts and improve Fisher Information.",
            self.chk_gate_wraparound: "Wrap gate tails around the repetition period. Disable to clip tails at the period boundaries.",
            self.chk_opt_detection: "Enable optimisation of detection gate boundaries.",
            self.chk_opt_excitation: "Enable optimisation of the excitation waveform or width.",
            self.combo_optimization_mode: "Joint optimisation now alternates sequentially; this hidden compatibility control remains fixed to Sequential.",
            self.combo_optimization_first: "When both optimisations are enabled, choose which one runs first in the alternating sequential loop.",
            self.spin_optimization_iterations: "Maximum number of alternating detection/excitation rounds when both optimisation targets are enabled.",
            self.combo_optimization_objective: "Excitation optimisation objective. Fisher Throughput is the default and combines peak photon efficiency with throughput scaling.",
            self.spin_optimization_fi_loss: "Maximum absolute peak photon-efficiency loss allowed in throughput mode, expressed as F^-2 percentage points relative to the Dirac-reference design.",
            self.chk_optimization_realtime: "When enabled, update the main analysis widgets during optimisation. Disable this for a faster run.",
            self.spin_optimization_steps_to_show: "Number of optimisation states to retain for the final Precision, Accuracy, and Diagnostics displays, including start and finish.",
            self.chk_optimization_validate_mc: "Run Monte Carlo validation for the retained optimisation states after the numerical optimisation has finished.",
            self.combo_detection_algorithm: "Detection-gate optimisation algorithm family. Fisher Compression is the default strategy.",
            self.btn_detection_algorithm_settings: "Open advanced settings for the currently selected detection-gate optimiser.",
            self.combo_detection_start_anchor: "Constrain where the first optimised gate starts.",
            self.spin_detection_start_anchor: "Custom start time for the first gate when the anchor is set to Custom.",
            self.combo_detection_end_anchor: "Constrain where the last optimised gate ends.",
            self.spin_detection_end_anchor: "Custom end time for the last gate when the anchor is set to Custom.",
            self.combo_excitation_optimization_profile: "Excitation profile family to optimise.",
            self.combo_excitation_constraint: "Choose whether excitation optimisation preserves pulse area or preserves peak amplitude.",
            self.spin_excitation_width_min: "Lower width bound in nanoseconds for Gaussian or square excitation optimisation. Supports values down to 0.0001 ns (100 fs).",
            self.spin_excitation_width_max: "Upper width bound in nanoseconds for Gaussian or square excitation optimisation. Supports values down to 0.0001 ns (100 fs).",
            self.spin_excitation_control_points: "Number of control points for free-form excitation optimisation.",
            self.txt_optimization_hint: "Execution note for the current optimisation implementation status.",
            self.btn_run_optimization: "Run the currently supported optimisation workflow from the Optimisation tab.",
            self.btn_exit_optimization: "Exit optimisation mode by clearing the optimisation targets.",
            self.radio_sweep_off: "Disable instrument batch sweeping.",
            self.btn_manage_inst: "Open the instrument-profile manager.",
            self.btn_precision: "Run the theory and optional Monte Carlo precision workflow.",
            self.btn_interrupt: "Request interruption of the current run.",
            self.btn_export: "Preview the latest precision report and save it as an HTML package with SVG and CSV assets.",
            self.btn_simulate: "Generate a synthetic validation image using the swept x-axis parameter.",
        }
        for widget, text in tooltips.items():
            widget.setToolTip(text)

        for name, row in self.param_rows.items():
            row["val"].setToolTip(f"Nominal value for {name} in the current model.")
            row["fix"].setToolTip(f"Keep {name} fixed during inverse estimation.")

        for spec in self.sweep_options.values():
            spec["radio"].setToolTip(f"Activate the batch sweep mode: {spec['title']}.")
            spec["values"].setToolTip("Comma-separated sweep values for this instrument parameter.")
            if spec["extra"] is not None:
                spec["extra"].setToolTip(f"Additional option for {spec['title']}.")

    def enforce_single_x_selection(self):
        """Ensures that at least one visible checkbox is selected."""
        checked = [name for name, chk in self.x_group.items() if chk.isChecked() and chk.isVisible()]
        if not checked:
            # Fallback to tau1 which is always visible
            for name, chk in self.x_group.items():
                chk.setChecked(name == "tau1")
            checked = ["tau1"]
        selected_name = checked[0]
        for name, row in self.param_rows.items():
            if row['x'].isVisible():
                row['fix'].setChecked(name != selected_name)

    def update_param_visibility(self):
        """Hides parameters not used in current model architecture."""
        model = self.combo_decay_model.currentText().lower()
        n = self.spin_n_comp.value()
        
        # Mapping parameter names to visibility rules
        # tau1: always
        # tau2: if n > 1
        # alpha: if n > 1
        # bg: always
        # beta: if model == 'stretched'
        
        rules = {
            "tau1": True,
            "tau2": n > 1,
            "alpha": n > 1,
            "background": True,
            "beta": model == "stretched"
        }
        
        for name, visible in rules.items():
            row = self.param_rows[name]
            row['label'].setVisible(visible)
            # Find the actual row in the form layout
            # Widgets in the layout are the label and the QHBoxLayout container
            # We must also hide the individual widgets in the layout
            for i in range(row['layout'].count()):
                w = row['layout'].itemAt(i).widget()
                if w: w.setVisible(visible)
            
            # If a parameter becomes invisible but was the X-axis, 
            # we must move X-axis to a visible one
            if not visible and row['x'].isChecked():
                row['x'].setChecked(False)
        
        self.enforce_single_x_selection()

    def _update_detection_algorithm_settings_tooltip(self):
        algorithm = self.combo_detection_algorithm.currentText().lower()
        if algorithm == "direct mean f minimisation":
            text = (
                "Direct optimiser settings.\n"
                f"Restarts: {int(self.detection_opt_restarts)}\n"
                f"SLSQP ftol: {float(self.detection_opt_ftol):.2g}\n"
                f"Max iterations per restart: {int(self.detection_opt_maxiter)}"
            )
        elif algorithm in {"partition theorem bottom-up", "partition theorem top-down"}:
            text = (
                "Partition optimiser settings.\n"
                f"Fine bins per gate: {int(self.detection_opt_fine_bins_per_gate)}\n"
                f"Fine-bin cap: {int(self.detection_opt_fine_bin_cap)}"
            )
        else:
            text = (
                "Fisher Compression settings.\n"
                f"Fine bins per gate: {int(self.detection_opt_fine_bins_per_gate)}\n"
                f"Fine-bin cap: {int(self.detection_opt_fine_bin_cap)}\n"
                f"Nuisance-aware: {'On' if self.detection_opt_fc_nuisance_aware else 'Off'}\n"
                f"Auto-compress: {'On' if self.detection_opt_fc_auto_compress else 'Off'}\n"
                f"Initial gates: {int(self.detection_opt_fc_initial_gates)}\n"
                f"Minimum gates: {int(self.detection_opt_fc_min_gates)}\n"
                f"Max F^-2 loss: {float(self.detection_opt_fc_max_f_loss_pct):g}%"
            )
        self.btn_detection_algorithm_settings.setToolTip(text)

    def _open_detection_algorithm_settings(self):
        dialog = QDialog(self)
        algorithm = self.combo_detection_algorithm.currentText().lower()
        dialog.setWindowTitle(f"{self.combo_detection_algorithm.currentText()} Settings")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        widgets = {}

        if algorithm == "direct mean f minimisation":
            spin_restarts = QSpinBox()
            spin_restarts.setRange(1, 200)
            spin_restarts.setValue(int(self.detection_opt_restarts))
            spin_restarts.setToolTip("Number of random optimiser restarts for the direct mean-F search.")
            form.addRow("Restarts:", spin_restarts)
            widgets["restarts"] = spin_restarts

            spin_ftol = QDoubleSpinBox()
            spin_ftol.setRange(1e-8, 1e-1)
            spin_ftol.setDecimals(8)
            spin_ftol.setSingleStep(1e-4)
            spin_ftol.setValue(float(self.detection_opt_ftol))
            spin_ftol.setToolTip("SLSQP convergence tolerance for each restart.")
            form.addRow("SLSQP ftol:", spin_ftol)
            widgets["ftol"] = spin_ftol

            spin_maxiter = QSpinBox()
            spin_maxiter.setRange(5, 500)
            spin_maxiter.setValue(int(self.detection_opt_maxiter))
            spin_maxiter.setToolTip("Maximum SLSQP iterations allowed within each restart.")
            form.addRow("Max iterations per restart:", spin_maxiter)
            widgets["maxiter"] = spin_maxiter
        else:
            spin_fine_bins = QSpinBox()
            spin_fine_bins.setRange(2, 64)
            spin_fine_bins.setValue(int(self.detection_opt_fine_bins_per_gate))
            spin_fine_bins.setToolTip("Number of fine histogram bins allocated per requested gate before partition optimisation.")
            form.addRow("Fine bins per gate:", spin_fine_bins)
            widgets["fine_bins"] = spin_fine_bins

            spin_fine_cap = QSpinBox()
            spin_fine_cap.setRange(24, 2048)
            spin_fine_cap.setSingleStep(8)
            spin_fine_cap.setValue(int(self.detection_opt_fine_bin_cap))
            spin_fine_cap.setToolTip("Upper limit for the fine histogram used internally by the partition or compression solver.")
            form.addRow("Fine-bin cap:", spin_fine_cap)
            widgets["fine_cap"] = spin_fine_cap

            if algorithm == "fisher compression":
                chk_nuisance = QCheckBox("Use nuisance-aware effective FI (Schur complement)")
                chk_nuisance.setChecked(bool(self.detection_opt_fc_nuisance_aware))
                chk_nuisance.setToolTip("Project the parameter of interest against unfixed nuisance parameters using the Schur complement before computing Fisher Compression segment costs.")
                form.addRow(chk_nuisance)
                widgets["nuisance"] = chk_nuisance

                chk_auto = QCheckBox("Auto-compress until max F^-2 loss")
                chk_auto.setChecked(bool(self.detection_opt_fc_auto_compress))
                chk_auto.setToolTip("Start from a finer optimised partition and reduce the gate count until the peak photon-efficiency loss exceeds the chosen absolute F^-2 limit.")
                form.addRow(chk_auto)
                widgets["auto"] = chk_auto

                spin_initial_gates = QSpinBox()
                spin_initial_gates.setRange(2, 512)
                spin_initial_gates.setValue(int(self.detection_opt_fc_initial_gates))
                spin_initial_gates.setToolTip("Initial number of gates for the finer Fisher-compression partition before compression begins.")
                form.addRow("Initial gates:", spin_initial_gates)
                widgets["initial_gates"] = spin_initial_gates

                spin_min_gates = QSpinBox()
                spin_min_gates.setRange(1, 512)
                spin_min_gates.setValue(int(self.detection_opt_fc_min_gates))
                spin_min_gates.setToolTip("Smallest gate count the auto-compression loop is allowed to reach.")
                form.addRow("Minimum gates:", spin_min_gates)
                widgets["min_gates"] = spin_min_gates

                spin_loss = QDoubleSpinBox()
                spin_loss.setRange(0.0, 100.0)
                spin_loss.setDecimals(3)
                spin_loss.setSingleStep(0.5)
                spin_loss.setValue(float(self.detection_opt_fc_max_f_loss_pct))
                spin_loss.setToolTip("Maximum allowed absolute peak photon-efficiency loss, expressed as F^-2 percentage points, compared with the initial finer optimised partition.")
                form.addRow("Max F^-2 loss (%):", spin_loss)
                widgets["max_loss"] = spin_loss

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec():
            if "restarts" in widgets:
                self.detection_opt_restarts = int(widgets["restarts"].value())
                self.detection_opt_ftol = float(widgets["ftol"].value())
                self.detection_opt_maxiter = int(widgets["maxiter"].value())
            else:
                self.detection_opt_fine_bins_per_gate = int(widgets["fine_bins"].value())
                self.detection_opt_fine_bin_cap = int(widgets["fine_cap"].value())
                if "auto" in widgets:
                    self.detection_opt_fc_nuisance_aware = bool(widgets["nuisance"].isChecked())
                    self.detection_opt_fc_auto_compress = bool(widgets["auto"].isChecked())
                    self.detection_opt_fc_initial_gates = int(widgets["initial_gates"].value())
                    self.detection_opt_fc_min_gates = int(widgets["min_gates"].value())
                    self.detection_opt_fc_max_f_loss_pct = float(widgets["max_loss"].value())
            self._update_detection_algorithm_settings_tooltip()

    def _on_tab_changed(self, index):
        # Map tab index to manual section ID
        mapping = {
            0: "controller", # Decay Model
            1: "simulation", # Images
            2: "math",       # Excitation
            3: "math",       # Detection
            4: "controller", # Optimization
            5: "fisher"      # Batch Sweep
        }
        section = mapping.get(index, "intro")
        self.context_changed.emit(section)

    def _sync_optimization_ui(self, *_args):
        detection_enabled = self.chk_opt_detection.isChecked()
        excitation_enabled = self.chk_opt_excitation.isChecked()
        optimisation_active = detection_enabled or excitation_enabled
        multi_target = detection_enabled and excitation_enabled
        throughput_mode = self.combo_optimization_objective.currentText().lower().startswith("fisher throughput")
        free_form = self.combo_excitation_optimization_profile.currentText().lower() == "free form"
        selected_algorithm = self.combo_detection_algorithm.currentText().lower()
        self.combo_optimization_mode.setEnabled(False)
        self.combo_optimization_first.setEnabled(multi_target)
        self.spin_optimization_iterations.setEnabled(multi_target)
        self.combo_optimization_objective.setEnabled(excitation_enabled)
        self.spin_optimization_fi_loss.setEnabled(excitation_enabled and throughput_mode)

        self.combo_detection_algorithm.setEnabled(detection_enabled)
        self.btn_detection_algorithm_settings.setEnabled(
            detection_enabled and selected_algorithm in {
                "fisher compression",
                "direct mean f minimisation",
                "partition theorem bottom-up",
                "partition theorem top-down",
            }
        )
        self.combo_detection_start_anchor.setEnabled(detection_enabled)
        self.combo_detection_end_anchor.setEnabled(detection_enabled)
        self.spin_detection_start_anchor.setEnabled(
            detection_enabled and self.combo_detection_start_anchor.currentText().lower() == "custom"
        )
        self.spin_detection_end_anchor.setEnabled(
            detection_enabled and self.combo_detection_end_anchor.currentText().lower() == "custom"
        )

        self.combo_excitation_optimization_profile.setEnabled(excitation_enabled)
        self.combo_excitation_constraint.setEnabled(excitation_enabled)
        self.spin_excitation_width_min.setEnabled(excitation_enabled and not free_form)
        self.spin_excitation_width_max.setEnabled(excitation_enabled and not free_form)
        self.spin_excitation_control_points.setEnabled(excitation_enabled and free_form)
        self.chk_optimization_realtime.setEnabled(optimisation_active)
        self.spin_optimization_steps_to_show.setEnabled(optimisation_active)
        self.chk_optimization_validate_mc.setEnabled(optimisation_active)
        self.btn_run_optimization.setEnabled(optimisation_active and not self.optimization_running_state)
        self.btn_exit_optimization.setEnabled(optimisation_active and not self.optimization_running_state)
        self._update_detection_algorithm_settings_tooltip()
        self.set_optimization_mode_active(optimisation_active, running=self.optimization_running_state)

    def _update_irf_ui(self, index=0):
        """Toggles visibility based on profile (Gaussian vs Rectangular)."""
        mode = self.combo_profile.currentText().lower()
        is_rect = "rectangular" in mode
        is_free_form = "free form" in mode
        self.label_rise.setVisible(is_rect); self.spin_rise.setVisible(is_rect)
        self.label_fall.setVisible(is_rect); self.spin_fall.setVisible(is_rect)
        
        if is_rect or is_free_form:
            self.label_irf_pos.setText("Position (Start ns):")
        else:
            self.label_irf_pos.setText("Position (Center ns):")

    def update_gridded_mle_summary(self):
        use_log_grid = (
            self.combo_fx_scale.currentText().lower() == "log"
            and self.get_selected_x_param() in {"tau1", "tau2", "beta"}
            and self.spin_fx_min.value() > 0
            and self.spin_fx_max.value() > 0
        )
        if use_log_grid:
            step_ratio = (self.spin_fx_max.value() / self.spin_fx_min.value()) ** (1.0 / max(1, self.spin_fx_steps.value() - 1))
            pad_factor = max(step_ratio, 1.25)
            grid_min = max(1e-6, self.spin_fx_min.value() / pad_factor)
            grid_max = max(grid_min * 1.0001, self.spin_fx_max.value() * pad_factor)
            grid_scale = "Log"
        else:
            coarse_step = (self.spin_fx_max.value() - self.spin_fx_min.value()) / max(1, self.spin_fx_steps.value() - 1)
            grid_min = max(1e-6, self.spin_fx_min.value() - coarse_step)
            grid_max = self.spin_fx_max.value() + coarse_step
            grid_scale = "Linear"
        grid_steps = max(3, ((self.spin_fx_steps.value() - 1) + 2) * self.spin_grid_fine_factor.value() + 1)
        self.lbl_grid_min.setText(f"{grid_min:.3f}")
        self.lbl_grid_max.setText(f"{grid_max:.3f}")
        self.lbl_grid_steps.setText(f"{grid_steps}")
        self.lbl_grid_scale.setText(grid_scale)

    def update_image_validation_summary(self):
        param_name = self.get_selected_x_param()
        self.lbl_image_param.setText(param_name)
        self.lbl_image_x_summary.setText(
            f"Min {self.spin_fx_min.value():.3f} | Max {self.spin_fx_max.value():.3f} | Steps {self.spin_fx_steps.value()}"
        )
        n_values = max(int(self.spin_fx_steps.value()), 1)
        target_repeats = max(int(self.spin_image_repeats.value()), 1)
        total_pixels = n_values * target_repeats
        side = max(int(np.ceil(np.sqrt(total_pixels))), 1)
        band_width = max(int(np.ceil(side / n_values)), 1)
        x_pixels = max(n_values * band_width, n_values)
        y_pixels = max(int(np.ceil(total_pixels / x_pixels)), 1)
        if y_pixels > 10:
            y_pixels = int(np.ceil(y_pixels / 10.0) * 10)
        self.lbl_image_x_pixels.setText(str(x_pixels))
        self.lbl_image_y_pixels.setText(str(y_pixels))
        self.lbl_image_band_width.setText(str(band_width))
        self.lbl_image_effective_repeats.setText(str(band_width * y_pixels))

    def get_selected_x_param(self):
        for name, chk in self.x_group.items():
            if chk.isChecked():
                return name
        return "tau1"

    def _update_sweep_inputs_enabled(self):
        batch_enabled = not self.radio_sweep_off.isChecked()
        active_spec = None
        for spec in self.sweep_options.values():
            active = batch_enabled and spec["radio"].isChecked()
            for widget in spec["widgets"]:
                widget.setEnabled(active)
            if active:
                active_spec = spec
        if active_spec is None:
            self.lbl_sweep_detail_title.setText("Batch sweep disabled")
            self.sweep_detail_stack.hide()
        else:
            self.lbl_sweep_detail_title.setText(active_spec["title"])
            self.sweep_detail_stack.show()
            self.sweep_detail_stack.setCurrentWidget(active_spec["detail"])

    def get_selected_sweep_param(self):
        for key, spec in self.sweep_options.items():
            if spec["radio"].isChecked():
                return key
        return "laser_pulse_fwhm_ns"

    def get_selected_sweep_values_text(self):
        spec = self.sweep_options.get(self.get_selected_sweep_param())
        return spec["values"].text() if spec else ""

    def _sync_precision_execution_ui(self, mc_enabled):
        self.chk_compute_ci.setEnabled(mc_enabled)
        self.spin_mc_repeats.setEnabled(mc_enabled)
        self.spin_accuracy_pvalue.setEnabled(mc_enabled)
        self.spin_bootstrap_samples.setEnabled(mc_enabled)
        self.spin_ci_level.setEnabled(mc_enabled and self.chk_compute_ci.isChecked())

    def update_from_config(self, cfg):
        self.blockSignals(True)
        try:
            # Decay model / sweep controls
            decay_model_map = {
                "exponential": "Exponential",
                "stretched": "Stretched",
                "custom": "Custom",
            }
            self.combo_decay_model.setCurrentText(decay_model_map.get(cfg.decay_model, "Exponential"))
            self.spin_n_comp.setValue(cfg.n_components)
            self.chk_pulse_train_decay.setChecked(cfg.b_decay_wrapping)
            self.spin_fx_min.setValue(cfg.f_x_min)
            self.spin_fx_max.setValue(cfg.f_x_max)
            self.spin_fx_steps.setValue(cfg.f_x_steps)
            self.spin_grid_fine_factor.setValue(cfg.grid_fine_factor)
            scale_map = {"log": "Log", "linear": "Linear", "exp": "Exponential"}
            self.combo_fx_scale.setCurrentText(scale_map.get(cfg.f_x_scale, "Log"))
            self.chk_validate_mc.setChecked(cfg.precision_validate_mc)
            self.chk_compute_ci.setChecked(getattr(cfg, "precision_compute_ci", False))
            self.spin_precision_photons.setValue(cfg.precision_photons)
            self.spin_mc_repeats.setValue(cfg.precision_mc_repeats)
            self.spin_accuracy_pvalue.setValue(getattr(cfg, "precision_accuracy_pvalue", 0.001))
            self.spin_bootstrap_samples.setValue(getattr(cfg, "precision_bootstrap_samples", 2000))
            self.spin_ci_level.setValue(getattr(cfg, "precision_ci_level", 95.0))

            # Laser / Physics
            self.spin_period.setValue(cfg.period)
            self.chk_decay_wrap.setChecked(cfg.b_decay_wrapping)
            profile_map = {
                "gaussian": "Gaussian",
                "rectangular": "Rectangular",
                "free_form": "Free Form",
                "ideal (dirac)": "Ideal (Dirac)",
            }
            self.combo_profile.setCurrentText(profile_map.get(cfg.irf_profile, "Gaussian"))
            self.spin_fwhm.setValue(cfg.irf_fwhm)
            self.spin_irf_pos.setValue(cfg.irf_position)
            self.spin_rise.setValue(cfg.irf_rise_time)
            self.spin_fall.setValue(cfg.irf_fall_time)
            
            # Burst Excitation
            self.group_burst.setChecked(cfg.burst_enabled)
            self.spin_burst_period.setValue(cfg.burst_sub_period * 1000.0) # ns to ps
            self.spin_burst_fwhm.setValue(cfg.burst_sub_fwhm * 1000.0) # ns to ps

            # Model params (dynamic rows)
            p_map = {"tau1": cfg.taus[0], "tau2": cfg.taus[1] if len(cfg.taus)>1 else 1.0,
                    "alpha": cfg.amplitudes[0], "background": cfg.background_level, "beta": cfg.beta}
            for name, val in p_map.items():
                if name in self.param_rows:
                    self.param_rows[name]['val'].setValue(val)
                    self.param_rows[name]['fix'].setChecked(cfg.fixed_params.get(name, False))
                    self.param_rows[name]['x'].setChecked(cfg.f_x_param == name)
            
            # Gating alignment
            gate_type_map = {"equal": "Equal", "custom": "Custom"}
            self.spin_num_gates.setValue(max(2, len(cfg.gate_edges) - 1))
            self.combo_gate_type.setCurrentText(gate_type_map.get(cfg.gate_type, "Equal"))
            self.edit_gate_widths.setText(", ".join(f"{edge:g}" for edge in cfg.gate_edges))
            self.spin_gate_rise.setValue(cfg.gate_rise)
            self.spin_gate_fall.setValue(getattr(cfg, "gate_fall", cfg.gate_rise))
            self.spin_gate_first.setValue(cfg.gate_first_start)
            if cfg.gate_start_mode == "irf_3sigma": self.radio_gate_irf.setChecked(True)
            elif cfg.gate_start_mode == "start": self.radio_gate_start.setChecked(True)
            elif cfg.gate_start_mode == "free": self.radio_gate_free.setChecked(True)
            self.spin_gate_last.setValue(getattr(cfg, "gate_last_end", cfg.period))
            if getattr(cfg, "gate_end_mode", "period") == "free":
                self.radio_gate_end_free.setChecked(True)
            else:
                self.radio_gate_end_period.setChecked(True)
            if getattr(cfg, "gate_collection_mode", "histogram") == "sequential":
                self.radio_gate_collection_seq.setChecked(True)
            else:
                self.radio_gate_collection_hist.setChecked(True)
            overlap_mode = getattr(cfg, "gate_overlap_mode", "jitter_only")
            if overlap_mode == "never":
                self.radio_overlap_never.setChecked(True)
            elif overlap_mode == "allow":
                self.radio_overlap_yes.setChecked(True)
            else:
                self.radio_overlap_jitter.setChecked(True)
            self.spin_gate_overlap.setValue(getattr(cfg, "gate_overlap_ns", 0.0))
            overlap_effect = getattr(cfg, "gate_overlap_effect", "exclusive")
            if overlap_effect == "duplicate_events":
                self.radio_overlap_effect_duplicate.setChecked(True)
            elif overlap_effect == "independent_duplicates":
                self.radio_overlap_effect_independent.setChecked(True)
            else:
                self.radio_overlap_effect_exclusive.setChecked(True)
            self.chk_gate_wraparound.setChecked(getattr(cfg, "gate_wraparound", True))

            # Optimization
            self.chk_opt_detection.setChecked(getattr(cfg, "optimize_detection_gates", False))
            self.chk_opt_excitation.setChecked(getattr(cfg, "optimize_excitation_profile", False))
            optimization_mode_map = {"sequential": "Sequential", "iterative": "Iterative"}
            self.combo_optimization_mode.setCurrentText(
                optimization_mode_map.get(getattr(cfg, "optimization_mode", "sequential"), "Sequential")
            )
            optimization_first_map = {"detection": "Detection First", "excitation": "Excitation First"}
            self.combo_optimization_first.setCurrentText(
                optimization_first_map.get(getattr(cfg, "optimization_first", "detection"), "Detection First")
            )
            self.spin_optimization_iterations.setValue(getattr(cfg, "optimization_iterations", 20))
            optimization_objective_map = {
                "fisher_information": "Fisher Information",
                "fisher_throughput": "Fisher Throughput",
            }
            self.combo_optimization_objective.setCurrentText(
                optimization_objective_map.get(getattr(cfg, "optimization_objective", "fisher_throughput"), "Fisher Throughput")
            )
            self.spin_optimization_fi_loss.setValue(getattr(cfg, "optimization_max_fi_loss_pct", 5.0))
            self.chk_optimization_realtime.setChecked(getattr(cfg, "optimization_realtime_visualization", False))
            self.spin_optimization_steps_to_show.setValue(getattr(cfg, "optimization_intermediate_steps", 6))
            self.chk_optimization_validate_mc.setChecked(getattr(cfg, "optimization_validate_mc_intermediates", False))

            detection_algorithm_map = {
                "fisher_compression": "Fisher Compression",
                "direct_slsqp": "Direct Mean F Minimisation",
                "partition_bottom_up": "Partition Theorem Bottom-Up",
                "partition_top_down": "Partition Theorem Top-Down",
            }
            self.combo_detection_algorithm.setCurrentText(
                detection_algorithm_map.get(getattr(cfg, "detection_optimization_algorithm", "fisher_compression"), "Fisher Compression")
            )
            self.detection_opt_fine_bins_per_gate = int(getattr(cfg, "detection_opt_fine_bins_per_gate", 12))
            self.detection_opt_fine_bin_cap = int(getattr(cfg, "detection_opt_fine_bin_cap", 256))
            self.detection_opt_fc_nuisance_aware = bool(getattr(cfg, "detection_opt_fc_nuisance_aware", True))
            self.detection_opt_fc_auto_compress = bool(getattr(cfg, "detection_opt_fc_auto_compress", False))
            self.detection_opt_fc_initial_gates = int(getattr(cfg, "detection_opt_fc_initial_gates", 16))
            self.detection_opt_fc_min_gates = int(getattr(cfg, "detection_opt_fc_min_gates", 2))
            self.detection_opt_fc_max_f_loss_pct = float(getattr(cfg, "detection_opt_fc_max_f_loss_pct", 5.0))
            detection_start_map = {"zero": "Stick to 0", "irf": "Start after IRF", "custom": "Custom"}
            self.combo_detection_start_anchor.setCurrentText(
                detection_start_map.get(getattr(cfg, "detection_opt_start_anchor", "zero"), "Stick to 0")
            )
            self.spin_detection_start_anchor.setValue(getattr(cfg, "detection_opt_start_time", 0.0))
            detection_end_map = {"period": "Stick to period", "custom": "Custom"}
            self.combo_detection_end_anchor.setCurrentText(
                detection_end_map.get(getattr(cfg, "detection_opt_end_anchor", "period"), "Stick to period")
            )
            self.spin_detection_end_anchor.setValue(getattr(cfg, "detection_opt_end_time", cfg.period))
            self.detection_opt_restarts = int(getattr(cfg, "detection_opt_restarts", 20))
            self.detection_opt_ftol = float(getattr(cfg, "detection_opt_ftol", 1e-4))
            self.detection_opt_maxiter = int(getattr(cfg, "detection_opt_maxiter", 50))
            self._update_detection_algorithm_settings_tooltip()

            excitation_profile_map = {
                "gaussian": "Gaussian",
                "rectangular": "Square",
                "free_form": "Free Form",
            }
            self.combo_excitation_optimization_profile.setCurrentText(
                excitation_profile_map.get(getattr(cfg, "excitation_optimization_profile", "gaussian"), "Gaussian")
            )
            excitation_constraint_map = {
                "fixed_dose": "Fixed dose (area)",
                "fixed_peak": "Fixed peak",
            }
            self.combo_excitation_constraint.setCurrentText(
                excitation_constraint_map.get(getattr(cfg, "excitation_optimization_constraint", "fixed_dose"), "Fixed dose (area)")
            )
            self.spin_excitation_width_min.setValue(getattr(cfg, "excitation_optimization_width_min", 0.05))
            self.spin_excitation_width_max.setValue(getattr(cfg, "excitation_optimization_width_max", 10.0))
            self.spin_excitation_control_points.setValue(getattr(cfg, "excitation_optimization_control_points", 8))

            # Instrument params
            self.spin_photons.setValue(int(round(cfg.a_photons)))
            self.spin_image_repeats.setValue(int(getattr(cfg, "image_mc_repeats", getattr(cfg, "n_repeats", 200))))
            image_fit_map = {
                "gridded_mle": "Gridded MLE",
                "mle": "MLE",
                "tail": "Tail Fitting",
            }
            self.combo_image_fit_method.setCurrentText(
                image_fit_map.get(getattr(cfg, "image_fit_method", "gridded_mle"), "Gridded MLE")
            )
            self.spin_jitter.setValue(int(round(cfg.timing_jitter)))
            self.spin_deadtime.setValue(int(round(cfg.detector_deadtime)))
            self.chk_multihit.setChecked(cfg.b_multihit_mode)
            self.update_image_validation_summary()

            # Batch sweep
            legacy_sweep_map = {
                "irf_fwhm": "laser_pulse_fwhm_ns",
                "timing_jitter": "detector_jitter_ps",
                "num_gates": "number_of_gates",
                "detector_deadtime": "deadtime_fixed_countrate_ns",
            }
            selected_key = legacy_sweep_map.get(cfg.instr_sweep_param, cfg.instr_sweep_param)
            if selected_key not in self.sweep_options:
                selected_key = "laser_pulse_fwhm_ns"
            if cfg.instr_sweep_active:
                self.sweep_options[selected_key]["radio"].setChecked(True)
            else:
                self.radio_sweep_off.setChecked(True)
            if cfg.instr_sweep_vals:
                self.sweep_options[selected_key]["values"].setText(", ".join(f"{val:g}" for val in cfg.instr_sweep_vals))
            if "deadtime_fixed_countrate_ns" in self.sweep_options and self.sweep_options["deadtime_fixed_countrate_ns"]["extra"] is not None:
                self.sweep_options["deadtime_fixed_countrate_ns"]["extra"].setText(f"{cfg.instr_sweep_fixed_countrate_kcps:g}")
            if "countrate_fixed_deadtime_kcps" in self.sweep_options and self.sweep_options["countrate_fixed_deadtime_kcps"]["extra"] is not None:
                self.sweep_options["countrate_fixed_deadtime_kcps"]["extra"].setText(f"{cfg.instr_sweep_fixed_deadtime_ns:g}")
            gate_mode = "Sharp Rise, Sweep Fall" if cfg.instr_sweep_gate_sharp_edge == "sharp_rise" else "Sharp Fall, Sweep Rise"
            burst_mode = "Sharp Rise, Sweep Fall" if cfg.instr_sweep_burst_sharp_edge == "sharp_rise" else "Sharp Fall, Sweep Rise"
            if "gate_edge_one_sharp_ps" in self.sweep_options and self.sweep_options["gate_edge_one_sharp_ps"]["extra"] is not None:
                self.sweep_options["gate_edge_one_sharp_ps"]["extra"].setCurrentText(gate_mode)
            if "burst_edge_one_sharp_ns" in self.sweep_options and self.sweep_options["burst_edge_one_sharp_ns"]["extra"] is not None:
                self.sweep_options["burst_edge_one_sharp_ns"]["extra"].setCurrentText(burst_mode)
            
        finally:
            self._update_irf_ui()
            self.update_param_visibility()
            self.update_gridded_mle_summary()
            self.update_image_validation_summary()
            self._sync_precision_execution_ui(cfg.precision_validate_mc)
            self._sync_gate_controls()
            self._sync_optimization_ui()
            self._update_sweep_inputs_enabled()
            self.blockSignals(False)

    def set_theme(self, theme_name):
        self.current_theme = str(theme_name).lower()
        dark = self.current_theme == "dark"
        bg = "#0a0a0a" if dark else "#ffffff"
        text = "#e5eefb" if dark else "#0f172a"
        grid = "#334155" if dark else "#d7dee8"
        for plot in (self.optimization_objective_plot, self.optimization_best_f_plot):
            plot.setBackground(bg)
            for axis_name in ("bottom", "left"):
                axis = plot.getAxis(axis_name)
                axis.setTextPen(pg.mkPen(text))
                axis.setPen(pg.mkPen(text))
            plot.showGrid(x=True, y=True, alpha=0.25)
        self.optimization_objective_curve.setPen(pg.mkPen("#ef4444", width=2))
        self.optimization_objective_curve.setSymbolBrush(pg.mkBrush("#ef4444"))
        self.optimization_objective_curve.setSymbolPen(pg.mkPen("#ef4444"))
        self.optimization_best_f_curve.setPen(pg.mkPen("#22c55e", width=2))
        self.optimization_best_f_curve.setSymbolBrush(pg.mkBrush("#22c55e"))
        self.optimization_best_f_curve.setSymbolPen(pg.mkPen("#22c55e"))
        self.optimization_objective_plot.getPlotItem().getViewBox().setBorder(pg.mkPen(grid))
        self.optimization_best_f_plot.getPlotItem().getViewBox().setBorder(pg.mkPen(grid))

    def set_optimization_mode_active(self, active, running=False):
        self.optimization_running_state = bool(running)
        if running:
            self.lbl_optimization_banner.setText("Optimisation mode active: optimisation running")
            self.lbl_optimization_banner.setStyleSheet(
                "padding: 8px 10px; border-radius: 8px; background: #991b1b; color: white; font-weight: bold;"
            )
        elif active:
            self.lbl_optimization_banner.setText("Optimisation mode active")
            self.lbl_optimization_banner.setStyleSheet(
                "padding: 8px 10px; border-radius: 8px; background: #7f1d1d; color: white; font-weight: bold;"
            )
        else:
            self.lbl_optimization_banner.setText("Optimisation mode inactive")
            self.lbl_optimization_banner.setStyleSheet(
                "padding: 8px 10px; border-radius: 8px; background: #334155; color: white; font-weight: bold;"
            )
        self.btn_exit_optimization.setEnabled(bool(active) and not bool(running))
        self.btn_run_optimization.setEnabled(bool(active) and not bool(running))

    def set_optimization_status(self, text):
        self.txt_optimization_hint.setPlainText(str(text))

    def set_optimization_current_value(self, text):
        self.lbl_optimization_current.setText(str(text))

    def _copy_widget_to_clipboard(self, widget):
        pixmap = widget.grab()
        QGuiApplication.clipboard().setPixmap(pixmap)

    def clear_optimization_progress(self):
        self.optimization_objective_curve.setData([], [])
        self.optimization_best_f_curve.setData([], [])

    def update_optimization_progress(self, iterations, objective_values, best_f_values):
        x_obj = np.asarray(iterations, dtype=float)
        y_obj = np.asarray(objective_values, dtype=float)
        x_best = np.asarray(iterations, dtype=float)
        y_best = np.asarray(best_f_values, dtype=float)
        self.optimization_objective_curve.setData(x_obj, y_obj)
        self.optimization_best_f_curve.setData(x_best, y_best)
        if x_obj.size:
            self.optimization_objective_plot.enableAutoRange()
            self.optimization_best_f_plot.enableAutoRange()
