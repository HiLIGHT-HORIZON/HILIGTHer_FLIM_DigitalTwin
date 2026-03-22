import re

with open('python/gui/widgets/controls.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Make burst layout maximum width
text = re.sub(
    r'self\.group_burst\.setSizePolicy\(QSizePolicy\.Policy\.Preferred, QSizePolicy\.Policy\.Maximum\)',
    'self.group_burst.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)',
    text
)

# Format the burst spin boxes
new_add_row = '''        input_width = 120
        self.combo_profile.setFixedWidth(input_width)
        self.spin_period.setFixedWidth(input_width)
        self.spin_fwhm.setFixedWidth(input_width)
        self.spin_irf_pos.setFixedWidth(input_width)
        self.spin_rise.setFixedWidth(input_width)
        self.spin_fall.setFixedWidth(input_width)
        self.spin_burst_period.setFixedWidth(input_width)
        self.spin_burst_fwhm.setFixedWidth(input_width)

        burst_container = QHBoxLayout()
        burst_container.setContentsMargins(0, 0, 0, 0)
        burst_container.addWidget(self.group_burst)
        burst_container.addStretch()
        laser_layout.addRow(burst_container)'''
text = text.replace('        laser_layout.addRow(self.group_burst)', new_add_row)

lbl_burst_period_repl = '''        lbl_burst_period = QLabel("Pulse distance (ps):")
        lbl_burst_period.setMinimumWidth(130)
        burst_l.addRow(lbl_burst_period, self.spin_burst_period)'''
text = text.replace('        burst_l.addRow("Pulse distance (ps):", self.spin_burst_period)', lbl_burst_period_repl)

lbl_burst_fwhm_repl = '''        lbl_burst_fwhm = QLabel("Burst FWHM (ps):")
        lbl_burst_fwhm.setMinimumWidth(130)
        burst_l.addRow(lbl_burst_fwhm, self.spin_burst_fwhm)'''
text = text.replace('        burst_l.addRow("Burst FWHM (ps):", self.spin_burst_fwhm)', lbl_burst_fwhm_repl)

# Ideal detector
ideal_detector_code = '''        self.chk_ideal_detector = QCheckBox("Ideal detector")
        self.chk_ideal_detector.setChecked(True)
        hw_layout.addRow(self.chk_ideal_detector)
        self.chk_ideal_detector.toggled.connect(self._on_ideal_detector_toggled)

        self.spin_jitter = QSpinBox(); self.spin_jitter.setValue(150)'''
text = text.replace('        self.spin_jitter = QSpinBox(); self.spin_jitter.setValue(150)', ideal_detector_code)

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

# Add widget references for hiding
text = text.replace('        hw_layout.addRow(detector_row_one)', '        self.detector_row_one_widget = detector_row_one\\n        hw_layout.addRow(detector_row_one)')
text = text.replace('        hw_layout.addRow(detector_runtime_row)', '        self.detector_runtime_row_widget = detector_runtime_row\\n        hw_layout.addRow(detector_runtime_row)')
text = text.replace('        hw_layout.addRow(detector_effects_row)', '        self.detector_effects_row_widget = detector_effects_row\\n        hw_layout.addRow(detector_effects_row)')

# Update ideal load logic in update_from_config
ideal_detector_load = '''
            is_detector_ideal = (
                cfg.timing_jitter == 0.0 and
                cfg.detector_deadtime == 0.0 and
                cfg.b_multihit_mode and
                getattr(cfg, "detector_afterpulsing_probability", 0.0) == 0.0 and
                getattr(cfg, "detector_dark_count_rate_cps", 0.0) == 0.0
            )
            self.chk_ideal_detector.blockSignals(True)
            self.chk_ideal_detector.setChecked(is_detector_ideal)
            self.chk_ideal_detector.blockSignals(False)
            self._on_ideal_detector_toggled(is_detector_ideal)

            is_ideal = ('''
text = text.replace('            is_ideal = (', ideal_detector_load)

with open('python/gui/widgets/controls.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Done")
