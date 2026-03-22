import re

with open('python/gui/widgets/controls.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Fix Gating: move Ideal Gates to top
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

# 2. Fix Detection inputs width
# We want to use setFixedWidth as input_width = 120, and change `, 1)` stretches!
old_det_row_1 = '''        detector_row_jitter_deadtime_layout.addWidget(QLabel("Jitter (ps):"))
        detector_row_jitter_deadtime_layout.addWidget(self.spin_jitter, 1)
        detector_row_jitter_deadtime_layout.addWidget(QLabel("Deadtime (ns):"))
        detector_row_jitter_deadtime_layout.addWidget(self.spin_deadtime, 1)'''
new_det_row_1 = '''        self.spin_jitter.setFixedWidth(120)
        self.spin_deadtime.setFixedWidth(120)
        detector_row_jitter_deadtime_layout.addWidget(QLabel("Jitter (ps):"))
        detector_row_jitter_deadtime_layout.addWidget(self.spin_jitter)
        detector_row_jitter_deadtime_layout.addWidget(QLabel("Deadtime (ns):"))
        detector_row_jitter_deadtime_layout.addWidget(self.spin_deadtime)
        detector_row_jitter_deadtime_layout.addStretch()'''
text = text.replace(old_det_row_1, new_det_row_1)

old_det_row_dwell = '''        detector_row_dwell_layout.addWidget(QLabel("Pixel dwell:"))
        detector_row_dwell_layout.addWidget(self.spin_pixel_dwell, 1)
        detector_row_dwell_layout.addWidget(self.combo_pixel_dwell_unit)'''
new_det_row_dwell = '''        self.spin_pixel_dwell.setFixedWidth(120)
        self.combo_pixel_dwell_unit.setFixedWidth(60)
        detector_row_dwell_layout.addWidget(QLabel("Pixel dwell:"))
        detector_row_dwell_layout.addWidget(self.spin_pixel_dwell)
        detector_row_dwell_layout.addWidget(self.combo_pixel_dwell_unit)'''
text = text.replace(old_det_row_dwell, new_det_row_dwell)

old_det_row_runtime = '''        detector_row_multihit_layout.addWidget(self.chk_multihit)
        detector_row_multihit_layout.addWidget(QLabel("Max events/period:"))
        detector_row_multihit_layout.addWidget(self.spin_max_events_per_period, 1)'''
new_det_row_runtime = '''        self.spin_max_events_per_period.setFixedWidth(120)
        detector_row_multihit_layout.addWidget(self.chk_multihit)
        detector_row_multihit_layout.addWidget(QLabel("Max events/period:"))
        detector_row_multihit_layout.addWidget(self.spin_max_events_per_period)
        detector_row_multihit_layout.addStretch()'''
text = text.replace(old_det_row_runtime, new_det_row_runtime)

old_det_row_effects = '''        detector_effects_layout.addWidget(QLabel("Afterpulsing (%):"))
        detector_effects_layout.addWidget(self.spin_afterpulsing, 1)
        detector_effects_layout.addWidget(QLabel("Dark count rate (cps):"))
        detector_effects_layout.addWidget(self.spin_dark_count_rate, 1)'''
new_det_row_effects = '''        self.spin_afterpulsing.setFixedWidth(120)
        self.spin_dark_count_rate.setFixedWidth(120)
        detector_effects_layout.addWidget(QLabel("Afterpulsing (%):"))
        detector_effects_layout.addWidget(self.spin_afterpulsing)
        detector_effects_layout.addWidget(QLabel("Dark count rate (cps):"))
        detector_effects_layout.addWidget(self.spin_dark_count_rate)
        detector_effects_layout.addStretch()'''
text = text.replace(old_det_row_effects, new_det_row_effects)

with open('python/gui/widgets/controls.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Detection layout compactified")
