from PyQt6.QtWidgets import QApplication
import numpy as np

from gui.widgets.fisher_plot import FisherWidget


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
