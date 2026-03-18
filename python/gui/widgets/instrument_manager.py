import os
import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QPushButton, QInputDialog, QMessageBox, QFileDialog, QLabel)
from PyQt6.QtCore import Qt

class InstrumentManager(QDialog):
    """
    Python port of InstrumentManager.m
    Handles loading, saving, and applying instrument profiles.
    """
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Instrument Profile Manager")
        self.resize(500, 450)
        self.config = config
        
        # Primary path for new profiles
        self.profiles_dir = os.path.join(os.path.dirname(__file__), "..", "..", "profiles", "instruments")
        if not os.path.exists(self.profiles_dir):
            os.makedirs(self.profiles_dir)
            
        # Legacy path from MATLAB workspace
        self.legacy_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "AppProperties", "instruments")
            
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Available Instrument Profiles</b>"))
        
        # List of profiles
        self.list_widget = QListWidget()
        self.refresh_list()
        layout.addWidget(self.list_widget)
        
        # Actions
        btn_layout = QHBoxLayout()
        
        btn_new = QPushButton("🆕 Save Current...")
        btn_new.clicked.connect(self.save_current_as)
        btn_layout.addWidget(btn_new)
        
        btn_apply = QPushButton("⚡ Apply Selected")
        btn_apply.setStyleSheet("background-color: #1e3a8a; color: white; font-weight: bold;")
        btn_apply.clicked.connect(self.apply_selected)
        btn_layout.addWidget(btn_apply)
        
        btn_delete = QPushButton("🗑️ Delete")
        btn_delete.clicked.connect(self.delete_selected)
        btn_layout.addWidget(btn_delete)
        
        layout.addLayout(btn_layout)
        
        # Close button
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

        self.profile_paths = {} # name -> full_path

    def refresh_list(self):
        self.list_widget.clear()
        self.profile_paths = {}
        
        # 1. Search Legacy
        if os.path.exists(self.legacy_dir):
            for f in os.listdir(self.legacy_dir):
                if f.endswith(".json"):
                    name = f.replace(".json", "") + " (Legacy)"
                    self.list_widget.addItem(name)
                    self.profile_paths[name] = os.path.join(self.legacy_dir, f)
                    
        # 2. Search Local
        if os.path.exists(self.profiles_dir):
            for f in os.listdir(self.profiles_dir):
                if f.endswith(".json"):
                    name = f.replace(".json", "")
                    self.list_widget.addItem(name)
                    self.profile_paths[name] = os.path.join(self.profiles_dir, f)

    def _translate_legacy(self, legacy_data):
        """Maps MATLAB JSON fields to PhysicsConfig fields."""
        mapping = {
            "T": "period",
            "fwhm": "irf_fwhm",
            "profile": "irf_profile",
            "toff": "period",
            "rise_time": "irf_rise_time",
            "fall_time": "irf_fall_time",
            "bPulseTrain": "b_decay_wrapping",
            "PT_Trep": "period",
            "PT_sigma": "burst_sub_fwhm",
            "r": "expansion_ratio",
            "gates": "gate_edges",
            "N_photons": "a_photons",
            "M": "n_repeats",
            "dt": "dt_input",
            "gate_widths": "gate_widths",
            "dt_override": "dt_override",
            "jitter": "timing_jitter",
            "deadtime": "detector_deadtime",
            "name": "label"
        }
        
        new_data = {}
        for legacy_key, val in legacy_data.items():
            if legacy_key in mapping:
                new_key = mapping[legacy_key]
                # Type/Value fixes
                if new_key == "irf_profile" and isinstance(val, str):
                    val = val.lower()
                if legacy_key == "gate_type" and isinstance(val, str):
                    if "Custom" in val: new_data["gate_type"] = "custom"
                    elif "Equal" in val: new_data["gate_type"] = "equal"
                    continue
                new_data[new_key] = val
            
            # Special case for dt -> dt_override
            if legacy_key == "dt" and "dt_override" not in new_data:
                new_data["dt_override"] = val
                
        return new_data

    def save_current_as(self):
        if not self.config: return
        
        name, ok = QInputDialog.getText(self, "Save Profile", "Enter instrument name:")
        if ok and name:
            safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
            filename = f"{safe_name}.json"
            filepath = os.path.join(self.profiles_dir, filename)
            
            try:
                data = self.config.dict()
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=4)
                self.refresh_list()
                QMessageBox.information(self, "Success", f"Profile '{name}' saved.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save profile: {str(e)}")

    def apply_selected(self):
        selected = self.list_widget.currentItem()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select a profile first.")
            return
        
        name = selected.text()
        filepath = self.profile_paths.get(name)
        if not filepath: return
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # If legacy, translate first
            if "(Legacy)" in name:
                data = self._translate_legacy(data)
            
            # Update parent config
            for key, val in data.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, val)
            
            # Ensure Gate Consistency
            # If gate_widths was updated but not gate_edges, or vice-versa
            if "gate_widths" in data and "gate_edges" not in data:
                import numpy as np
                edges = [0.0]
                for w in data["gate_widths"]: edges.append(edges[-1] + w)
                self.config.gate_edges = edges
            elif "gate_edges" in data and "gate_widths" not in data:
                import numpy as np
                self.config.gate_widths = np.diff(data["gate_edges"]).tolist()

            QMessageBox.information(self, "Success", f"Profile '{name}' applied.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load profile: {str(e)}")

    def delete_selected(self):
        selected = self.list_widget.currentItem()
        if not selected: return
        
        name = selected.text()
        if "(Legacy)" in name:
            QMessageBox.warning(self, "Protected", "Legacy profiles in AppProperties cannot be deleted from here.")
            return
            
        filepath = self.profile_paths.get(name)
        if not filepath: return
        
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete profile '{name}'?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(filepath)
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete file: {str(e)}")
