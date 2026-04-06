from pathlib import Path
import xml.etree.ElementTree as ET

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from gui.widgets import clipboard_export as clipboard_export_module
from gui.widgets.clipboard_export import (
    ClipboardExportDialog,
    ClipboardExportManager,
    ClipboardExportProfileStore,
    ClipboardExportSettings,
)


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_clipboard_export_profile_store_round_trip(tmp_path, monkeypatch):
    store_dir = tmp_path / "clipboard_exports"
    monkeypatch.setattr(clipboard_export_module, "_STORE_DIR", str(store_dir))
    monkeypatch.setattr(clipboard_export_module, "_INSTALL_PATH", str(store_dir / "defaults.install.json"))
    monkeypatch.setattr(clipboard_export_module, "_CURRENT_PATH", str(store_dir / "defaults.current.json"))

    store = ClipboardExportProfileStore()
    current = ClipboardExportSettings(fmt="svg", include_legend=True, grid_x=False, show_bounding_box=True)
    store.save_current(current)
    assert store.load_current() == current

    profiles = {
        "Paper figure": ClipboardExportSettings(
            use_defaults=False,
            fmt="svg",
            dpi=600,
            include_legend=True,
            grid_x=False,
            grid_y=False,
            show_bounding_box=True,
        )
    }
    store.save_profiles(profiles)

    payload = Path(store_dir / "defaults.current.json").read_text(encoding="utf-8")
    assert '"Paper figure"' in payload
    loaded = store.load_profiles()
    assert loaded["Paper figure"] == profiles["Paper figure"]


def test_clipboard_export_dialog_can_save_rename_and_delete_profiles(monkeypatch):
    _app()
    dialog = ClipboardExportDialog(ClipboardExportSettings(), saved_profiles={})

    monkeypatch.setattr(
        clipboard_export_module.QInputDialog,
        "getText",
        staticmethod(lambda *args, **kwargs: ("Paper figure", True)),
    )
    dialog._save_profile(force_prompt=True)
    assert "Paper figure" in dialog.saved_profiles()

    dialog.combo_profiles.setCurrentIndex(dialog.combo_profiles.findData("Paper figure"))
    monkeypatch.setattr(
        clipboard_export_module.QInputDialog,
        "getText",
        staticmethod(lambda *args, **kwargs: ("Slides", True)),
    )
    dialog._rename_profile()
    assert "Slides" in dialog.saved_profiles()
    assert "Paper figure" not in dialog.saved_profiles()

    monkeypatch.setattr(
        clipboard_export_module.QMessageBox,
        "question",
        staticmethod(lambda *args, **kwargs: clipboard_export_module.QMessageBox.StandardButton.Yes),
    )
    dialog._delete_profile()
    assert "Slides" not in dialog.saved_profiles()


def test_clipboard_export_dialog_keeps_selected_profile_while_editing():
    _app()
    profile = ClipboardExportSettings(use_defaults=False, fmt="svg", dpi=600, tick_length=8.0, marker_size=9.0)
    dialog = ClipboardExportDialog(profile, saved_profiles={"Paper figure": profile})

    assert dialog.combo_profiles.currentData() == "Paper figure"
    dialog.spin_dpi.setValue(601)

    assert dialog.combo_profiles.currentData() == "Paper figure"
    assert dialog.btn_profile_save.text() == "Update*"


def test_merge_svg_polylines_merges_connected_segments():
    svg = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg">
  <g stroke="#ff0000" fill="none">
    <polyline points="0,0 1,1 " />
    <polyline points="1,1 2,0 " />
    <polyline points="5,5 6,6 " />
  </g>
