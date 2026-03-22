import json
from copy import deepcopy

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from backend.decay_model_store import DecayModelStore, evaluate_decay_curve
from backend.models import PhysicsConfig


PARAM_COLUMNS = [
    ("name", "Name"),
    ("label", "Label"),
    ("unit", "Unit"),
    ("default", "Default"),
    ("sweep_min", "Sweep min"),
    ("sweep_max", "Sweep max"),
    ("sweep_steps", "Steps"),
    ("scale", "Scale"),
    ("description", "Description"),
]


class CustomModelEditorDialog(QDialog):
    """Editor for hardcoded and custom decay models, including sweep defaults."""

    def __init__(self, cfg: PhysicsConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Model Editor")
        self.resize(1280, 760)
        self.cfg = deepcopy(cfg)
        self.store = DecayModelStore()
        self.current_key = str(cfg.decay_model or "exponential")
        self.current_definition = None
        self._loading = False

        root = QHBoxLayout(self)

        left = QVBoxLayout()
        left.addWidget(QLabel("<b>Decay models</b>"))
        self.model_list = QListWidget()
        self.model_list.currentItemChanged.connect(self._on_model_changed)
        left.addWidget(self.model_list, 1)

        left_buttons = QGridLayout()
        self.btn_new = QPushButton("New")
        self.btn_duplicate = QPushButton("Duplicate")
        self.btn_delete = QPushButton("Delete")
        self.btn_import = QPushButton("Import")
        self.btn_export = QPushButton("Export")
        self.btn_save = QPushButton("Save")
        left_buttons.addWidget(self.btn_new, 0, 0)
        left_buttons.addWidget(self.btn_duplicate, 0, 1)
        left_buttons.addWidget(self.btn_delete, 1, 0)
        left_buttons.addWidget(self.btn_import, 1, 1)
        left_buttons.addWidget(self.btn_export, 2, 0)
        left_buttons.addWidget(self.btn_save, 2, 1)
        left.addLayout(left_buttons)
        root.addLayout(left, 1)

        main = QVBoxLayout()
        meta_group = QGroupBox("Model definition")
        meta_form = QFormLayout(meta_group)
        self.edit_key = QLineEdit()
        self.edit_name = QLineEdit()
        self.edit_expression = QTextEdit()
        self.edit_expression.setPlaceholderText("Use t and parameter names, for example: np.exp(-t / tau1)")
        self.lbl_mode = QLabel("")
        meta_form.addRow("Key:", self.edit_key)
        meta_form.addRow("Name:", self.edit_name)
        meta_form.addRow("Definition:", self.edit_expression)
        meta_form.addRow("Status:", self.lbl_mode)
        main.addWidget(meta_group)

        self.param_group = QGroupBox("Parameters and sweep defaults")
        param_layout = QVBoxLayout(self.param_group)
        self.param_table = QTableWidget(0, len(PARAM_COLUMNS))
        self.param_table.setHorizontalHeaderLabels([label for _, label in PARAM_COLUMNS])
        self.param_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.param_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        param_layout.addWidget(self.param_table)
        param_buttons = QHBoxLayout()
        self.btn_add_param = QPushButton("Add parameter")
        self.btn_remove_param = QPushButton("Remove selected")
        param_buttons.addWidget(self.btn_add_param)
        param_buttons.addWidget(self.btn_remove_param)
        param_buttons.addStretch()
        param_layout.addLayout(param_buttons)
        main.addWidget(self.param_group, 1)

        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_plot = pg.PlotWidget(background="#111111")
        self.preview_plot.setLabel("bottom", "Time", units="ns")
        self.preview_plot.setLabel("left", "Amplitude")
        self.preview_plot.showGrid(x=True, y=True, alpha=0.2)
        self.preview_curve = self.preview_plot.plot(pen=pg.mkPen("#8b5cf6", width=2))
        preview_layout.addWidget(self.preview_plot)
        self.preview_note = QLabel("Preview uses the current period and the current parameter defaults.")
        preview_layout.addWidget(self.preview_note)
        main.addWidget(preview_group, 1)

        bottom = QHBoxLayout()
        self.btn_apply = QPushButton("Apply selected")
        self.btn_close = QPushButton("Close")
        bottom.addStretch()
        bottom.addWidget(self.btn_apply)
        bottom.addWidget(self.btn_close)
        main.addLayout(bottom)
        root.addLayout(main, 3)

        self.btn_new.clicked.connect(self._create_new_model)
        self.btn_duplicate.clicked.connect(self._duplicate_current_model)
        self.btn_delete.clicked.connect(self._delete_current_model)
        self.btn_import.clicked.connect(self._import_model)
        self.btn_export.clicked.connect(self._export_model)
        self.btn_save.clicked.connect(self._save_current_model)
        self.btn_add_param.clicked.connect(self._add_parameter_row)
        self.btn_remove_param.clicked.connect(self._remove_selected_parameter)
        self.btn_apply.clicked.connect(self.accept)
        self.btn_close.clicked.connect(self.reject)
        self.param_table.itemChanged.connect(self._refresh_preview)
        self.edit_expression.textChanged.connect(self._refresh_preview)
        self.edit_key.textChanged.connect(self._refresh_preview)

        self._reload_list()

    def _reload_list(self):
        self._loading = True
        self.model_list.clear()
        for definition in self.store.all_models():
            item = QListWidgetItem(definition["name"])
            item.setData(Qt.ItemDataRole.UserRole, definition["key"])
            if definition.get("built_in"):
                item.setToolTip("Built-in model. You can adjust sweep defaults but not the equation.")
            self.model_list.addItem(item)
            if definition["key"] == self.current_key:
                self.model_list.setCurrentItem(item)
        self._loading = False
        if self.model_list.currentItem() is None and self.model_list.count():
            self.model_list.setCurrentRow(0)
        if self.model_list.currentItem() is not None:
            self._on_model_changed(self.model_list.currentItem(), None)

    def _definition_from_ui(self):
        definition = deepcopy(self.current_definition or {})
        definition["key"] = self.edit_key.text().strip()
        definition["name"] = self.edit_name.text().strip() or definition["key"]
        definition["expression"] = self.edit_expression.toPlainText().strip()
        parameters = []
        for row in range(self.param_table.rowCount()):
            item = {}
            for col, (key, _label) in enumerate(PARAM_COLUMNS):
                text = self.param_table.item(row, col).text().strip() if self.param_table.item(row, col) else ""
                if key in {"default", "sweep_min", "sweep_max"}:
                    item[key] = float(text or 0.0)
                elif key == "sweep_steps":
                    item[key] = int(float(text or 1))
                else:
                    item[key] = text
            item.setdefault("bounds_min", None)
            item.setdefault("bounds_max", None)
            parameters.append(item)
        definition["parameters"] = parameters
        return definition

    def _on_model_changed(self, current, _previous):
        if self._loading or current is None:
            return
        self.current_key = str(current.data(Qt.ItemDataRole.UserRole))
        self.current_definition = self.store.get(self.current_key)
        self._load_definition_to_ui()

    def _load_definition_to_ui(self):
        definition = deepcopy(self.current_definition or {})
        built_in = bool(definition.get("built_in"))
        self.edit_key.setText(str(definition.get("key", "")))
        self.edit_name.setText(str(definition.get("name", "")))
        self.edit_expression.setPlainText(str(definition.get("expression", definition.get("equation_html", ""))))
        self.edit_key.setReadOnly(built_in)
        self.edit_name.setReadOnly(False)
        self.edit_expression.setReadOnly(built_in)
        self.btn_delete.setEnabled(not built_in)
        self.btn_add_param.setEnabled(not built_in)
        self.btn_remove_param.setEnabled(not built_in)
        self.lbl_mode.setText("Built-in model" if built_in else "Custom model")

        self.param_table.blockSignals(True)
        self.param_table.setRowCount(0)
        for param in self.store.runtime_param_defs(self._cfg_for_preview(definition)):
            self._add_parameter_row(param)
        self.param_table.blockSignals(False)
        self._refresh_preview()

    def _cfg_for_preview(self, definition):
        cfg = deepcopy(self.cfg)
        cfg.decay_model = str(definition.get("key", cfg.decay_model))
        if cfg.decay_model not in {"exponential", "stretched"}:
            cfg.custom_model_params = {
                item["name"]: float(item.get("default", 0.0))
                for item in definition.get("parameters", [])
            }
            cfg.custom_decay_script = str(definition.get("expression", ""))
        return cfg

    def _create_new_model(self):
        key, ok = QInputDialog.getText(self, "New custom model", "Model key:")
        if not ok or not key.strip():
            return
        self.current_definition = {
            "key": key.strip(),
            "name": key.strip(),
            "built_in": False,
            "expression": "np.exp(-t / tau1)",
            "parameters": [
                {
                    "name": "tau1",
                    "label": "Tau 1",
                    "unit": "ns",
                    "default": 2.5,
                    "sweep_min": 0.2,
                    "sweep_max": 8.0,
                    "sweep_steps": 30,
                    "scale": "log",
                    "description": "Primary lifetime parameter.",
                }
            ],
        }
        self.current_key = key.strip()
        self._load_definition_to_ui()

    def _duplicate_current_model(self):
        if self.current_definition is None:
            return
        new_key, ok = QInputDialog.getText(self, "Duplicate model", "New model key:")
        if not ok or not new_key.strip():
            return
        definition = self._definition_from_ui()
        definition["key"] = new_key.strip()
        definition["name"] = f"{definition.get('name', self.current_key)} copy"
        self.store.upsert_custom_model(definition)
        self.current_key = definition["key"]
        self._reload_list()

    def _delete_current_model(self):
        if self.current_definition is None or self.current_definition.get("built_in"):
            return
        if QMessageBox.question(self, "Delete model", f"Delete {self.current_key}?") != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_custom_model(self.current_key)
        self.current_key = "exponential"
        self._reload_list()

    def _save_current_model(self):
        definition = self._definition_from_ui()
        if self.current_definition and self.current_definition.get("built_in"):
            for param in definition.get("parameters", []):
                self.store.set_sweep_override(
                    self.cfg,
                    definition["key"],
                    param["name"],
                    sweep_min=param.get("sweep_min", 0.0),
                    sweep_max=param.get("sweep_max", 1.0),
                    sweep_steps=param.get("sweep_steps", 20),
                    scale=param.get("scale", "linear"),
                )
            self.current_definition = definition
            QMessageBox.information(self, "Saved", "Built-in sweep defaults updated for this session.")
            return
        saved = self.store.upsert_custom_model(definition, previous_key=self.current_key)
        self.current_key = saved["key"]
        self.current_definition = saved
        self._reload_list()
        QMessageBox.information(self, "Saved", f"Custom model '{saved['name']}' saved.")

    def _export_model(self):
        if self.current_definition is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export model", f"{self.current_key}.json", "JSON (*.json)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.store.export_model(self.current_key))

    def _import_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import model", "", "JSON (*.json)")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as handle:
            imported = self.store.import_model(handle.read())
        self.current_key = imported["key"]
        self._reload_list()

    def _add_parameter_row(self, values=None):
        values = values or {
            "name": "param",
            "label": "Parameter",
            "unit": "",
            "default": 1.0,
            "sweep_min": 0.0,
            "sweep_max": 1.0,
            "sweep_steps": 20,
            "scale": "linear",
            "description": "",
        }
        row = self.param_table.rowCount()
        self.param_table.insertRow(row)
        for col, (key, _label) in enumerate(PARAM_COLUMNS):
            item = QTableWidgetItem(str(values.get(key, "")))
            self.param_table.setItem(row, col, item)

    def _remove_selected_parameter(self):
        rows = sorted({index.row() for index in self.param_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.param_table.removeRow(row)
        self._refresh_preview()

    def _refresh_preview(self, *_args):
        try:
            definition = self._definition_from_ui()
            cfg = self._cfg_for_preview(definition)
            t = np.linspace(0.0, max(float(cfg.period), 1e-3), 1200)
            y = evaluate_decay_curve(cfg, t, definition)
            y = y / max(float(np.max(y)), 1e-12)
            self.preview_curve.setData(t, y)
            self.preview_note.setText("Preview uses the current period and the current parameter defaults.")
        except Exception as exc:  # noqa: BLE001
            self.preview_curve.setData([], [])
            self.preview_note.setText(f"Preview error: {exc}")

    def selected_model_key(self):
        return str(self.current_key or "exponential")
