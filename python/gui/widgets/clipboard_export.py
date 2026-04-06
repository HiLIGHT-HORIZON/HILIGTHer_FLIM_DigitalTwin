from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Callable, Dict, Optional
import json
import os
import shutil
import xml.etree.ElementTree as ET

import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter, SVGExporter
from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, QSize, QMimeData, Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPalette, QPen, QPixmap
from PyQt6.QtSvg import QSvgGenerator
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


_PYTHON_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_STORE_DIR = os.path.join(_PYTHON_ROOT, "profiles", "clipboard_exports")
_INSTALL_PATH = os.path.join(_STORE_DIR, "defaults.install.json")
_CURRENT_PATH = os.path.join(_STORE_DIR, "defaults.current.json")


@dataclass
class ClipboardExportSettings:
    use_defaults: bool = True
    include_legend: bool = False
    dpi: int = 1000
    aspect_w: float = 1.0
    aspect_h: float = 1.0
    size_w: float = 4.0
    size_h: float = 4.0
    unit: str = "cm"
    lock_aspect: bool = True
    font_size_pt: float = 0.0
    theme_mode: str = "gui"
    fmt: str = "png"
    grid_x: bool = True
    grid_y: bool = True
    grid_alpha: float = 0.3
    show_bounding_box: bool = False
    tick_visibility: str = "major_minor"
    tick_direction: str = "inner"
    tick_length: float = 0.0
    plot_line_width: float = 0.0
    axis_line_width: float = 0.0
    marker_size: float = 0.0

    @classmethod
    def from_dict(cls, payload: Optional[dict]) -> "ClipboardExportSettings":
        if not isinstance(payload, dict):
            return cls()
        defaults = asdict(cls())
        sanitized = {}
        for key, default_value in defaults.items():
            value = payload.get(key, default_value)
            if isinstance(default_value, bool):
                sanitized[key] = bool(value)
            elif isinstance(default_value, int):
                try:
                    sanitized[key] = int(value)
                except Exception:
                    sanitized[key] = default_value
            elif isinstance(default_value, float):
                try:
                    sanitized[key] = float(value)
                except Exception:
                    sanitized[key] = default_value
            else:
                sanitized[key] = str(value)
        sanitized["unit"] = sanitized["unit"] if sanitized["unit"] in {"cm", "in"} else "cm"
        sanitized["theme_mode"] = sanitized["theme_mode"] if sanitized["theme_mode"] in {"gui", "light", "dark"} else "gui"
        sanitized["fmt"] = sanitized["fmt"] if sanitized["fmt"] in {"png", "svg"} else "png"
        sanitized["tick_visibility"] = sanitized["tick_visibility"] if sanitized["tick_visibility"] in {"major_minor", "major", "none"} else "major_minor"
        sanitized["tick_direction"] = sanitized["tick_direction"] if sanitized["tick_direction"] in {"inner", "outer"} else "inner"
        sanitized["grid_alpha"] = min(max(float(sanitized["grid_alpha"]), 0.0), 1.0)
        sanitized["tick_length"] = max(float(sanitized["tick_length"]), 0.0)
        sanitized["plot_line_width"] = max(float(sanitized["plot_line_width"]), 0.0)
        sanitized["axis_line_width"] = max(float(sanitized["axis_line_width"]), 0.0)
        sanitized["marker_size"] = max(float(sanitized["marker_size"]), 0.0)
        sanitized["aspect_w"] = max(float(sanitized["aspect_w"]), 0.1)
        sanitized["aspect_h"] = max(float(sanitized["aspect_h"]), 0.1)
        sanitized["size_w"] = max(float(sanitized["size_w"]), 0.1)
        sanitized["size_h"] = max(float(sanitized["size_h"]), 0.1)
        sanitized["dpi"] = max(int(sanitized["dpi"]), 72)
        sanitized["font_size_pt"] = max(float(sanitized["font_size_pt"]), 0.0)
        return cls(**sanitized)

    def to_dict(self) -> dict:
        return asdict(self)


def _default_clipboard_export_payload() -> dict:
    return {
        "current": ClipboardExportSettings().to_dict(),
        "profiles": {},
    }