</svg>
"""

    merged = ClipboardExportManager._merge_svg_polylines(svg).decode("utf-8")
    assert merged.count("<polyline") == 2
    assert 'points="0,0 1,1 2,0 "' in merged


def test_svg_export_with_legend_uses_vector_legend_not_embedded_image():
    _app()
    plot = pg.PlotWidget()
    plot.resize(400, 300)
    plot.plot([1, 2, 3], [1.0, 0.7, 0.4], pen=pg.mkPen("#6c5ce7", width=2))
    settings = ClipboardExportSettings(use_defaults=False, fmt="svg", include_legend=True)

    mime = ClipboardExportManager._render_pyqtgraph_svg_mime(
        plot,
        settings,
        legend_entries=[{"label": "Theory", "color": "#6c5ce7", "style": "line"}],
    )
    svg = bytes(mime.data("image/svg+xml")).decode("utf-8")

    assert "<image" not in svg
    assert "Legend" in svg
    assert "Theory" in svg


def test_plot_style_override_restores_grid_and_bounding_box():
    _app()
    plot = pg.PlotWidget()
    plot.showGrid(x=True, y=False, alpha=0.3)
    plot.getPlotItem().vb.setBorder(None)
    curve = plot.plot([1, 2, 3], [1, 2, 3], pen=pg.mkPen("#ff0000", width=2), symbol="o", symbolSize=6)
    scatter = pg.ScatterPlotItem(size=8, pen=pg.mkPen("#00aa88"), brush=pg.mkBrush("#00aa88"))
    scatter.setData([1.5, 2.5], [1.25, 2.25])
    plot.addItem(scatter)

    state = ClipboardExportManager._capture_plot_style_state(plot)
    settings = ClipboardExportSettings(
        use_defaults=False,
        grid_x=False,
        grid_y=True,
        grid_alpha=0.6,
        show_bounding_box=True,
        tick_visibility="major",
        tick_direction="outer",
        tick_length=12.0,
        plot_line_width=4.5,
        axis_line_width=3.0,
        marker_size=11.0,
    )
    ClipboardExportManager._apply_plot_style_override(plot, settings)

    plot_item = plot.getPlotItem()
    assert not plot_item.ctrl.xGridCheck.isChecked()
    assert plot_item.ctrl.yGridCheck.isChecked()
    assert plot_item.getAxis("bottom").style["maxTickLevel"] == 0
    assert plot_item.getAxis("bottom").style["tickLength"] == 12
    assert plot_item.getAxis("bottom")._tickLevels is not None
    assert len(plot_item.getAxis("bottom")._tickLevels) == 1
    assert plot_item.getAxis("bottom").pen().widthF() == 3.0
    assert plot_item.getAxis("bottom").tickPen().color() == plot_item.getAxis("bottom").pen().color()
    assert plot_item.getAxis("top").isVisible()
    assert plot_item.getAxis("right").isVisible()
    assert plot_item.getAxis("top").tickPen().style() == Qt.PenStyle.NoPen
    assert plot_item.getAxis("right").tickPen().style() == Qt.PenStyle.NoPen
    assert plot_item.vb.border.style() == Qt.PenStyle.NoPen
    assert curve.opts["pen"].widthF() == 4.5
    assert float(curve.opts["symbolSize"]) == 11.0
    assert float(scatter.opts["size"]) == 11.0

    ClipboardExportManager._restore_plot_style_state(plot, state)
    assert plot_item.ctrl.xGridCheck.isChecked() == state["grid_x"]
    assert plot_item.ctrl.yGridCheck.isChecked() == state["grid_y"]
    assert plot_item.getAxis("bottom")._tickLevels == state["axes"]["bottom"]["explicit_ticks"]
    assert plot_item.getAxis("top").isVisible() == state["axes"]["top"]["visible"]
    assert plot_item.getAxis("right").isVisible() == state["axes"]["right"]["visible"]
    assert curve.opts["pen"].widthF() == state["items"][0]["pen"].widthF()
    assert float(curve.opts["symbolSize"]) == state["items"][0]["symbol_size"]
    assert float(scatter.opts["size"]) == state["items"][1]["scatter_size"]


def test_export_tick_labels_include_all_visible_tick_levels():
    _app()
    plot = pg.PlotWidget()
    plot.resize(500, 400)
    plot.plot([0, 1, 2, 3], [1, 2, 3, 4], pen=pg.mkPen("#6c5ce7", width=2))

    settings = ClipboardExportSettings(
        use_defaults=False,
        tick_visibility="major_minor",
        tick_direction="outer",
        tick_length=10.0,
    )
    ClipboardExportManager._apply_plot_style_override(plot, settings)

    bottom_levels = plot.getPlotItem().getAxis("bottom")._tickLevels
    left_levels = plot.getPlotItem().getAxis("left")._tickLevels

    assert bottom_levels is not None and len(bottom_levels) == 2
    assert left_levels is not None and len(left_levels) == 2
    assert all(label != "" for level in bottom_levels for _value, label in level)
    assert all(label != "" for level in left_levels for _value, label in level)


def test_svg_tick_cleanup_anchors_main_ticks_and_removes_box_ticks():
    _app()
    plot = pg.PlotWidget()
    plot.resize(500, 500)
    plot.plot([0.6, 1, 2, 3, 4, 5, 6, 7], [3.2, 2.6, 1.2, 1.1, 1.3, 1.6, 2.0, 2.4], pen=pg.mkPen("#6c5ce7", width=2))
    settings = ClipboardExportSettings(
        use_defaults=False,
        fmt="svg",
        include_legend=False,
        show_bounding_box=True,
        tick_visibility="major_minor",
        tick_direction="outer",
        grid_x=False,
        grid_y=False,
    )

    ClipboardExportManager._apply_plot_style_override(plot, settings)
    ClipboardExportManager._prepare_plot_source(plot, settings)
    mime = ClipboardExportManager._render_pyqtgraph_svg_mime(plot, settings)
    root = ET.fromstring(bytes(mime.data("image/svg+xml")))
    ns = {"svg": "http://www.w3.org/2000/svg"}

    axis_groups = {
        group.attrib.get("id"): group
        for group in root.findall(".//svg:g", ns)
        if group.attrib.get("id", "").startswith("AxisItem_")
    }
    assert len(axis_groups) == 4

    def _axis_kind(group):
        first_polyline = group.find("./svg:g/svg:polyline", ns)
        points = ClipboardExportManager._parse_svg_points(first_polyline.attrib["points"])
        (x1, y1), (x2, y2) = points
        if abs(y1 - y2) <= 1e-6:
            return ("top" if y1 < 100 else "bottom"), y1
        return ("left" if x1 < 500 else "right"), x1

    classified = {}
    for group in axis_groups.values():
        side, axis_value = _axis_kind(group)
        classified[side] = (group, axis_value)

    bottom_group, bottom_axis_y = classified["bottom"]
    left_group, left_axis_x = classified["left"]
    top_group, _top_axis_y = classified["top"]
    right_group, _right_axis_x = classified["right"]

    bottom_tick = bottom_group.findall("./svg:g/svg:polyline", ns)[1]
    bottom_points = ClipboardExportManager._parse_svg_points(bottom_tick.attrib["points"])
    assert bottom_points[0][1] == bottom_axis_y
    assert bottom_points[1][1] > bottom_axis_y

    left_tick = left_group.findall("./svg:g/svg:polyline", ns)[1]
    left_points = ClipboardExportManager._parse_svg_points(left_tick.attrib["points"])
    assert left_points[0][0] == left_axis_x
    assert left_points[1][0] < left_axis_x

    assert not any(node.tag.endswith("path") or node.tag.endswith("polyline") for child in list(top_group)[1:] for node in child.iter())
    assert not any(node.tag.endswith("path") or node.tag.endswith("polyline") for child in list(right_group)[1:] for node in child.iter())
