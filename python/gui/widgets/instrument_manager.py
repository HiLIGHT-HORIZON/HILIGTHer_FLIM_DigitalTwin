import copy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from backend.profile_store import InstrumentProfileStore
from backend.twin_engine import TwinEngine
from .diagnostics_plot import DiagnosticsWidget


class InstrumentManager(QDialog):
    """Versioned instrument-profile manager with compatibility preview and repair."""

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Instrument Profile Manager")
        self.resize(1180, 720)
        self.config = config
        self.applied_config = None
        self.selected_profile = None
        self.store = InstrumentProfileStore()
        self.store.ensure_default_profiles()

        root = QVBoxLayout(self)
        header = QLabel("<b>Instrument Profiles</b>")
        header.setStyleSheet("font-size: 14px;")
        root.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_panel.setFrameShape(QFrame.Shape.StyledPanel)
        body.addWidget(left_panel, 2)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_profile_selected)
        left_layout.addWidget(self.list_widget, 1)

        button_grid = QGridLayout()
        button_grid.setHorizontalSpacing(8)
        button_grid.setVerticalSpacing(8)
        left_layout.addLayout(button_grid)

        self.btn_save = QPushButton("Save Current...")
        self.btn_save.clicked.connect(self.save_current_as)
        button_grid.addWidget(self.btn_save, 0, 0)

        self.btn_apply = QPushButton("Apply Selected")
        self.btn_apply.setStyleSheet("background-color: #1e3a8a; color: white; font-weight: bold;")
        self.btn_apply.clicked.connect(self.apply_selected)
        button_grid.addWidget(self.btn_apply, 0, 1)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_list)
        button_grid.addWidget(self.btn_refresh, 0, 2)

        self.btn_import = QPushButton("Import...")
        self.btn_import.clicked.connect(self.import_profile)
        button_grid.addWidget(self.btn_import, 1, 0)

        self.btn_export = QPushButton("Export...")
        self.btn_export.clicked.connect(self.export_selected)
        button_grid.addWidget(self.btn_export, 1, 1)

        self.btn_repair = QPushButton("Repair JSON")
        self.btn_repair.clicked.connect(self.repair_selected)
        button_grid.addWidget(self.btn_repair, 1, 2)

        self.btn_rename = QPushButton("Rename")
        self.btn_rename.clicked.connect(self.rename_selected)
        button_grid.addWidget(self.btn_rename, 2, 0)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self.delete_selected)
        button_grid.addWidget(self.btn_delete, 2, 1)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        button_grid.addWidget(self.btn_close, 2, 2)

        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_panel.setFrameShape(QFrame.Shape.StyledPanel)
        body.addWidget(right_panel, 3)

        self.lbl_summary = QLabel("Select a profile to preview its diagnostics and compatibility status.")
        self.lbl_summary.setWordWrap(True)
        right_layout.addWidget(self.lbl_summary)

        self.compatibility_box = QTextEdit()
        self.compatibility_box.setReadOnly(True)
        self.compatibility_box.setMinimumHeight(120)
        right_layout.addWidget(self.compatibility_box)

        self.preview_widget = DiagnosticsWidget()
        self.preview_widget.chk_autoplay.setChecked(False)
        self.preview_widget.chk_autoplay.setEnabled(False)
        self.preview_widget.btn_prev.hide()
        self.preview_widget.btn_next.hide()
        right_layout.addWidget(self.preview_widget, 1)

        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        for profile in self.store.list_profiles():
            item = QListWidgetItem(profile["name"])
            item.setData(Qt.ItemDataRole.UserRole, profile["name"])
            item.setToolTip(profile.get("path", ""))
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        else:
            self.selected_profile = None
            self.compatibility_box.setPlainText("No instrument profiles found.")
            self.lbl_summary.setText("Select a profile to preview its diagnostics and compatibility status.")
            self.preview_widget.clear_frames()

    def _selected_profile_name(self):
        item = self.list_widget.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _build_preview_frame(self, cfg):
        preview_cfg = copy.deepcopy(cfg)
        engine = TwinEngine(preview_cfg)
        engine.distill_gates()
        irf = engine.dt_excitation(engine.time_vector)
        pdf = engine.dt_pdf(engine.time_vector)
        return {
            "time_vec": engine.time_vector,
            "gate_shapes": engine.gate_shapes,
            "irf": irf,
            "pdf": pdf,
            "label": f"Preview: {preview_cfg.label or 'Instrument Profile'}",
            "background_curves": None,
        }

    def _format_compatibility(self, inspection, payload):
        lines = [
            f"Schema version: {payload.get('schema_version', 'legacy')}",
            f"Profile type: {payload.get('profile_type', 'unknown')}",
        ]
        missing = inspection.get("missing", [])
        extra = inspection.get("extra", [])
        if not missing and not extra:
            lines.append("Compatibility: current schema; no missing or obsolete parameters detected.")
        else:
            lines.append("Compatibility: schema drift detected.")
            if missing:
                lines.append(f"Missing parameters: {', '.join(missing)}")
                lines.append("Behaviour: missing values can be filled from current defaults.")
            if extra:
                lines.append(f"Obsolete/unknown parameters: {', '.join(extra)}")
                lines.append("Behaviour: obsolete values can be ignored or removed by repairing the JSON.")
        return "\n".join(lines)

    def _on_profile_selected(self, current, _previous):
        name = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        if not name:
            self.selected_profile = None
            self.preview_widget.clear_frames()
            self.compatibility_box.clear()
            return
        try:
            loaded = self.store.load_profile(name, sanitize=True)
        except Exception as exc:
            self.selected_profile = None
            self.compatibility_box.setPlainText(f"Failed to load profile:\n{exc}")
            self.preview_widget.clear_frames()
            return
        self.selected_profile = loaded
        payload = loaded["payload"]
        inspection = loaded["inspection"]
        cfg = loaded["config"]
        self.lbl_summary.setText(
            f"<b>{payload.get('name', name)}</b><br>"
            f"{payload.get('description', 'No description provided.')}"
        )
        self.compatibility_box.setPlainText(self._format_compatibility(inspection, payload))
        try:
            frame = self._build_preview_frame(cfg)
            self.preview_widget.set_sweep_frames([frame])
        except Exception as exc:
            self.preview_widget.clear_frames()
            self.compatibility_box.append(f"\nPreview unavailable:\n{exc}")

    def _resolve_profile_application(self, name):
        loaded = self.store.load_profile(name, sanitize=True)
        inspection = loaded["inspection"]
        if not inspection.get("has_issues"):
            return loaded["config"], False

        msg = QMessageBox(self)
        msg.setWindowTitle("Profile Compatibility")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText("This profile does not fully match the current instrument schema.")
        msg.setInformativeText(
            "You can apply it with missing values filled from defaults and extra values ignored, "
            "or repair the stored JSON first."
        )
        msg.setDetailedText(self._format_compatibility(inspection, loaded["payload"]))
        apply_btn = msg.addButton("Apply with defaults", QMessageBox.ButtonRole.AcceptRole)
        repair_btn = msg.addButton("Repair JSON and apply", QMessageBox.ButtonRole.ActionRole)
        msg.addButton(QMessageBox.StandardButton.Cancel)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == apply_btn:
            return loaded["config"], False
        if clicked == repair_btn:
            repaired = self.store.repair_profile(name)
            repaired_loaded = self.store.load_profile(repaired["name"], sanitize=True)
            self.refresh_list()
            self._select_profile_by_name(repaired["name"])
            return repaired_loaded["config"], True
        return None, False

    def _select_profile_by_name(self, name):
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if item.data(Qt.ItemDataRole.UserRole) == name:
                self.list_widget.setCurrentItem(item)
                return

    def save_current_as(self):
        if self.config is None:
            return
        name, ok = QInputDialog.getText(self, "Save Profile", "Enter instrument name:")
        if not ok or not name.strip():
            return
        self.store.save_profile(name.strip(), self.config, description="")
        self.refresh_list()
        self._select_profile_by_name(name.strip())
        QMessageBox.information(self, "Saved", f"Profile '{name.strip()}' saved.")

    def apply_selected(self):
        name = self._selected_profile_name()
        if not name:
            QMessageBox.warning(self, "Warning", "Please select a profile first.")
            return
        try:
            cfg, repaired = self._resolve_profile_application(name)
        except Exception as exc:
            QMessageBox.warning(self, "Apply Profile", str(exc))
            return
        if cfg is None:
            return
        self.applied_config = copy.deepcopy(cfg)
        self.applied_config.active_instrument_profile = name
        suffix = " after repair" if repaired else ""
        QMessageBox.information(self, "Applied", f"Profile '{name}' applied{suffix}.")
        self.accept()

    def rename_selected(self):
        name = self._selected_profile_name()
        if not name:
            QMessageBox.warning(self, "Warning", "Please select a profile first.")
            return
        new_name, ok = QInputDialog.getText(self, "Rename Profile", "New profile name:", text=name)
        if not ok or not new_name.strip():
            return
        payload = self.store.rename_profile(name, new_name.strip())
        self.refresh_list()
        self._select_profile_by_name(payload["name"])

    def delete_selected(self):
        name = self._selected_profile_name()
        if not name:
            return
        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete profile '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_profile(name)
        self.refresh_list()

    def import_profile(self):
        source_path, _ = QFileDialog.getOpenFileName(self, "Import Profile", "", "JSON Files (*.json)")
        if not source_path:
            return
        try:
            payload = self.store.load_profile_payload(source_path)
            inspection = self.store.inspect_config_dict(payload.get("config"))
            if inspection.get("has_issues"):
                msg = QMessageBox(self)
                msg.setWindowTitle("Import Profile")
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setText("The imported profile does not fully match the current schema.")
                msg.setInformativeText("Import with defaults, repair and import, or cancel.")
                msg.setDetailedText(self._format_compatibility(inspection, payload))
                import_btn = msg.addButton("Import with defaults", QMessageBox.ButtonRole.AcceptRole)
                repair_btn = msg.addButton("Repair and import", QMessageBox.ButtonRole.ActionRole)
                msg.addButton(QMessageBox.StandardButton.Cancel)
                msg.exec()
                clicked = msg.clickedButton()
                if clicked == repair_btn:
                    imported = self.store.import_profile(source_path)
                    self.store.repair_profile(imported["name"])
                elif clicked == import_btn:
                    self.store.import_profile(source_path)
                else:
                    return
            else:
                self.store.import_profile(source_path)
        except Exception as exc:
            QMessageBox.warning(self, "Import Profile", str(exc))
            return
        self.refresh_list()

    def repair_selected(self):
        name = self._selected_profile_name()
        if not name:
            QMessageBox.warning(self, "Warning", "Please select a profile first.")
            return
        try:
            payload = self.store.repair_profile(name)
        except Exception as exc:
            QMessageBox.warning(self, "Repair Profile", str(exc))
            return
        self.refresh_list()
        self._select_profile_by_name(payload["name"])
        QMessageBox.information(self, "Repair Profile", f"Profile '{payload['name']}' was sanitised and rewritten.")

    def export_selected(self):
        name = self._selected_profile_name()
        if not name:
            QMessageBox.warning(self, "Warning", "Please select a profile first.")
            return
        destination_path, _ = QFileDialog.getSaveFileName(self, "Export Profile", f"{name}.json", "JSON Files (*.json)")
        if not destination_path:
            return
        self.store.export_profile(name, destination_path)
        QMessageBox.information(self, "Exported", f"Profile '{name}' exported.")

