from PyQt6.QtWidgets import QApplication

from gui.widgets.controls import ControlWidget


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_equal_gate_type_displays_generated_edges_and_locks_editor():
    _app()
    widget = ControlWidget()
    widget.combo_gate_type.setCurrentText("Equal")
    widget.spin_num_gates.setValue(4)
    widget.radio_gate_start.setChecked(True)
    widget.radio_gate_end_period.setChecked(True)
    widget.spin_period.setValue(12.5)
    widget._sync_gate_controls()

    assert widget.edit_gate_widths.isReadOnly()
    assert widget.spin_num_gates.isEnabled()
    assert widget.edit_gate_widths.text().startswith("0")
    assert widget.lbl_gate_error.text() == ""


def test_custom_gate_type_enables_editor_and_reports_syntax_errors():
    _app()
    widget = ControlWidget()
    widget.combo_gate_type.setCurrentText("Custom")
    widget.edit_gate_widths.setText("0, 1.5, nope, 4.0")
    widget._sync_gate_controls()

    assert not widget.edit_gate_widths.isReadOnly()
    assert not widget.spin_num_gates.isEnabled()
    assert "comma-separated list of numbers" in widget.lbl_gate_error.text().lower()


def test_custom_gate_type_updates_gate_count_from_valid_edges():
    _app()
    widget = ControlWidget()
    widget.combo_gate_type.setCurrentText("Custom")
    widget.edit_gate_widths.setText("0, 1.5, 3.0, 6.0")
    widget._sync_gate_controls()

    assert widget.spin_num_gates.value() == 3
    assert widget.lbl_gate_error.text() == ""
