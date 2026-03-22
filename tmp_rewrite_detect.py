import re

with open('python/gui/widgets/controls.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Restore missing spin_afterpulsing and dark_count_rate, and apply fixed widths (compact logic)
old_detector = '''        detector_group = QGroupBox("Detector properties")
        hw_layout = QFormLayout(detector_group)
        self.spin_jitter = QSpinBox(); self.spin_jitter.setValue(150)
        self.spin_deadtime = QSpinBox(); self.spin_deadtime.setValue(45)
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
        hw_layout.addRow(detector_row_one)
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
        hw_layout.addRow(detector_runtime_row)
        detection_layout.addWidget(detector_group)'''

new_detector = '''        detector_group = QGroupBox("Detector properties")
        hw_layout = QFormLayout(detector_group)
        
        self.chk_ideal_detector = QCheckBox("Ideal detector")
        self.chk_ideal_detector.setChecked(True)
        hw_layout.addRow(self.chk_ideal_detector)
        self.chk_ideal_detector.toggled.connect(self._on_ideal_detector_toggled)

        self.spin_jitter = QSpinBox(); self.spin_jitter.setValue(150)
        self.spin_deadtime = QSpinBox(); self.spin_deadtime.setValue(45)
        self.spin_pixel_dwell = QDoubleSpinBox()
        self.spin_pixel_dwell.setRange(1e-6, 1e9)
        self.spin_pixel_dwell.setDecimals(6)
        self.spin_pixel_dwell.setSingleStep(1.0)
        self.combo_pixel_dwell_unit = QComboBox()
        self.combo_pixel_dwell_unit.addItems(["ns", "us", "ms", "s"])
        
        # User width edits logic: input_width = 120
        self.spin_jitter.setFixedWidth(120)
        self.spin_deadtime.setFixedWidth(120)
        self.spin_pixel_dwell.setFixedWidth(120)
        self.combo_pixel_dwell_unit.setFixedWidth(60)

        detector_row_one = QWidget()
        detector_row_one_layout = QHBoxLayout(detector_row_one)
        detector_row_one_layout.setContentsMargins(0, 0, 0, 0)
        detector_row_one_layout.setSpacing(6)
        detector_row_one_layout.addWidget(QLabel("Jitter (ps):"))
        detector_row_one_layout.addWidget(self.spin_jitter)
        detector_row_one_layout.addWidget(QLabel("Deadtime (ns):"))
        detector_row_one_layout.addWidget(self.spin_deadtime)
        detector_row_one_layout.addStretch()
        self.detector_row_one_widget = detector_row_one
        hw_layout.addRow(detector_row_one)
        
        detector_row_dwell = QWidget()
        detector_row_dwell_layout = QHBoxLayout(detector_row_dwell)
        detector_row_dwell_layout.setContentsMargins(0, 0, 0, 0)
        detector_row_dwell_layout.setSpacing(6)
        detector_row_dwell_layout.addWidget(QLabel("Pixel dwell:"))
        detector_row_dwell_layout.addWidget(self.spin_pixel_dwell)
        detector_row_dwell_layout.addWidget(self.combo_pixel_dwell_unit)
        detector_row_dwell_layout.addStretch()
        hw_layout.addRow(detector_row_dwell)

        self.lbl_estimated_count_rate = QLabel("0 cps")
        self.chk_multihit = QCheckBox("Multihit Detection"); self.chk_multihit.setChecked(True)
        self.spin_max_events_per_period = QSpinBox()
        self.spin_max_events_per_period.setRange(1, self.EVENT_CAPACITY_UNLIMITED)
        self.spin_max_events_per_period.setValue(self.EVENT_CAPACITY_UNLIMITED)
        self.spin_max_events_per_period.setFixedWidth(120)

        self.spin_afterpulsing = QDoubleSpinBox()
        self.spin_afterpulsing.setRange(0.0, 100.0)
        self.spin_afterpulsing.setDecimals(3)
        self.spin_afterpulsing.setSingleStep(0.1)
        self.spin_afterpulsing.setValue(0.0)
        self.spin_afterpulsing.setFixedWidth(120)

        self.spin_dark_count_rate = QDoubleSpinBox()
        self.spin_dark_count_rate.setRange(0.0, 1e12)
        self.spin_dark_count_rate.setDecimals(3)
        self.spin_dark_count_rate.setSingleStep(100.0)
        self.spin_dark_count_rate.setValue(0.0)
        self.spin_dark_count_rate.setFixedWidth(120)

        detector_runtime_row = QWidget()
        detector_runtime_layout = QHBoxLayout(detector_runtime_row)
        detector_runtime_layout.setContentsMargins(0, 0, 0, 0)
        detector_runtime_layout.setSpacing(6)
        detector_runtime_layout.addWidget(self.chk_multihit)
        detector_runtime_layout.addWidget(QLabel("Max events/period:"))
        detector_runtime_layout.addWidget(self.spin_max_events_per_period)
        detector_runtime_layout.addStretch()
        self.detector_runtime_row_widget = detector_runtime_row
        hw_layout.addRow(detector_runtime_row)

        detector_effects_row = QWidget()
        detector_effects_layout = QHBoxLayout(detector_effects_row)
        detector_effects_layout.setContentsMargins(0, 0, 0, 0)
        detector_effects_layout.setSpacing(6)
        detector_effects_layout.addWidget(QLabel("Afterpulsing (%):"))
        detector_effects_layout.addWidget(self.spin_afterpulsing)
        detector_effects_layout.addWidget(QLabel("Dark count rate (cps):"))
        detector_effects_layout.addWidget(self.spin_dark_count_rate)
        detector_effects_layout.addStretch()
        self.detector_effects_row_widget = detector_effects_row
        hw_layout.addRow(detector_effects_row)
        
        detector_row_count_rate = QWidget()
        detector_row_count_rate_layout = QHBoxLayout(detector_row_count_rate)
        detector_row_count_rate_layout.setContentsMargins(0, 0, 0, 0)
        detector_row_count_rate_layout.setSpacing(6)
        detector_row_count_rate_layout.addWidget(QLabel("Avg count rate:"))
        detector_row_count_rate_layout.addWidget(self.lbl_estimated_count_rate)
        detector_row_count_rate_layout.addStretch()
        hw_layout.addRow(detector_row_count_rate)

        detection_layout.addWidget(detector_group)'''

text = text.replace(old_detector, new_detector)

# Move Ideal gates
old_gate = '''        # Gating
        gating_group = QGroupBox("Gate properties")
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

        self.chk_ideal_gates = QCheckBox("Ideal gates")
        self.chk_ideal_gates.setChecked(True)
        gate_layout.addRow(self.chk_ideal_gates)
        self.chk_ideal_gates.toggled.connect(self._on_ideal_gates_toggled)'''

new_gate = '''        # Gating
        gating_group = QGroupBox("Gate properties")
        gate_layout = QFormLayout(gating_group)
        
        self.chk_ideal_gates = QCheckBox("Ideal gates")
        self.chk_ideal_gates.setChecked(True)
        gate_layout.addRow(self.chk_ideal_gates)
        self.chk_ideal_gates.toggled.connect(self._on_ideal_gates_toggled)

        self.spin_num_gates = QSpinBox(); self.spin_num_gates.setRange(2, 512); self.spin_num_gates.setValue(4)
        self.combo_gate_type = QComboBox(); self.combo_gate_type.addItems(["Equal", "Custom"])
        gate_layout.addRow(two_column_row("Num Gates:", self.spin_num_gates, "Gate Type:", self.combo_gate_type))
        self.label_gate_definition = QLabel("Gate Edges (ns):")
        self.edit_gate_widths = QLineEdit()
        gate_layout.addRow(self.label_gate_definition, self.edit_gate_widths)
        self.lbl_gate_error = QLabel("")
        self.lbl_gate_error.setStyleSheet("color: #dc2626; font-weight: bold;")
        gate_layout.addRow("", self.lbl_gate_error)'''

text = text.replace(old_gate, new_gate)


# Inject Ideal Detector callback
callback_code = '''        self._update_irf_ui()
        self._on_ideal_detector_toggled(False)

    def _on_ideal_detector_toggled(self, checked):
        vis = not checked
        if hasattr(self, "detector_row_one_widget"):
            self.detector_row_one_widget.setVisible(vis)
            self.detector_runtime_row_widget.setVisible(vis)
            if hasattr(self, "detector_effects_row_widget"):
                self.detector_effects_row_widget.setVisible(vis)
            if checked:
                self.spin_jitter.setValue(0)
                self.spin_deadtime.setValue(0)
                self.chk_multihit.setChecked(True)
                self.spin_max_events_per_period.setValue(self.EVENT_CAPACITY_UNLIMITED)
                if hasattr(self, "spin_afterpulsing"):
                    self.spin_afterpulsing.setValue(0.0)
                if hasattr(self, "spin_dark_count_rate"):
                    self.spin_dark_count_rate.setValue(0.0)
            self.advanced_config_changed.emit()'''
text = text.replace('        self._update_irf_ui()', callback_code)


with open('python/gui/widgets/controls.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Done Detector/Gate")
