import re

with open('python/gui/widgets/controls.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Add get_selected_decay_model_key
get_method = '''        self._apply_default_x_range(selected_name)
        self._apply_default_x_scale(selected_name)

    def get_selected_decay_model_key(self):
        text = self.combo_decay_model.currentText().strip().lower()
        if text == "add custom model...":
            return "exponential"
        if text == "custom":
            return "custom"
        return text'''
text = text.replace('''        self._apply_default_x_range(selected_name)
        self._apply_default_x_scale(selected_name)''', get_method)

# Add photon syncing and background logic
sync_methods = '''    def _sync_photon_budget_from_precision(self, value):
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

    def _update_estimated_count_rate(self) -> None:'''

text = text.replace('''    def _update_estimated_count_rate(self) -> None:''', sync_methods)

# Update _update_estimated_count_rate logic
text = text.replace('avg_photons = float(self.spin_photons.value())', 'avg_photons = float(self.spin_precision_photons.value())')

# Update __init__ connections
init_conns_old = '''        self.radio_f_basis_collected.toggled.connect(self._sync_f_photon_basis_controls)
        self.spin_photons.valueChanged.connect(self._update_estimated_count_rate)
        self.spin_deadtime.valueChanged.connect(self._sync_detector_event_controls)'''
init_conns_new = '''        self.radio_f_basis_collected.toggled.connect(self._sync_f_photon_basis_controls)
        self.spin_precision_photons.valueChanged.connect(self._sync_photon_budget_from_precision)
        self.spin_photons.valueChanged.connect(self._sync_photon_budget_from_validation)
        self.spin_photons.valueChanged.connect(self._update_estimated_count_rate)
        self.spin_deadtime.valueChanged.connect(self._sync_detector_event_controls)'''
text = text.replace(init_conns_old, init_conns_new)

init_conns_old2 = '''        self.spin_max_events_per_period.valueChanged.connect(self._sync_detector_event_controls)
        self._sync_optimization_ui()'''
init_conns_new2 = '''        self.spin_max_events_per_period.valueChanged.connect(self._sync_detector_event_controls)
        self.spin_dark_count_rate.valueChanged.connect(self._sync_background_source_controls)
        self._sync_optimization_ui()'''
text = text.replace(init_conns_old2, init_conns_new2)

init_conns_old3 = '''        self._set_detector_dwell_from_seconds(self.event_pixel_dwell_time_s)
        self._sync_detector_event_controls()'''
init_conns_new3 = '''        self._set_detector_dwell_from_seconds(self.event_pixel_dwell_time_s)
        self._sync_detector_event_controls()
        self._sync_background_source_controls()'''
text = text.replace(init_conns_old3, init_conns_new3)

# Add ideal_detector_load logic inside update_from_config
cfg_load = '''        finally:
            self._update_irf_ui()
            self.update_param_visibility()
            self.update_gridded_mle_summary()
            self.update_image_validation_summary()
            self._sync_precision_execution_ui(cfg.precision_validate_mc)
            self._sync_gate_controls()
            self._sync_optimization_ui()
            self._sync_background_source_controls()'''
text = text.replace('''        finally:
            self._update_irf_ui()
            self.update_param_visibility()
            self.update_gridded_mle_summary()
            self.update_image_validation_summary()
            self._sync_precision_execution_ui(cfg.precision_validate_mc)
            self._sync_gate_controls()
            self._sync_optimization_ui()''', cfg_load)

# Add Ideal detector check logic inside update_from_config
ideal_det_load = '''            is_detector_ideal = (
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

            # Optimization'''
text = text.replace('''            # Optimization''', ideal_det_load)

text = text.replace('            self.spin_photons.setValue(int(round(cfg.a_photons)))', '            self.spin_photons.setValue(int(round(cfg.precision_photons)))')

with open('python/gui/widgets/controls.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Done user edits")
