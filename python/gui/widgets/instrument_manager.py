from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QInputDialog,
    QMessageBox,
    QFileDialog,
    QLabel,
)

from backend.profile_store import InstrumentProfileStore


class InstrumentManager(QDialog):
    """Versioned instrument-profile manager."""

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Instrument Profile Manager")
        self.resize(640, 500)
        self.config = config
        self.store = InstrumentProfileStore()
        self.store.ensure_default_profiles()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Instrument Profiles</b>"))

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        row1 = QHBoxLayout()
        self.btn_save = QPushButton("Save Current...")
        self.btn_save.clicked.connect(self.save_current_as)
        row1.addWidget(self.btn_save)
        self.btn_apply = QPushButton("Apply Selected")
        self.btn_apply.setStyleSheet("background-color: #1e3a8a; color: white; font-weight: bold;")
        self.btn_apply.clicked.connect(self.apply_selected)
        row1.addWidget(self.btn_apply)
        self.btn_rename = QPushButton("Rename")
        self.btn_rename.clicked.connect(self.rename_selected)
        row1.addWidget(self.btn_rename)
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self.delete_selected)
        row1.addWidget(self.btn_delete)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.btn_import = QPushButton("Import...")
        self.btn_import.clicked.connect(self.import_profile)
        row2.addWidget(self.btn_import)
        self.btn_export = QPushButton("Export...")
        self.btn_export.clicked.connect(self.export_selected)
        row2.addWidget(self.btn_export)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_list)
        row2.addWidget(self.btn_refresh)
        row2.addStretch()
        layout.addLayout(row2)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        layout.addWidget(self.btn_close)

        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        for profile in self.store.list_profiles():
            label = profile["name"]
            if profile.get("description"):
                label = f"{label} — {profile['description']}"
            self.list_widget.addItem(label)

    def _selected_profile_name(self):
        item = self.list_widget.currentItem()
        if item is None:
            return None
        return item.text().split(" — ", 1)[0]

    def save_current_as(self):
        if self.config is None:
            return
        name, ok = QInputDialog.getText(self, "Save Profile", "Enter instrument name:")
        if not ok or not name.strip():
            return
        self.store.save_profile(name.strip(), self.config, description="Saved from desktop workspace")
        self.refresh_list()
        QMessageBox.information(self, "Saved", f"Profile '{name.strip()}' saved.")

    def apply_selected(self):
        name = self._selected_profile_name()
        if not name:
            QMessageBox.warning(self, "Warning", "Please select a profile first.")
            return
        loaded = self.store.load_profile(name)
        if self.config is not None:
            cfg = loaded["config"]
            for key, value in (cfg.model_dump() if hasattr(cfg, "model_dump") else cfg.dict()).items():
                setattr(self.config, key, value)
            self.config.active_instrument_profile = name
        QMessageBox.information(self, "Applied", f"Profile '{name}' applied.")
        self.accept()

    def rename_selected(self):
        name = self._selected_profile_name()
        if not name:
            QMessageBox.warning(self, "Warning", "Please select a profile first.")
            return
        new_name, ok = QInputDialog.getText(self, "Rename Profile", "New profile name:", text=name)
        if not ok or not new_name.strip():
            return
        self.store.rename_profile(name, new_name.strip())
        self.refresh_list()

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
        self.store.import_profile(source_path)
        self.refresh_list()

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
