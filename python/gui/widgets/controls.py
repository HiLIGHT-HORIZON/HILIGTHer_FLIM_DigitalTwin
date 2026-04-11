import base64
import html
import re
from io import BytesIO
from statistics import NormalDist

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QDoubleSpinBox, QSpinBox, QPushButton,
                             QComboBox, QLabel, QGroupBox, QTabWidget,
                             QCheckBox, QLineEdit, QRadioButton, QButtonGroup,
                             QStackedWidget, QTextEdit, QToolButton, QDialog,
                             QScrollArea, QSizePolicy, QFileDialog,
                             QDialogButtonBox, QMessageBox, QStyle)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QColor
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np
import pyqtgraph as pg
from .freeform_irf_editor import FreeFormIRFEditor
from .clipboard_export import ClipboardExportManager
try:
    from backend.batch_sweep_store import BatchSweepStore
except ImportError:
    from python.backend.batch_sweep_store import BatchSweepStore
try:
    from backend.profile_store import InstrumentProfileStore
except ImportError:
    from python.backend.profile_store import InstrumentProfileStore
try:
    from backend.decay_model_store import DecayModelStore
except ImportError:
    from python.backend.decay_model_store import DecayModelStore

class ControlWidget(QWidget):
    context_changed = pyqtSignal(str) # Emits section ID for manual
    advanced_config_changed = pyqtSignal()
    custom_model_editor_requested = pyqtSignal()
    EVENT_CAPACITY_UNLIMITED = 1_000_000
    PRECISION_PRESETS = {
        "Low resolution": {
            "photons": 400,
            "mc_repeats": 20,
            "accuracy_pvalue": 0.0001,
            "bootstrap_samples": 40,
            "basis": "period",
        },
        "Medium res.": {
            "photons": 10_000,
            "mc_repeats": 100,
            "accuracy_pvalue": 0.0001,
            "bootstrap_samples": 200,
            "basis": "period",
        },
        "High res.": {
            "photons": 10_000,
            "mc_repeats": 400,
            "accuracy_pvalue": 0.0001,
            "bootstrap_samples": 1600,
            "basis": "period",
        },
    }
    OPT_HISTORY_COLORS = {
        "objective": "#ef4444",
        "min_f": "#22c55e",
        "min_eff": "#38bdf8",
        "auc_eff": "#f59e0b",
        "throughput": "#a855f7",
        "throughput_auc": "#e879f9",
        "gate_count": "#94a3b8",
    }

    def __init__(self):
        super().__init__()
        self.current_theme = "dark"
        self.optimization_running_state = False
        self._anchor_syncing = False
        self._f_photon_basis_syncing = False
        self._photon_budget_syncing = False
        self._precision_preset_syncing = False
        self.current_f_photon_basis_mode = "period"
        self.simulation_mode_preference = "auto"
        self.event_deadtime_mode = "nonparalyzable"
        self.event_multihit_capacity = None
        self.event_routing_mode = "exclusive"
        self.event_arbitration_rule = "random"
        self.event_share_resource_group = False
        self.event_return_timestamps = False
        self.event_pixel_dwell_time_s = 1e-3
        self._ideal_detector_syncing = False
        self._ideal_gates_syncing = False
        self.batch_sweep_store = BatchSweepStore()
        self.instrument_profile_store = InstrumentProfileStore()
        self.decay_model_store = DecayModelStore()
        self._math_render_cache = {}
        self.batch_sweep_defaults = self.batch_sweep_store.load_current()
        layout = QVBoxLayout(self)

        # Main Tab Container
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        def two_column_row(left_label, left_widget, right_label, right_widget):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            row_layout.addWidget(QLabel(left_label))
            row_layout.addWidget(left_widget, 1)
            row_layout.addWidget(QLabel(right_label))
            row_layout.addWidget(right_widget, 1)
            return row

        # --- TAB 0: DECAY MODEL (NOW FIRST) ---
        decay_tab = QWidget()
        decay_layout = QVBoxLayout(decay_tab)

        model_group = QGroupBox("Model Architecture")
        model_form = QFormLayout(model_group)
        model_form.setHorizontalSpacing(6)
        model_form.setVerticalSpacing(6)
        self.combo_decay_model = QComboBox()
        self.combo_decay_model.setToolTip("Select the mathematical form used for the fluorescence decay.")
        self.spin_n_comp = QSpinBox()
        self.spin_n_comp.setRange(1, 10)
        self.spin_n_comp.setValue(1)
        model_row = QWidget()
        model_row_layout = QHBoxLayout(model_row)
        model_row_layout.setContentsMargins(0, 0, 0, 0)
        model_row_layout.setSpacing(6)
        model_row_layout.addWidget(QLabel("Decay:"))
        model_row_layout.addWidget(self.combo_decay_model, 2)
        model_row_layout.addWidget(QLabel("N components:"))
        model_row_layout.addWidget(self.spin_n_comp, 1)
        self.combo_decay_model.setMaximumWidth(190)
        self.spin_n_comp.setMaximumWidth(64)
        self.btn_edit_model = QPushButton()
        self.btn_edit_model.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.btn_edit_model.setToolTip("Open the decay-model editor for custom models and sweep defaults.")
        self.btn_edit_model.setFixedWidth(32)
        self.btn_edit_model.clicked.connect(self.custom_model_editor_requested.emit)
        model_row_layout.addWidget(self.btn_edit_model)

        self.btn_model_math = QPushButton()
        self.btn_model_math.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        self.btn_model_math.setToolTip("Show or hide the decay-model mathematics.")
        self.btn_model_math.setFixedWidth(32)
        self.btn_model_math.setCheckable(True)
        self.btn_model_math.setChecked(False)
        self.btn_model_math.clicked.connect(lambda checked: self.model_math_panel.setVisible(bool(checked)))
        model_row_layout.addWidget(self.btn_model_math)
        model_form.addRow(model_row)

        self.chk_pulse_train_decay = QCheckBox("Decay wrapping")
        self.chk_pulse_train_decay.setToolTip("Wrap long fluorescence decays across the repetition period so previous pulses contribute to the current acquisition window.")
        self.btn_simulation_mode_badge = QToolButton()
        self.btn_simulation_mode_badge.setText("Poisson (+DTF)")
        self.btn_simulation_mode_badge.setToolTip("Click to cycle simulation-core preference. DTF = detector transfer function.")
        self.btn_simulation_mode_badge.clicked.connect(self._cycle_simulation_mode_preference)
        core_row = QWidget()
        core_row_layout = QHBoxLayout(core_row)
        core_row_layout.setContentsMargins(0, 0, 0, 0)
        core_row_layout.setSpacing(6)
        core_row_layout.addWidget(self.chk_pulse_train_decay)
        core_row_layout.addSpacing(10)
        core_row_layout.addWidget(QLabel("Sim. core:"))
        core_row_layout.addWidget(self.btn_simulation_mode_badge, 0)
        core_row_layout.addStretch()
        model_form.addRow(core_row)

        self.model_math_panel = QTextEdit()
        self.model_math_panel.setReadOnly(True)
        self.model_math_panel.setVisible(False)
        self.model_math_panel.setMinimumHeight(120)
        model_form.addRow(self.model_math_panel)

        decay_layout.addWidget(model_group)

        # Precision Parameters Table/Matrix
        param_group = QGroupBox("Decay parameters")
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
            label.setToolTip(tooltip)
            val.setToolTip(tooltip)
            self.param_rows[name] = {'label': label, 'layout': h, 'val': val, 'fix': fix_chk, 'x': x_chk}
            return val, fix_chk, x_chk

        self.p_tau1, self.f_tau1, self.x_tau1 = add_param_row("tau1", "Tau 1 (ns):", "Primary lifetime")
        self.p_tau2, self.f_tau2, self.x_tau2 = add_param_row("tau2", "Tau 2 (ns):", "Secondary lifetime")
        self.p_alpha, self.f_alpha, self.x_alpha = add_param_row("alpha", "Alpha 1 (frac):", "Fractional contribution")
        self.p_bg, self.f_bg, self.x_bg = add_param_row("background", "Background (%):", "Background fraction of the total decay in percent.")
        self.p_beta, self.f_beta, self.x_beta = add_param_row("beta", "Beta (KWW):", "Stretching factor")
        self._add_param_row_helper = add_param_row
        self.base_param_names = {"tau1", "tau2", "alpha", "background", "beta"}
        self._last_decay_model_key = "exponential"
        self._last_n_components = int(self.spin_n_comp.value())

        # Single selection logic for X-axis (Radio-style)
        self.x_group = {
            "tau1": self.x_tau1, "tau2": self.x_tau2,
            "alpha": self.x_alpha, "background": self.x_bg, "beta": self.x_beta
        }
        self.default_x_ranges = {
            "tau1": (0.5, 7.5),
            "tau2": (0.5, 7.5),
            "alpha": (0.0, 1.0),
            "background": (0.0, 25.0),
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
        self.combo_decay_model.currentIndexChanged.connect(self._handle_decay_model_selection_changed)
        self.spin_n_comp.valueChanged.connect(self._handle_component_count_changed)
        self.refresh_decay_model_options("exponential")
        self.update_param_visibility()

        # F-Value Curve Resolution
        sweep_grid_group = QGroupBox("Precision Sweep Configuration")
        sweep_grid_form = QFormLayout(sweep_grid_group)
        sweep_grid_form.setHorizontalSpacing(6)
        sweep_grid_form.setVerticalSpacing(6)
        self.spin_fx_min = QDoubleSpinBox()
        self.spin_fx_min.setRange(0.0, 1000)
        self.spin_fx_min.setValue(0.5)

        self.spin_fx_max = QDoubleSpinBox()
        self.spin_fx_max.setRange(0.0, 1000)
        self.spin_fx_max.setValue(7.5)
        self.spin_fx_steps = QSpinBox()
        self.spin_fx_steps.setRange(10, 500)
        self.spin_fx_steps.setValue(30)

        self.spin_grid_fine_factor = QSpinBox()
        self.spin_grid_fine_factor.setRange(1, 1000)
        self.spin_grid_fine_factor.setValue(100)
        self.combo_fx_scale = QComboBox()
        self.combo_fx_scale.addItems(["Log", "Linear", "Exponential"])
        self.lbl_fx_min = QLabel("Min Tau 1 (ns):")
        self.lbl_fx_max = QLabel("Max:")
        row_one = QWidget()
        row_one_layout = QHBoxLayout(row_one)
        row_one_layout.setContentsMargins(0, 0, 0, 0)
        row_one_layout.setSpacing(6)
        row_one_layout.addWidget(self.lbl_fx_min)
        row_one_layout.addWidget(self.spin_fx_min, 1)
        row_one_layout.addWidget(self.lbl_fx_max)
        row_one_layout.addWidget(self.spin_fx_max, 1)
        row_one_layout.addWidget(QLabel("Steps:"))
        row_one_layout.addWidget(self.spin_fx_steps, 1)
        sweep_grid_form.addRow(row_one)
        row_two = QWidget()
        row_two_layout = QHBoxLayout(row_two)
        row_two_layout.setContentsMargins(0, 0, 0, 0)
        row_two_layout.setSpacing(6)
        row_two_layout.addWidget(QLabel("Grid scale:"))
        row_two_layout.addWidget(self.combo_fx_scale, 1)
        row_two_layout.addWidget(QLabel("MLE Fine Factor:"))
        row_two_layout.addWidget(self.spin_grid_fine_factor, 1)
        sweep_grid_form.addRow(row_two)
        decay_layout.addWidget(sweep_grid_group)

        mle_group = QGroupBox("Gridded MLE Definition")
        mle_form = QFormLayout(mle_group)
        self.lbl_grid_min = QLabel("0.100")
        self.lbl_grid_max = QLabel("10.000")
        self.lbl_grid_steps = QLabel("5000")
        self.lbl_grid_mle_min = QLabel("Grid MLE min (ns):")
        mle_row = QWidget()
        mle_row_layout = QHBoxLayout(mle_row)
        mle_row_layout.setContentsMargins(0, 0, 0, 0)
        mle_row_layout.setSpacing(6)
        mle_row_layout.addWidget(self.lbl_grid_mle_min)
        mle_row_layout.addWidget(self.lbl_grid_min, 1)
        mle_row_layout.addWidget(QLabel("Max:"))
        mle_row_layout.addWidget(self.lbl_grid_max, 1)
        mle_row_layout.addWidget(QLabel("MLE grid steps:"))
        mle_row_layout.addWidget(self.lbl_grid_steps, 1)
        mle_form.addRow(mle_row)
        decay_layout.addWidget(mle_group)

        exec_group = QGroupBox("Fisher Information")
        exec_form = QFormLayout(exec_group)
        exec_group.setStyleSheet("QGroupBox::title { color: #d946ef; font-weight: bold; }")
        self.combo_precision_preset = QComboBox()
        self.combo_precision_preset.addItem("Custom")
        self.combo_precision_preset.addItems(list(self.PRECISION_PRESETS.keys()))
        exec_form.addRow("Defaults:", self.combo_precision_preset)
        self.chk_validate_mc = QCheckBox("Validate with Monte Carlo")
        self.chk_validate_mc.setChecked(False)
        self.chk_compute_ci = QCheckBox("Evaluate CI")
        self.chk_compute_ci.setChecked(False)

        self.spin_ci_level = QDoubleSpinBox()
        self.spin_ci_level.setRange(50.0, 99.999)
        self.spin_ci_level.setDecimals(3)
        self.spin_ci_level.setSingleStep(0.5)
        self.spin_ci_level.setValue(99.7)
        mc_toggle_row = QWidget()
        mc_toggle_layout = QHBoxLayout(mc_toggle_row)
        mc_toggle_layout.setContentsMargins(0, 0, 0, 0)
        mc_toggle_layout.setSpacing(6)
        mc_toggle_layout.addWidget(self.chk_validate_mc)
        mc_toggle_layout.addWidget(self.chk_compute_ci)
        mc_toggle_layout.addWidget(QLabel("CI Level (%):"))
        mc_toggle_layout.addWidget(self.spin_ci_level)
        self.lbl_ci_sigma_equiv = QLabel()
        mc_toggle_layout.addWidget(self.lbl_ci_sigma_equiv)
        mc_toggle_layout.addStretch()
        exec_form.addRow(mc_toggle_row)

        self.spin_precision_photons = QSpinBox()
        self.spin_precision_photons.setRange(1, 10_000_000)
        self.spin_precision_photons.setValue(2000)

        self.spin_mc_repeats = QSpinBox()
        self.spin_mc_repeats.setRange(10, 5000)
        self.spin_mc_repeats.setValue(400)
        exec_form.addRow(two_column_row("Photons:", self.spin_precision_photons, "MC Repeats:", self.spin_mc_repeats))

        self.spin_accuracy_pvalue = QDoubleSpinBox()
        self.spin_accuracy_pvalue.setRange(0.00000001, 0.5)
        self.spin_accuracy_pvalue.setDecimals(8)
        self.spin_accuracy_pvalue.setSingleStep(0.000001)
        self.spin_accuracy_pvalue.setValue(0.0001)

        self.spin_bootstrap_samples = QSpinBox()
        self.spin_bootstrap_samples.setRange(1, 100000)
        self.spin_bootstrap_samples.setSingleStep(100)
        self.spin_bootstrap_samples.setValue(2000)
        exec_form.addRow(two_column_row("Estimator accuracy p-value:", self.spin_accuracy_pvalue, "Bootstrap resamples:", self.spin_bootstrap_samples))
        self.combo_deadtime_correction = QComboBox()
        self.combo_deadtime_correction.addItems([
            "None",
            "Isbaner-style histogram",
            "Rapp (MCPDF)",
            "Rapp (MCHC)",
        ])
        exec_form.addRow("Dead-time correction:", self.combo_deadtime_correction)

        basis_row = QWidget()
        basis_row_layout = QHBoxLayout(basis_row)
        basis_row_layout.setContentsMargins(0, 0, 0, 0)
        basis_row_layout.setSpacing(8)
        self.lbl_f_basis = QLabel("Compute F-value on")
        self.radio_f_basis_period = QRadioButton("All in acquisition period")
        self.radio_f_basis_all = QRadioButton("All")
        self.radio_f_basis_collected = QRadioButton("Only collected (disregard losses)")
        self.radio_f_basis_period.setChecked(True)
        self.f_photon_basis_bg = QButtonGroup()
        self.f_photon_basis_bg.addButton(self.radio_f_basis_period)
        self.f_photon_basis_bg.addButton(self.radio_f_basis_all)
        self.f_photon_basis_bg.addButton(self.radio_f_basis_collected)
        basis_row_layout.addWidget(self.lbl_f_basis)
        basis_row_layout.addWidget(self.radio_f_basis_period)
        basis_row_layout.addWidget(self.radio_f_basis_all)
        basis_row_layout.addWidget(self.radio_f_basis_collected)
        basis_row_layout.addStretch()
        exec_form.addRow(basis_row)
        self.chk_validate_mc.toggled.connect(self._sync_precision_execution_ui)
        self.chk_compute_ci.toggled.connect(lambda _: self._sync_precision_execution_ui(self.chk_validate_mc.isChecked()))
        self.combo_precision_preset.currentTextChanged.connect(self._apply_precision_preset)
        self.spin_precision_photons.valueChanged.connect(self._sync_precision_preset_selection)
        self.spin_mc_repeats.valueChanged.connect(self._sync_precision_preset_selection)
        self.spin_accuracy_pvalue.valueChanged.connect(self._sync_precision_preset_selection)
        self.spin_bootstrap_samples.valueChanged.connect(self._sync_precision_preset_selection)
        self.spin_ci_level.valueChanged.connect(self._update_ci_sigma_equivalence)
        self.radio_f_basis_period.toggled.connect(self._sync_precision_preset_selection)
        self.radio_f_basis_all.toggled.connect(self._sync_precision_preset_selection)
        self.radio_f_basis_collected.toggled.connect(self._sync_precision_preset_selection)
        self._sync_precision_execution_ui(self.chk_validate_mc.isChecked())
        self._update_ci_sigma_equivalence()
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
        self.spin_image_repeats = QSpinBox()
        self.spin_image_repeats.setRange(1, 100000)
        self.spin_image_repeats.setValue(200)
        stat_layout.addRow(two_column_row("Photons:", self.spin_photons, "MC repeats (aim):", self.spin_image_repeats))
        acq_layout.addWidget(stat_group)

        res_group = QGroupBox("Data features")
        res_layout = QFormLayout(res_group)
        self.lbl_image_param = QLabel("tau1")
        self.lbl_image_x_pixels = QLabel("90")
        self.lbl_image_y_pixels = QLabel("70")
        self.lbl_image_band_width = QLabel("3")
        self.lbl_image_effective_repeats = QLabel("210")
        self.lbl_image_sweep_min = QLabel("0.500")
        self.lbl_image_sweep_max = QLabel("7.500")
        self.lbl_image_sweep_steps = QLabel("30")
        line1 = QWidget()
        line1_layout = QHBoxLayout(line1)
        line1_layout.setContentsMargins(0, 0, 0, 0)
        line1_layout.setSpacing(6)
        line1_layout.addWidget(QLabel("X (precision sweep):"))
        line1_layout.addWidget(self.lbl_image_param, 1)
        line1_layout.addWidget(QLabel("X pixels:"))
        line1_layout.addWidget(self.lbl_image_x_pixels, 1)
        res_layout.addRow(line1)
        line2 = QWidget()
        line2_layout = QHBoxLayout(line2)
        line2_layout.setContentsMargins(0, 0, 0, 0)
        line2_layout.setSpacing(6)
        line2_layout.addWidget(QLabel("Swept values min"))
        line2_layout.addWidget(self.lbl_image_sweep_min, 1)
        line2_layout.addWidget(QLabel("max"))
        line2_layout.addWidget(self.lbl_image_sweep_max, 1)
        line2_layout.addWidget(QLabel("steps"))
        line2_layout.addWidget(self.lbl_image_sweep_steps, 1)
        line2_layout.addWidget(QLabel("stripe width"))
        line2_layout.addWidget(self.lbl_image_band_width, 1)
        res_layout.addRow(line2)
        line3 = QWidget()
        line3_layout = QHBoxLayout(line3)
        line3_layout.setContentsMargins(0, 0, 0, 0)
        line3_layout.setSpacing(6)
        line3_layout.addWidget(QLabel("Y dimension (Monte Carlo):"))
        line3_layout.addWidget(self.lbl_image_y_pixels, 1)
        line3_layout.addWidget(QLabel("Replicates/value:"))
        line3_layout.addWidget(self.lbl_image_effective_repeats, 1)
        res_layout.addRow(line3)
        self.lbl_image_replicates_comment = QLabel("Replicates are stripe widths x Y pixels")
        self.lbl_image_replicates_comment.setWordWrap(True)
        res_layout.addRow(self.lbl_image_replicates_comment)
        acq_layout.addWidget(res_group)

        analysis_group = QGroupBox("Image Analysis")
        analysis_form = QFormLayout(analysis_group)
        self.combo_image_fit_method = QComboBox()
        self.combo_image_fit_method.addItems(["Gridded MLE", "Iterative Reconvolution", "Tail Fitting"])
        self.btn_fit_image = QPushButton("REFIT")
        self.btn_fit_image.setStyleSheet("background-color: #16a34a; color: white; font-weight: bold;")
        fit_row = QWidget()
        fit_row_layout = QHBoxLayout(fit_row)
        fit_row_layout.setContentsMargins(0, 0, 0, 0)
        fit_row_layout.setSpacing(6)
        fit_row_layout.addWidget(self.combo_image_fit_method, 1)
        fit_row_layout.addWidget(self.btn_fit_image, 0)
        analysis_form.addRow("Lifetime fitting:", fit_row)
        acq_layout.addWidget(analysis_group)

        self.spin_fx_min.valueChanged.connect(self.update_image_validation_summary)
        self.spin_fx_max.valueChanged.connect(self.update_image_validation_summary)
        self.spin_fx_steps.valueChanged.connect(self.update_image_validation_summary)
        self.spin_image_repeats.valueChanged.connect(self.update_image_validation_summary)
        acq_layout.addStretch()
        self.update_image_validation_summary()
        self.tabs.addTab(acq_tab, "MC Image validation")

        # --- TAB 2: LASER / IRF (REFACTORED) ---
        laser_tab = QWidget()
        laser_main_layout = QVBoxLayout(laser_tab)
        laser_inner_widget = QWidget()
        laser_layout = QFormLayout(laser_inner_widget)
        laser_layout.setHorizontalSpacing(6)
        laser_layout.setVerticalSpacing(6)
        laser_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)

        self.spin_period = QDoubleSpinBox(); self.spin_period.setRange(0.1, 1000); self.spin_period.setValue(12.5)
        laser_layout.addRow("Period (ns):", self.spin_period)

        self.combo_profile = QComboBox()
        self.combo_profile.addItems(["Gaussian", "Rectangular", "Free Form", "Ideal (Dirac)"])
        laser_layout.addRow("Laser profile:", self.combo_profile)

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

        self.btn_freeform_mode = QPushButton("Editing")
        self.btn_freeform_mode.setCheckable(True)
        self.btn_freeform_mode.setChecked(True)
        self.freeform_editor = FreeFormIRFEditor()
        self.freeform_editor.setMinimumHeight(150)
        self.freeform_editor.setMaximumHeight(210)
        self.freeform_editor.setMaximumWidth(420)
        self.freeform_editor.btn_reset.clicked.disconnect()
        self.freeform_editor.btn_reset.clicked.connect(self._reset_freeform_from_current_inputs)
        self.lbl_freeform_editor = QLabel("Free-form editor:")
        self.lbl_freeform_help = QLabel(
            "Double-click a point to select it.\n"
            "Drag to move. Double-click empty space then Add Point to insert."
        )
        self.lbl_freeform_help.setWordWrap(True)
        freeform_header = QWidget()
        freeform_header_layout = QHBoxLayout(freeform_header)
        freeform_header_layout.setContentsMargins(0, 0, 0, 0)
        freeform_header_layout.setSpacing(6)
        freeform_header_layout.addWidget(self.lbl_freeform_editor)
        freeform_header_layout.addWidget(self.btn_freeform_mode)
        freeform_header_layout.addStretch()
        freeform_container = QWidget()
        freeform_container_layout = QVBoxLayout(freeform_container)
        freeform_container_layout.setContentsMargins(0, 0, 0, 0)
        freeform_container_layout.setSpacing(4)
        freeform_container_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        freeform_container_layout.addWidget(freeform_header, 0, Qt.AlignmentFlag.AlignLeft)
        freeform_container_layout.addWidget(self.lbl_freeform_help, 0, Qt.AlignmentFlag.AlignLeft)
        freeform_container_layout.addWidget(self.freeform_editor)
        laser_layout.addRow(freeform_container)

        # Burst Excitation Sub-group
        self.group_burst = QGroupBox("Burst Excitation")
        self.group_burst.setCheckable(True)
        self.group_burst.setChecked(False)
        self.group_burst.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.group_burst.setMaximumWidth(330)
        burst_l = QFormLayout(self.group_burst)
        burst_l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        burst_l.setVerticalSpacing(4)

        lbl_burst_period = QLabel("Interpulse distance (ps):")
        lbl_burst_period.setMinimumWidth(130)
        self.lbl_burst_period = lbl_burst_period
        self.spin_burst_period = QDoubleSpinBox()
        self.spin_burst_period.setRange(1.0, 100000.0)
        self.spin_burst_period.setValue(100.0)
        self.spin_burst_period.setKeyboardTracking(False)
        self.spin_burst_period.setToolTip("Peak-to-peak distance between sub-pulses in the burst (ps).")
        burst_period_row = QWidget()
        burst_period_row_layout = QHBoxLayout(burst_period_row)
        burst_period_row_layout.setContentsMargins(0, 0, 0, 0)
        burst_period_row_layout.setSpacing(6)
        burst_period_row_layout.addWidget(self.spin_burst_period)
        self.lbl_burst_rate = QLabel("~ 10.000 GHz")
        self.lbl_burst_rate.setMinimumWidth(90)
        burst_period_row_layout.addWidget(self.lbl_burst_rate)
        burst_period_row_layout.addStretch()
        burst_l.addRow(lbl_burst_period, burst_period_row)

        lbl_burst_fwhm = QLabel("Pulse FWHM (ps):")
        lbl_burst_fwhm.setMinimumWidth(130)
        self.lbl_burst_fwhm = lbl_burst_fwhm
        self.spin_burst_fwhm = QDoubleSpinBox()
        self.spin_burst_fwhm.setRange(1.0, 100000.0)
        self.spin_burst_fwhm.setValue(100.0)
        self.spin_burst_fwhm.setToolTip("Pulse-width (FWHM) of each sub-pulse in the burst (ps).")
        burst_l.addRow(lbl_burst_fwhm, self.spin_burst_fwhm)

        input_width = 140
        self.combo_profile.setFixedWidth(input_width)
        self.spin_period.setFixedWidth(input_width)
        self.spin_fwhm.setFixedWidth(input_width)
        self.spin_irf_pos.setFixedWidth(input_width)
        self.spin_rise.setFixedWidth(input_width)
        self.spin_fall.setFixedWidth(input_width)
        self.spin_burst_period.setFixedWidth(input_width // 2)
        self.spin_burst_fwhm.setFixedWidth(input_width // 2)

        burst_container = QHBoxLayout()
        burst_container.setContentsMargins(0, 0, 0, 0)
        burst_container.addWidget(self.group_burst)
        burst_container.addStretch()
        laser_layout.addRow(burst_container)

        laser_main_layout.addWidget(laser_inner_widget)
        laser_main_layout.addStretch()

        self.tabs.addTab(laser_tab, "Excitation")

        # Connect IRF profile changes for the excitation-specific controls
        self.combo_profile.currentIndexChanged.connect(self._update_irf_ui)
        self.btn_freeform_mode.toggled.connect(self._on_freeform_mode_toggled)
        self.spin_period.valueChanged.connect(self._on_excitation_geometry_changed)
        self.spin_fwhm.valueChanged.connect(self._on_excitation_geometry_changed)
        self.spin_irf_pos.valueChanged.connect(self._on_excitation_geometry_changed)
        self.spin_burst_period.valueChanged.connect(self._update_burst_ui_state)
        self._update_irf_ui()

        # Detection
        detection_tab = QWidget()
        detection_layout = QVBoxLayout(detection_tab)

        detector_group = QGroupBox("Detector Properties")
        hw_layout = QFormLayout(detector_group)
        self.chk_ideal_detector = QCheckBox("Ideal detector")
        self.btn_detector_math = QPushButton()
        self.btn_detector_math.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        self.btn_detector_math.setToolTip("Show or hide the detector transfer mathematics.")
        self.btn_detector_math.setCheckable(True)
        self.btn_detector_math.setChecked(False)
        self.btn_detector_math.setFixedWidth(32)
        self.btn_detector_math.clicked.connect(lambda checked: self.detector_math_panel.setVisible(bool(checked)))
        detector_header_row = QWidget()
        detector_header_layout = QHBoxLayout(detector_header_row)
        detector_header_layout.setContentsMargins(0, 0, 0, 0)
        detector_header_layout.setSpacing(6)
        detector_header_layout.addWidget(self.chk_ideal_detector)
        detector_header_layout.addWidget(self.btn_detector_math, 0)
        detector_header_layout.addStretch()
        hw_layout.addRow(detector_header_row)
        self.spin_jitter = QSpinBox(); self.spin_jitter.setValue(150)
        self.spin_deadtime = QSpinBox(); self.spin_deadtime.setRange(0, 1000); self.spin_deadtime.setValue(45)
        self.spin_pixel_dwell = QDoubleSpinBox()
        self.spin_pixel_dwell.setRange(1e-6, 1e9)
        self.spin_pixel_dwell.setDecimals(6)
        self.spin_pixel_dwell.setSingleStep(1.0)
        self.combo_pixel_dwell_unit = QComboBox()
        self.combo_pixel_dwell_unit.addItems(["ns", "us", "ms", "s"])
        detector_row_one = QWidget()
        detector_row_one_layout = QHBoxLayout(detector_row_one)
        detector_row_one_layout.setContentsMargins(0, 0, 0, 0)
        detector_row_one_layout.setSpacing(6)
        detector_row_one_layout.addWidget(QLabel("Jitter (ps):"))
        detector_row_one_layout.addWidget(self.spin_jitter, 1)
        detector_row_one_layout.addWidget(QLabel("Deadtime (ns):"))
        detector_row_one_layout.addWidget(self.spin_deadtime, 1)
        detector_row_one_layout.addWidget(QLabel("Pixel dwell:"))
        detector_row_one_layout.addWidget(self.spin_pixel_dwell, 1)
        detector_row_one_layout.addWidget(self.combo_pixel_dwell_unit)
        self.detector_row_one_widget = detector_row_one
        hw_layout.addRow(self.detector_row_one_widget)
        self.lbl_estimated_count_rate = QLabel("0 cps")
        self.chk_multihit = QCheckBox("Multihit Detection"); self.chk_multihit.setChecked(True)
        self.spin_max_events_per_period = QSpinBox()
        self.spin_max_events_per_period.setRange(1, self.EVENT_CAPACITY_UNLIMITED)
        self.spin_max_events_per_period.setValue(self.EVENT_CAPACITY_UNLIMITED)
        detector_runtime_row = QWidget()
        detector_runtime_layout = QHBoxLayout(detector_runtime_row)
        detector_runtime_layout.setContentsMargins(0, 0, 0, 0)
        detector_runtime_layout.setSpacing(6)
        detector_runtime_layout.addWidget(QLabel("Avg count rate:"))
        detector_runtime_layout.addWidget(self.lbl_estimated_count_rate, 1)
        detector_runtime_layout.addWidget(self.chk_multihit)
        detector_runtime_layout.addWidget(QLabel("Max events/period:"))
        detector_runtime_layout.addWidget(self.spin_max_events_per_period, 1)
        self.detector_runtime_row_widget = detector_runtime_row
        hw_layout.addRow(self.detector_runtime_row_widget)
        self.spin_afterpulsing = QDoubleSpinBox()
        self.spin_afterpulsing.setRange(0.0, 100.0)
        self.spin_afterpulsing.setDecimals(3)
        self.spin_afterpulsing.setSingleStep(0.1)
        self.spin_afterpulsing.setValue(0.0)
        self.spin_dark_count_rate = QDoubleSpinBox()
        self.spin_dark_count_rate.setRange(0.0, 1e12)
        self.spin_dark_count_rate.setDecimals(3)
        self.spin_dark_count_rate.setSingleStep(10.0)
        self.spin_dark_count_rate.setValue(0.0)
        detector_effects_row = QWidget()
        detector_effects_layout = QHBoxLayout(detector_effects_row)
        detector_effects_layout.setContentsMargins(0, 0, 0, 0)
        detector_effects_layout.setSpacing(6)
        detector_effects_layout.addWidget(QLabel("Afterpulsing (%):"))
        detector_effects_layout.addWidget(self.spin_afterpulsing, 1)
        detector_effects_layout.addWidget(QLabel("Dark count rate (cps):"))
        detector_effects_layout.addWidget(self.spin_dark_count_rate, 1)
        self.detector_effects_row_widget = detector_effects_row
        hw_layout.addRow(self.detector_effects_row_widget)

        detector_input_width = 110
        for widget in (
            self.spin_jitter,
            self.spin_deadtime,
            self.spin_pixel_dwell,
            self.spin_max_events_per_period,
            self.spin_afterpulsing,
            self.spin_dark_count_rate,
        ):
            widget.setFixedWidth(detector_input_width)
        self.combo_pixel_dwell_unit.setFixedWidth(70)
        self.detector_math_panel = QTextEdit()
        self.detector_math_panel.setReadOnly(True)
        self.detector_math_panel.setVisible(False)
        self.detector_math_panel.setMinimumHeight(120)
        hw_layout.addRow(self.detector_math_panel)
        detection_layout.addWidget(detector_group)

        # Gating
        gating_group = QGroupBox("Gate Properties")
        gate_layout = QFormLayout(gating_group)
        self.chk_ideal_gates = QCheckBox("Ideal gates")
        self.chk_ideal_gates.setChecked(True)
        gate_layout.addRow(self.chk_ideal_gates)
        self.spin_num_gates = QSpinBox(); self.spin_num_gates.setRange(2, 512); self.spin_num_gates.setValue(4)
        self.combo_gate_type = QComboBox(); self.combo_gate_type.addItems(["Equal", "Custom"])
        gate_layout.addRow(two_column_row("Num Gates:", self.spin_num_gates, "Gate Type:", self.combo_gate_type))
        self.label_gate_definition = QLabel("Gate Edges (ns):")
        self.edit_gate_widths = QLineEdit()
        gate_layout.addRow(self.label_gate_definition, self.edit_gate_widths)
        self.lbl_gate_error = QLabel("")
        self.lbl_gate_error.setStyleSheet("color: #dc2626; font-weight: bold;")
        gate_layout.addRow("", self.lbl_gate_error)
        self.spin_gate_rise = QDoubleSpinBox(); self.spin_gate_rise.setValue(0.0)
        self.spin_gate_fall = QDoubleSpinBox(); self.spin_gate_fall.setValue(0.0)
        edge_wrap_row = QWidget()
        edge_wrap_row_layout = QHBoxLayout(edge_wrap_row)
        edge_wrap_row_layout.setContentsMargins(0, 0, 0, 0)
        edge_wrap_row_layout.setSpacing(6)
        edge_wrap_row_layout.addWidget(QLabel("Edge rise/fall (ns):"))
        edge_wrap_row_layout.addWidget(self.spin_gate_rise, 1)
        edge_wrap_row_layout.addWidget(self.spin_gate_fall, 1)
        self.chk_gate_wraparound = QCheckBox("Wrap around")
        self.chk_gate_wraparound.setChecked(False)
        edge_wrap_row_layout.addWidget(self.chk_gate_wraparound)
        self.gate_nonideal_row_widget = edge_wrap_row
        gate_layout.addRow(self.gate_nonideal_row_widget)

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
        anchors_row = QWidget()
        anchors_row_layout = QHBoxLayout(anchors_row)
        anchors_row_layout.setContentsMargins(0, 0, 0, 0)
        anchors_row_layout.setSpacing(6)
        anchors_row_layout.addWidget(start_group, 1)
        anchors_row_layout.addWidget(end_group, 1)
        self.gate_anchor_row_widget = anchors_row
        gate_layout.addRow(self.gate_anchor_row_widget)

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
        overlap_group = QGroupBox("Gate Overlap")
        overlap_layout = QVBoxLayout(overlap_group)
        self.radio_overlap_jitter = QRadioButton("Only for jittering/skewness")
        self.radio_overlap_never = QRadioButton("Never")
        self.radio_overlap_yes = QRadioButton("Yes (under development)")
        self.radio_overlap_never.setChecked(True)
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
        overlap_row = QWidget()
        overlap_row_layout = QHBoxLayout(overlap_row)
        overlap_row_layout.setContentsMargins(0, 0, 0, 0)
        overlap_row_layout.setSpacing(6)
        overlap_row_layout.addWidget(overlap_group, 1)
        overlap_row_layout.addWidget(overlap_effect_group, 1)
        self.gate_overlap_row_widget = overlap_row
        gate_layout.addRow(self.gate_overlap_row_widget)
        self.gate_collection_group = collection_group
        gate_layout.addRow(self.gate_collection_group)

        for widget in (
            self.spin_num_gates,
            self.combo_gate_type,
            self.spin_gate_rise,
            self.spin_gate_fall,
            self.spin_gate_first,
            self.spin_gate_last,
            self.spin_gate_overlap,
        ):
            widget.setFixedWidth(detector_input_width)

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
        self.chk_opt_count_rate = QCheckBox("Optimise count rate")
        scope_row = QWidget()
        scope_row_layout = QHBoxLayout(scope_row)
        scope_row_layout.setContentsMargins(0, 0, 0, 0)
        scope_row_layout.addWidget(self.chk_opt_detection)
        scope_row_layout.addWidget(self.chk_opt_excitation)
        scope_row_layout.addWidget(self.chk_opt_count_rate)
        scope_row_layout.addStretch()
        optimization_scope_form.addRow(scope_row)

        self.combo_optimization_mode = QComboBox()
        self.combo_optimization_mode.addItems(["Sequential"])
        self.combo_optimization_mode.hide()

        self.combo_optimization_first = QComboBox()
        self.combo_optimization_first.addItems(["Detection First", "Excitation First", "Count Rate First"])
        self.spin_optimization_iterations = QSpinBox()
        self.spin_optimization_iterations.setRange(1, 50)
        self.spin_optimization_iterations.setValue(20)
        optimization_scope_form.addRow(two_column_row("Run Order:", self.combo_optimization_first, "Max iterations:", self.spin_optimization_iterations))
        optimization_layout.addWidget(optimization_scope_group)

        optimization_view_group = QGroupBox("Optimisation Visualisation")
        optimization_view_form = QFormLayout(optimization_view_group)
        self.chk_optimization_realtime = QCheckBox("Real-time display")
        self.chk_optimization_realtime.setChecked(False)
        self.spin_optimization_realtime_interval = QDoubleSpinBox()
        self.spin_optimization_realtime_interval.setRange(0.2, 3600.0)
        self.spin_optimization_realtime_interval.setDecimals(1)
        self.spin_optimization_realtime_interval.setSingleStep(0.5)
        self.spin_optimization_realtime_interval.setValue(5.0)
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
        optimization_view_row_layout.addWidget(QLabel("Refresh (s):"))
        optimization_view_row_layout.addWidget(self.spin_optimization_realtime_interval)
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
        self.detection_opt_group = detection_opt_group
        optimization_layout.addWidget(self.detection_opt_group)

        excitation_opt_group = QGroupBox("Excitation Optimisation")
        excitation_opt_form = QFormLayout(excitation_opt_group)
        self.combo_excitation_optimization_profile = QComboBox()
        self.combo_excitation_optimization_profile.addItems(["Gaussian", "Square", "Free Form"])
        self.combo_excitation_constraint = QComboBox()
        self.combo_excitation_constraint.addItems(["Fixed dose (area)", "Fixed peak"])
        self.combo_optimization_objective = QComboBox()
        self.combo_optimization_objective.addItems([
            "Fisher Information",
            "Fisher Throughput",
            "Photon Efficiency AUC",
            "Throughput AUC",
        ])
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
        self.excitation_opt_group = excitation_opt_group
        optimization_layout.addWidget(self.excitation_opt_group)

        count_rate_opt_group = QGroupBox("Count-Rate Optimisation")
        count_rate_opt_form = QFormLayout(count_rate_opt_group)
        self.spin_count_rate_min_kcps = QDoubleSpinBox()
        self.spin_count_rate_min_kcps.setRange(0.001, 1_000_000.0)
        self.spin_count_rate_min_kcps.setDecimals(3)
        self.spin_count_rate_min_kcps.setValue(10.0)
        self.spin_count_rate_max_kcps = QDoubleSpinBox()
        self.spin_count_rate_max_kcps.setRange(0.001, 1_000_000.0)
        self.spin_count_rate_max_kcps.setDecimals(3)
        self.spin_count_rate_max_kcps.setValue(1000.0)
        count_rate_opt_form.addRow(two_column_row("Min rate (kcps):", self.spin_count_rate_min_kcps, "Max rate (kcps):", self.spin_count_rate_max_kcps))
        self.spin_count_rate_steps = QSpinBox()
        self.spin_count_rate_steps.setRange(2, 200)
        self.spin_count_rate_steps.setValue(24)
        self.combo_count_rate_scale = QComboBox()
        self.combo_count_rate_scale.addItems(["Log", "Linear"])
        count_rate_opt_form.addRow(two_column_row("Steps:", self.spin_count_rate_steps, "Scale:", self.combo_count_rate_scale))
        self.chk_count_rate_accuracy_guard = QCheckBox("Protect accuracy")
        self.chk_count_rate_accuracy_guard.setChecked(True)
        self.spin_count_rate_max_bias_pct = QDoubleSpinBox()
        self.spin_count_rate_max_bias_pct.setRange(0.0, 1000.0)
        self.spin_count_rate_max_bias_pct.setDecimals(3)
        self.spin_count_rate_max_bias_pct.setSingleStep(0.1)
        self.spin_count_rate_max_bias_pct.setValue(2.0)
        count_rate_opt_form.addRow(
            two_column_row("Guard:", self.chk_count_rate_accuracy_guard, "Max bias (%):", self.spin_count_rate_max_bias_pct)
        )
        self.count_rate_opt_group = count_rate_opt_group
        optimization_layout.addWidget(self.count_rate_opt_group)
        self.opt_groups = [optimization_scope_group, optimization_view_group, self.detection_opt_group, self.excitation_opt_group]

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

        objective_header = QWidget()
        objective_header_layout = QHBoxLayout(objective_header)
        objective_header_layout.setContentsMargins(0, 0, 0, 0)
        objective_header.setMaximumHeight(0)
        objective_header.setVisible(False)
        objective_header_layout.addWidget(QLabel("Optimisation History"))
        objective_header_layout.addStretch()
        self.btn_copy_optimization_objective = QPushButton("📋")
        self.btn_copy_optimization_objective.setToolTip("Copy optimisation-history plot to clipboard")
        self.btn_copy_optimization_objective.setMaximumWidth(30)
        self.btn_copy_optimization_objective.setStyleSheet("padding: 2px; font-size: 14px;")
        self.btn_copy_optimization_objective.clicked.connect(
            lambda: self._copy_widget_to_clipboard(self.optimization_best_f_plot)
        )
        objective_header_layout.addWidget(self.btn_copy_optimization_objective)
        self.btn_export_settings_optimization_objective = QPushButton("⚙")
        self.btn_export_settings_optimization_objective.setToolTip("Clipboard export settings")
        self.btn_export_settings_optimization_objective.setMaximumWidth(30)
        self.btn_export_settings_optimization_objective.setStyleSheet("padding: 2px; font-size: 14px;")
        self.btn_export_settings_optimization_objective.clicked.connect(
            lambda: ClipboardExportManager.configure(
                "optimization_objective_plot",
                parent=self,
                export_source=self.optimization_objective_plot,
            )
        )
        objective_header_layout.addWidget(self.btn_export_settings_optimization_objective)
        optimization_layout.addWidget(objective_header)

        self.optimization_objective_plot = pg.PlotWidget()
        self.optimization_objective_plot.setMinimumHeight(0)
        self.optimization_objective_plot.setMaximumHeight(0)
        self.optimization_objective_plot.setMaximumWidth(0)
        self.optimization_objective_plot.showGrid(x=True, y=True, alpha=0.25)
        self.optimization_objective_plot.setLabel("left", "Objective")
        self.optimization_objective_plot.setLabel("bottom", "Iteration")
        self.optimization_objective_plot.setLogMode(x=False, y=True)
        optimization_layout.addWidget(self.optimization_objective_plot)

        best_f_header = QWidget()
        best_f_header_layout = QHBoxLayout(best_f_header)
        best_f_header_layout.setContentsMargins(0, 0, 0, 0)
        best_f_header_layout.addWidget(QLabel("Optimisation History"))
        self.chk_opt_hist_log_x = QCheckBox("Log X")
        self.chk_opt_hist_log_x.setChecked(False)
        self.chk_opt_hist_log_y = QCheckBox("Log Y")
        self.chk_opt_hist_log_y.setChecked(True)
        best_f_header_layout.addWidget(self.chk_opt_hist_log_x)
        best_f_header_layout.addWidget(self.chk_opt_hist_log_y)
        self.btn_copy_optimization_best_f = QPushButton("📋")
        self.btn_copy_optimization_best_f.setToolTip("Copy minimum-F plot to clipboard")
        self.btn_copy_optimization_best_f.setMaximumWidth(30)
        self.btn_copy_optimization_best_f.setStyleSheet("padding: 2px; font-size: 14px;")
        self.btn_copy_optimization_best_f.clicked.connect(
            lambda: self._copy_widget_to_clipboard(self.optimization_best_f_plot)
        )
        best_f_header_layout.addWidget(self.btn_copy_optimization_best_f)
        self.btn_export_settings_optimization_best_f = QPushButton("⚙")
        self.btn_export_settings_optimization_best_f.setToolTip("Clipboard export settings")
        self.btn_export_settings_optimization_best_f.setMaximumWidth(30)
        self.btn_export_settings_optimization_best_f.setStyleSheet("padding: 2px; font-size: 14px;")
        self.btn_export_settings_optimization_best_f.clicked.connect(
            lambda: ClipboardExportManager.configure(
                "optimization_best_f_plot",
                parent=self,
                export_source=self.optimization_best_f_plot,
            )
        )
        best_f_header_layout.addWidget(self.btn_export_settings_optimization_best_f)
        best_f_header_layout.addStretch()
        optimization_layout.addWidget(best_f_header)

        self.optimization_best_f_plot = pg.PlotWidget()
        self.optimization_best_f_plot.setMinimumHeight(180)
        self.optimization_best_f_plot.setMaximumHeight(220)
        self.optimization_best_f_plot.setMaximumWidth(640)
        self.optimization_best_f_plot.showGrid(x=True, y=True, alpha=0.25)
        self.optimization_best_f_plot.setLabel("left", "")
        self.optimization_best_f_plot.setLabel("bottom", "Iteration")
        self.optimization_best_f_plot.setLogMode(x=False, y=True)
        self.optimization_best_f_plot.showAxis("right")
        self.optimization_best_f_plot.setLabel("right", "")
        self.optimization_objective_curve = self.optimization_best_f_plot.plot(
            pen=pg.mkPen(self.OPT_HISTORY_COLORS["objective"], width=2),
            symbol="o",
            symbolSize=5,
            symbolBrush=pg.mkBrush(self.OPT_HISTORY_COLORS["objective"]),
            symbolPen=pg.mkPen(self.OPT_HISTORY_COLORS["objective"]),
        )
        self.optimization_aux_axes = {}
        self.optimization_aux_vbs = {}
        self.optimization_best_f_curve = pg.PlotDataItem(
            pen=pg.mkPen(self.OPT_HISTORY_COLORS["min_f"], width=2),
            symbol="o",
            symbolSize=5,
            symbolBrush=pg.mkBrush(self.OPT_HISTORY_COLORS["min_f"]),
            symbolPen=pg.mkPen(self.OPT_HISTORY_COLORS["min_f"]),
        )
        self.optimization_best_eff_curve = pg.PlotDataItem(
            pen=pg.mkPen(self.OPT_HISTORY_COLORS["min_eff"], width=2),
            symbol="o",
            symbolSize=4,
            symbolBrush=pg.mkBrush(self.OPT_HISTORY_COLORS["min_eff"]),
            symbolPen=pg.mkPen(self.OPT_HISTORY_COLORS["min_eff"]),
        )
        self.optimization_auc_eff_curve = pg.PlotDataItem(
            pen=pg.mkPen(self.OPT_HISTORY_COLORS["auc_eff"], width=2),
            symbol="o",
            symbolSize=4,
            symbolBrush=pg.mkBrush(self.OPT_HISTORY_COLORS["auc_eff"]),
            symbolPen=pg.mkPen(self.OPT_HISTORY_COLORS["auc_eff"]),
        )
        self.optimization_throughput_curve = pg.PlotDataItem(
            pen=pg.mkPen(self.OPT_HISTORY_COLORS["throughput"], width=2),
            symbol="o",
            symbolSize=4,
            symbolBrush=pg.mkBrush(self.OPT_HISTORY_COLORS["throughput"]),
            symbolPen=pg.mkPen(self.OPT_HISTORY_COLORS["throughput"]),
        )
        self.optimization_throughput_auc_curve = pg.PlotDataItem(
            pen=pg.mkPen("#e879f9", width=2),
            symbol="o",
            symbolSize=4,
            symbolBrush=pg.mkBrush("#e879f9"),
            symbolPen=pg.mkPen("#e879f9"),
        )
        self.optimization_gate_count_curve = pg.PlotDataItem(
            pen=pg.mkPen(self.OPT_HISTORY_COLORS["gate_count"], width=2),
            symbol="o",
            symbolSize=4,
            symbolBrush=pg.mkBrush(self.OPT_HISTORY_COLORS["gate_count"]),
            symbolPen=pg.mkPen(self.OPT_HISTORY_COLORS["gate_count"]),
        )
        self._add_optimization_aux_axis("min_f", "Min F", self.optimization_best_f_curve)
        self._add_optimization_aux_axis("min_eff", "Min F^-2", self.optimization_best_eff_curve)
        self._add_optimization_aux_axis("auc_eff", "AUC F^-2", self.optimization_auc_eff_curve)
        self._add_optimization_aux_axis("throughput", "Throughput", self.optimization_throughput_curve)
        self._add_optimization_aux_axis("throughput_auc", "Throughput AUC", self.optimization_throughput_auc_curve)
        self._add_optimization_aux_axis("gate_count", "Gate count", self.optimization_gate_count_curve)
        self.optimization_right_vb = self.optimization_aux_vbs["min_f"]
        self.optimization_right_axis = self.optimization_aux_axes["min_f"]
        for key in ("min_eff", "auc_eff", "throughput", "throughput_auc", "gate_count"):
            self.optimization_aux_axes[key].setVisible(False)
            self.optimization_aux_vbs[key].setVisible(False)
        self.optimization_best_f_plot.getViewBox().sigResized.connect(self._sync_optimization_history_viewboxes)
        optimization_layout.addWidget(self.optimization_best_f_plot)

        metrics_legend = QWidget()
        metrics_legend_layout = QHBoxLayout(metrics_legend)
        metrics_legend_layout.setContentsMargins(0, 0, 0, 0)
        metrics_legend_layout.setSpacing(8)
        self.chk_opt_hist_objective = QCheckBox("Objective")
        self.chk_opt_hist_f = QCheckBox("Min F")
        self.chk_opt_hist_eff = QCheckBox("Min F^-2")
        self.chk_opt_hist_auc = QCheckBox("AUC F^-2")
        self.chk_opt_hist_throughput = QCheckBox("Throughput")
        self.chk_opt_hist_throughput_auc = QCheckBox("Throughput AUC")
        self.chk_opt_hist_gates = QCheckBox("Gate count")
        metrics_legend.setVisible(False)
        metrics_legend.setMaximumHeight(0)
        self.chk_opt_hist_log_x.toggled.connect(self._apply_optimization_history_axes)
        self.chk_opt_hist_log_y.toggled.connect(self._apply_optimization_history_axes)
        metrics_legend_layout.addStretch()
        optimization_layout.addWidget(metrics_legend)
        self.optimization_history_metric_defs = [
            ("objective", "Objective"),
            ("min_f", "Min F"),
            ("min_eff", "Min F^-2"),
            ("auc_eff", "AUC F^-2"),
            ("throughput", "Throughput"),
            ("throughput_auc", "Throughput AUC"),
            ("gate_count", "Gate count"),
        ]
        axis_selector = QWidget()
        axis_selector_layout = QVBoxLayout(axis_selector)
        axis_selector_layout.setContentsMargins(0, 0, 0, 0)
        axis_selector_layout.setSpacing(16)
        left_axis_widget = QWidget()
        left_axis_layout = QHBoxLayout(left_axis_widget)
        left_axis_layout.setContentsMargins(0, 0, 0, 0)
        left_axis_layout.setSpacing(8)
        left_axis_layout.addWidget(QLabel("Left axis:"))
        right_axis_widget = QWidget()
        right_axis_layout = QHBoxLayout(right_axis_widget)
        right_axis_layout.setContentsMargins(0, 0, 0, 0)
        right_axis_layout.setSpacing(8)
        right_axis_layout.addWidget(QLabel("Right axis:"))
        self.opt_hist_left_group = QButtonGroup(self)
        self.opt_hist_left_group.setExclusive(True)
        self.opt_hist_right_group = QButtonGroup(self)
        self.opt_hist_right_group.setExclusive(True)
        self.opt_hist_left_buttons = {}
        self.opt_hist_right_buttons = {}
        for key, label in self.optimization_history_metric_defs:
            left_btn = QRadioButton(label)
            right_btn = QRadioButton(label)
            self.opt_hist_left_group.addButton(left_btn)
            self.opt_hist_right_group.addButton(right_btn)
            self.opt_hist_left_buttons[key] = left_btn
            self.opt_hist_right_buttons[key] = right_btn
            left_axis_layout.addWidget(left_btn)
            right_axis_layout.addWidget(right_btn)
            left_btn.toggled.connect(self._on_optimization_axis_selection_changed)
            right_btn.toggled.connect(self._on_optimization_axis_selection_changed)
        self.opt_hist_left_buttons["objective"].setChecked(True)
        self.opt_hist_right_buttons["min_f"].setChecked(True)
        axis_selector_layout.addWidget(left_axis_widget, 1)
        axis_selector_layout.addWidget(right_axis_widget, 1)
        axis_selector_layout.addStretch()
        optimization_layout.addWidget(axis_selector)
        self._style_optimization_history_controls()
        self._apply_optimization_history_axes()

        optimization_layout.addStretch()
        self.tabs.addTab(optimization_tab, "Optimisation")

        self.combo_detection_start_anchor.currentIndexChanged.connect(self._sync_optimization_ui)
        self.combo_detection_start_anchor.currentIndexChanged.connect(self._sync_main_gate_controls_from_optimization)
        self.combo_detection_end_anchor.currentIndexChanged.connect(self._sync_optimization_ui)
        self.combo_detection_end_anchor.currentIndexChanged.connect(self._sync_main_gate_controls_from_optimization)
        self.spin_detection_start_anchor.valueChanged.connect(self._sync_main_gate_controls_from_optimization)
        self.spin_detection_end_anchor.valueChanged.connect(self._sync_main_gate_controls_from_optimization)
        self.combo_detection_algorithm.currentIndexChanged.connect(self._sync_optimization_ui)
        self.combo_optimization_mode.currentIndexChanged.connect(self._sync_optimization_ui)
        self.combo_optimization_objective.currentIndexChanged.connect(self._sync_optimization_ui)
        self.combo_excitation_optimization_profile.currentIndexChanged.connect(self._sync_optimization_ui)
        self.chk_opt_detection.toggled.connect(self._sync_optimization_ui)
        self.chk_opt_excitation.toggled.connect(self._sync_optimization_ui)
        self.chk_opt_count_rate.toggled.connect(self._sync_optimization_ui)
        self.chk_count_rate_accuracy_guard.toggled.connect(self._sync_optimization_ui)
        self.chk_optimization_realtime.toggled.connect(self._sync_optimization_ui)
        self.radio_f_basis_period.toggled.connect(self._sync_f_photon_basis_controls)
        self.radio_f_basis_all.toggled.connect(self._sync_f_photon_basis_controls)
        self.radio_f_basis_collected.toggled.connect(self._sync_f_photon_basis_controls)
        self.spin_precision_photons.valueChanged.connect(self._sync_photon_budget_from_precision)
        self.spin_photons.valueChanged.connect(self._sync_photon_budget_from_validation)
        self.spin_photons.valueChanged.connect(self._update_estimated_count_rate)
        self.spin_deadtime.valueChanged.connect(self._sync_detector_event_controls)
        self.spin_pixel_dwell.valueChanged.connect(self._sync_detector_event_controls)
        self.combo_pixel_dwell_unit.currentIndexChanged.connect(self._sync_detector_event_controls)
        self.chk_multihit.toggled.connect(self._sync_detector_event_controls)
        self.spin_max_events_per_period.valueChanged.connect(self._sync_detector_event_controls)
        self.spin_dark_count_rate.valueChanged.connect(self._sync_background_source_controls)
        self._sync_optimization_ui()
        self._sync_f_photon_basis_controls()
        self._set_detector_dwell_from_seconds(self.event_pixel_dwell_time_s)
        self._sync_detector_event_controls()
        self._sync_background_source_controls()

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
        sweep_list_group.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        sweep_list_layout.addWidget(self.radio_sweep_off)
        instr_layout.addWidget(sweep_list_group)

        self.sweep_detail_group = QGroupBox("Sweep Values")
        self.sweep_detail_form = QFormLayout(self.sweep_detail_group)
        self.sweep_detail_group.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.lbl_sweep_detail_title = QLabel("Batch sweep disabled")
        mode_header = QWidget()
        mode_header_layout = QHBoxLayout(mode_header)
        mode_header_layout.setContentsMargins(0, 0, 0, 0)
        mode_header_layout.setSpacing(4)
        mode_header_layout.addWidget(self.lbl_sweep_detail_title, 1)
        self.btn_sweep_load = self._make_icon_button(QStyle.StandardPixmap.SP_BrowserReload, "Load current sweep defaults from the active JSON file.", "Load")
        self.btn_sweep_save = self._make_icon_button(QStyle.StandardPixmap.SP_DialogSaveButton, "Save the currently edited sweep defaults to the active JSON file. This overwrites the current JSON.", "Save")
        self.btn_sweep_import = self._make_icon_button(QStyle.StandardPixmap.SP_DialogOpenButton, "Import sweep defaults from a JSON file and replace the current editable defaults.", "Import")
        self.btn_sweep_export = self._make_icon_button(QStyle.StandardPixmap.SP_DriveFDIcon, "Export the current editable sweep defaults to a JSON file.", "Export")
        self.btn_sweep_reset = self._make_icon_button(QStyle.StandardPixmap.SP_RestoreDefaultsButton, "Reset the active sweep-default JSON back to the installation defaults.", "Reset")
        for button in (
            self.btn_sweep_load,
            self.btn_sweep_save,
            self.btn_sweep_import,
            self.btn_sweep_export,
            self.btn_sweep_reset,
        ):
            mode_header_layout.addWidget(button, 0)
        self.sweep_detail_form.addRow("Mode:", mode_header)
        self.sweep_detail_stack = QStackedWidget()
        self.sweep_detail_form.addRow(self.sweep_detail_stack)
        instr_layout.addWidget(self.sweep_detail_group)

        def add_sweep_option(key, title, values_default, values_label="Values:",
                             extra_widget=None, extra_label=None, row_kind="numeric"):
            radio = QRadioButton(title)
            detail = QWidget()
            detail_layout = QVBoxLayout(detail)
            detail_layout.setContentsMargins(0, 0, 0, 0)
            detail_layout.setSpacing(6)
            values_container = QWidget()
            values_container_layout = QVBoxLayout(values_container)
            values_container_layout.setContentsMargins(0, 0, 0, 0)
            values_container_layout.setSpacing(4)
            add_top_row = QHBoxLayout()
            add_top_row.setContentsMargins(0, 0, 0, 0)
            add_top_row.setSpacing(4)
            btn_add_top = self._make_plus_button("Add a new sweep value.")
            add_top_row.addWidget(btn_add_top, 0)
            add_top_row.addStretch(1)
            values_container_layout.addLayout(add_top_row)
            rows_host = QWidget()
            rows_host_layout = QVBoxLayout(rows_host)
            rows_host_layout.setContentsMargins(0, 0, 0, 0)
            rows_host_layout.setSpacing(4)
            values_container_layout.addWidget(rows_host)
            detail_layout.addWidget(values_container)
            widgets = []
            extra_form = None
            if extra_widget is not None and extra_label is not None:
                extra_form = QFormLayout()
                extra_form.setContentsMargins(0, 0, 0, 0)
                extra_form.addRow(extra_label, extra_widget)
                detail_layout.addLayout(extra_form)
                widgets.append(extra_widget)
            sweep_list_layout.addWidget(radio)
            self.sweep_detail_stack.addWidget(detail)
            self.sweep_button_group.addButton(radio)
            self.sweep_options[key] = {
                "radio": radio,
                "title": title,
                "values": [],
                "extra": extra_widget,
                "widgets": widgets,
                "detail": detail,
                "rows_host_layout": rows_host_layout,
                "btn_add_top": btn_add_top,
                "values_label": values_label,
                "row_kind": row_kind,
            }
            initial_values = self._parse_float_list(values_default) if row_kind == "numeric" else list(values_default)
            self._set_sweep_values(key, initial_values)
            btn_add_top.clicked.connect(lambda _checked=False, sweep_key=key: self._append_sweep_value_row(sweep_key, None, 0))
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
        add_sweep_option("detector_jitter_ps", "Detector Jitter (ps)", "0, 25, 50, 100, 150")
        deadtime_rate = QLineEdit("100.0")
        add_sweep_option(
            "deadtime_fixed_countrate_ns",
            "Detector Deadtime (ns)",
            "0, 10, 25, 45, 90",
            extra_widget=deadtime_rate,
            extra_label="Count rate (kcps):",
        )
        add_sweep_option(
            "countrate_via_dwell_hz",
            "Count Rate via Pixel Dwell",
            "100000, 1000000, 10000000, 100000000, 1000000000",
        )
        add_sweep_option("multihit_capabilities", "Max events/period", "1, 2, 4, 8")
        add_sweep_option("afterpulsing_probability_pct", "Afterpulsing Probability (%)", "0, 0.5, 1, 2, 5")
        add_sweep_option("dark_count_rate_cps", "Detector Dark Count Rate (cps)", "0, 100, 1000, 10000, 100000")
        profile_names = [entry.get("name", "") for entry in self.instrument_profile_store.list_profiles()]
        if not profile_names:
            profile_names = ["HiLIGHT"]
        add_sweep_option(
            "instrument_profile",
            "Instrument Profiles",
            profile_names,
            row_kind="profile",
        )
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

        self._load_batch_sweep_defaults_into_ui(self.batch_sweep_defaults)
        self.sweep_options["countrate_via_dwell_hz"]["radio"].toggled.connect(self._sync_countrate_sweep_defaults)
        self.btn_sweep_load.clicked.connect(self._load_batch_sweep_defaults_from_store)
        self.btn_sweep_save.clicked.connect(self._save_batch_sweep_defaults_to_store)
        self.btn_sweep_import.clicked.connect(self._import_batch_sweep_defaults)
        self.btn_sweep_export.clicked.connect(self._export_batch_sweep_defaults)
        self.btn_sweep_reset.clicked.connect(self._reset_batch_sweep_defaults)

        self.radio_sweep_off.setChecked(True)
        self._update_sweep_inputs_enabled()

        instr_layout.addStretch()
        self.tabs.addTab(instr_tab, "Batch Sweep")
        self.tabs.tabBar().moveTab(1, 3)

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

        self.btn_precision = QPushButton("Run Analysis")
        self.btn_precision.setStyleSheet(
            "QPushButton { background-color: #1e3a8a; color: white; font-weight: bold; }"
            "QPushButton:disabled { background-color: #1f2937; color: #6b7280; }"
        )
        self.btn_precision.setMinimumHeight(btn_height)

        self.btn_export = QPushButton("SAVE AS")
        self.btn_export.setStyleSheet("background-color: #334155; color: white; font-weight: bold;")
        self.btn_export.setMinimumHeight(btn_height)

        self.btn_simulate = QPushButton("2D MC tests")
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
        self.chk_ideal_detector.toggled.connect(self._on_ideal_detector_toggled)
        self.chk_ideal_gates.toggled.connect(self._on_ideal_gates_toggled)
        self.spin_jitter.valueChanged.connect(self._sync_ideal_detector_checkbox_from_values)
        self.spin_deadtime.valueChanged.connect(self._sync_ideal_detector_checkbox_from_values)
        self.spin_afterpulsing.valueChanged.connect(self._sync_ideal_detector_checkbox_from_values)
        self.spin_dark_count_rate.valueChanged.connect(self._sync_ideal_detector_checkbox_from_values)
        self.chk_multihit.toggled.connect(self._sync_ideal_detector_checkbox_from_values)
        self.spin_max_events_per_period.valueChanged.connect(self._sync_ideal_detector_checkbox_from_values)
        self.spin_jitter.valueChanged.connect(self._update_detector_math_panel)
        self.spin_deadtime.valueChanged.connect(self._update_detector_math_panel)
        self.spin_afterpulsing.valueChanged.connect(self._update_detector_math_panel)
        self.spin_dark_count_rate.valueChanged.connect(self._update_detector_math_panel)
        self.chk_multihit.toggled.connect(self._update_detector_math_panel)
        self.chk_ideal_detector.toggled.connect(self._update_detector_math_panel)
        self.spin_gate_rise.valueChanged.connect(self._sync_ideal_gates_checkbox_from_values)
        self.spin_gate_fall.valueChanged.connect(self._sync_ideal_gates_checkbox_from_values)
        self.radio_overlap_jitter.toggled.connect(self._sync_ideal_gates_checkbox_from_values)
        self.radio_overlap_never.toggled.connect(self._sync_ideal_gates_checkbox_from_values)
        self.radio_overlap_yes.toggled.connect(self._sync_ideal_gates_checkbox_from_values)
        self.spin_gate_overlap.valueChanged.connect(self._sync_ideal_gates_checkbox_from_values)
        self.radio_overlap_effect_exclusive.toggled.connect(self._sync_ideal_gates_checkbox_from_values)
        self.radio_overlap_effect_duplicate.toggled.connect(self._sync_ideal_gates_checkbox_from_values)
        self.radio_overlap_effect_independent.toggled.connect(self._sync_ideal_gates_checkbox_from_values)
        self.spin_num_gates.valueChanged.connect(self._update_detector_math_panel)
        self.chk_ideal_gates.toggled.connect(self._update_detector_math_panel)
        self._sync_gate_controls()
        self._sync_ideal_detector_checkbox_from_values()
        self._sync_ideal_gates_checkbox_from_values()
        self._update_model_math_panel()
        self._update_detector_math_panel()
        self._update_simulation_mode_badge(
            {
                "preference": self.simulation_mode_preference,
                "effective_mode": "ideal_poisson",
                "requires_event_driven": False,
                "forced_event_driven": False,
                "reason": "Default simulation-core preference.",
                "approximated_event_effects": False,
            }
        )
        self._render_optimization_history()

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
        if self._anchor_syncing:
            return
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
        self._sync_optimization_controls_from_main_gate()
        self._apply_ideal_gates_state(self.chk_ideal_gates.isChecked())

    def _sync_optimization_controls_from_main_gate(self):
        self._anchor_syncing = True
        try:
            if self.radio_gate_irf.isChecked():
                self.combo_detection_start_anchor.setCurrentText("Start after IRF")
            elif self.radio_gate_free.isChecked():
                self.combo_detection_start_anchor.setCurrentText("Custom")
            else:
                self.combo_detection_start_anchor.setCurrentText("Stick to 0")
            self.spin_detection_start_anchor.setValue(float(self.spin_gate_first.value()))

            if self.radio_gate_end_free.isChecked():
                self.combo_detection_end_anchor.setCurrentText("Custom")
            else:
                self.combo_detection_end_anchor.setCurrentText("Stick to period")
            self.spin_detection_end_anchor.setValue(float(self.spin_gate_last.value()))
        finally:
            self._anchor_syncing = False

    def _sync_main_gate_controls_from_optimization(self, *_args):
        if self._anchor_syncing:
            return
        self._anchor_syncing = True
        try:
            start_mode = self.combo_detection_start_anchor.currentText().lower()
            if start_mode == "start after irf":
                self.radio_gate_irf.setChecked(True)
            elif start_mode == "custom":
                self.radio_gate_free.setChecked(True)
                self.spin_gate_first.setValue(float(self.spin_detection_start_anchor.value()))
            else:
                self.radio_gate_start.setChecked(True)
            if start_mode != "custom":
                self.spin_gate_first.setValue(float(self.spin_detection_start_anchor.value()))

            end_mode = self.combo_detection_end_anchor.currentText().lower()
            if end_mode == "custom":
                self.radio_gate_end_free.setChecked(True)
                self.spin_gate_last.setValue(float(self.spin_detection_end_anchor.value()))
            else:
                self.radio_gate_end_period.setChecked(True)
            if end_mode != "custom":
                self.spin_gate_last.setValue(float(self.spin_detection_end_anchor.value()))
        finally:
            self._anchor_syncing = False
        self._sync_gate_controls()

    def _sync_f_photon_basis_controls(self, *_args):
        if self._f_photon_basis_syncing:
            return
        self._f_photon_basis_syncing = True
        try:
            if self.radio_f_basis_collected.isChecked():
                mode = "collected"
            elif self.radio_f_basis_all.isChecked():
                mode = "all"
            else:
                mode = "period"
            self.current_f_photon_basis_mode = mode
        finally:
            self._f_photon_basis_syncing = False

    def _current_precision_basis_mode(self):
        if self.radio_f_basis_collected.isChecked():
            return "collected"
        if self.radio_f_basis_all.isChecked():
            return "all"
        return "period"

    def _set_precision_basis_mode(self, mode):
        mode_norm = str(mode).lower()
        if mode_norm == "collected":
            self.radio_f_basis_collected.setChecked(True)
        elif mode_norm == "all":
            self.radio_f_basis_all.setChecked(True)
        else:
            self.radio_f_basis_period.setChecked(True)

    def _matching_precision_preset(self):
        basis_mode = self._current_precision_basis_mode()
        for label, preset in self.PRECISION_PRESETS.items():
            if int(self.spin_precision_photons.value()) != int(preset["photons"]):
                continue
            if int(self.spin_mc_repeats.value()) != int(preset["mc_repeats"]):
                continue
            if not np.isclose(float(self.spin_accuracy_pvalue.value()), float(preset["accuracy_pvalue"]), rtol=0.0, atol=1e-12):
                continue
            if int(self.spin_bootstrap_samples.value()) != int(preset["bootstrap_samples"]):
                continue
            if basis_mode != str(preset.get("basis", "period")).lower():
                continue
            return label
        return "Custom"

    def _sync_precision_preset_selection(self, *_args):
        if self._precision_preset_syncing:
            return
        self._precision_preset_syncing = True
        try:
            self.combo_precision_preset.setCurrentText(self._matching_precision_preset())
        finally:
            self._precision_preset_syncing = False

    def _apply_precision_preset(self, preset_name):
        if self._precision_preset_syncing:
            return
        preset = self.PRECISION_PRESETS.get(str(preset_name))
        if preset is None:
            self._sync_precision_preset_selection()
            return
        self._precision_preset_syncing = True
        try:
            self.spin_precision_photons.setValue(int(preset["photons"]))
            self.spin_mc_repeats.setValue(int(preset["mc_repeats"]))
            self.spin_accuracy_pvalue.setValue(float(preset["accuracy_pvalue"]))
            self.spin_bootstrap_samples.setValue(int(preset["bootstrap_samples"]))
            self._set_precision_basis_mode(preset.get("basis", "period"))
            self.combo_precision_preset.setCurrentText(str(preset_name))
        finally:
            self._precision_preset_syncing = False
        self._sync_precision_preset_selection()

    def _update_ci_sigma_equivalence(self, *_args):
        ci_level = min(max(float(self.spin_ci_level.value()), 0.0), 99.999)
        central_probability = 0.5 + (ci_level / 200.0)
        sigma_equivalent = NormalDist().inv_cdf(central_probability)
        self.lbl_ci_sigma_equiv.setText(f"{sigma_equivalent:.1f}\u03c3")

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
        self._update_model_math_panel()

    def get_selected_decay_model_key(self):
        key = self.combo_decay_model.currentData()
        if isinstance(key, str) and key and key != "__add_custom__":
            return key
        return str(getattr(self, "_last_decay_model_key", "exponential") or "exponential")

    def refresh_decay_model_options(self, selected_key=None):
        current_key = str(selected_key or self.get_selected_decay_model_key() or "exponential")
        self.combo_decay_model.blockSignals(True)
        self.combo_decay_model.clear()
        for definition in self.decay_model_store.all_models():
            self.combo_decay_model.addItem(str(definition.get("name", definition.get("key", ""))), str(definition.get("key", "")))
        self.combo_decay_model.addItem("Add custom model...", "__add_custom__")
        match_index = self.combo_decay_model.findData(current_key)
        if match_index < 0:
            match_index = self.combo_decay_model.findData("exponential")
        if match_index < 0:
            match_index = 0
        self.combo_decay_model.setCurrentIndex(match_index)
        self.combo_decay_model.blockSignals(False)
        self._last_decay_model_key = self.get_selected_decay_model_key()
        self.update_param_visibility()

    def _runtime_cfg_for_defs(self):
        try:
            from backend.models import PhysicsConfig
        except ImportError:
            from python.backend.models import PhysicsConfig

        cfg = PhysicsConfig()
        cfg.decay_model = self.get_selected_decay_model_key()
        cfg.n_components = int(self.spin_n_comp.value())
        if "tau1" in self.param_rows:
            cfg.taus[0] = float(self.param_rows["tau1"]["val"].value())
        if "tau2" in self.param_rows:
            cfg.taus[1] = float(self.param_rows["tau2"]["val"].value())
        if "alpha" in self.param_rows:
            cfg.amplitudes[0] = float(self.param_rows["alpha"]["val"].value())
            if len(cfg.amplitudes) > 1:
                cfg.amplitudes[1] = max(0.0, 1.0 - cfg.amplitudes[0])
        if "background" in self.param_rows:
            cfg.background_level = float(self.param_rows["background"]["val"].value()) / 100.0
        if "beta" in self.param_rows:
            cfg.beta = float(self.param_rows["beta"]["val"].value())
        params = {}
        for name, row in self.param_rows.items():
            if name in self.base_param_names:
                continue
            params[name] = float(row["val"].value())
        cfg.custom_model_params = params
        return cfg

    def _runtime_param_meta(self, param_name):
        cfg = self._runtime_cfg_for_defs()
        for item in self.decay_model_store.runtime_param_defs(cfg):
            if str(item.get("name", "")) == str(param_name):
                return item
        return {}

    def _ensure_param_row(self, name, definition):
        row = self.param_rows.get(name)
        if row is None:
            unit = str(definition.get("unit", "") or "").strip()
            label_text = str(definition.get("label", name.title()))
            if unit:
                label_text = f"{label_text} ({unit}):"
            else:
                label_text = f"{label_text}:"
            tooltip = str(definition.get("description", "") or label_text)
            val, fix_chk, x_chk = self._add_param_row_helper(name, label_text, tooltip)
            x_chk.setProperty("param_name", name)
            x_chk.clicked.connect(self._handle_x_selection)
            self.x_group[name] = x_chk
            row = self.param_rows[name]
            row["val"].setValue(float(definition.get("default", 0.0) or 0.0))
        return row

    def _remove_dynamic_param_row(self, name):
        row = self.param_rows.pop(name, None)
        if row is None:
            return
        if name in self.x_group:
            self.x_group.pop(name, None)
        label = row["label"]
        self.param_grid.removeWidget(label)
        label.deleteLater()
        for idx in range(row["layout"].count()):
            widget = row["layout"].itemAt(idx).widget()
            if widget is not None:
                widget.deleteLater()

    def _handle_decay_model_selection_changed(self, *_args):
        key = self.combo_decay_model.currentData()
        if key == "__add_custom__":
            revert_index = self.combo_decay_model.findData(getattr(self, "_last_decay_model_key", "exponential"))
            if revert_index >= 0:
                self.combo_decay_model.blockSignals(True)
                self.combo_decay_model.setCurrentIndex(revert_index)
                self.combo_decay_model.blockSignals(False)
            self.custom_model_editor_requested.emit()
            return
        self._last_decay_model_key = self.get_selected_decay_model_key()
        self.update_param_visibility()

    def _handle_component_count_changed(self, value):
        new_count = int(value)
        old_count = int(getattr(self, "_last_n_components", 1))
        self._last_n_components = new_count
        if (
            old_count <= 1
            and new_count > 1
            and self.get_selected_decay_model_key() == "exponential"
            and "alpha" in self.param_rows
        ):
            alpha_spin = self.param_rows["alpha"]["val"]
            if abs(float(alpha_spin.value()) - 1.0) <= 1e-9:
                alpha_spin.blockSignals(True)
                alpha_spin.setValue(0.5)
                alpha_spin.blockSignals(False)
        self.update_param_visibility()

    def _apply_default_x_range(self, param_name):
        meta = self._runtime_param_meta(param_name)
        min_val = meta.get("sweep_min")
        max_val = meta.get("sweep_max")
        if min_val is None or max_val is None:
            if param_name not in self.default_x_ranges:
                return
            min_val, max_val = self.default_x_ranges[param_name]
        self.spin_fx_min.setValue(min_val)
        self.spin_fx_max.setValue(max_val)

    def _apply_default_x_scale(self, param_name):
        meta = self._runtime_param_meta(param_name)
        scale = str(meta.get("scale", "") or "").lower()
        if scale == "log":
            self.combo_fx_scale.setCurrentText("Log")
            return
        if scale == "linear":
            self.combo_fx_scale.setCurrentText("Linear")
            return
        if param_name in self.default_x_scales:
            self.combo_fx_scale.setCurrentText(self.default_x_scales[param_name])

    def _apply_tooltips(self):
        self.tabs.setTabToolTip(0, "Decay model, precision target, Monte Carlo validation, and bootstrap settings.")
        self.tabs.setTabToolTip(1, "Synthetic image generation settings.")
        self.tabs.setTabToolTip(2, "Excitation and IRF definition.")
        self.tabs.setTabToolTip(3, "Detector and gating settings.")
        self.tabs.setTabToolTip(4, "Detection and excitation optimisation settings.")
        self.tabs.setTabToolTip(0, "Decay model, Fisher sweep, and simulation-core settings.")
        self.tabs.setTabToolTip(1, "Laser excitation profile and burst-envelope settings.")
        self.tabs.setTabToolTip(2, "Detector and gate geometry settings.")
        self.tabs.setTabToolTip(3, "Monte Carlo image validation and fitted-image testing.")
        self.tabs.setTabToolTip(4, "Detection and excitation optimisation workflows.")
        self.tabs.setTabToolTip(5, "Instrument batch sweeps for comparative precision runs.")

        tooltips = {
            self.spin_n_comp: "Number of decay components used in the forward and inverse model.",
            self.spin_fx_min: "Minimum value of the selected swept decay parameter, shown with the correct physical units.",
            self.spin_fx_max: "Maximum value of the selected swept decay parameter, shown with the correct physical units.",
            self.spin_fx_steps: "Number of points in the precision sweep.",
            self.spin_grid_fine_factor: "Refinement factor used to build the gridded MLE lookup axis.",
            self.combo_fx_scale: "Spacing of the target-parameter sweep values.",
            self.chk_validate_mc: "Run Monte Carlo validation alongside the theoretical Fisher calculation.",
            self.chk_compute_ci: "Bootstrap the Monte Carlo repeats to estimate a confidence interval for F or F^-2.",
            self.combo_precision_preset: "Apply one of the built-in Fisher precision defaults for photons, Monte Carlo repeats, bootstrap count, and photon-basis reporting.",
            self.spin_precision_photons: "Photon count used in Fisher and Monte Carlo precision analysis.",
            self.spin_mc_repeats: "Number of Monte Carlo repeats per point on the precision sweep.",
            self.spin_accuracy_pvalue: "Bootstrap-based p-value threshold used to judge estimator accuracy.",
            self.spin_bootstrap_samples: "Number of bootstrap resamples used for p-values and confidence intervals.",
            self.spin_ci_level: "Confidence level used for the Monte Carlo interval display.",
            self.combo_deadtime_correction: "Apply a dead-time correction companion estimator and theory curve using the selected correction family. Isbaner and Rapp (MCHC) first correct the histogram and then reuse the standard detector-free gridded MLE, while Rapp (MCPDF) remains a detector-aware companion fit.",
            self.lbl_ci_sigma_equiv: "Approximate Gaussian sigma-equivalent for the currently selected central confidence interval.",
            self.spin_photons: "Average photon budget for synthetic image generation.",
            self.spin_image_repeats: "Requested number of Monte Carlo-style repeats represented for each swept x-axis value.",
            self.combo_image_fit_method: "Lifetime-fitting backend for the validation image.",
            self.btn_fit_image: "Fit the generated validation image using the selected algorithm.",
            self.spin_period: "Measurement repetition period in nanoseconds.",
            self.combo_profile: "Laser profile used to build the excitation waveform in the forward model.",
            self.spin_fwhm: "IRF width for Gaussian mode or pulse duration for rectangular mode.",
            self.spin_irf_pos: "IRF temporal position within the period.",
            self.spin_rise: "Rising edge time for rectangular excitation profiles.",
            self.spin_fall: "Falling edge time for rectangular excitation profiles.",
            self.btn_freeform_mode: "Switch between Editing and Using the free-form excitation profile.",
            self.freeform_editor: "Visual editor for free-form excitation. Double-click a point to select it, drag to move it, or double-click empty space and then Add Point to insert a new breakpoint.",
            self.group_burst: "Enable and configure burst excitation sub-pulses. The selected laser profile acts as the burst envelope.",
            self.spin_burst_period: "Interpulse distance between neighbouring sub-pulses in the burst (ps).",
            self.spin_burst_fwhm: "Pulse-width (FWHM) of each sub-pulse in the burst (ps).",
            self.spin_jitter: "Detector timing jitter in picoseconds.",
            self.spin_deadtime: "Detector deadtime in nanoseconds. Non-zero deadtime uses a nonparalyzable detector model.",
            self.spin_pixel_dwell: "Pixel dwell time used to infer the average count rate and the strength of deadtime or pile-up effects.",
            self.combo_pixel_dwell_unit: "Units for the pixel dwell time.",
            self.lbl_estimated_count_rate: "Estimated average count rate derived from the configured photons per pixel and pixel dwell time.",
            self.chk_ideal_detector: "Restore ideal detector behaviour by setting jitter, deadtime, afterpulsing, and dark counts to zero while allowing unlimited multihit collection.",
            self.chk_multihit: "Allow more than one accepted photon event in each repetition period.",
            self.spin_max_events_per_period: "Maximum accepted photon events in each repetition period. Disable multihit to force single-hit operation.",
            self.spin_afterpulsing: "Detector afterpulsing probability in percent. Higher values add delayed detector-originated counts after true events.",
            self.spin_dark_count_rate: "Detector dark count rate in counts per second. Non-zero dark counts replace the manual decay background control.",
            self.chk_ideal_gates: "Restore ideal gate shapes with zero edge rise/fall and no explicit overlap effects.",
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
            self.radio_f_basis_period: "Estimate precision from the photons actually collected, then report F against the photons that fell inside the acquisition period before gate or pile-up losses.",
            self.radio_f_basis_all: "Estimate precision from the photons actually collected, then report F against the full available photon budget, including photons outside the acquisition period.",
            self.radio_f_basis_collected: "Estimate and report F on the collected-photon basis only, with no loss rescaling.",
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
            self.chk_opt_count_rate: "Sweep count rate by changing pixel dwell time and optimise the selected Fisher objective.",
            self.spin_count_rate_min_kcps: "Minimum count rate considered during count-rate optimisation, in kilocounts per second.",
            self.spin_count_rate_max_kcps: "Maximum count rate considered during count-rate optimisation, in kilocounts per second.",
            self.spin_count_rate_steps: "Number of count-rate candidates evaluated between the minimum and maximum bounds.",
            self.combo_count_rate_scale: "Spacing of the count-rate candidates during optimisation.",
            self.chk_count_rate_accuracy_guard: "Reject count-rate candidates whose predicted estimator bias exceeds the selected threshold.",
            self.spin_count_rate_max_bias_pct: "Maximum allowed predicted absolute relative bias across the sweep during count-rate optimisation.",
            self.spin_optimization_iterations: "Maximum number of alternating detection/excitation rounds when both optimisation targets are enabled.",
            self.combo_optimization_objective: "Excitation optimisation objective. Fisher Throughput is the default and combines peak photon efficiency with throughput scaling.",
            self.spin_optimization_fi_loss: "Maximum absolute peak photon-efficiency loss allowed in throughput mode, expressed as F^-2 percentage points relative to the Dirac-reference design.",
            self.chk_optimization_realtime: "When enabled, update the main analysis widgets during optimisation. Disable this for a faster run.",
            self.spin_optimization_realtime_interval: "Minimum number of seconds between live Precision, Accuracy, and Diagnostics refreshes during optimisation.",
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
            self.chk_opt_hist_log_x: "Show the optimisation-history x axis in logarithmic scale.",
            self.chk_opt_hist_log_y: "Show the optimisation-history y axes in logarithmic scale.",
            self.radio_sweep_off: "Disable instrument batch sweeping.",
            self.btn_manage_inst: "Open the instrument-profile manager.",
            self.btn_precision: "Run the current analysis workflow, including precision calculations and active result views.",
            self.btn_interrupt: "Request interruption of the current run.",
            self.btn_export: "Preview the latest precision report and save it as an HTML package with SVG and CSV assets.",
            self.btn_simulate: "Generate and analyse synthetic 2D Monte Carlo validation images using the swept x-axis parameter.",
        }
        for widget, text in tooltips.items():
            widget.setToolTip(text)

        for name, row in self.param_rows.items():
            row["val"].setToolTip(f"Nominal value for {name} in the current model.")
            row["fix"].setToolTip(f"Keep {name} fixed during inverse estimation.")

        for spec in self.sweep_options.values():
            spec["radio"].setToolTip(f"Activate the batch sweep mode: {spec['title']}.")
            for row in spec["values"]:
                row["edit"].setToolTip("One sweep value for this instrument parameter. Use the plus button to add more values.")
                row["trash"].setToolTip("Remove this sweep value.")
                row["add"].setToolTip("Add a new sweep value below this one.")
            spec["btn_add_top"].setToolTip("Add a new sweep value to this mode.")
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
        cfg = self._runtime_cfg_for_defs()
        model = self.decay_model_store.get(cfg.decay_model)
        supports_components = bool(model.get("supports_components", False))
        if not supports_components:
            self.spin_n_comp.blockSignals(True)
            self.spin_n_comp.setValue(1)
            self.spin_n_comp.blockSignals(False)
            cfg.n_components = 1
        self.spin_n_comp.setEnabled(supports_components)

        runtime_defs = self.decay_model_store.runtime_param_defs(cfg)
        desired_names = [str(item.get("name", "")) for item in runtime_defs]
        for name in list(self.param_rows.keys()):
            if name not in desired_names and name not in self.base_param_names:
                self._remove_dynamic_param_row(name)

        for definition in runtime_defs:
            name = str(definition.get("name", ""))
            row = self._ensure_param_row(name, definition)
            unit = str(definition.get("unit", "") or "").strip()
            label_text = str(definition.get("label", name.title()))
            row["label"].setText(f"{label_text} ({unit}):" if unit else f"{label_text}:")
            tooltip = str(definition.get("description", "") or label_text)
            row["label"].setToolTip(tooltip)
            row["val"].setToolTip(tooltip)
            lower = definition.get("bounds_min")
            upper = definition.get("bounds_max")
            row["val"].setRange(float(lower if lower is not None else 0.0), float(upper if upper is not None else 1000.0))
            row["val"].setVisible(True)
            row["label"].setVisible(True)
            for i in range(row["layout"].count()):
                w = row["layout"].itemAt(i).widget()
                if w:
                    w.setVisible(True)

        for name in list(self.param_rows.keys()):
            if name in desired_names:
                continue
            row = self.param_rows[name]
            row["label"].setVisible(False)
            for i in range(row["layout"].count()):
                w = row["layout"].itemAt(i).widget()
                if w:
                    w.setVisible(False)
            if row["x"].isChecked():
                row["x"].setChecked(False)
        self.enforce_single_x_selection()
        self._update_model_math_panel()
        self._update_detector_math_panel()

    def _update_model_math_panel(self):
        if not hasattr(self, "model_math_panel"):
            return
        model_key = self.get_selected_decay_model_key()
        definition = self.decay_model_store.get(model_key)
        equation = str(definition.get("equation_html") or definition.get("expression") or "n/a")
        description = str(definition.get("description_specialist") or definition.get("description_plain") or "")
        params = []
        for item in self.decay_model_store.runtime_param_defs(self._runtime_cfg_for_defs()):
            name = str(item.get("name", ""))
            if name not in self.param_rows:
                continue
            params.append(f"{item.get('label', name)} = {self.param_rows[name]['val'].value():g} {item.get('unit', '')}".strip())
        model_name = str(definition.get("name", model_key))
        self.model_math_panel.setHtml(
            f"<b>{model_name}</b><br>"
            f"<span style='color:#93c5fd;'>I(t)</span> = <code>{equation}</code><br><br>"
            f"{description}<br><br>"
            f"<b>Active parameters</b><br>{'<br>'.join(params) if params else 'None'}"
        )

    def _update_detector_math_panel(self):
        if not hasattr(self, "detector_math_panel") or not hasattr(self, "chk_ideal_detector"):
            return
        ideal_detector = bool(self.chk_ideal_detector.isChecked())
        ideal_gates = bool(self.chk_ideal_gates.isChecked())
        deadtime_ns = float(self.spin_deadtime.value())
        jitter_ps = float(self.spin_jitter.value())
        afterpulse_pct = float(self.spin_afterpulsing.value())
        dark_cps = float(self.spin_dark_count_rate.value())
        multihit = bool(self.chk_multihit.isChecked())
        gate_count = int(self.spin_num_gates.value())
        transfer_terms = [
            "<b>Detector transfer</b>",
            "p_det(t) ∝ G(t) · [p_latent(t) * T_det(t)]",
            f"Ideal detector: {'yes' if ideal_detector else 'no'}",
            f"Ideal gates: {'yes' if ideal_gates else 'no'}",
            f"Gate count: {gate_count}",
            f"Timing jitter σ_t = {jitter_ps:g} ps",
            f"Dead time t_d = {deadtime_ns:g} ns",
            f"Multihit enabled: {'yes' if multihit else 'no'}",
            f"Afterpulsing = {afterpulse_pct:g}%",
            f"Dark count rate = {dark_cps:g} cps",
        ]
        if ideal_gates:
            transfer_terms.append("G(t) is ideal contiguous binning with no overlap and no wraparound.")
        else:
            transfer_terms.append("G(t) includes finite rise/fall, overlap rules, and optional wraparound.")
        if ideal_detector:
            transfer_terms.append("T_det(t)=1 except for gating; detector-event distortions are disabled.")
        else:
            transfer_terms.append("T_det(t) includes timing blur, dead time, multihit constraints, afterpulsing, and dark counts.")
        self.detector_math_panel.setHtml("<br>".join(transfer_terms))

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

    def _normalise_latex_expression(self, expression: str) -> str:
        text = str(expression or "").strip()
        if not text:
            return r"\mathrm{n/a}"
        text = text.replace("\\\\", "\\")
        text = text.replace("⋅", r"\cdot ")
        text = re.sub(r"(?<!\\)alpha", r"\\alpha", text)
        text = re.sub(r"(?<!\\)beta", r"\\beta", text)
        text = re.sub(r"(?<!\\)tau", r"\\tau", text)
        return text

    def _render_latex_block(self, latex: str, color: str) -> str:
        uri = self._latex_to_data_uri(latex, color=color)
        if uri:
            return f"<div style='margin:4px 0;'><img src='{uri}'></div>"
        return f"<pre style='margin:4px 0; color:{color};'>{html.escape(latex)}</pre>"

    def _latex_to_data_uri(self, latex: str, color: str = "#e5e7eb", fontsize: float = 14.0) -> str:
        key = (latex, color, float(fontsize))
        cached = self._math_render_cache.get(key)
        if cached:
            return cached
        try:
            fig = Figure(figsize=(0.01, 0.01), dpi=200)
            fig.patch.set_alpha(0.0)
            canvas = FigureCanvasAgg(fig)
            text_artist = fig.text(0.0, 0.0, f"${latex}$", color=color, fontsize=fontsize)
            canvas.draw()
            bbox = text_artist.get_window_extent(renderer=canvas.get_renderer()).expanded(1.02, 1.12)
            fig.set_size_inches(max(bbox.width / fig.dpi, 0.01), max(bbox.height / fig.dpi, 0.01))
            text_artist.set_position((0.0, 0.0))
            canvas.draw()
            buffer = BytesIO()
            fig.savefig(buffer, format="png", dpi=200, transparent=True, bbox_inches="tight", pad_inches=0.02)
            data = base64.b64encode(buffer.getvalue()).decode("ascii")
            uri = f"data:image/png;base64,{data}"
            self._math_render_cache[key] = uri
            return uri
        except Exception:
            return ""

    def _update_model_math_panel(self):
        if not hasattr(self, "model_math_panel"):
            return
        model_key = self.get_selected_decay_model_key()
        definition = self.decay_model_store.get(model_key)
        equation = str(definition.get("equation_html") or definition.get("expression") or "n/a").strip()
        description = str(definition.get("description_specialist") or definition.get("description_plain") or "")
        model_name = str(definition.get("name", model_key))
        self.model_math_panel.setHtml(
            "<div style='line-height:1.45;'>"
            f"<div style='font-weight:700; color:#ffffff; margin-bottom:6px;'>{html.escape(model_name)}</div>"
            f"{self._render_latex_block(self._normalise_latex_expression(equation), '#dbeafe')}"
            f"<div style='margin-top:8px; color:#cbd5e1;'>{html.escape(description)}</div>"
            "</div>"
        )

    def _update_detector_math_panel(self):
        if not hasattr(self, "detector_math_panel") or not hasattr(self, "chk_ideal_detector"):
            return
        ideal_detector = bool(self.chk_ideal_detector.isChecked())
        ideal_gates = bool(self.chk_ideal_gates.isChecked())
        multihit = bool(self.chk_multihit.isChecked())
        eq_main = r"p_{\mathrm{det}}(t)\propto G(t)\,\left[p_{\mathrm{latent}}(t)\ast T_{\mathrm{det}}(t)\right]"
        eq_gates = r"G(t)=\sum_k \mathbf{1}_{[t_k,t_{k+1})}(t)" if ideal_gates else r"G(t)\ \mathrm{includes\ rise/fall,\ overlap,\ and\ optional\ wraparound}"
        eq_transfer = r"T_{\mathrm{det}}(t)=1" if ideal_detector else r"T_{\mathrm{det}}(t)\ \mathrm{encodes\ jitter,\ dead\ time,\ multihit,\ afterpulsing,\ and\ dark\ counts}"
        notes = [
            "Ideal gates use contiguous non-overlapping bins over the acquisition window." if ideal_gates else "Non-ideal gates include the configured edge transitions and overlap rules.",
            "Ideal detector disables detector-event distortions beyond gating." if ideal_detector else "Detector transfer function is active. DTF models detector-event distortions applied to the latent decay.",
            "Multihit collection is enabled." if multihit else "Single-hit collection is enforced per excitation period.",
        ]
        self.detector_math_panel.setHtml(
            "<div style='line-height:1.45;'>"
            "<div style='font-weight:700; color:#ffffff; margin-bottom:6px;'>Detector transfer</div>"
            f"{self._render_latex_block(eq_main, '#dbeafe')}"
            f"{self._render_latex_block(eq_gates, '#cbd5e1')}"
            f"{self._render_latex_block(eq_transfer, '#cbd5e1')}"
            f"<div style='margin-top:8px; color:#cbd5e1;'>{'<br>'.join(html.escape(item) for item in notes)}</div>"
            "</div>"
        )

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
            self.advanced_config_changed.emit()

    def _open_event_simulation_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Event-driven Detector Settings")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        combo_deadtime = QComboBox()
        combo_deadtime.addItems(["None", "Nonparalyzable", "Paralyzable"])
        combo_deadtime.setCurrentText(str(self.event_deadtime_mode).replace("_", " ").title())
        combo_deadtime.setToolTip("Deadtime law applied to each detector resource group.")
        form.addRow("Deadtime mode:", combo_deadtime)

        combo_capacity = QComboBox()
        combo_capacity.addItems(["Infinite", "First-hit", "Custom"])
        current_capacity = self.event_multihit_capacity
        if current_capacity is None:
            combo_capacity.setCurrentText("Infinite" if self.chk_multihit.isChecked() else "First-hit")
        elif int(current_capacity) == 1:
            combo_capacity.setCurrentText("First-hit")
        else:
            combo_capacity.setCurrentText("Custom")
        combo_capacity.setToolTip("Accepted hits per detector resource during one pixel dwell.")
        spin_capacity = QSpinBox()
        spin_capacity.setRange(2, 10_000)
        spin_capacity.setValue(int(current_capacity) if current_capacity not in (None, 1) else 4)
        spin_capacity.setEnabled(combo_capacity.currentText() == "Custom")
        spin_capacity.setToolTip("Finite multihit capacity used when Custom is selected.")
        combo_capacity.currentTextChanged.connect(lambda text: spin_capacity.setEnabled(text == "Custom"))
        capacity_row = QWidget()
        capacity_layout = QHBoxLayout(capacity_row)
        capacity_layout.setContentsMargins(0, 0, 0, 0)
        capacity_layout.setSpacing(6)
        capacity_layout.addWidget(combo_capacity, 2)
        capacity_layout.addWidget(QLabel("Custom C:"))
        capacity_layout.addWidget(spin_capacity, 1)
        form.addRow("Capacity:", capacity_row)

        combo_routing = QComboBox()
        combo_routing.addItems(["Exclusive", "Nonexclusive"])
        combo_routing.setCurrentText(str(self.event_routing_mode).replace("_", " ").title())
        combo_routing.setToolTip("How simultaneously accepted channels are routed for the same latent photon.")
        form.addRow("Routing:", combo_routing)

        combo_arbitration = QComboBox()
        combo_arbitration.addItems(["Random", "Priority", "All If Independent"])
        combo_arbitration.setCurrentText(str(self.event_arbitration_rule).replace("_", " ").title())
        combo_arbitration.setToolTip("Rule used when multiple channels compete for the same event.")
        form.addRow("Arbitration:", combo_arbitration)

        chk_shared = QCheckBox("Share detector resource group across gates")
        chk_shared.setChecked(bool(self.event_share_resource_group))
        chk_shared.setToolTip("If enabled, all gates share the same deadtime/capacity resource.")
        form.addRow(chk_shared)

        chk_timestamps = QCheckBox("Return accepted event timestamps")
        chk_timestamps.setChecked(bool(self.event_return_timestamps))
        chk_timestamps.setToolTip("Include accepted event timestamps in event-driven simulation results.")
        form.addRow(chk_timestamps)

        dwell_row = QWidget()
        dwell_layout = QHBoxLayout(dwell_row)
        dwell_layout.setContentsMargins(0, 0, 0, 0)
        dwell_layout.setSpacing(6)
        spin_dwell = QDoubleSpinBox()
        spin_dwell.setRange(1e-6, 1e9)
        spin_dwell.setDecimals(6)
        spin_dwell.setSingleStep(1.0)
        combo_dwell_units = QComboBox()
        combo_dwell_units.addItems(["ns", "us", "ms", "s"])
        dwell_s = float(getattr(self, "event_pixel_dwell_time_s", 1e-3))
        if dwell_s >= 1.0:
            spin_dwell.setValue(dwell_s)
            combo_dwell_units.setCurrentText("s")
        elif dwell_s >= 1e-3:
            spin_dwell.setValue(dwell_s * 1e3)
            combo_dwell_units.setCurrentText("ms")
        elif dwell_s >= 1e-6:
            spin_dwell.setValue(dwell_s * 1e6)
            combo_dwell_units.setCurrentText("us")
        else:
            spin_dwell.setValue(dwell_s * 1e9)
            combo_dwell_units.setCurrentText("ns")
        spin_dwell.setToolTip("Pixel dwell time used to infer count rate for event-driven deadtime and pile-up effects.")
        combo_dwell_units.setToolTip("Units for the pixel dwell time.")
        dwell_layout.addWidget(spin_dwell, 2)
        dwell_layout.addWidget(combo_dwell_units, 1)
        form.addRow("Pixel dwell time:", dwell_row)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec():
            self.event_deadtime_mode = combo_deadtime.currentText().strip().lower().replace(" ", "_")
            capacity_mode = combo_capacity.currentText().strip().lower()
            if capacity_mode == "infinite":
                self.event_multihit_capacity = None
                self.chk_multihit.setChecked(True)
            elif capacity_mode == "first-hit":
                self.event_multihit_capacity = 1
                self.chk_multihit.setChecked(False)
            else:
                self.event_multihit_capacity = int(spin_capacity.value())
                self.chk_multihit.setChecked(True)
            self.event_routing_mode = combo_routing.currentText().strip().lower().replace(" ", "_")
            self.event_arbitration_rule = combo_arbitration.currentText().strip().lower().replace(" ", "_")
            self.event_share_resource_group = bool(chk_shared.isChecked())
            self.event_return_timestamps = bool(chk_timestamps.isChecked())
            dwell_value = float(spin_dwell.value())
            dwell_unit = combo_dwell_units.currentText()
            scale = {"ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1.0}.get(dwell_unit, 1.0)
            self.event_pixel_dwell_time_s = dwell_value * scale
            self.advanced_config_changed.emit()

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

    def _detector_dwell_seconds(self) -> float:
        value = float(self.spin_pixel_dwell.value())
        unit = self.combo_pixel_dwell_unit.currentText()
        scale = {"ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1.0}.get(unit, 1.0)
        return max(value * scale, 1e-12)

    def _set_detector_dwell_from_seconds(self, dwell_s: float) -> None:
        dwell_s = float(max(dwell_s, 1e-12))
        if dwell_s >= 1.0:
            self.spin_pixel_dwell.setValue(dwell_s)
            self.combo_pixel_dwell_unit.setCurrentText("s")
        elif dwell_s >= 1e-3:
            self.spin_pixel_dwell.setValue(dwell_s * 1e3)
            self.combo_pixel_dwell_unit.setCurrentText("ms")
        elif dwell_s >= 1e-6:
            self.spin_pixel_dwell.setValue(dwell_s * 1e6)
            self.combo_pixel_dwell_unit.setCurrentText("us")
        else:
            self.spin_pixel_dwell.setValue(dwell_s * 1e9)
            self.combo_pixel_dwell_unit.setCurrentText("ns")

    def _format_count_rate(self, rate_hz: float) -> str:
        rate_hz = float(max(rate_hz, 0.0))
        if rate_hz >= 1e9:
            return f"{rate_hz / 1e9:.3f} Gcps"
        if rate_hz >= 1e6:
            return f"{rate_hz / 1e6:.3f} Mcps"
        if rate_hz >= 1e3:
            return f"{rate_hz / 1e3:.3f} kcps"
        return f"{rate_hz:.3f} cps"

    def _sync_photon_budget_from_precision(self, value):
        if self._photon_budget_syncing:
            return
        self._photon_budget_syncing = True
        try:
            self.spin_photons.setValue(int(value))
        finally:
            self._photon_budget_syncing = False
        self._update_estimated_count_rate()

    def _sync_photon_budget_from_validation(self, value):
        if self._photon_budget_syncing:
            return
        self._photon_budget_syncing = True
        try:
            self.spin_precision_photons.setValue(int(value))
        finally:
            self._photon_budget_syncing = False
        self._update_estimated_count_rate()

    def _sync_background_source_controls(self, *_args):
        dark_active = float(getattr(self, "spin_dark_count_rate", None).value()) > 0.0 if hasattr(self, "spin_dark_count_rate") else False
        if "background" in self.param_rows:
            row = self.param_rows["background"]
            row["val"].setEnabled(not dark_active)
            row["fix"].setEnabled(not dark_active)
            row["x"].setEnabled(not dark_active)
            if dark_active and row["x"].isChecked():
                row["x"].setChecked(False)

    def _sync_ideal_detector_checkbox_from_values(self, *_args):
        if self._ideal_detector_syncing:
            return
        capacity_val = int(self.spin_max_events_per_period.value())
        is_ideal = (
            float(self.spin_jitter.value()) == 0.0
            and float(self.spin_deadtime.value()) == 0.0
            and float(self.spin_afterpulsing.value()) == 0.0
            and float(self.spin_dark_count_rate.value()) == 0.0
            and self.chk_multihit.isChecked()
            and capacity_val >= self.EVENT_CAPACITY_UNLIMITED
        )
        self._ideal_detector_syncing = True
        try:
            self.chk_ideal_detector.setChecked(is_ideal)
        finally:
            self._ideal_detector_syncing = False
        self._apply_ideal_detector_state(is_ideal)

    def _apply_ideal_detector_state(self, is_ideal: bool):
        self.detector_row_one_widget.setVisible(not is_ideal)
        self.detector_runtime_row_widget.setVisible(not is_ideal)
        self.detector_effects_row_widget.setVisible(not is_ideal)
        for widget in (
            self.spin_jitter,
            self.spin_deadtime,
            self.spin_pixel_dwell,
            self.combo_pixel_dwell_unit,
            self.chk_multihit,
            self.spin_max_events_per_period,
            self.spin_afterpulsing,
            self.spin_dark_count_rate,
        ):
            widget.setEnabled(not is_ideal)

    def _on_ideal_detector_toggled(self, checked: bool):
        if self._ideal_detector_syncing:
            return
        self._ideal_detector_syncing = True
        try:
            if checked:
                self.spin_jitter.setValue(0)
                self.spin_deadtime.setValue(0)
                self.spin_afterpulsing.setValue(0.0)
                self.spin_dark_count_rate.setValue(0.0)
                self.chk_multihit.setChecked(True)
                self.spin_max_events_per_period.setValue(self.EVENT_CAPACITY_UNLIMITED)
            self._apply_ideal_detector_state(bool(checked))
        finally:
            self._ideal_detector_syncing = False
        self._sync_detector_event_controls()
        self._sync_background_source_controls()

    def _sync_ideal_gates_checkbox_from_values(self, *_args):
        if self._ideal_gates_syncing:
            return
        is_ideal = (
            float(self.spin_gate_rise.value()) == 0.0
            and float(self.spin_gate_fall.value()) == 0.0
            and self.radio_overlap_never.isChecked()
            and float(self.spin_gate_overlap.value()) == 0.0
            and self.radio_overlap_effect_exclusive.isChecked()
            and self.radio_gate_collection_hist.isChecked()
            and not self.chk_gate_wraparound.isChecked()
        )
        self._ideal_gates_syncing = True
        try:
            self.chk_ideal_gates.setChecked(is_ideal)
        finally:
            self._ideal_gates_syncing = False
        self._apply_ideal_gates_state(is_ideal)

    def _apply_ideal_gates_state(self, is_ideal: bool):
        self.gate_nonideal_row_widget.setVisible(not is_ideal)
        self.gate_collection_group.setVisible(not is_ideal)
        self.gate_overlap_row_widget.setVisible(not is_ideal)
        self.spin_gate_rise.setEnabled(not is_ideal)
        self.spin_gate_fall.setEnabled(not is_ideal)
        self.chk_gate_wraparound.setEnabled(not is_ideal)
        self.radio_gate_collection_hist.setEnabled(not is_ideal)
        self.radio_gate_collection_seq.setEnabled(not is_ideal)
        self.radio_overlap_jitter.setEnabled(not is_ideal)
        self.radio_overlap_never.setEnabled(not is_ideal)
        self.radio_overlap_yes.setEnabled(not is_ideal)
        self.spin_gate_overlap.setEnabled((not is_ideal) and self.radio_overlap_yes.isChecked())
        self.radio_overlap_effect_exclusive.setEnabled(not is_ideal)
        self.radio_overlap_effect_duplicate.setEnabled(not is_ideal)
        self.radio_overlap_effect_independent.setEnabled(not is_ideal)

    def _on_ideal_gates_toggled(self, checked: bool):
        if self._ideal_gates_syncing:
            return
        self._ideal_gates_syncing = True
        try:
            if checked:
                self.spin_gate_rise.setValue(0.0)
                self.spin_gate_fall.setValue(0.0)
                self.radio_gate_collection_hist.setChecked(True)
                self.radio_overlap_never.setChecked(True)
                self.spin_gate_overlap.setValue(0.0)
                self.radio_overlap_effect_exclusive.setChecked(True)
                self.chk_gate_wraparound.setChecked(False)
            self._apply_ideal_gates_state(bool(checked))
        finally:
            self._ideal_gates_syncing = False
        self._sync_gate_controls()

    def _update_estimated_count_rate(self) -> None:
        dwell_s = float(max(getattr(self, "event_pixel_dwell_time_s", self._detector_dwell_seconds()), 1e-12))
        avg_photons = float(self.spin_precision_photons.value())
        self.lbl_estimated_count_rate.setText(self._format_count_rate(avg_photons / dwell_s))

    def _sync_detector_event_controls(self, *_args) -> None:
        self.event_pixel_dwell_time_s = self._detector_dwell_seconds()
        self.event_deadtime_mode = "none" if float(self.spin_deadtime.value()) <= 0.0 else "nonparalyzable"

        if self.chk_multihit.isChecked():
            self.spin_max_events_per_period.setEnabled(True)
            if self.spin_max_events_per_period.value() < 2:
                self.spin_max_events_per_period.setValue(2)
            cap_val = int(self.spin_max_events_per_period.value())
            self.event_multihit_capacity = None if cap_val >= self.EVENT_CAPACITY_UNLIMITED else cap_val
        else:
            if self.spin_max_events_per_period.value() != 1:
                self.spin_max_events_per_period.setValue(1)
            self.spin_max_events_per_period.setEnabled(False)
            self.event_multihit_capacity = 1

        self._update_estimated_count_rate()
        self._apply_ideal_detector_state(self.chk_ideal_detector.isChecked())

    def _cycle_simulation_mode_preference(self):
        order = ["auto", "event_driven", "ideal_poisson"]
        current = str(getattr(self, "simulation_mode_preference", "auto")).lower()
        if current not in order:
            current = "auto"
        next_idx = (order.index(current) + 1) % len(order)
        self.simulation_mode_preference = order[next_idx]
        self._set_core_badge(
            self.btn_simulation_mode_badge,
            {
                "preference": self.simulation_mode_preference,
                "effective_mode": self.simulation_mode_preference if self.simulation_mode_preference != "auto" else "ideal_poisson",
                "requires_event_driven": False,
                "forced_event_driven": self.simulation_mode_preference == "event_driven",
                "reason": "User-selected simulation-core preference.",
            }
        )
        self.advanced_config_changed.emit()

    def _set_core_badge(self, button, status):
        preference = str((status or {}).get("preference", "auto")).lower()
        effective = str((status or {}).get("effective_mode", "ideal_poisson")).lower()
        required = bool((status or {}).get("requires_event_driven", False))
        approximated = bool((status or {}).get("approximated_event_effects", False))
        reason = str((status or {}).get("reason", ""))

        if preference == "event_driven":
            text = "Event-driven (forced)"
            bg = "#d946ef"
        elif approximated and effective == "ideal_poisson":
            if preference == "ideal_poisson":
                text = "Ideal Poisson (forced, detector effects)"
            else:
                text = "Ideal Poisson (detector effects)"
            bg = "#f59e0b"
        elif preference == "ideal_poisson":
            text = "Ideal Poisson (forced)"
            bg = "#16a34a"
        elif effective == "event_driven":
            text = "Event-driven (auto)"
            bg = "#d946ef"
        else:
            text = "Ideal Poisson (auto)"
            bg = "#16a34a"

        button.setText(text)
        button.setStyleSheet(
            f"QToolButton {{ background-color: {bg}; color: white; font-weight: bold; border-radius: 6px; padding: 4px 10px; }}"
        )
        tooltip = f"Effective core: {effective}\nPreference: {preference}\nReason: {reason}"
        if required and preference == "auto":
            tooltip += "\nThe current detector configuration requires the event-driven core."
        elif approximated and effective == "ideal_poisson":
            tooltip += "\nDetector event effects are being approximated by the Ideal Poisson core."
        button.setToolTip(tooltip)

    def _set_core_badge(self, button, status):
        preference = str((status or {}).get("preference", "auto")).lower()
        effective = str((status or {}).get("effective_mode", "ideal_poisson")).lower()
        required = bool((status or {}).get("requires_event_driven", False))
        approximated = bool((status or {}).get("approximated_event_effects", False))
        reason = str((status or {}).get("reason", ""))

        if effective == "event_driven":
            text = "Event-driven"
            bg = "#d946ef"
        elif approximated and effective == "ideal_poisson":
            text = "Poisson (+DTF)"
            bg = "#f59e0b"
        else:
            text = "Poisson"
            bg = "#16a34a"

        button.setText(text)
        button.setStyleSheet(
            f"QToolButton {{ background-color: {bg}; color: white; font-weight: bold; border-radius: 6px; padding: 4px 8px; }}"
        )

        pref_label = {
            "auto": "auto",
            "ideal_poisson": "Poisson",
            "event_driven": "event-driven",
        }.get(preference, preference)
        eff_label = {
            "ideal_poisson": "Poisson",
            "event_driven": "event-driven",
        }.get(effective, effective)
        lines = [
            f"Effective core: {eff_label}",
            f"Preference: {pref_label}",
        ]
        if approximated and effective == "ideal_poisson":
            lines.append("DTF = detector transfer function.")
            lines.append("Detector event effects are being approximated by the Poisson core.")
        if required and preference == "auto":
            lines.append("The current detector configuration requires the event-driven core.")
        if reason:
            lines.append(f"Reason: {reason}")
        button.setToolTip("\n".join(lines))

    def _update_simulation_mode_badge(self, status):
        self._set_core_badge(self.btn_simulation_mode_badge, status)

    def _sync_optimization_ui(self, *_args):
        if self.chk_opt_count_rate.isChecked():
            if self.chk_opt_detection.isChecked():
                self.chk_opt_detection.blockSignals(True)
                self.chk_opt_detection.setChecked(False)
                self.chk_opt_detection.blockSignals(False)
            if self.chk_opt_excitation.isChecked():
                self.chk_opt_excitation.blockSignals(True)
                self.chk_opt_excitation.setChecked(False)
                self.chk_opt_excitation.blockSignals(False)
        detection_enabled = self.chk_opt_detection.isChecked()
        excitation_enabled = self.chk_opt_excitation.isChecked()
        count_rate_enabled = self.chk_opt_count_rate.isChecked()
        optimisation_active = detection_enabled or excitation_enabled or count_rate_enabled
        multi_target = sum(1 for enabled in (detection_enabled, excitation_enabled, count_rate_enabled) if enabled) > 1
        objective_text = self.combo_optimization_objective.currentText().lower()
        throughput_mode = objective_text in {"fisher throughput", "throughput auc"}
        free_form = self.combo_excitation_optimization_profile.currentText().lower() == "free form"
        selected_algorithm = self.combo_detection_algorithm.currentText().lower()
        self.combo_optimization_mode.setEnabled(False)
        self.combo_optimization_first.setEnabled(multi_target)
        self.spin_optimization_iterations.setEnabled(multi_target)
        self.combo_optimization_objective.setEnabled(excitation_enabled or count_rate_enabled)
        self.spin_optimization_fi_loss.setEnabled((excitation_enabled or count_rate_enabled) and throughput_mode)
        self.chk_opt_detection.setEnabled(not count_rate_enabled)
        self.chk_opt_excitation.setEnabled(not count_rate_enabled)

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
        self.detection_opt_group.setVisible(detection_enabled)

        self.combo_excitation_optimization_profile.setEnabled(excitation_enabled)
        self.combo_excitation_constraint.setEnabled(excitation_enabled)
        self.spin_excitation_width_min.setEnabled(excitation_enabled and not free_form)
        self.spin_excitation_width_max.setEnabled(excitation_enabled and not free_form)
        self.spin_excitation_control_points.setEnabled(excitation_enabled and free_form)
        self.excitation_opt_group.setVisible(excitation_enabled)
        self.spin_count_rate_min_kcps.setEnabled(count_rate_enabled)
        self.spin_count_rate_max_kcps.setEnabled(count_rate_enabled)
        self.spin_count_rate_steps.setEnabled(count_rate_enabled)
        self.combo_count_rate_scale.setEnabled(count_rate_enabled)
        self.chk_count_rate_accuracy_guard.setEnabled(count_rate_enabled)
        self.spin_count_rate_max_bias_pct.setEnabled(count_rate_enabled and self.chk_count_rate_accuracy_guard.isChecked())
        self.count_rate_opt_group.setVisible(count_rate_enabled)
        self.chk_optimization_realtime.setEnabled(optimisation_active)
        self.spin_optimization_realtime_interval.setEnabled(optimisation_active and self.chk_optimization_realtime.isChecked())
        self.spin_optimization_steps_to_show.setEnabled(optimisation_active)
        self.chk_optimization_validate_mc.setEnabled(optimisation_active)
        self._update_detection_algorithm_settings_tooltip()
        self.set_optimization_mode_active(optimisation_active, running=self.optimization_running_state)

    def _default_freeform_points(self):
        period = max(self.spin_period.value(), 1e-6)
        start = float(np.clip(self.spin_irf_pos.value(), 0.0, period))
        width = max(float(self.spin_fwhm.value()), 0.0)
        end = float(np.clip(start + width, start, period))
        times = [0.0, start, start, end, end, period]
        amps = [0.0, 0.0, 1.0, 1.0, 0.0, 0.0]
        return times, amps

    def _reset_freeform_from_current_inputs(self):
        times, amps = self._default_freeform_points()
        self.freeform_editor.reset_rectangular(self.spin_irf_pos.value(), self.spin_fwhm.value(), self.spin_period.value())
        return times, amps

    def _on_excitation_geometry_changed(self, *_args):
        self.freeform_editor.set_period(self.spin_period.value())
        if "free form" in self.combo_profile.currentText().lower():
            times, amps = self.freeform_editor.get_points()
            if len(times) < 2:
                self.freeform_editor.set_points(*self._default_freeform_points())
        self._update_burst_ui_state()

    def _on_freeform_mode_toggled(self, checked):
        edit_mode = bool(checked)
        self.btn_freeform_mode.setText("Editing" if edit_mode else "Using")
        self.freeform_editor.set_edit_mode(edit_mode)

    def _update_irf_ui(self, index=0):
        """Toggles visibility based on profile (Gaussian vs Rectangular)."""
        mode = self.combo_profile.currentText().lower()
        is_gaussian = "gaussian" in mode
        is_rect = "rectangular" in mode
        is_free_form = "free form" in mode
        is_dirac = "ideal (dirac)" in mode
        self.label_rise.setVisible(is_rect); self.spin_rise.setVisible(is_rect)
        self.label_fall.setVisible(is_rect); self.spin_fall.setVisible(is_rect)
        self.lbl_freeform_editor.setVisible(is_free_form)
        self.lbl_freeform_help.setVisible(is_free_form)
        self.btn_freeform_mode.setVisible(is_free_form)
        self.freeform_editor.setVisible(is_free_form)
        self.spin_fwhm.setEnabled(not is_dirac)
        if is_dirac:
            self.spin_fwhm.blockSignals(True)
            self.spin_fwhm.setValue(0.0)
            self.spin_fwhm.blockSignals(False)
        elif self.spin_fwhm.value() <= 0.0 and not is_free_form:
            self.spin_fwhm.setValue(0.25)

        if is_rect or is_free_form:
            self.label_irf_pos.setText("Position (Start ns):")
        else:
            self.label_irf_pos.setText("Position (Center ns):")
        if is_free_form:
            self._on_freeform_mode_toggled(self.btn_freeform_mode.isChecked())
            times, amps = self.freeform_editor.get_points()
            if len(times) < 2 or np.allclose(amps, 0.0):
                self._reset_freeform_from_current_inputs()
        if is_gaussian and self.group_burst.isChecked():
            self.group_burst.setChecked(False)
        self.group_burst.setEnabled(not is_gaussian)
        self.group_burst.setToolTip(
            "Burst excitation is disabled for Gaussian laser envelopes."
            if is_gaussian else
            "Enable and configure a sub-pulse train modulated by the selected laser envelope."
        )
        self._update_burst_ui_state()

    def _format_burst_rate_label(self, period_ps):
        period_ps = max(float(period_ps), 1e-12)
        rate_hz = 1.0e12 / period_ps
        if rate_hz >= 1.0e9:
            return f"~ {rate_hz / 1.0e9:.3f} GHz"
        if rate_hz >= 1.0e6:
            return f"~ {rate_hz / 1.0e6:.3f} MHz"
        if rate_hz >= 1.0e3:
            return f"~ {rate_hz / 1.0e3:.3f} kHz"
        return f"~ {rate_hz:.0f} Hz"

    def _update_burst_ui_state(self, *_args):
        if hasattr(self, "lbl_burst_rate") and hasattr(self, "spin_burst_period"):
            self.lbl_burst_rate.setText(self._format_burst_rate_label(self.spin_burst_period.value()))

    def update_gridded_mle_summary(self):
        param_name = self.get_selected_x_param()
        meta = self._runtime_param_meta(param_name)
        units = str(meta.get("unit", "") or "")
        unit_suffix = f" ({units})" if units else ""
        label = str(meta.get("label", param_name.title()) or param_name.title())
        self.lbl_fx_min.setText(f"Min {label}{unit_suffix}:")
        self.lbl_grid_mle_min.setText(f"Grid MLE min{unit_suffix}:")
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

    def update_image_validation_summary(self):
        param_name = self.get_selected_x_param()
        self.lbl_image_param.setText(param_name)
        self.lbl_image_sweep_min.setText(f"{self.spin_fx_min.value():.3f}")
        self.lbl_image_sweep_max.setText(f"{self.spin_fx_max.value():.3f}")
        self.lbl_image_sweep_steps.setText(str(self.spin_fx_steps.value()))
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

    def _make_icon_button(self, standard_icon, tooltip, text=""):
        button = QToolButton()
        button.setIcon(self.style().standardIcon(standard_icon))
        button.setAutoRaise(True)
        button.setToolTip(tooltip)
        if text:
            button.setText(text)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        return button

    def _make_plus_button(self, tooltip):
        button = QToolButton()
        button.setText("+")
        button.setAutoRaise(True)
        button.setToolTip(tooltip)
        return button

    def _make_trash_button(self, tooltip):
        button = QToolButton()
        button.setText("−")
        button.setAutoRaise(True)
        button.setToolTip(tooltip)
        return button

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)

    def _append_sweep_value_row(self, key, value=None, index=None):
        spec = self.sweep_options[key]
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        btn_trash = self._make_trash_button("Remove this sweep value.")
        if spec.get("row_kind") == "profile":
            edit = QComboBox()
            profile_names = [entry.get("name", "") for entry in self.instrument_profile_store.list_profiles()]
            if not profile_names:
                profile_names = ["HiLIGHT"]
            edit.addItems(profile_names)
            if value is not None and str(value) in profile_names:
                edit.setCurrentText(str(value))
            edit.setToolTip("Select one stored instrument profile for this sweep point.")
            edit.setMinimumWidth(280)
        else:
            edit = QLineEdit("" if value is None else f"{float(value):g}")
            edit.setPlaceholderText("Sweep value")
            edit.setToolTip("One sweep value for this instrument parameter.")
        btn_add = self._make_plus_button("Add a new sweep value after this row.")
        row_layout.addWidget(btn_trash, 0)
        row_layout.addWidget(edit, 1)
        row_layout.addWidget(btn_add, 0)

        row_spec = {"widget": row_widget, "edit": edit, "trash": btn_trash, "add": btn_add}
        values = spec["values"]
        if index is None or index >= len(values):
            values.append(row_spec)
            spec["rows_host_layout"].addWidget(row_widget)
        else:
            values.insert(index, row_spec)
            spec["rows_host_layout"].insertWidget(index, row_widget)

        btn_add.clicked.connect(lambda _checked=False, sweep_key=key, current_edit=edit: self._insert_sweep_value_after(sweep_key, current_edit))
        btn_trash.clicked.connect(lambda _checked=False, sweep_key=key, current_edit=edit: self._remove_sweep_value_row(sweep_key, current_edit))

    def _insert_sweep_value_after(self, key, edit):
        spec = self.sweep_options[key]
        current_index = next((idx for idx, row in enumerate(spec["values"]) if row["edit"] is edit), len(spec["values"]) - 1)
        self._append_sweep_value_row(key, None, current_index + 1)
        self._update_sweep_inputs_enabled()

    def _remove_sweep_value_row(self, key, edit):
        spec = self.sweep_options[key]
        if len(spec["values"]) <= 1:
            spec["values"][0]["edit"].clear()
            return
        for idx, row in enumerate(spec["values"]):
            if row["edit"] is edit:
                removed = spec["values"].pop(idx)
                removed["widget"].deleteLater()
                break
        self._update_sweep_inputs_enabled()

    def _set_sweep_values(self, key, values):
        spec = self.sweep_options[key]
        self._clear_layout(spec["rows_host_layout"])
        spec["values"] = []
        clean_values = list(values) if values else [None]
        for value in clean_values:
            self._append_sweep_value_row(key, value)

    def _get_sweep_values(self, key):
        spec = self.sweep_options.get(key)
        if spec is None:
            return []
        values = []
        for row in spec["values"]:
            if spec.get("row_kind") == "profile":
                text = row["edit"].currentText().strip()
                if text:
                    values.append(text)
            else:
                text = row["edit"].text().strip()
                if not text:
                    continue
                try:
                    values.append(float(text))
                except ValueError:
                    continue
        return values

    def _collect_batch_sweep_defaults_from_ui(self):
        payload = {}
        for key, spec in self.sweep_options.items():
            payload[key] = {
                "title": spec["title"],
                "values": self._get_sweep_values(key),
            }
            if spec["extra"] is not None:
                if isinstance(spec["extra"], QComboBox):
                    extra_value = spec["extra"].currentText()
                else:
                    extra_value = spec["extra"].text()
                if key == "deadtime_fixed_countrate_ns":
                    payload[key]["extra"] = {"count_rate_kcps": float(extra_value) if str(extra_value).strip() else 100.0}
                else:
                    payload[key]["extra"] = {"mode": extra_value}
        return payload

    def _load_batch_sweep_defaults_into_ui(self, payload):
        for key, spec in self.sweep_options.items():
            incoming = payload.get(key, {}) if isinstance(payload, dict) else {}
            self._set_sweep_values(key, incoming.get("values", []))
            if spec["extra"] is not None:
                extra_payload = incoming.get("extra", {}) if isinstance(incoming.get("extra", {}), dict) else {}
                if isinstance(spec["extra"], QComboBox):
                    spec["extra"].setCurrentText(str(extra_payload.get("mode", spec["extra"].currentText())))
                else:
                    if key == "deadtime_fixed_countrate_ns":
                        spec["extra"].setText(f"{float(extra_payload.get('count_rate_kcps', 100.0)):g}")
                    else:
                        spec["extra"].setText(str(extra_payload.get("value", spec["extra"].text())))

    def _load_batch_sweep_defaults_from_store(self):
        self.batch_sweep_defaults = self.batch_sweep_store.load_current()
        self._load_batch_sweep_defaults_into_ui(self.batch_sweep_defaults)

    def _save_batch_sweep_defaults_to_store(self):
        answer = QMessageBox.question(
            self,
            "Overwrite batch sweep defaults?",
            "Saving will overwrite the current batch-sweep JSON in use. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.batch_sweep_defaults = self._collect_batch_sweep_defaults_from_ui()
        self.batch_sweep_store.save_current(self.batch_sweep_defaults)

    def _import_batch_sweep_defaults(self):
        file_path, _filter = QFileDialog.getOpenFileName(
            self,
            "Import batch sweep defaults",
            "",
            "JSON files (*.json)",
        )
        if not file_path:
            return
        self.batch_sweep_defaults = self.batch_sweep_store.import_file(file_path)
        self._load_batch_sweep_defaults_into_ui(self.batch_sweep_defaults)

    def _export_batch_sweep_defaults(self):
        file_path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export batch sweep defaults",
            "batch_sweep_defaults.json",
            "JSON files (*.json)",
        )
        if not file_path:
            return
        self.batch_sweep_store.save_current(self._collect_batch_sweep_defaults_from_ui())
        self.batch_sweep_store.export_current(file_path)

    def _reset_batch_sweep_defaults(self):
        self.batch_sweep_defaults = self.batch_sweep_store.reset_current()
        self._load_batch_sweep_defaults_into_ui(self.batch_sweep_defaults)

    def _update_sweep_inputs_enabled(self):
        batch_enabled = not self.radio_sweep_off.isChecked()
        active_spec = None
        for spec in self.sweep_options.values():
            active = batch_enabled and spec["radio"].isChecked()
            for widget in spec["widgets"]:
                widget.setEnabled(active)
            spec["btn_add_top"].setEnabled(active)
            for row in spec["values"]:
                row["edit"].setEnabled(active)
                row["trash"].setEnabled(active)
                row["add"].setEnabled(active)
            if active:
                active_spec = spec
        if active_spec is None:
            self.lbl_sweep_detail_title.setText("Batch sweep disabled")
            self.sweep_detail_stack.hide()
        else:
            self.lbl_sweep_detail_title.setText(active_spec["title"])
            self.sweep_detail_stack.show()
            self.sweep_detail_stack.setCurrentWidget(active_spec["detail"])
        self.sweep_detail_group.adjustSize()

    def _sync_countrate_sweep_defaults(self, checked):
        if checked:
            self.spin_precision_photons.setValue(1000)

    def get_selected_sweep_param(self):
        for key, spec in self.sweep_options.items():
            if spec["radio"].isChecked():
                return key
        return "laser_pulse_fwhm_ns"

    def get_selected_sweep_values_text(self):
        values = self._get_sweep_values(self.get_selected_sweep_param())
        formatted = []
        for val in values:
            if isinstance(val, (int, float)):
                formatted.append(f"{float(val):g}")
            else:
                formatted.append(str(val))
        return ", ".join(formatted)

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
            self.refresh_decay_model_options(getattr(cfg, "decay_model", "exponential"))
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
            self.spin_accuracy_pvalue.setValue(getattr(cfg, "precision_accuracy_pvalue", 0.0001))
            self.spin_bootstrap_samples.setValue(getattr(cfg, "precision_bootstrap_samples", 2000))
            self.spin_ci_level.setValue(getattr(cfg, "precision_ci_level", 99.7))
            deadtime_correction_map = {
                "none": "None",
                "isbaner_histogram": "Isbaner-style histogram",
                "rapp_mcpdf": "Rapp (MCPDF)",
                "rapp_inspired_inverse": "Rapp (MCPDF)",
                "rapp_stationary": "Rapp (MCPDF)",
                "rapp_mchc": "Rapp (MCHC)",
            }
            self.combo_deadtime_correction.setCurrentText(
                deadtime_correction_map.get(getattr(cfg, "deadtime_correction_method", "none"), "None")
            )

            # Laser / Physics
            self.spin_period.setValue(cfg.period)
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
            freeform_times = list(getattr(cfg, "irf_freeform_times", []) or [])
            freeform_points = list(getattr(cfg, "irf_freeform_points", []) or [])
            if freeform_times and len(freeform_times) == len(freeform_points):
                self.freeform_editor.set_points(freeform_times, freeform_points)
            else:
                self.freeform_editor.reset_rectangular(cfg.irf_position, cfg.irf_fwhm, cfg.period)
            self.btn_freeform_mode.setChecked(bool(getattr(cfg, "irf_freeform_edit_mode", True)))

            # Burst Excitation
            self.group_burst.setChecked(cfg.burst_enabled)
            self.spin_burst_period.setValue(cfg.burst_sub_period * 1000.0) # ns to ps
            self.spin_burst_fwhm.setValue(cfg.burst_sub_fwhm * 1000.0) # ns to ps

            # Model params (dynamic rows)
            p_map = {"tau1": cfg.taus[0], "tau2": cfg.taus[1] if len(cfg.taus)>1 else 1.0,
                    "alpha": cfg.amplitudes[0], "background": cfg.background_level * 100.0, "beta": cfg.beta}
            p_map.update(dict(getattr(cfg, "custom_model_params", {}) or {}))
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
            self.chk_opt_count_rate.setChecked(getattr(cfg, "optimize_count_rate", False))
            optimization_mode_map = {"sequential": "Sequential", "iterative": "Iterative"}
            self.combo_optimization_mode.setCurrentText(
                optimization_mode_map.get(getattr(cfg, "optimization_mode", "sequential"), "Sequential")
            )
            optimization_first_map = {"detection": "Detection First", "excitation": "Excitation First", "count_rate": "Count Rate First"}
            self.combo_optimization_first.setCurrentText(
                optimization_first_map.get(getattr(cfg, "optimization_first", "detection"), "Detection First")
            )
            self.spin_optimization_iterations.setValue(getattr(cfg, "optimization_iterations", 20))
            f_basis = str(getattr(cfg, "optimization_f_photon_basis", "period")).lower()
            self.radio_f_basis_period.setChecked(f_basis == "period")
            self.radio_f_basis_all.setChecked(f_basis == "all")
            self.radio_f_basis_collected.setChecked(f_basis == "collected")
            optimization_objective_map = {
                "fisher_information": "Fisher Information",
                "fisher_throughput": "Fisher Throughput",
                "photon_efficiency_auc": "Photon Efficiency AUC",
                "throughput_auc": "Throughput AUC",
            }
            self.combo_optimization_objective.setCurrentText(
                optimization_objective_map.get(getattr(cfg, "optimization_objective", "fisher_throughput"), "Fisher Throughput")
            )
            self.spin_optimization_fi_loss.setValue(getattr(cfg, "optimization_max_fi_loss_pct", 5.0))
            self.chk_optimization_realtime.setChecked(getattr(cfg, "optimization_realtime_visualization", False))
            self.spin_optimization_realtime_interval.setValue(float(getattr(cfg, "optimization_realtime_interval_s", 5.0)))
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
            self.spin_count_rate_min_kcps.setValue(float(getattr(cfg, "count_rate_optimization_min_kcps", 10.0)))
            self.spin_count_rate_max_kcps.setValue(float(getattr(cfg, "count_rate_optimization_max_kcps", 1000.0)))
            self.spin_count_rate_steps.setValue(int(getattr(cfg, "count_rate_optimization_steps", 24)))
            self.combo_count_rate_scale.setCurrentText("Linear" if str(getattr(cfg, "count_rate_optimization_scale", "log")).lower() == "linear" else "Log")
            self.chk_count_rate_accuracy_guard.setChecked(bool(getattr(cfg, "count_rate_optimization_enforce_accuracy", True)))
            self.spin_count_rate_max_bias_pct.setValue(float(getattr(cfg, "count_rate_optimization_max_bias_pct", 2.0)))
            self._update_irf_ui()

            # Instrument params
            self.spin_photons.setValue(int(round(cfg.precision_photons)))
            self.spin_image_repeats.setValue(int(getattr(cfg, "image_mc_repeats", getattr(cfg, "n_repeats", 200))))
            image_fit_map = {
                "gridded_mle": "Gridded MLE",
                "mle": "Iterative Reconvolution",
                "tail": "Tail Fitting",
            }
            self.combo_image_fit_method.setCurrentText(
                image_fit_map.get(getattr(cfg, "image_fit_method", "gridded_mle"), "Gridded MLE")
            )
            self.spin_jitter.setValue(int(round(cfg.timing_jitter)))
            self.spin_deadtime.setValue(int(round(cfg.detector_deadtime)))
            self.spin_afterpulsing.setValue(float(getattr(cfg, "detector_afterpulsing_probability", 0.0)) * 100.0)
            self.spin_dark_count_rate.setValue(float(getattr(cfg, "detector_dark_count_rate_cps", 0.0)))
            self.chk_multihit.setChecked(cfg.b_multihit_mode)
            self.event_deadtime_mode = str(getattr(cfg, "event_deadtime_mode", "nonparalyzable")).lower()
            self.event_multihit_capacity = getattr(cfg, "event_multihit_capacity", None)
            self.event_routing_mode = str(getattr(cfg, "event_routing_mode", "exclusive")).lower()
            self.event_arbitration_rule = str(getattr(cfg, "event_arbitration_rule", "random")).lower()
            self.event_share_resource_group = bool(getattr(cfg, "event_share_resource_group", False))
            self.event_return_timestamps = bool(getattr(cfg, "event_return_timestamps", False))
            self.event_pixel_dwell_time_s = float(getattr(cfg, "event_pixel_dwell_time_s", 1e-3))
            self._set_detector_dwell_from_seconds(self.event_pixel_dwell_time_s)
            capacity = getattr(cfg, "event_multihit_capacity", None)
            if bool(getattr(cfg, "b_multihit_mode", True)):
                if capacity is None:
                    self.spin_max_events_per_period.setValue(self.EVENT_CAPACITY_UNLIMITED)
                else:
                    self.spin_max_events_per_period.setValue(max(int(capacity), 2))
            else:
                self.spin_max_events_per_period.setValue(1)
            self._sync_detector_event_controls()
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
                self._set_sweep_values(selected_key, cfg.instr_sweep_vals)
            if "deadtime_fixed_countrate_ns" in self.sweep_options and self.sweep_options["deadtime_fixed_countrate_ns"]["extra"] is not None:
                self.sweep_options["deadtime_fixed_countrate_ns"]["extra"].setText(f"{cfg.instr_sweep_fixed_countrate_kcps:g}")
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
            self._sync_ideal_detector_checkbox_from_values()
            self._sync_ideal_gates_checkbox_from_values()
            self._sync_optimization_ui()
            self._sync_background_source_controls()
            self._update_model_math_panel()
            self._update_detector_math_panel()
            self._update_sweep_inputs_enabled()
            self._update_ci_sigma_equivalence()
            self._sync_precision_preset_selection()
            self.blockSignals(False)

    def set_theme(self, theme_name):
        self.current_theme = str(theme_name).lower()
        dark = self.current_theme == "dark"
        bg = "#0a0a0a" if dark else "#ffffff"
        text = "#e5eefb" if dark else "#0f172a"
        grid = "#334155" if dark else "#d7dee8"
        self.freeform_editor.set_theme(theme_name)
        for plot in (self.optimization_objective_plot, self.optimization_best_f_plot):
            plot.setBackground(bg)
            for axis_name in ("bottom", "left", "right"):
                axis = plot.getAxis(axis_name)
                axis.setTextPen(pg.mkPen(text))
                axis.setPen(pg.mkPen(text))
            plot.showGrid(x=True, y=True, alpha=0.25)
        if getattr(self, "optimization_right_vb", None) is not None:
            self.optimization_right_vb.setBackgroundColor(bg)
        if getattr(self, "optimization_right_axis", None) is not None:
            self.optimization_right_axis.setTextPen(pg.mkPen(text))
            self.optimization_right_axis.setPen(pg.mkPen(text))
        self.optimization_objective_plot.getPlotItem().getViewBox().setBorder(pg.mkPen(grid))
        self.optimization_best_f_plot.getPlotItem().getViewBox().setBorder(pg.mkPen(grid))
        self._style_optimization_history_controls()
        self._update_optimization_history_curve_styles()

        # Reset tab and group color, will be re-applied if active in set_optimization_mode_active
        default_color = QColor(text)
        self.tabs.tabBar().setTabTextColor(4, default_color)
        for group in getattr(self, "opt_groups", []):
            group.setStyleSheet("")

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

        # Update tab color and groupbox titles to red if active
        dark = self.current_theme == "dark"
        if active:
            color = QColor("#ef4444") if dark else QColor("#b91c1c")
            style = f"QGroupBox::title {{ color: {color.name()}; font-weight: bold; }}"
            self.tabs.tabBar().setTabTextColor(4, color)
            for group in getattr(self, "opt_groups", []):
                group.setStyleSheet(style)
        else:
            color = QColor("#e5eefb") if dark else QColor("#0f172a")
            self.tabs.tabBar().setTabTextColor(4, color)
            for group in getattr(self, "opt_groups", []):
                group.setStyleSheet("")

    def set_optimization_status(self, text):
        self.txt_optimization_hint.setPlainText(str(text))

    def set_optimization_current_value(self, text):
        self.lbl_optimization_current.setText(str(text))

    def _add_optimization_aux_axis(self, key, label, curve):
        plot_item = self.optimization_best_f_plot.getPlotItem()
        axis = pg.AxisItem("right")
        vb = pg.ViewBox()
        plot_item.layout.addItem(axis, 2, 3 + len(self.optimization_aux_axes))
        axis.linkToView(vb)
        vb.setXLink(plot_item.vb)
        self.optimization_best_f_plot.scene().addItem(vb)
        vb.addItem(curve)
        axis.setLabel("")
        self.optimization_aux_axes[key] = axis
        self.optimization_aux_vbs[key] = vb

    def _apply_optimization_history_axes(self):
        log_x = self.chk_opt_hist_log_x.isChecked()
        log_y = self.chk_opt_hist_log_y.isChecked()
        self.optimization_best_f_plot.setLogMode(x=log_x, y=log_y)
        try:
            self.optimization_best_f_plot.getAxis("bottom").setLogMode(log_x)
            self.optimization_best_f_plot.getAxis("left").setLogMode(log_y)
        except Exception:
            pass
        try:
            self.optimization_right_axis.setLogMode(log_y)
        except Exception:
            pass
        for curve in (self.optimization_objective_curve, self.optimization_best_f_curve):
            if hasattr(curve, "setLogMode"):
                curve.setLogMode(log_x, log_y)
        self.optimization_best_f_plot.getAxis("left").setLabel("")
        if getattr(self, "optimization_right_axis", None) is not None:
            self.optimization_right_axis.setLabel("")
        self._update_optimization_history_curve_styles()
        self._update_optimization_history_ranges()
        self._sync_optimization_history_viewboxes()

    def _style_optimization_history_controls(self):
        for key, _label in getattr(self, "optimization_history_metric_defs", []):
            color = self.OPT_HISTORY_COLORS.get(key, "#e5eefb")
            for widget in (self.opt_hist_left_buttons.get(key), self.opt_hist_right_buttons.get(key)):
                if widget is not None:
                    widget.setStyleSheet(
                        f"QRadioButton {{ color: {color}; font-weight: bold; }}"
                        f"QRadioButton::indicator {{ width: 14px; height: 14px; }}"
                    )

    def _get_selected_optimization_axis_metric(self, side):
        buttons = self.opt_hist_left_buttons if side == "left" else self.opt_hist_right_buttons
        for key, widget in buttons.items():
            if widget.isChecked():
                return key
        return "objective" if side == "left" else "min_f"

    def _get_optimization_history_series(self, key):
        cache = getattr(self, "optimization_history_cache", None) or {}
        return np.asarray(cache.get(key, []), dtype=float)

    def _set_optimization_metric_enabled(self, key, enabled):
        for buttons in (getattr(self, "opt_hist_left_buttons", {}), getattr(self, "opt_hist_right_buttons", {})):
            widget = buttons.get(key)
            if widget is not None:
                widget.setEnabled(enabled)

    def _on_optimization_axis_selection_changed(self, _checked):
        self._render_optimization_history()

    def _update_optimization_history_curve_styles(self):
        left_key = self._get_selected_optimization_axis_metric("left")
        right_key = self._get_selected_optimization_axis_metric("right")
        left_color = self.OPT_HISTORY_COLORS.get(left_key, "#ef4444")
        right_color = self.OPT_HISTORY_COLORS.get(right_key, "#22c55e")
        self.optimization_objective_curve.setPen(pg.mkPen(left_color, width=2))
        self.optimization_objective_curve.setSymbolBrush(pg.mkBrush(left_color))
        self.optimization_objective_curve.setSymbolPen(pg.mkPen(left_color))
        self.optimization_best_f_curve.setPen(pg.mkPen(right_color, width=2))
        self.optimization_best_f_curve.setSymbolBrush(pg.mkBrush(right_color))
        self.optimization_best_f_curve.setSymbolPen(pg.mkPen(right_color))
        self.optimization_best_f_plot.getAxis("left").setTextPen(pg.mkPen(left_color))
        self.optimization_best_f_plot.getAxis("left").setPen(pg.mkPen(left_color))
        if getattr(self, "optimization_right_axis", None) is not None:
            self.optimization_right_axis.setTextPen(pg.mkPen(right_color))
            self.optimization_right_axis.setPen(pg.mkPen(right_color))

    def _copy_widget_to_clipboard(self, widget):
        key = "optimization_best_f_plot" if widget is self.optimization_best_f_plot else "optimization_objective_plot"
        ClipboardExportManager.export_widget(key, widget, parent=self, theme_target=self)

    def clear_optimization_progress(self):
        self.optimization_history_cache = {
            "iterations": np.asarray([], dtype=float),
            "objective": np.asarray([], dtype=float),
            "min_f": np.asarray([], dtype=float),
            "min_eff": np.asarray([], dtype=float),
            "auc_eff": np.asarray([], dtype=float),
            "throughput": np.asarray([], dtype=float),
            "throughput_auc": np.asarray([], dtype=float),
            "gate_count": np.asarray([], dtype=float),
        }
        self._render_optimization_history()

    def _render_optimization_history(self):
        cache = getattr(self, "optimization_history_cache", None) or {}
        x_vals = np.asarray(cache.get("iterations", []), dtype=float)
        x_plot = x_vals + 1.0 if self.chk_opt_hist_log_x.isChecked() else x_vals
        left_key = self._get_selected_optimization_axis_metric("left")
        right_key = self._get_selected_optimization_axis_metric("right")
        left_y = self._get_optimization_history_series(left_key)
        right_y = self._get_optimization_history_series(right_key)
        self.optimization_objective_curve.setVisible(left_y.size > 0)
        self.optimization_best_f_curve.setVisible(right_y.size > 0)
        self.optimization_objective_curve.setData(x_plot, left_y)
        self.optimization_best_f_curve.setData(x_plot, right_y)
        self._update_optimization_history_curve_styles()
        self._apply_optimization_history_axes()

    def _sync_optimization_history_viewboxes(self):
        main_vb = self.optimization_best_f_plot.getViewBox()
        rect = main_vb.sceneBoundingRect()
        right_vb = getattr(self, "optimization_right_vb", None)
        if right_vb is not None:
            right_vb.setGeometry(rect)
            right_vb.linkedViewChanged(main_vb, right_vb.XAxis)

    @staticmethod
    def _finite_range(values, positive_only=False):
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        if positive_only:
            arr = arr[arr > 0]
        if arr.size == 0:
            return None
        lo = float(np.min(arr))
        hi = float(np.max(arr))
        if hi <= lo:
            pad = max(abs(lo) * 0.05, 1e-6)
            lo_out = max(lo - pad, 1e-12) if positive_only else (lo - pad)
            hi_out = max(hi + pad, lo_out * 1.05) if positive_only else (hi + pad)
            return lo_out, hi_out
        pad = max((hi - lo) * 0.08, 1e-6)
        lo_out = max(lo - pad, 1e-12) if positive_only else (lo - pad)
        hi_out = hi + pad
        return lo_out, hi_out

    def _update_optimization_history_ranges(self):
        cache = getattr(self, "optimization_history_cache", None) or {}
        x_vals = np.asarray(cache.get("iterations", []), dtype=float)
        log_x = self.chk_opt_hist_log_x.isChecked()
        log_y = self.chk_opt_hist_log_y.isChecked()
        x_plot = x_vals + 1.0 if log_x else x_vals
        x_range = self._finite_range(x_plot, positive_only=log_x)
        main_vb = self.optimization_best_f_plot.getViewBox()
        if x_range is not None:
            main_vb.setXRange(*x_range, padding=0.0)
        left_key = self._get_selected_optimization_axis_metric("left")
        right_key = self._get_selected_optimization_axis_metric("right")
        left_range = self._finite_range(cache.get(left_key, []), positive_only=log_y)
        if left_range is not None:
            main_vb.setYRange(*left_range, padding=0.0)
        right_vb = getattr(self, "optimization_right_vb", None)
        if right_vb is not None:
            right_range = self._finite_range(cache.get(right_key, []), positive_only=log_y)
            if right_range is not None:
                right_vb.setYRange(*right_range, padding=0.0)
            if x_range is not None:
                right_vb.setXRange(*x_range, padding=0.0)
        self._sync_optimization_history_viewboxes()

    def update_optimization_progress(self, iterations, objective_values, metrics=None):
        metrics = metrics or {}
        self.optimization_history_cache = {
            "iterations": np.asarray(iterations, dtype=float),
            "objective": np.asarray(objective_values, dtype=float),
            "min_f": np.asarray(metrics.get("min_f", []), dtype=float),
            "min_eff": np.asarray(metrics.get("min_eff", []), dtype=float),
            "auc_eff": np.asarray(metrics.get("auc_eff", []), dtype=float),
            "throughput": np.asarray(metrics.get("throughput", []), dtype=float),
            "throughput_auc": np.asarray(metrics.get("throughput_auc", []), dtype=float),
            "gate_count": np.asarray(metrics.get("gate_count", []), dtype=float),
        }
        gate_count = np.asarray(metrics.get("gate_count", []), dtype=float)
        show_gate_count = gate_count.size > 0 and np.any(np.isfinite(gate_count)) and np.unique(gate_count[np.isfinite(gate_count)]).size > 1
        self._set_optimization_metric_enabled("gate_count", show_gate_count)
        if not show_gate_count:
            if self._get_selected_optimization_axis_metric("left") == "gate_count":
                self.opt_hist_left_buttons["objective"].setChecked(True)
            if self._get_selected_optimization_axis_metric("right") == "gate_count":
                self.opt_hist_right_buttons["min_f"].setChecked(True)
        self._render_optimization_history()