class ClipboardExportProfileStore:
    """Persistence layer for clipboard export defaults and named profiles."""

    def __init__(self):
        os.makedirs(_STORE_DIR, exist_ok=True)
        self._ensure_install_defaults()
        self._ensure_current_defaults()

    def _ensure_install_defaults(self) -> None:
        if not os.path.exists(_INSTALL_PATH):
            with open(_INSTALL_PATH, "w", encoding="utf-8") as handle:
                json.dump(_default_clipboard_export_payload(), handle, indent=2)

    def _ensure_current_defaults(self) -> None:
        if not os.path.exists(_CURRENT_PATH):
            shutil.copyfile(_INSTALL_PATH, _CURRENT_PATH)

    @staticmethod
    def _normalize_profile_name(name: str) -> str:
        return " ".join(str(name or "").split()).strip()

    def _sanitize_payload(self, payload: Optional[dict]) -> dict:
        if not isinstance(payload, dict):
            payload = {}
        current = ClipboardExportSettings.from_dict(payload.get("current")).to_dict()
        profiles_in = payload.get("profiles", {})
        profiles_out = {}
        if isinstance(profiles_in, dict):
            for raw_name, raw_settings in profiles_in.items():
                name = self._normalize_profile_name(raw_name)
                if not name:
                    continue
                profiles_out[name] = ClipboardExportSettings.from_dict(raw_settings).to_dict()
        return {"current": current, "profiles": dict(sorted(profiles_out.items(), key=lambda item: item[0].lower()))}

    def _load_payload(self) -> dict:
        self._ensure_current_defaults()
        try:
            with open(_CURRENT_PATH, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            payload = _default_clipboard_export_payload()
        return self._sanitize_payload(payload)

    def _save_payload(self, payload: dict) -> None:
        os.makedirs(_STORE_DIR, exist_ok=True)
        with open(_CURRENT_PATH, "w", encoding="utf-8") as handle:
            json.dump(self._sanitize_payload(payload), handle, indent=2)

    def load_current(self) -> ClipboardExportSettings:
        return ClipboardExportSettings.from_dict(self._load_payload().get("current"))

    def save_current(self, settings: ClipboardExportSettings) -> None:
        payload = self._load_payload()
        payload["current"] = ClipboardExportSettings.from_dict(settings.to_dict()).to_dict()
        self._save_payload(payload)

    def load_profiles(self) -> Dict[str, ClipboardExportSettings]:
        payload = self._load_payload()
        return {
            name: ClipboardExportSettings.from_dict(profile_payload)
            for name, profile_payload in payload.get("profiles", {}).items()
        }

    def save_profiles(self, profiles: Dict[str, ClipboardExportSettings]) -> None:
        payload = self._load_payload()
        payload["profiles"] = {
            self._normalize_profile_name(name): ClipboardExportSettings.from_dict(settings.to_dict()).to_dict()
            for name, settings in profiles.items()
            if self._normalize_profile_name(name)
        }
        self._save_payload(payload)


class ClipboardExportDialog(QDialog):
    PROFILE_CURRENT = "__current__"

    def __init__(
        self,
        settings: ClipboardExportSettings,
        saved_profiles: Optional[Dict[str, ClipboardExportSettings]] = None,
        parent: Optional[QWidget] = None,
        *,
        source_size: Optional[tuple[float, float]] = None,
        current_font_pt: Optional[float] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Clipboard Export Settings")
        self._syncing = False
        self._result_settings = replace(settings)
        self._saved_profiles = {
            str(name): replace(profile)
            for name, profile in (saved_profiles or {}).items()
        }
        self._initial_matching_profile = next(
            (name for name, profile in self._saved_profiles.items() if settings == profile),
            self.PROFILE_CURRENT,
        )
        self._source_size = (
            max(float(source_size[0]), 1.0),
            max(float(source_size[1]), 1.0),
        ) if source_size else None
        self._source_aspect = self._normalized_aspect(
            source_size[0] if source_size else settings.aspect_w,
            source_size[1] if source_size else settings.aspect_h,
        )
        self._current_font_pt = float(current_font_pt or 0.0)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        profile_row = QWidget()
        profile_layout = QHBoxLayout(profile_row)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(6)
        self.combo_profiles = QComboBox()
        self.btn_profile_save = QPushButton("Save")
        self.btn_profile_save_as = QPushButton("Save As")
        self.btn_profile_rename = QPushButton("Rename")
        self.btn_profile_delete = QPushButton("Delete")
        profile_layout.addWidget(self.combo_profiles, stretch=1)
        profile_layout.addWidget(self.btn_profile_save)
        profile_layout.addWidget(self.btn_profile_save_as)
        profile_layout.addWidget(self.btn_profile_rename)
        profile_layout.addWidget(self.btn_profile_delete)
        form.addRow("Profile:", profile_row)

        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(72, 10000)
        self.spin_dpi.setValue(int(settings.dpi))
        form.addRow("Resolution (DPI):", self.spin_dpi)
        self.chk_use_defaults = QCheckBox("Use default settings")
        self.chk_use_defaults.setChecked(bool(settings.use_defaults))
        form.addRow("", self.chk_use_defaults)
        self.chk_include_legend = QCheckBox("Include legend")
        self.chk_include_legend.setChecked(bool(settings.include_legend))
        form.addRow("", self.chk_include_legend)

        aspect_row = QWidget()
        aspect_layout = QHBoxLayout(aspect_row)
        aspect_layout.setContentsMargins(0, 0, 0, 0)
        aspect_layout.setSpacing(6)
        self.spin_aspect_w = QDoubleSpinBox()
        self.spin_aspect_w.setRange(0.1, 100.0)
        self.spin_aspect_w.setDecimals(3)
        self.spin_aspect_w.setValue(float(settings.aspect_w))
        self.spin_aspect_h = QDoubleSpinBox()
        self.spin_aspect_h.setRange(0.1, 100.0)
        self.spin_aspect_h.setDecimals(3)
        self.spin_aspect_h.setValue(float(settings.aspect_h))
        aspect_layout.addWidget(self.spin_aspect_w)
        aspect_layout.addWidget(QLabel(":"))
        aspect_layout.addWidget(self.spin_aspect_h)
        aspect_layout.addStretch()
        form.addRow("Aspect ratio:", aspect_row)
        self.chk_lock_aspect = QCheckBox("Lock aspect ratio")
        self.chk_lock_aspect.setChecked(bool(settings.lock_aspect))
        form.addRow("", self.chk_lock_aspect)

        size_row = QWidget()
        size_layout = QHBoxLayout(size_row)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.setSpacing(6)
        self.spin_size_w = QDoubleSpinBox()
        self.spin_size_w.setRange(0.1, 100.0)
        self.spin_size_w.setDecimals(3)
        self.spin_size_w.setValue(float(settings.size_w))
        self.spin_size_h = QDoubleSpinBox()
        self.spin_size_h.setRange(0.1, 100.0)
        self.spin_size_h.setDecimals(3)
        self.spin_size_h.setValue(float(settings.size_h))
        self.combo_unit = QComboBox()
        self.combo_unit.addItems(["cm", "in"])
        self.combo_unit.setCurrentText(str(settings.unit))
        size_layout.addWidget(self.spin_size_w)
        size_layout.addWidget(QLabel("x"))
        size_layout.addWidget(self.spin_size_h)
        size_layout.addWidget(self.combo_unit)
        size_layout.addStretch()
        form.addRow("Export size:", size_row)

        self.spin_font_size = QDoubleSpinBox()
        self.spin_font_size.setRange(0.0, 144.0)
        self.spin_font_size.setDecimals(1)
        self.spin_font_size.setSingleStep(0.5)
        self.spin_font_size.setSpecialValueText("GUI default")
        self.spin_font_size.setValue(float(settings.font_size_pt))
        if self._current_font_pt > 0.0:
            self.spin_font_size.setToolTip(f"GUI default is currently {self._current_font_pt:.1f} pt.")
        form.addRow("Font size (pt):", self.spin_font_size)

        line_row = QWidget()
        line_layout = QHBoxLayout(line_row)
        line_layout.setContentsMargins(0, 0, 0, 0)
        line_layout.setSpacing(6)
        self.spin_plot_line_width = QDoubleSpinBox()
        self.spin_plot_line_width.setRange(0.0, 20.0)
        self.spin_plot_line_width.setDecimals(1)
        self.spin_plot_line_width.setSingleStep(0.2)
        self.spin_plot_line_width.setSpecialValueText("Original")
        self.spin_plot_line_width.setValue(float(settings.plot_line_width))
        self.spin_axis_line_width = QDoubleSpinBox()
        self.spin_axis_line_width.setRange(0.0, 20.0)
        self.spin_axis_line_width.setDecimals(1)
        self.spin_axis_line_width.setSingleStep(0.2)
        self.spin_axis_line_width.setSpecialValueText("Original")
        self.spin_axis_line_width.setValue(float(settings.axis_line_width))
        line_layout.addWidget(QLabel("Plots"))
        line_layout.addWidget(self.spin_plot_line_width)
        line_layout.addWidget(QLabel("Axes"))
        line_layout.addWidget(self.spin_axis_line_width)
        self.spin_marker_size = QDoubleSpinBox()
        self.spin_marker_size.setRange(0.0, 100.0)
        self.spin_marker_size.setDecimals(1)
        self.spin_marker_size.setSingleStep(0.5)
        self.spin_marker_size.setSpecialValueText("Original")
        self.spin_marker_size.setValue(float(settings.marker_size))
        line_layout.addWidget(QLabel("Markers"))
        line_layout.addWidget(self.spin_marker_size)
        line_layout.addStretch()
        form.addRow("Line width:", line_row)

        self.combo_theme = QComboBox()
        self.combo_theme.addItem("GUI choice", "gui")
        self.combo_theme.addItem("Light", "light")
        self.combo_theme.addItem("Dark", "dark")
        self.combo_theme.setCurrentIndex(max(self.combo_theme.findData(settings.theme_mode), 0))
        form.addRow("Export theme:", self.combo_theme)

        grid_row = QWidget()
        grid_layout = QHBoxLayout(grid_row)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(6)
        self.chk_grid_x = QCheckBox("X grid")
        self.chk_grid_x.setChecked(bool(settings.grid_x))
        self.chk_grid_y = QCheckBox("Y grid")
        self.chk_grid_y.setChecked(bool(settings.grid_y))
        self.spin_grid_alpha = QDoubleSpinBox()
        self.spin_grid_alpha.setRange(0.0, 1.0)
        self.spin_grid_alpha.setDecimals(2)
        self.spin_grid_alpha.setSingleStep(0.05)
        self.spin_grid_alpha.setValue(float(settings.grid_alpha))
        self.spin_grid_alpha.setSuffix(" alpha")
        grid_layout.addWidget(self.chk_grid_x)
        grid_layout.addWidget(self.chk_grid_y)
        grid_layout.addWidget(self.spin_grid_alpha)
        grid_layout.addStretch()
        form.addRow("Grid:", grid_row)

        self.chk_show_bounding_box = QCheckBox("Show plot bounding box")
        self.chk_show_bounding_box.setChecked(bool(settings.show_bounding_box))
        form.addRow("", self.chk_show_bounding_box)

        ticks_row = QWidget()
        ticks_layout = QHBoxLayout(ticks_row)
        ticks_layout.setContentsMargins(0, 0, 0, 0)
        ticks_layout.setSpacing(6)
        self.combo_tick_visibility = QComboBox()
        self.combo_tick_visibility.addItem("Major + minor", "major_minor")
        self.combo_tick_visibility.addItem("Major only", "major")
        self.combo_tick_visibility.addItem("No ticks", "none")
        self.combo_tick_visibility.setCurrentIndex(max(self.combo_tick_visibility.findData(settings.tick_visibility), 0))
        self.combo_tick_direction = QComboBox()
        self.combo_tick_direction.addItem("Inner", "inner")
        self.combo_tick_direction.addItem("Outer", "outer")
        self.combo_tick_direction.setCurrentIndex(max(self.combo_tick_direction.findData(settings.tick_direction), 0))
        self.spin_tick_length = QDoubleSpinBox()
        self.spin_tick_length.setRange(0.0, 100.0)
        self.spin_tick_length.setDecimals(1)
        self.spin_tick_length.setSingleStep(0.5)
        self.spin_tick_length.setSpecialValueText("Original")
        self.spin_tick_length.setValue(float(settings.tick_length))
        ticks_layout.addWidget(self.combo_tick_visibility)
        ticks_layout.addWidget(self.combo_tick_direction)
        ticks_layout.addWidget(QLabel("Length"))
        ticks_layout.addWidget(self.spin_tick_length)
        ticks_layout.addStretch()
        form.addRow("Ticks:", ticks_row)

        self.combo_format = QComboBox()
        self.combo_format.addItem("PNG", "png")
        self.combo_format.addItem("SVG", "svg")
        self.combo_format.setCurrentIndex(max(self.combo_format.findData(settings.fmt), 0))
        form.addRow("Clipboard format:", self.combo_format)

        layout.addLayout(form)

        self.chk_apply_all = QCheckBox("Apply to all graphs")
        layout.addWidget(self.chk_apply_all)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.combo_profiles.currentIndexChanged.connect(self._on_profile_selected)
        self.btn_profile_save.clicked.connect(self._save_profile)
        self.btn_profile_save_as.clicked.connect(lambda: self._save_profile(force_prompt=True))
        self.btn_profile_rename.clicked.connect(self._rename_profile)
        self.btn_profile_delete.clicked.connect(self._delete_profile)

        self.spin_aspect_w.valueChanged.connect(lambda *_: self._sync_from_aspect("w"))
        self.spin_aspect_h.valueChanged.connect(lambda *_: self._sync_from_aspect("h"))
        self.spin_size_w.valueChanged.connect(lambda *_: self._sync_from_size("w"))
        self.spin_size_h.valueChanged.connect(lambda *_: self._sync_from_size("h"))
        self.chk_lock_aspect.toggled.connect(self._update_lock_state)
        self.combo_unit.currentTextChanged.connect(self._update_lock_state)
        self.chk_use_defaults.toggled.connect(self._update_controls_enabled)
        self.chk_use_defaults.toggled.connect(self._update_lock_state)
        self.chk_use_defaults.toggled.connect(self._populate_default_values)
        self.combo_unit.currentTextChanged.connect(self._populate_default_values)
        self.spin_dpi.valueChanged.connect(self._populate_default_values)
        for signal in (
            self.chk_use_defaults.toggled,
            self.chk_include_legend.toggled,
            self.spin_dpi.valueChanged,
            self.spin_aspect_w.valueChanged,
            self.spin_aspect_h.valueChanged,
            self.chk_lock_aspect.toggled,
            self.spin_size_w.valueChanged,
            self.spin_size_h.valueChanged,
            self.combo_unit.currentTextChanged,
            self.spin_font_size.valueChanged,
            self.spin_plot_line_width.valueChanged,
            self.spin_axis_line_width.valueChanged,
            self.spin_marker_size.valueChanged,
            self.combo_theme.currentIndexChanged,
            self.chk_grid_x.toggled,
            self.chk_grid_y.toggled,
            self.spin_grid_alpha.valueChanged,
            self.chk_show_bounding_box.toggled,
            self.combo_tick_visibility.currentIndexChanged,
            self.combo_tick_direction.currentIndexChanged,
            self.spin_tick_length.valueChanged,
            self.combo_format.currentIndexChanged,
        ):
            signal.connect(self._on_settings_edited)
        self._populate_profile_combo(selected_name=self._initial_matching_profile)
        self._populate_default_values()
        self._update_controls_enabled()
        self._update_lock_state()
        self._update_profile_buttons()

    def _populate_profile_combo(self, selected_name: Optional[str] = None):
        self._syncing = True
        try:
            current_data = self.combo_profiles.currentData()
            if selected_name is None:
                selected_name = current_data if isinstance(current_data, str) else self.PROFILE_CURRENT
            self.combo_profiles.clear()
            self.combo_profiles.addItem("Current settings", self.PROFILE_CURRENT)
            for name in sorted(self._saved_profiles, key=str.lower):
                self.combo_profiles.addItem(name, name)
            index = self.combo_profiles.findData(selected_name)
            self.combo_profiles.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self._syncing = False
        self._update_profile_buttons()

    def _selected_profile_name(self) -> Optional[str]:
        data = self.combo_profiles.currentData()
        if data in (None, self.PROFILE_CURRENT):
            return None
        return str(data)

    def _update_profile_buttons(self):
        profile_name = self._selected_profile_name()
        has_named_profile = profile_name is not None
        is_dirty = False
        if has_named_profile:
            is_dirty = self.export_settings() != self._saved_profiles.get(profile_name)
        self.btn_profile_save.setText("Update*" if has_named_profile and is_dirty else "Update" if has_named_profile else "Save")
        self.btn_profile_rename.setEnabled(has_named_profile)
        self.btn_profile_delete.setEnabled(has_named_profile)

    def _apply_settings_to_controls(self, settings: ClipboardExportSettings):
        self._syncing = True
        try:
            self.chk_use_defaults.setChecked(bool(settings.use_defaults))
            self.chk_include_legend.setChecked(bool(settings.include_legend))
            self.spin_dpi.setValue(int(settings.dpi))
            self.spin_aspect_w.setValue(float(settings.aspect_w))
            self.spin_aspect_h.setValue(float(settings.aspect_h))
            self.chk_lock_aspect.setChecked(bool(settings.lock_aspect))
            self.spin_size_w.setValue(float(settings.size_w))
            self.spin_size_h.setValue(float(settings.size_h))
            self.combo_unit.setCurrentText(str(settings.unit))
            self.spin_font_size.setValue(float(settings.font_size_pt))
            self.spin_plot_line_width.setValue(float(settings.plot_line_width))
            self.spin_axis_line_width.setValue(float(settings.axis_line_width))
            self.spin_marker_size.setValue(float(settings.marker_size))
            self.combo_theme.setCurrentIndex(max(self.combo_theme.findData(settings.theme_mode), 0))
            self.chk_grid_x.setChecked(bool(settings.grid_x))
            self.chk_grid_y.setChecked(bool(settings.grid_y))
            self.spin_grid_alpha.setValue(float(settings.grid_alpha))
            self.chk_show_bounding_box.setChecked(bool(settings.show_bounding_box))
            self.combo_tick_visibility.setCurrentIndex(max(self.combo_tick_visibility.findData(settings.tick_visibility), 0))
            self.combo_tick_direction.setCurrentIndex(max(self.combo_tick_direction.findData(settings.tick_direction), 0))
            self.spin_tick_length.setValue(float(settings.tick_length))
            self.combo_format.setCurrentIndex(max(self.combo_format.findData(settings.fmt), 0))
        finally:
            self._syncing = False
        self._populate_default_values()
        self._update_controls_enabled()
        self._update_lock_state()
        self._update_profile_buttons()

    def _on_profile_selected(self, *_args):
        if self._syncing:
            return
        profile_name = self._selected_profile_name()
        self._update_profile_buttons()
        if profile_name is None:
            return
        settings = self._saved_profiles.get(profile_name)
        if settings is not None:
            self._apply_settings_to_controls(settings)

    def _on_settings_edited(self, *_args):
        if self._syncing:
            return
        self._update_profile_buttons()

    def _prompt_profile_name(self, title: str, initial: str = "") -> Optional[str]:
        name, ok = QInputDialog.getText(self, title, "Profile name:", text=initial)
        if not ok:
            return None
        name = ClipboardExportProfileStore._normalize_profile_name(name)
        if not name:
            QMessageBox.warning(self, "Invalid profile", "Please enter a non-empty profile name.")
            return None
        return name

    def _save_profile(self, *_args, force_prompt: bool = False):
        current_name = self._selected_profile_name()
        target_name = current_name
        if force_prompt or current_name is None:
            target_name = self._prompt_profile_name("Save export profile", current_name or "")
            if target_name is None:
                return
        if current_name != target_name and target_name in self._saved_profiles:
            answer = QMessageBox.question(
                self,
                "Overwrite profile?",
                f'A profile named "{target_name}" already exists. Overwrite it?',
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._saved_profiles[str(target_name)] = self.export_settings()
        self._populate_profile_combo(selected_name=str(target_name))
        self._update_profile_buttons()

    def _rename_profile(self):
        current_name = self._selected_profile_name()
        if current_name is None:
            return
        target_name = self._prompt_profile_name("Rename export profile", current_name)
        if target_name is None or target_name == current_name:
            return
        if target_name in self._saved_profiles:
            answer = QMessageBox.question(
                self,
                "Replace profile?",
                f'A profile named "{target_name}" already exists. Replace it?',
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._saved_profiles[str(target_name)] = replace(self._saved_profiles[current_name])
        self._saved_profiles.pop(current_name, None)
        self._populate_profile_combo(selected_name=str(target_name))
        self._update_profile_buttons()

    def _delete_profile(self):
        current_name = self._selected_profile_name()
        if current_name is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete profile?",
            f'Delete the export profile "{current_name}"?',
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._saved_profiles.pop(current_name, None)
        self._populate_profile_combo(selected_name=self.PROFILE_CURRENT)
        self._update_profile_buttons()

    @staticmethod
    def _normalized_aspect(width: float, height: float) -> tuple[float, float]:
        width = max(float(width), 1e-9)
        height = max(float(height), 1e-9)
        if width >= height:
            return width / height, 1.0
        return 1.0, height / width

    def _set_aspect_report(self):
        self._syncing = True
        try:
            self.spin_aspect_w.setValue(self._source_aspect[0])
            self.spin_aspect_h.setValue(self._source_aspect[1])
        finally:
            self._syncing = False

    def _update_lock_state(self):
        if self.chk_use_defaults.isChecked():
            self._set_aspect_report()
            return
        locked = self.chk_lock_aspect.isChecked()
        self.spin_aspect_w.setEnabled(locked)
        self.spin_aspect_h.setEnabled(locked)
        if not locked:
            self._set_aspect_report()
        else:
            self._sync_from_aspect("w")

    def _sync_from_aspect(self, source: str):
        if self._syncing or self.chk_use_defaults.isChecked() or not self.chk_lock_aspect.isChecked():
            return
        self._syncing = True
        try:
            ratio = max(self.spin_aspect_w.value(), 1e-9) / max(self.spin_aspect_h.value(), 1e-9)
            if source == "w":
                self.spin_size_h.setValue(max(self.spin_size_w.value() / ratio, 0.1))
            else:
                self.spin_size_w.setValue(max(self.spin_size_h.value() * ratio, 0.1))
        finally:
            self._syncing = False

    def _sync_from_size(self, source: str):
        if self._syncing or self.chk_use_defaults.isChecked():
            return
        self._syncing = True
        try:
            if not self.chk_lock_aspect.isChecked():
                aspect_w, aspect_h = self._normalized_aspect(self.spin_size_w.value(), self.spin_size_h.value())
                self.spin_aspect_w.setValue(aspect_w)
                self.spin_aspect_h.setValue(aspect_h)
            else:
                ratio = max(self.spin_aspect_w.value(), 1e-9) / max(self.spin_aspect_h.value(), 1e-9)
                if source == "w":
                    self.spin_size_h.setValue(max(self.spin_size_w.value() / ratio, 0.1))
                else:
                    self.spin_size_w.setValue(max(self.spin_size_h.value() * ratio, 0.1))
        finally:
            self._syncing = False

    def _update_controls_enabled(self):
        enabled = not self.chk_use_defaults.isChecked()
        for widget in (
            self.chk_include_legend,
            self.spin_dpi,
            self.spin_aspect_w,
            self.spin_aspect_h,
            self.chk_lock_aspect,
            self.spin_size_w,
            self.spin_size_h,
            self.combo_unit,
            self.spin_font_size,
            self.spin_plot_line_width,
            self.spin_axis_line_width,
            self.spin_marker_size,
            self.combo_theme,
            self.chk_grid_x,
            self.chk_grid_y,
            self.spin_grid_alpha,
            self.chk_show_bounding_box,
            self.combo_tick_visibility,
            self.combo_tick_direction,
            self.spin_tick_length,
            self.combo_format,
        ):
            widget.setEnabled(enabled)

    def _populate_default_values(self):
        if not self.chk_use_defaults.isChecked():
            return
        self._syncing = True
        try:
            self._set_aspect_report()
            if self._source_size is not None:
                unit_scale = 1.0 / 2.54 if self.combo_unit.currentText() == "cm" else 1.0
                self.spin_size_w.setValue(max(self._source_size[0] / max(self.spin_dpi.value(), 1) / unit_scale, 0.1))
                self.spin_size_h.setValue(max(self._source_size[1] / max(self.spin_dpi.value(), 1) / unit_scale, 0.1))
            if self._current_font_pt > 0.0:
                self.spin_font_size.setValue(self._current_font_pt)
            self.combo_theme.setCurrentIndex(max(self.combo_theme.findData("gui"), 0))
            self.combo_format.setCurrentIndex(max(self.combo_format.findData("png"), 0))
        finally:
            self._syncing = False

    def export_settings(self) -> ClipboardExportSettings:
        return ClipboardExportSettings(
            use_defaults=bool(self.chk_use_defaults.isChecked()),
            include_legend=bool(self.chk_include_legend.isChecked()),
            dpi=int(self.spin_dpi.value()),
            aspect_w=float(self.spin_aspect_w.value()),
            aspect_h=float(self.spin_aspect_h.value()),
            size_w=float(self.spin_size_w.value()),
            size_h=float(self.spin_size_h.value()),
            unit=str(self.combo_unit.currentText()),
            lock_aspect=bool(self.chk_lock_aspect.isChecked()),
            font_size_pt=float(self.spin_font_size.value()),
            plot_line_width=float(self.spin_plot_line_width.value()),
            axis_line_width=float(self.spin_axis_line_width.value()),
            marker_size=float(self.spin_marker_size.value()),
            theme_mode=str(self.combo_theme.currentData()),
            fmt=str(self.combo_format.currentData()),
            grid_x=bool(self.chk_grid_x.isChecked()),
            grid_y=bool(self.chk_grid_y.isChecked()),
            grid_alpha=float(self.spin_grid_alpha.value()),
            show_bounding_box=bool(self.chk_show_bounding_box.isChecked()),
            tick_visibility=str(self.combo_tick_visibility.currentData()),
            tick_direction=str(self.combo_tick_direction.currentData()),
            tick_length=float(self.spin_tick_length.value()),
        )

    def saved_profiles(self) -> Dict[str, ClipboardExportSettings]:
        return {
            str(name): replace(settings)
            for name, settings in self._saved_profiles.items()
        }


class ClipboardExportManager:
    _store = ClipboardExportProfileStore()
    _global_settings = _store.load_current()
    _saved_profiles = _store.load_profiles()
    _per_graph_settings: Dict[str, ClipboardExportSettings] = {}

    @classmethod
    def settings_for(cls, graph_key: str) -> ClipboardExportSettings:
        return replace(cls._per_graph_settings.get(graph_key, cls._global_settings))

    @classmethod
    def configure(
        cls,
        graph_key: str,
        parent: Optional[QWidget] = None,
        *,
        export_source=None,
    ) -> None:
        dialog = ClipboardExportDialog(
            cls.settings_for(graph_key),
            saved_profiles=cls._saved_profiles,
            parent=parent,
            source_size=cls._source_size(export_source),
            current_font_pt=cls._current_font_size(export_source),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.export_settings()
        cls._saved_profiles = dialog.saved_profiles()
        cls._store.save_profiles(cls._saved_profiles)
        if dialog.chk_apply_all.isChecked():
            cls._global_settings = replace(settings)
            cls._per_graph_settings.clear()
            cls._store.save_current(cls._global_settings)
        else:
            cls._per_graph_settings[graph_key] = replace(settings)

    @classmethod
    def export_widget(
        cls,
        graph_key: str,
        widget: QWidget,
        *,
        parent: Optional[QWidget] = None,
        theme_target: Optional[QWidget] = None,
        export_source=None,
        export_legend_entries: Optional[Callable[[], list[dict]]] = None,
    ) -> None:
        settings = cls.settings_for(graph_key)
        source = export_source or widget
        theme_owner = theme_target or widget
        original_theme = getattr(theme_owner, "current_theme", None)
        use_defaults = bool(settings.use_defaults)
        override_theme = None if use_defaults else settings.theme_mode if settings.theme_mode in {"light", "dark"} else None
        font_state = cls._capture_font_state(source)
        size_state = cls._capture_size_state(source)
        plot_style_state = cls._capture_plot_style_state(source)
        if override_theme and hasattr(theme_owner, "set_theme"):
            theme_owner.set_theme(override_theme)
        font_size_pt = 0.0 if use_defaults else settings.font_size_pt
        cls._apply_font_override(source, font_size_pt)
        cls._apply_plot_style_override(source, settings, use_defaults=use_defaults)
        cls._refresh_source(source)
        try:
            legend_entries = []
            if settings.include_legend and export_legend_entries is not None:
                try:
                    legend_entries = list(export_legend_entries() or [])
                except Exception:
                    legend_entries = []
            if cls._is_pyqtgraph_source(source):
                cls._prepare_plot_source(source, settings, use_defaults=use_defaults)
                if settings.fmt == "svg":
                    mime = cls._render_pyqtgraph_svg_mime(source, settings, legend_entries=legend_entries, use_defaults=use_defaults)
                else:
                    mime = cls._render_pyqtgraph_png_mime(source, settings, legend_entries=legend_entries, use_defaults=use_defaults)
            elif settings.fmt == "svg":
                mime = cls._render_svg_mime(widget, settings)
            else:
                mime = cls._render_png_mime(widget, settings)
            if mime is not None:
                QGuiApplication.clipboard().setMimeData(mime)
        finally:
            cls._restore_size_state(source, size_state)
            if override_theme and original_theme is not None and hasattr(theme_owner, "set_theme"):
                theme_owner.set_theme(original_theme)
            cls._restore_plot_style_state(source, plot_style_state)
            cls._restore_font_state(source, font_state)
            cls._refresh_source(source)

    @staticmethod
    def _target_pixels(settings: ClipboardExportSettings) -> tuple[int, int]:
        unit_scale = 1.0 / 2.54 if settings.unit == "cm" else 1.0
        width_px = max(int(round(settings.size_w * unit_scale * settings.dpi)), 1)
        height_px = max(int(round(settings.size_h * unit_scale * settings.dpi)), 1)
        return width_px, height_px

    @staticmethod
    def _source_size(source) -> Optional[tuple[float, float]]:
        if source is None:
            return None
        if hasattr(source, "size") and callable(source.size):
            size = source.size()
            return float(max(size.width(), 1)), float(max(size.height(), 1))
        if hasattr(source, "boundingRect") and callable(source.boundingRect):
            rect = source.boundingRect()
            return float(max(rect.width(), 1.0)), float(max(rect.height(), 1.0))
        return None

    @staticmethod
    def _current_font_size(source) -> Optional[float]:
        widget = source if isinstance(source, QWidget) else None
        if widget is None and hasattr(source, "scene") and callable(source.scene):
            scene = source.scene()
            views = scene.views() if scene is not None else []
            widget = views[0] if views else None
        return float(widget.font().pointSizeF()) if isinstance(widget, QWidget) else None

    @staticmethod
    def _is_pyqtgraph_source(source) -> bool:
        return isinstance(source, (pg.PlotWidget, pg.PlotItem, pg.GraphicsLayoutWidget, pg.GraphicsLayout))

    @staticmethod
    def _plot_item_for_source(source):
        if isinstance(source, pg.PlotWidget):
            return source.getPlotItem()
        if isinstance(source, pg.PlotItem):
            return source
        return None

    @classmethod
    def _capture_plot_style_state(cls, source):
        plot_item = cls._plot_item_for_source(source)
        if plot_item is None:
            return None
        grid_x = False
        grid_y = False
        grid_alpha = 0
        if hasattr(plot_item, "ctrl"):
            grid_x = bool(plot_item.ctrl.xGridCheck.isChecked())
            grid_y = bool(plot_item.ctrl.yGridCheck.isChecked())
            grid_alpha = int(plot_item.ctrl.gridAlphaSlider.value())
        axes = {}
        for axis_name in ("bottom", "left", "top", "right"):
            axis = plot_item.getAxis(axis_name)
            axes[axis_name] = {
                "visible": axis.isVisible(),
                "grid": axis.grid,
                "explicit_ticks": [list(level) for level in axis._tickLevels] if getattr(axis, "_tickLevels", None) is not None else None,
                "tick_length": int(axis.style.get("tickLength", -5)),
                "max_tick_level": int(axis.style.get("maxTickLevel", 2)),
                "show_values": bool(axis.style.get("showValues", True)),
                "pen": QPen(axis.pen()),
                "text_pen": QPen(axis.textPen()),
                "tick_pen": QPen(axis.tickPen()),
            }
        items = []
        for item in getattr(plot_item, "items", []):
            item_state = {"item": item}
            if hasattr(item, "opts") and isinstance(getattr(item, "opts"), dict) and "pen" in item.opts:
                pen = item.opts.get("pen")
                item_state["pen"] = QPen(pen) if isinstance(pen, QPen) else pen
                if "symbolSize" in item.opts:
                    item_state["symbol_size"] = float(item.opts.get("symbolSize") or 0.0)
                if "size" in item.opts:
                    item_state["scatter_size"] = float(item.opts.get("size") or 0.0)
            elif hasattr(item, "pen") and callable(item.pen):
                try:
                    pen = item.pen()
                    item_state["pen"] = QPen(pen) if isinstance(pen, QPen) else pen
                except Exception:
                    pass
            if len(item_state) > 1:
                items.append(item_state)
        return {
            "grid_x": grid_x,
            "grid_y": grid_y,
            "grid_alpha": grid_alpha,
            "axes": axes,
            "items": items,
            "border": QPen(plot_item.vb.border) if isinstance(plot_item.vb.border, QPen) else plot_item.vb.border,
        }

    @classmethod
    def _plot_border_pen(cls, theme_mode: str, source) -> QPen:
        bg = cls._export_background(theme_mode, source)
        color = QColor("#cbd5e1") if bg.lightness() < 128 else QColor("#475569")
        return pg.mkPen(color=color, width=1.1)

    @staticmethod
    def _pen_with_width(pen, width: float):
        if not isinstance(pen, QPen):
            return pen
        new_pen = QPen(pen)
        new_pen.setWidthF(float(width))
        return new_pen

    @staticmethod
    def _tick_level_count(tick_visibility: str) -> int:
        return {"major_minor": 1, "major": 0, "none": 0}.get(str(tick_visibility), 1)

    @staticmethod
    def _tick_length(direction: str, tick_visibility: str, default_length: float) -> float:
        if str(tick_visibility) == "none":
            return 0
        magnitude = max(abs(float(default_length)), 5.0)
        return int(round(float(magnitude) if str(direction) == "outer" else -float(magnitude)))

    @classmethod
    def _apply_export_tick_labels(cls, plot_item, settings: ClipboardExportSettings) -> None:
        if str(settings.tick_visibility) == "none":
            for axis_name in ("bottom", "left"):
                plot_item.getAxis(axis_name).setTicks(None)
            return
        vb_rect = plot_item.vb.sceneBoundingRect()
        axis_specs = {
            "bottom": (plot_item.getAxis("bottom"), tuple(plot_item.vb.viewRange()[0]), float(max(vb_rect.width(), 1.0))),
            "left": (plot_item.getAxis("left"), tuple(plot_item.vb.viewRange()[1]), float(max(vb_rect.height(), 1.0))),
        }
        visible_levels = max(cls._tick_level_count(settings.tick_visibility) + 1, 1)
        for axis_name, (axis, view_range, axis_size) in axis_specs.items():
            levels = []
            for spacing, values in list(axis.tickValues(view_range[0], view_range[1], axis_size))[:visible_levels]:
                labels = axis.tickStrings(values, 1.0, spacing)
                levels.append([(float(value), str(label)) for value, label in zip(values, labels)])
            axis.setTicks(levels or None)

    @classmethod
    def _apply_axis_tick_style(cls, axis, settings: ClipboardExportSettings, default_length: float) -> None:
        no_ticks = str(settings.tick_visibility) == "none"
        requested_length = float(settings.tick_length)
        base_length = requested_length if requested_length > 0.0 else default_length
        axis.setStyle(
            maxTickLevel=cls._tick_level_count(settings.tick_visibility),
            tickLength=0 if no_ticks else cls._tick_length(settings.tick_direction, settings.tick_visibility, base_length),
        )
        if no_ticks:
            axis.setTickPen(QPen(Qt.PenStyle.NoPen))

    @classmethod
    def _apply_plot_style_override(cls, source, settings: ClipboardExportSettings, *, use_defaults: bool = False) -> None:
        if use_defaults:
            return
        plot_item = cls._plot_item_for_source(source)
        if plot_item is None:
            return
        plot_item.showGrid(
            x=bool(settings.grid_x),
            y=bool(settings.grid_y),
            alpha=min(max(float(settings.grid_alpha), 0.0), 1.0),
        )
        bottom_axis = plot_item.getAxis("bottom")
        left_axis = plot_item.getAxis("left")
        top_axis = plot_item.getAxis("top")
        right_axis = plot_item.getAxis("right")
        axis_line_width = float(settings.axis_line_width)
        for axis in (bottom_axis, left_axis):
            base_pen = axis.pen()
            if axis_line_width > 0.0:
                base_pen = cls._pen_with_width(base_pen, axis_line_width)
            axis.setPen(base_pen)
            axis.setTickPen(QPen(base_pen))
        cls._apply_axis_tick_style(bottom_axis, settings, bottom_axis.style.get("tickLength", -5))
        cls._apply_axis_tick_style(left_axis, settings, left_axis.style.get("tickLength", -5))

        frame_pen = QPen(bottom_axis.pen())
        frame_text_pen = QPen(bottom_axis.textPen())
        for axis in (top_axis, right_axis):
            axis.setPen(frame_pen)
            axis.setTextPen(frame_text_pen)
            axis.setTickPen(QPen(Qt.PenStyle.NoPen))
            axis.setStyle(showValues=False, tickLength=0, maxTickLevel=0)
        plot_item.showAxis("top", bool(settings.show_bounding_box))
        plot_item.showAxis("right", bool(settings.show_bounding_box))
        plot_item.vb.setBorder(None)
        cls._apply_export_tick_labels(plot_item, settings)
        plot_line_width = float(settings.plot_line_width)
        marker_size = float(settings.marker_size)
        if plot_line_width > 0.0:
            for item in getattr(plot_item, "items", []):
                if hasattr(item, "opts") and isinstance(getattr(item, "opts"), dict) and isinstance(item.opts.get("pen"), QPen):
                    new_pen = cls._pen_with_width(item.opts["pen"], plot_line_width)
                    if hasattr(item, "setPen"):
                        item.setPen(new_pen)
                    elif hasattr(item, "setOpts"):
                        item.setOpts(pen=new_pen)
        if marker_size > 0.0:
            for item in getattr(plot_item, "items", []):
                if hasattr(item, "opts") and isinstance(getattr(item, "opts"), dict):
                    if item.opts.get("symbol") is not None and hasattr(item, "setSymbolSize"):
                        item.setSymbolSize(marker_size)
                    elif "size" in item.opts and hasattr(item, "setSize"):
                        item.setSize(marker_size)

    @classmethod
    def _restore_plot_style_state(cls, source, state) -> None:
        if state is None:
            return
        plot_item = cls._plot_item_for_source(source)
        if plot_item is None:
            return
        plot_item.showGrid(
            x=bool(state.get("grid_x", False)),
            y=bool(state.get("grid_y", False)),
            alpha=float(state.get("grid_alpha", 0)) / 255.0,
        )
        for axis_name, axis_state in (state.get("axes") or {}).items():
            axis = plot_item.getAxis(axis_name)
            axis.setPen(axis_state["pen"])
            axis.setTextPen(axis_state["text_pen"])
            axis.setTickPen(axis_state["tick_pen"])
            axis.setTicks(axis_state.get("explicit_ticks"))
            axis.setStyle(
                tickLength=int(axis_state.get("tick_length", -5)),
                maxTickLevel=int(axis_state.get("max_tick_level", 2)),
                showValues=bool(axis_state.get("show_values", True)),
            )
            axis.setGrid(axis_state.get("grid", False))
            plot_item.showAxis(axis_name, bool(axis_state["visible"]))
        for item_state in state.get("items", []):
            item = item_state.get("item")
            pen = item_state.get("pen")
            if item is None:
                continue
            if hasattr(item, "setPen"):
                try:
                    item.setPen(pen)
                except Exception:
                    pass
            if hasattr(item, "setSymbolSize") and "symbol_size" in item_state:
                try:
                    item.setSymbolSize(float(item_state["symbol_size"]))
                except Exception:
                    pass
            if hasattr(item, "setSize") and "scatter_size" in item_state:
                try:
                    item.setSize(float(item_state["scatter_size"]))
                except Exception:
                    pass
            if hasattr(item, "setOpts") and pen is not None:
                try:
                    item.setOpts(pen=pen)
                except Exception:
                    pass
        plot_item.vb.setBorder(state.get("border"))

    @staticmethod
    def _render_widget_svg_bytes(widget: QWidget, width_px: int, height_px: int, background: QColor, *, dpi: int) -> bytes:
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        generator = QSvgGenerator()
        generator.setOutputDevice(buffer)
        generator.setSize(QSize(width_px, height_px))
        generator.setViewBox(QRectF(0.0, 0.0, float(width_px), float(height_px)))
        generator.setResolution(int(dpi))

        painter = QPainter(generator)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.fillRect(QRectF(0.0, 0.0, float(width_px), float(height_px)), background)
        scale = min(width_px / max(widget.width(), 1), height_px / max(widget.height(), 1))
        render_w = max(int(round(widget.width() * scale)), 1)
        render_h = max(int(round(widget.height() * scale)), 1)
        x_off = max((width_px - render_w) / 2.0, 0.0)
        y_off = max((height_px - render_h) / 2.0, 0.0)
        painter.translate(x_off, y_off)
        painter.scale(scale, scale)
        widget.render(painter)
        painter.end()
        buffer.close()
        return bytes(data)

    @staticmethod
    def _render_graphics_scene_svg_bytes(source, width_px: int, height_px: int, background: QColor, *, dpi: int) -> bytes:
        scene = source.scene() if hasattr(source, "scene") and callable(source.scene) else None
        if scene is None:
            return b""
        if hasattr(source, "sceneBoundingRect") and callable(source.sceneBoundingRect):
            source_rect = source.sceneBoundingRect()
        elif hasattr(scene, "sceneRect") and callable(scene.sceneRect):
            source_rect = scene.sceneRect()
        else:
            source_rect = QRectF(0.0, 0.0, float(width_px), float(height_px))
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        generator = QSvgGenerator()
        generator.setOutputDevice(buffer)
        generator.setSize(QSize(width_px, height_px))
        generator.setViewBox(QRectF(0.0, 0.0, float(width_px), float(height_px)))
        generator.setResolution(int(dpi))

        painter = QPainter(generator)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.fillRect(QRectF(0.0, 0.0, float(width_px), float(height_px)), background)
        scene.render(painter, QRectF(0.0, 0.0, float(width_px), float(height_px)), source_rect)
        painter.end()
        buffer.close()
        return bytes(data)

    @staticmethod
    def _polyline_point_tokens(points_text: str) -> list[str]:
        return [token for token in str(points_text or "").replace("\n", " ").split(" ") if token]

    @staticmethod
    def _polyline_signature(element) -> tuple:
        attrib = dict(element.attrib)
        attrib.pop("points", None)
        return element.tag, tuple(sorted(attrib.items()))

    @staticmethod
    def _parse_svg_points(points_text: str) -> list[tuple[float, float]]:
        points = []
        for token in ClipboardExportManager._polyline_point_tokens(points_text):
            try:
                x_str, y_str = token.split(",", 1)
                points.append((float(x_str), float(y_str)))
            except Exception:
                continue
        return points

    @staticmethod
    def _format_svg_points(points: list[tuple[float, float]]) -> str:
        return " ".join(f"{x:g},{y:g}" for x, y in points) + (" " if points else "")

    @staticmethod
    def _svg_group_has_text(element) -> bool:
        return any(node.tag.endswith("text") for node in element.iter())

    @classmethod
    def _sanitize_svg_axis_ticks(cls, svg_bytes: bytes, settings: ClipboardExportSettings) -> bytes:
        try:
            root = ET.fromstring(svg_bytes)
        except ET.ParseError:
            return svg_bytes
        ET.register_namespace("", "http://www.w3.org/2000/svg")

        view_box = str(root.attrib.get("viewBox", "0 0 0 0")).split()
        if len(view_box) != 4:
            return svg_bytes
        try:
            view_width = float(view_box[2])
            view_height = float(view_box[3])
        except Exception:
            return svg_bytes

        max_tick_extent = max(min(view_width, view_height) * 0.05, 24.0)
        changed = False

        def axis_meta(axis_group):
            first_child = next((child for child in list(axis_group) if child.tag.endswith("g")), None)
            if first_child is None:
                return None
            axis_polyline = next((node for node in list(first_child) if node.tag.endswith("polyline")), None)
            if axis_polyline is None:
                return None
            points = cls._parse_svg_points(axis_polyline.attrib.get("points", ""))
            if len(points) != 2:
                return None
            (x1, y1), (x2, y2) = points
            if abs(y1 - y2) <= 1e-6:
                side = "top" if y1 < (view_height / 2.0) else "bottom"
                return {"orientation": "horizontal", "side": side, "axis_value": y1}
            if abs(x1 - x2) <= 1e-6:
                side = "left" if x1 < (view_width / 2.0) else "right"
                return {"orientation": "vertical", "side": side, "axis_value": x1, "axis_polyline": axis_polyline}
            return None

        for axis_group in root.iter():
            if not axis_group.tag.endswith("g"):
                continue
            if not str(axis_group.attrib.get("id", "")).startswith("AxisItem_"):
                continue
            meta = axis_meta(axis_group)
            if meta is None:
                continue

            side = meta["side"]
            orientation = meta["orientation"]
            axis_value = float(meta["axis_value"])
            axis_polyline = meta.get("axis_polyline")

            if side in {"top", "right"}:
                for child in list(axis_group)[1:]:
                    if cls._svg_group_has_text(child):
                        continue
                    if any(node.tag.endswith("polyline") or node.tag.endswith("path") for node in child.iter()):
                        axis_group.remove(child)
                        changed = True
                continue

            outward = str(settings.tick_direction) == "outer"
            for child in list(axis_group):
                if not child.tag.endswith("g"):
                    continue
                if cls._svg_group_has_text(child):
                    continue
                for polyline in child.iter():
                    if not polyline.tag.endswith("polyline"):
                        continue
                    if polyline is axis_polyline:
                        continue
                    points = cls._parse_svg_points(polyline.attrib.get("points", ""))
                    if len(points) != 2:
                        continue
                    (x1, y1), (x2, y2) = points
                    if orientation == "horizontal":
                        if abs(x1 - x2) > 1e-6 or min(abs(y1 - axis_value), abs(y2 - axis_value)) > max_tick_extent:
                            continue
                        axis_end = axis_value
                        distal_end = max(y1, y2) if outward else min(y1, y2)
                        if abs(distal_end - axis_end) > max_tick_extent:
                            continue
                        new_points = [(x1, axis_end), (x2, distal_end)]
                    else:
                        if abs(y1 - y2) > 1e-6 or min(abs(x1 - axis_value), abs(x2 - axis_value)) > max_tick_extent:
                            continue
                        axis_end = axis_value
                        distal_end = min(x1, x2) if outward else max(x1, x2)
                        if abs(distal_end - axis_end) > max_tick_extent:
                            continue
                        new_points = [(axis_end, y1), (distal_end, y2)]
                    polyline.attrib["points"] = cls._format_svg_points(new_points)
                    changed = True

        if not changed:
            return svg_bytes
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    @classmethod
    def _merge_svg_polylines(cls, svg_bytes: bytes) -> bytes:
        try:
            root = ET.fromstring(svg_bytes)
        except ET.ParseError:
            return svg_bytes
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        changed = False

        def merge_children(parent):
            nonlocal changed
            children = list(parent)
            merged_children = []
            idx = 0
            while idx < len(children):
                child = children[idx]
                merge_children(child)
                if child.tag.endswith("polyline"):
                    signature = cls._polyline_signature(child)
                    tokens = cls._polyline_point_tokens(child.attrib.get("points", ""))
                    next_idx = idx + 1
                    while next_idx < len(children):
                        sibling = children[next_idx]
                        if not sibling.tag.endswith("polyline") or cls._polyline_signature(sibling) != signature:
                            break
                        sibling_tokens = cls._polyline_point_tokens(sibling.attrib.get("points", ""))
                        if len(tokens) < 2 or len(sibling_tokens) < 2 or tokens[-1] != sibling_tokens[0]:
                            break
                        tokens.extend(sibling_tokens[1:])
                        next_idx += 1
                        changed = True
                    if tokens:
                        child.attrib["points"] = " ".join(tokens) + " "
                    merged_children.append(child)
                    idx = next_idx
                    continue
                merged_children.append(child)
                idx += 1
            if merged_children != children:
                parent[:] = merged_children

        merge_children(root)
        if not changed:
            return svg_bytes
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    @classmethod
    def _render_pyqtgraph_png_mime(
        cls,
        source,
        settings: ClipboardExportSettings,
        *,
        legend_entries: Optional[list[dict]] = None,
        use_defaults: bool = False,
    ) -> Optional[QMimeData]:
        width_px, height_px = cls._source_pixels(source) if use_defaults else cls._target_pixels(settings)
        exporter = ImageExporter(source.getPlotItem() if isinstance(source, pg.PlotWidget) else source)
        params = exporter.parameters()
        params["width"] = width_px
        params["height"] = height_px
        params["antialias"] = True
        params["background"] = cls._export_background("gui" if use_defaults else settings.theme_mode, source)
        plot_image = exporter.export(toBytes=True)
        image = cls._compose_plot_and_legend_image(plot_image, legend_entries or [], settings, use_defaults=use_defaults)

        array = QByteArray()
        buffer = QBuffer(array)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, b"PNG")
        buffer.close()

        mime = QMimeData()
        mime.setData("image/png", array)
        mime.setImageData(image)
        return mime

    @classmethod
    def _render_pyqtgraph_svg_mime(
        cls,
        source,
        settings: ClipboardExportSettings,
        *,
        legend_entries: Optional[list[dict]] = None,
        use_defaults: bool = False,
    ) -> Optional[QMimeData]:
        width_px, height_px = cls._source_pixels(source) if use_defaults else cls._target_pixels(settings)
        theme_mode = "gui" if use_defaults else settings.theme_mode
        background = cls._export_background(theme_mode, source)
        exporter = SVGExporter(source.getPlotItem() if isinstance(source, pg.PlotWidget) else source)
        params = exporter.parameters()
        params["width"] = float(width_px)
        params["height"] = float(height_px)
        params["background"] = background
        plot_svg = exporter.export(toBytes=True)
        plot_svg = cls._merge_svg_polylines(plot_svg)
        plot_svg = cls._sanitize_svg_axis_ticks(plot_svg, settings)
        if legend_entries:
            data = cls._compose_svg_with_legend(plot_svg, legend_entries, settings, width_px, height_px, use_defaults=use_defaults)
        else:
            data = plot_svg
        mime = QMimeData()
        mime.setData("image/svg+xml", QByteArray(data))
        return mime

    @staticmethod
    def _export_background(theme_mode: str, source) -> QColor:
        if theme_mode == "light":
            return QColor("#ffffff")
        if theme_mode == "dark":
            return QColor("#0a0a0a")
        widget = source if isinstance(source, QWidget) else None
        if widget is None and hasattr(source, "scene") and callable(source.scene):
            scene = source.scene()
            views = scene.views() if scene is not None else []
            widget = views[0] if views else None
        if isinstance(widget, QWidget):
            return widget.palette().color(QPalette.ColorRole.Window)
        return QColor("#ffffff")

    @staticmethod
    def _source_pixels(source) -> tuple[int, int]:
        size = ClipboardExportManager._source_size(source)
        if size is None:
            return 1, 1
        return max(int(round(size[0])), 1), max(int(round(size[1])), 1)

    @staticmethod
    def _refresh_source(source) -> None:
        if isinstance(source, QWidget):
            source.updateGeometry()
            source.repaint()
        app = QGuiApplication.instance()
        if app is not None:
            app.processEvents()

    @classmethod
    def _capture_font_state(cls, source):
        if source is None:
            return None
        if cls._is_pyqtgraph_source(source):
            plot_item = source.getPlotItem() if isinstance(source, pg.PlotWidget) else source
            state = []
            for axis_name in ("bottom", "left", "right", "top"):
                axis = plot_item.getAxis(axis_name) if hasattr(plot_item, "getAxis") else None
                if axis is None:
                    continue
                tick_font = axis.style.get("tickFont")
                state.append(
                    (
                        axis,
                        QFont(tick_font) if isinstance(tick_font, QFont) else None,
                        axis.labelStyle.copy(),
                    )
                )
            return ("pyqtgraph", state)
        if isinstance(source, QWidget):
            return ("widget", QFont(source.font()))
        return None

    @classmethod
    def _apply_font_override(cls, source, font_size_pt: float) -> None:
        if source is None or font_size_pt <= 0.0:
            return
        if cls._is_pyqtgraph_source(source):
            plot_item = source.getPlotItem() if isinstance(source, pg.PlotWidget) else source
            for axis_name in ("bottom", "left", "right", "top"):
                axis = plot_item.getAxis(axis_name) if hasattr(plot_item, "getAxis") else None
                if axis is None:
                    continue
                tick_font = QFont()
                tick_font.setPointSizeF(font_size_pt)
                axis.setStyle(tickFont=tick_font)
                label_style = axis.labelStyle.copy()
                label_style["font-size"] = f"{font_size_pt:.1f}pt"
                axis.setLabel(
                    text=axis.labelText or None,
                    units=axis.labelUnits or None,
                    **label_style,
                )
            return
        if isinstance(source, QWidget):
            font = QFont(source.font())
            font.setPointSizeF(font_size_pt)
            source.setFont(font)

    @staticmethod
    def _restore_font_state(source, state) -> None:
        if source is None or state is None:
            return
        kind, payload = state
        if kind == "pyqtgraph":
            for axis, tick_font, label_style in payload:
                axis.setStyle(tickFont=tick_font)
                axis.setLabel(text=axis.labelText or None, units=axis.labelUnits or None, **label_style)
            return
        if kind == "widget":
            source.setFont(payload)

    @staticmethod
    def _capture_size_state(source):
        if isinstance(source, QWidget):
            return source.size()
        return None

    @staticmethod
    def _restore_size_state(source, state) -> None:
        if source is None or state is None or not isinstance(source, QWidget):
            return
        source.resize(state)
        source.updateGeometry()

    @classmethod
    def _prepare_plot_source(cls, source, settings: ClipboardExportSettings, *, use_defaults: bool = False) -> None:
        if not isinstance(source, QWidget) or use_defaults:
            return
        width_px, height_px = cls._target_pixels(settings)
        app = QGuiApplication.instance()
        for _ in range(3):
            source.updateGeometry()
            source.repaint()
            if app is not None:
                app.processEvents()
            plot_item = source.getPlotItem() if isinstance(source, pg.PlotWidget) else source if isinstance(source, pg.PlotItem) else None
            if plot_item is None:
                source.resize(width_px, height_px)
                continue
            vb_rect = plot_item.vb.sceneBoundingRect()
            scene_rect = plot_item.sceneBoundingRect()
            extra_w = max(scene_rect.width() - vb_rect.width(), 0.0)
            extra_h = max(scene_rect.height() - vb_rect.height(), 0.0)
            target_total_w = int(round(width_px + extra_w))
            target_total_h = int(round(height_px + extra_h))
            source.resize(max(target_total_w, 1), max(target_total_h, 1))

    @classmethod
    def _render_static_legend_image(
        cls,
        legend_entries: list[dict],
        settings: ClipboardExportSettings,
        *,
        use_defaults: bool = False,
    ) -> Optional[QImage]:
        visible_entries = [entry for entry in legend_entries if entry.get("visible", True)]
        if not visible_entries:
            return None
        font_pt = float(settings.font_size_pt if (not use_defaults and settings.font_size_pt > 0.0) else 10.0)
        # Keep legend typography screen-like; export DPI should not inflate the legend
        # into something larger than the plot itself.
        scale = 1.0
        font = QFont()
        font.setPointSizeF(font_pt * scale)
        title_font = QFont(font)
        title_font.setBold(True)
        title_font.setPointSizeF(font.pointSizeF() + 1.0)
        metrics_probe = QImage(1, 1, QImage.Format.Format_ARGB32)
        painter = QPainter(metrics_probe)
        painter.setFont(font)
        fm = painter.fontMetrics()
        painter.setFont(title_font)
        title_fm = painter.fontMetrics()
        painter.end()
        title = "Legend"
        swatch_w = 18
        swatch_gap = 10
        margin = 12
        row_gap = 6
        text_width = max([fm.horizontalAdvance(str(entry.get("label", ""))) for entry in visible_entries] + [title_fm.horizontalAdvance(title)])
        width = margin * 2 + swatch_w + swatch_gap + text_width
        row_h = max(fm.height(), swatch_w)
        height = margin * 2 + title_fm.height() + row_gap + len(visible_entries) * row_h + max(len(visible_entries) - 1, 0) * row_gap
        bg = cls._export_background("gui" if use_defaults else settings.theme_mode, None)
        text_color = QColor("#0f172a") if bg.lightness() > 128 else QColor("#e5eefb")
        muted_color = QColor("#64748b") if bg.lightness() > 128 else QColor("#94a3b8")
        image = QImage(max(width, 1), max(height, 1), QImage.Format.Format_ARGB32)
        image.fill(bg)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(title_font)
        painter.setPen(text_color)
        y = margin + title_fm.ascent()
        painter.drawText(margin, y, title)
        y = margin + title_fm.height() + row_gap
        painter.setFont(font)
        for entry in visible_entries:
            label = str(entry.get("label", ""))
            color = QColor(str(entry.get("color", "#0f172a")))
            style = str(entry.get("style", "line"))
            sample_y = y + row_h // 2
            painter.setPen(pg.mkPen(color=color, width=2, style=Qt.PenStyle.DashLine if style == "dash" else Qt.PenStyle.SolidLine))
            x0 = margin
            x1 = margin + swatch_w
            if style in {"line", "dash"}:
                painter.drawLine(x0, sample_y, x1, sample_y)
            elif style == "marker":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                radius = 3
                painter.drawEllipse(int(round((x0 + x1) / 2 - radius)), int(round(sample_y - radius)), radius * 2, radius * 2)
            elif style == "line+marker":
                painter.drawLine(x0, sample_y, x1, sample_y)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                radius = 3
                painter.drawEllipse(int(round((x0 + x1) / 2 - radius)), int(round(sample_y - radius)), radius * 2, radius * 2)
                painter.setPen(pg.mkPen(color=color, width=2))
            painter.setPen(text_color if style != "muted" else muted_color)
            painter.drawText(margin + swatch_w + swatch_gap, y + fm.ascent(), label)
            y += row_h + row_gap
        painter.end()
        return image

    @classmethod
    def _compose_plot_and_legend_image(
        cls,
        plot_image: QImage,
        legend_entries: list[dict],
        settings: ClipboardExportSettings,
        *,
        use_defaults: bool = False,
    ) -> QImage:
        legend_image = cls._render_static_legend_image(legend_entries, settings, use_defaults=use_defaults)
        if legend_image is None:
            return plot_image
        gap = 24
        bg = cls._export_background("gui" if use_defaults else settings.theme_mode, None)
        total_width = plot_image.width() + gap + legend_image.width()
        total_height = max(plot_image.height(), legend_image.height())
        composite = QImage(total_width, total_height, QImage.Format.Format_ARGB32)
        composite.fill(bg)
        painter = QPainter(composite)
        plot_y = 0
        legend_y = 0
        painter.drawImage(0, plot_y, plot_image)
        painter.drawImage(plot_image.width() + gap, legend_y, legend_image)
        painter.end()
        return composite

    @classmethod
    def _render_static_legend_svg(
        cls,
        legend_entries: list[dict],
        settings: ClipboardExportSettings,
        *,
        use_defaults: bool = False,
    ) -> tuple[str, int, int]:
        visible_entries = [entry for entry in legend_entries if entry.get("visible", True)]
        if not visible_entries:
            return "", 0, 0
        font_pt = float(settings.font_size_pt if (not use_defaults and settings.font_size_pt > 0.0) else 10.0)
        font = QFont()
        font.setPointSizeF(font_pt)
        title_font = QFont(font)
        title_font.setBold(True)
        title_font.setPointSizeF(font.pointSizeF() + 1.0)
        metrics_probe = QImage(1, 1, QImage.Format.Format_ARGB32)
        painter = QPainter(metrics_probe)
        painter.setFont(font)
        fm = painter.fontMetrics()
        painter.setFont(title_font)
        title_fm = painter.fontMetrics()
        painter.end()

        title = "Legend"
        swatch_w = 18
        swatch_gap = 10
        margin = 12
        row_gap = 6
        text_width = max([fm.horizontalAdvance(str(entry.get("label", ""))) for entry in visible_entries] + [title_fm.horizontalAdvance(title)])
        width = margin * 2 + swatch_w + swatch_gap + text_width
        row_h = max(fm.height(), swatch_w)
        height = margin * 2 + title_fm.height() + row_gap + len(visible_entries) * row_h + max(len(visible_entries) - 1, 0) * row_gap
        bg = cls._export_background("gui" if use_defaults else settings.theme_mode, None)
        text_color = "#0f172a" if bg.lightness() > 128 else "#e5eefb"
        muted_color = "#64748b" if bg.lightness() > 128 else "#94a3b8"
        border = "#cbd5e1" if bg.lightness() > 128 else "#334155"

        lines = [
            f'<g transform="translate(0,0)">',
            f'<rect x="0" y="0" width="{width}" height="{height}" rx="8" ry="8" fill="{bg.name()}" stroke="{border}" stroke-width="1"/>',
            f'<text x="{margin}" y="{margin + title_fm.ascent()}" fill="{text_color}" font-family="Sans Serif" font-size="{title_font.pointSizeF():.1f}" font-weight="700">{title}</text>',
        ]
        y = margin + title_fm.height() + row_gap
        for entry in visible_entries:
            label = str(entry.get("label", ""))
            color = QColor(str(entry.get("color", "#0f172a"))).name()
            style = str(entry.get("style", "line"))
            sample_y = y + row_h / 2.0
            x0 = margin
            x1 = margin + swatch_w
            dash_attr = ' stroke-dasharray="6 4"' if style == "dash" else ""
            if style in {"line", "dash", "line+marker"}:
                lines.append(
                    f'<line x1="{x0}" y1="{sample_y:.2f}" x2="{x1}" y2="{sample_y:.2f}" '
                    f'stroke="{color}" stroke-width="2"{dash_attr}/>'
                )
            if style in {"marker", "line+marker"}:
                lines.append(
                    f'<circle cx="{(x0 + x1) / 2.0:.2f}" cy="{sample_y:.2f}" r="3" fill="{color}"/>'
                )
            label_color = muted_color if style == "muted" else text_color
            text_y = y + fm.ascent()
            lines.append(
                f'<text x="{margin + swatch_w + swatch_gap}" y="{text_y}" fill="{label_color}" '
                f'font-family="Sans Serif" font-size="{font.pointSizeF():.1f}">{label}</text>'
            )
            y += row_h + row_gap
        lines.append("</g>")
        return "".join(lines), width, height

    @classmethod
    def _compose_svg_with_legend(
        cls,
        plot_svg: bytes,
        legend_entries: list[dict],
        settings: ClipboardExportSettings,
        plot_width_px: int,
        plot_height_px: int,
        *,
        use_defaults: bool = False,
    ) -> bytes:
        legend_svg, legend_width, legend_height = cls._render_static_legend_svg(
            legend_entries,
            settings,
            use_defaults=use_defaults,
        )
        if not legend_svg:
            return plot_svg
        gap = 24
        total_width = plot_width_px + gap + legend_width
        total_height = max(plot_height_px, legend_height)
        plot_svg_text = plot_svg.decode("utf-8")
        plot_svg_body_start = plot_svg_text.find(">", plot_svg_text.find("<svg")) + 1
        plot_svg_body_end = plot_svg_text.rfind("</svg>")
        plot_body = plot_svg_text[plot_svg_body_start:plot_svg_body_end]
        bg = cls._export_background("gui" if use_defaults else settings.theme_mode, None).name()
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="{total_height}" '
            f'viewBox="0 0 {total_width} {total_height}">'
            f'<rect x="0" y="0" width="{total_width}" height="{total_height}" fill="{bg}"/>'
            f'<g transform="translate(0,0)">{plot_body}</g>'
            f'<g transform="translate({plot_width_px + gap},0)">{legend_svg}</g>'
            f"</svg>"
        )
        return svg.encode("utf-8")

    @classmethod
    def _render_png_mime(cls, widget: QWidget, settings: ClipboardExportSettings) -> Optional[QMimeData]:
        width_px, height_px = cls._target_pixels(settings)
        image = QImage(width_px, height_px, QImage.Format.Format_ARGB32)
        image.fill(cls._export_background(settings.theme_mode, widget))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        scale = min(width_px / max(widget.width(), 1), height_px / max(widget.height(), 1))
        render_w = max(int(round(widget.width() * scale)), 1)
        render_h = max(int(round(widget.height() * scale)), 1)
        x_off = max((width_px - render_w) // 2, 0)
        y_off = max((height_px - render_h) // 2, 0)
        painter.translate(x_off, y_off)
        painter.scale(scale, scale)
        widget.render(painter)
        painter.end()

        array = QByteArray()
        buffer = QBuffer(array)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, b"PNG")
        buffer.close()

        mime = QMimeData()
        mime.setData("image/png", array)
        mime.setImageData(image)
        return mime

    @classmethod
    def _render_svg_mime(cls, widget: QWidget, settings: ClipboardExportSettings) -> Optional[QMimeData]:
        width_px, height_px = cls._target_pixels(settings)
        data = cls._render_widget_svg_bytes(
            widget,
            width_px,
            height_px,
            cls._export_background(settings.theme_mode, widget),
            dpi=settings.dpi,
        )
        data = cls._merge_svg_polylines(data)

        mime = QMimeData()
        mime.setData("image/svg+xml", data)
        return mime
