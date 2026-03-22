import os
import sys
import json
from typing import Any, Dict


class DesktopAutomationAPI:
    """
    In-process automation surface for the live Qt desktop. This is intended for
    other Python software embedding or controlling the GUI without reaching into
    individual Qt widgets directly.
    """

    def __init__(self, window):
        self.window = window
        # Find data directory relative to this file
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        self.lock_file = os.path.join(self.data_dir, "app_locks.json")

    def _check_access(self):
        """Verify if the GUI API is currently locked."""
        if not os.path.exists(self.lock_file):
            return
        try:
            with open(self.lock_file, "r") as f:
                locks = json.load(f)
        except (json.JSONDecodeError, IOError):
            return

        if locks.get("gui_api_locked", False):
            raise PermissionError("Access Denied: HiLIGHTer GUI API is LOCKED.")

    def get_layout(self) -> Dict[str, Any]:
        self._check_access()
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
        self._check_access()
        self.window.sync_ui_to_config()
        cfg = self.window.engine.config
        return cfg.model_dump() if hasattr(cfg, "model_dump") else cfg.dict()

    def set_controller_state(self, config_patch: Dict[str, Any]) -> Dict[str, Any]:
        self._check_access()
        current = self.get_controller_state()
        current.update(config_patch)
        self.window.engine.config = self.window.engine.config.__class__(**current)
        self.window.control_widget.update_from_config(self.window.engine.config)
        self.window.refresh_diagnostics()
        return self.get_controller_state()

    def trigger_run(self):
        self._check_access()
        self.window.run_precision_analysis()
        return {"status": "run_complete"}

    def trigger_test(self):
        self._check_access()
        self.window.run_image_gen()
        return {"status": "test_complete"}

    def trigger_optimisation(self):
        self._check_access()
        self.window.run_optimization_workflow()
        return {"status": "optimisation_started" if self.window.optimization_running else "optimisation_not_started"}

    def trigger_export_preview(self):
        self._check_access()
        self.window.preview_last_precision_report()
        return {"status": "export_preview_opened"}

    def get_precision_plot(self) -> Dict[str, Any]:
        self._check_access()
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
                    "f_ci_lower": None if payload.get("f_ci_lower") is None else payload["f_ci_lower"].tolist(),
                    "f_ci_upper": None if payload.get("f_ci_upper") is None else payload["f_ci_upper"].tolist(),
                    "efficiency_ci_lower": None if payload.get("efficiency_ci_lower") is None else payload["efficiency_ci_lower"].tolist(),
                    "efficiency_ci_upper": None if payload.get("efficiency_ci_upper") is None else payload["efficiency_ci_upper"].tolist(),
                }
                for label, payload in widget.batch_data.items()
            },
        }

    def get_accuracy_plot(self) -> Dict[str, Any]:
        self._check_access()
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
        self._check_access()
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

    def get_optimisation_state(self) -> Dict[str, Any]:
        self._check_access()
        return {
            "mode_active": bool(self.window.optimization_mode_active),
            "running": bool(self.window.optimization_running),
            "has_results": self.window.last_optimization_run is not None,
            "saved": bool(self.window.optimization_results_saved),
            "imported": bool(self.window.optimization_results_imported),
            "objective_history": []
            if self.window.last_optimization_run is None
            else self.window.last_optimization_run["objective_history"].tolist(),
            "min_f_history": []
            if self.window.last_optimization_run is None
            else self.window.last_optimization_run["min_f_history"].tolist(),
        }
