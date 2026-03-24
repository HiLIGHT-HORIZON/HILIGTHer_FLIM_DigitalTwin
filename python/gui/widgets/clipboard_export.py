from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Dict, Optional
import base64

import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter, SVGExporter
from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, QMimeData, Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPalette, QPixmap
from PyQt6.QtSvg import QSvgGenerator
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


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


class ClipboardExportDialog(QDialog):
    def __init__(
        self,
        settings: ClipboardExportSettings,
        parent: Optional[QWidget] = None,
        *,
        source_size: Optional[tuple[float, float]] = None,
        current_font_pt: Optional[float] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Clipboard Export Settings")
        self._syncing = False
        self._result_settings = replace(settings)
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

        self.combo_theme = QComboBox()
        self.combo_theme.addItem("GUI choice", "gui")
        self.combo_theme.addItem("Light", "light")
        self.combo_theme.addItem("Dark", "dark")
        self.combo_theme.setCurrentIndex(max(self.combo_theme.findData(settings.theme_mode), 0))
        form.addRow("Export theme:", self.combo_theme)

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
        self._populate_default_values()
        self._update_controls_enabled()
        self._update_lock_state()

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
            self.combo_theme,
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
            theme_mode=str(self.combo_theme.currentData()),
            fmt=str(self.combo_format.currentData()),
        )


class ClipboardExportManager:
    _global_settings = ClipboardExportSettings()
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
            parent=parent,
            source_size=cls._source_size(export_source),
            current_font_pt=cls._current_font_size(export_source),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.export_settings()
        if dialog.chk_apply_all.isChecked():
            cls._global_settings = replace(settings)
            cls._per_graph_settings.clear()
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
        if override_theme and hasattr(theme_owner, "set_theme"):
            theme_owner.set_theme(override_theme)
        font_state = cls._capture_font_state(source)
        size_state = cls._capture_size_state(source)
        font_size_pt = 0.0 if use_defaults else settings.font_size_pt
        cls._apply_font_override(source, font_size_pt)
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
            cls._restore_font_state(source, font_state)
            if override_theme and original_theme is not None and hasattr(theme_owner, "set_theme"):
                theme_owner.set_theme(original_theme)

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
        exporter = SVGExporter(source.getPlotItem() if isinstance(source, pg.PlotWidget) else source)
        params = exporter.parameters()
        params["width"] = float(width_px)
        params["height"] = float(height_px)
        params["background"] = cls._export_background("gui" if use_defaults else settings.theme_mode, source)
        plot_svg = exporter.export(toBytes=True)
        if legend_entries:
            legend_image = cls._render_static_legend_image(legend_entries, settings, use_defaults=use_defaults)
            data = cls._compose_svg_with_legend(plot_svg, legend_image, settings, width_px, height_px, use_defaults=use_defaults)
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
    def _compose_svg_with_legend(
        cls,
        plot_svg: bytes,
        legend_image: Optional[QImage],
        settings: ClipboardExportSettings,
        plot_width_px: int,
        plot_height_px: int,
        *,
        use_defaults: bool = False,
    ) -> bytes:
        if legend_image is None:
            return plot_svg
        gap = 24
        total_width = plot_width_px + gap + legend_image.width()
        total_height = max(plot_height_px, legend_image.height())
        plot_svg_text = plot_svg.decode("utf-8")
        plot_svg_body_start = plot_svg_text.find(">", plot_svg_text.find("<svg")) + 1
        plot_svg_body_end = plot_svg_text.rfind("</svg>")
        plot_body = plot_svg_text[plot_svg_body_start:plot_svg_body_end]
        legend_png = QByteArray()
        buffer = QBuffer(legend_png)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        legend_image.save(buffer, b"PNG")
        buffer.close()
        legend_b64 = base64.b64encode(bytes(legend_png)).decode("ascii")
        bg = cls._export_background("gui" if use_defaults else settings.theme_mode, None).name()
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="{total_height}" '
            f'viewBox="0 0 {total_width} {total_height}">'
            f'<rect x="0" y="0" width="{total_width}" height="{total_height}" fill="{bg}"/>'
            f'<g transform="translate(0,0)">{plot_body}</g>'
            f'<image x="{plot_width_px + gap}" y="0" '
            f'width="{legend_image.width()}" height="{legend_image.height()}" '
            f'href="data:image/png;base64,{legend_b64}"/>'
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
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        generator = QSvgGenerator()
        generator.setOutputDevice(buffer)
        generator.setSize(widget.size())
        generator.setViewBox(QRectF(0.0, 0.0, float(width_px), float(height_px)))
        generator.setResolution(int(settings.dpi))

        painter = QPainter(generator)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
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

        mime = QMimeData()
        mime.setData("image/svg+xml", bytes(data))
        return mime
