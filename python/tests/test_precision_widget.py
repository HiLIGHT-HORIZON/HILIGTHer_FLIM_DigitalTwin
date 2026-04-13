from PyQt6.QtWidgets import QApplication
import numpy as np

from gui.widgets.diagnostics_plot import DiagnosticsWidget
from gui.widgets.fisher_plot import FisherWidget
from gui.widgets.mle_accuracy_plot import MLEAccuracyWidget


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_fisher_widget_labels_ci_checkbox_and_keeps_mc_as_points():
    _app()
    widget = FisherWidget()
    widget.plot_batch(
        np.array([1.0, 2.0, 3.0]),
        {
            "Theory": {
                "y": np.array([1.2, 1.1, 1.0]),
            },
            "Monte Carlo": {
                "y": np.array([1.25, 1.05, 1.02]),
                "compatible": np.array([True, True, True]),
                "f_ci_lower": np.array([1.1, 0.95, 0.9]),
                "f_ci_upper": np.array([1.4, 1.2, 1.15]),
            },
        },
        ideal_x=np.array([1.0, 2.0, 3.0]),
        ideal_f=np.array([1.0, 0.95, 0.9]),
        ci_level=99.7,
    )

    current = widget.series_groups["Current Configuration"]
    assert widget.chk_show_mc_ci.text() == "MC CI 99.7%"
    assert widget.chk_show_mc_ci.isEnabled()
    assert current["mc"]
    assert current["mc_ci"]
    assert current["mc"][0].opts["symbol"] == "o"

    widget.chk_show_mc_ci.setChecked(False)
    assert all(not item.isVisible() for item in current["mc_ci"])
    assert all(item.isVisible() for item in current["mc"])


def test_mle_accuracy_widget_summary_mode_plots_one_bar_per_curve():
    _app()
    widget = MLEAccuracyWidget()
    widget.plot_accuracy(
        np.array([1.0, 2.0, 3.0]),
        {
            "Curve A": {
                "mean": np.array([1.0, 2.2, 3.1]),
                "std": np.array([0.2, 0.2, 0.1]),
            },
            "Curve B": {
                "mean": np.array([0.7, 1.5, 3.6]),
                "std": np.array([0.2, 0.25, 0.3]),
            },
        },
    )

    widget.btn_accuracy_summary.setChecked(True)

    assert not widget.chk_stacked.isEnabled()
    assert "Accuracy Summary" in widget.legend_title.text()
    assert len(widget.series_items) == 2

    first_bar = widget.series_items[0][0][0]
    second_bar = widget.series_items[1][0][0]
    assert np.isclose(float(first_bar.opts["height"][0]), 0.81649658, rtol=1e-6)
    assert np.isclose(float(second_bar.opts["height"][0]), 1.84842275, rtol=1e-6)
    assert widget.summary_tick_labels == ["Curve A", "Curve B"]


def test_mle_accuracy_widget_summary_compacts_long_tick_labels():
    assert MLEAccuracyWidget._format_summary_tick_label("Count Rate = 1 GHz (deadtime corrected)") == "1 GHz\nDT corr."
    assert MLEAccuracyWidget._format_summary_tick_label("Count Rate = 1 GHz (Isbaner-lite corrected)") == "1 GHz\nIsbaner-lite corr."
    assert MLEAccuracyWidget._format_summary_tick_label("Current Configuration (Rapp (MCPDF-lite) corrected)") == "Current\nRapp MCPDF-lite corr."
    assert MLEAccuracyWidget._format_summary_tick_label("Current Configuration (Rapp (MCPDF-full) corrected)") == "Current\nRapp MCPDF-full corr."
    assert MLEAccuracyWidget._format_summary_tick_label("Current Configuration (Rapp (MCHC-full) corrected)") == "Current\nRapp MCHC-full corr."


def test_diagnostics_widget_histogram_overlays_enable_only_when_present():
    _app()
    widget = DiagnosticsWidget()
    time_vec = np.array([0.0, 1.0, 2.0], dtype=float)
    gate_shapes = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=float,
    )

    widget.update_plot(
        time_vec,
        gate_shapes,
        pdf=np.array([1.0, 0.4, 0.1], dtype=float),
        observed_hist=np.array([0.0, 1.0, 0.5], dtype=float),
        corrected_hist=np.array([0.0, 0.7, 1.0], dtype=float),
        observed_hist_label="Observed Histogram",
        corrected_hist_label="Corrected Histogram (Rapp (MCHC-lite))",
    )

    assert widget.chk_observed_hist.isEnabled()
    assert widget.chk_corrected_hist.isEnabled()

    widget.chk_observed_hist.setChecked(True)
    widget.chk_corrected_hist.setChecked(True)

    assert widget.observed_hist_curve.isVisible()
    assert widget.corrected_hist_curve.isVisible()

    widget.update_plot(
        time_vec,
        gate_shapes,
        pdf=np.array([1.0, 0.4, 0.1], dtype=float),
        observed_hist=None,
        corrected_hist=None,
    )

    assert not widget.chk_observed_hist.isEnabled()
    assert not widget.chk_corrected_hist.isEnabled()
    assert not widget.observed_hist_curve.isVisible()
    assert not widget.corrected_hist_curve.isVisible()
