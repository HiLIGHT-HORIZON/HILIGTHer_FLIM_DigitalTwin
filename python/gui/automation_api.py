from typing import Any, Dict


class DesktopAutomationAPI:
    """
    In-process automation surface for the live Qt desktop. This is intended for
    other Python software embedding or controlling the GUI without reaching into
    individual Qt widgets directly.
    """

    def __init__(self, window):
        self.window = window

    def get_layout(self) -> Dict[str, Any]:
        return {
            "docks": [
                "dock_params",
                "dock_fisher",
                "dock_mle_accuracy",
                "dock_diagnostics",
                "dock_map",
                "dock_decay",
                "dock_phasor",
            ]
        }

    def get_controller_state(self) -> Dict[str, Any]:
        self.window.sync_ui_to_config()
        cfg = self.window.engine.config
        return cfg.model_dump() if hasattr(cfg, "model_dump") else cfg.dict()

    def set_controller_state(self, config_patch: Dict[str, Any]) -> Dict[str, Any]:
        current = self.get_controller_state()
        current.update(config_patch)
        self.window.engine.config = self.window.engine.config.__class__(**current)
        self.window.control_widget.update_from_config(self.window.engine.config)
        self.window.refresh_diagnostics()
        return self.get_controller_state()

    def trigger_run(self):
        self.window.run_precision_analysis()
        return {"status": "run_complete"}

    def trigger_test(self):
        self.window.run_image_gen()
        return {"status": "test_complete"}

    def trigger_export_preview(self):
        self.window.preview_last_precision_report()
        return {"status": "export_preview_opened"}

    def get_precision_plot(self) -> Dict[str, Any]:
        widget = self.window.fisher_widget
        return {
            "x_label": widget.plot_widget.getAxis('bottom').labelText,
            "ideal_x": None if widget.ideal_tau is None else widget.ideal_tau.tolist(),
            "ideal_y": None if widget.ideal_f is None else widget.ideal_f.tolist(),
            "series": {
                label: {
                    "x": payload["x"].tolist(),
                    "y": payload["y"].tolist(),
                    "compatible": None if payload.get("compatible") is None else payload["compatible"].tolist(),
                }
                for label, payload in widget.batch_data.items()
            },
        }

    def get_accuracy_plot(self) -> Dict[str, Any]:
        widget = self.window.mle_accuracy_widget
        return {
            "x_label": widget.x_label,
            "series": {
                label: {
                    "x": payload["x"].tolist(),
                    "mean": payload["mean"].tolist(),
                    "std": payload["std"].tolist(),
                }
                for label, payload in widget.series_data.items()
            },
        }

    def get_diagnostics_frames(self) -> Dict[str, Any]:
        frames = getattr(self.window.diagnostics_widget, "frames", [])
        serialized = []
        for frame in frames:
            serialized.append({
                "label": frame.get("label"),
                "time": frame.get("time_vec").tolist() if frame.get("time_vec") is not None else None,
                "gates": frame.get("gate_shapes").tolist() if frame.get("gate_shapes") is not None else None,
                "irf": frame.get("irf").tolist() if frame.get("irf") is not None else None,
                "pdf": frame.get("pdf").tolist() if frame.get("pdf") is not None else None,
            })
        return {"frames": serialized}
