import copy
import os
import tempfile
from typing import Dict, Any, Optional

import numpy as np

from .gui_schema import get_gui_schema
from .importers import import_sdt
from .models import PhysicsConfig, UnifiedState
from .storage import storage
from .twin_engine import TwinEngine


class DigitalTwinService:
    """
    Shared orchestration layer for backend automation, HTTP APIs, GUI automation,
    and MCP tooling. The goal is one stable programmatic surface, regardless of
    whether the caller is a web client, another Python process, or an LLM agent.
    """

    def __init__(self, engine: Optional[TwinEngine] = None, state: Optional[UnifiedState] = None):
        self.engine = engine or TwinEngine()
        self.state = state or UnifiedState()

    def get_status(self) -> Dict[str, Any]:
        cfg = self.engine.config
        return {
            "status": "ready",
            "engine_label": cfg.label,
            "has_raw_data": self.engine.raw_data is not None,
            "has_tau_map": self.engine.tau_map is not None,
            "has_precision_grid": self.engine.grid_templates is not None,
            "config_summary": {
                "decay_model": cfg.decay_model,
                "n_components": cfg.n_components,
                "period_ns": cfg.period,
                "n_gates": max(0, len(cfg.gate_edges) - 1),
            },
        }

    def get_config(self) -> Dict[str, Any]:
        cfg = self.engine.config
        return cfg.model_dump() if hasattr(cfg, "model_dump") else cfg.dict()

    def update_config(self, config_patch: Dict[str, Any]) -> Dict[str, Any]:
        cfg_dict = self.get_config()
        cfg_dict.update(config_patch)
        self.engine.config = PhysicsConfig(**cfg_dict)
        self.engine.invalidate_grid()
        self.engine.distill_gates()
        return self.get_config()

    def get_gui_schema(self) -> Dict[str, Any]:
        return get_gui_schema()

    def get_data_summary(self) -> Dict[str, Any]:
        raw = self.engine.raw_data
        tau_map = self.engine.tau_map
        return {
            "raw_data_shape": None if raw is None else list(raw.shape),
            "tau_map_shape": None if tau_map is None else list(tau_map.shape),
            "tau_mean": None if tau_map is None else float(np.nanmean(tau_map)),
            "tau_min": None if tau_map is None else float(np.nanmin(tau_map)),
            "tau_max": None if tau_map is None else float(np.nanmax(tau_map)),
        }

    def get_results_snapshot(self) -> Dict[str, Any]:
        return {
            "tau_map": None if self.engine.tau_map is None else self.engine.tau_map.tolist(),
            "a_map": None if self.engine.a_map is None else self.engine.a_map.tolist(),
            "b_map": None if self.engine.b_map is None else self.engine.b_map.tolist(),
            "chi2_map": None if self.engine.chi2_map is None else self.engine.chi2_map.tolist(),
            "data_summary": self.get_data_summary(),
        }

    def get_diagnostics_snapshot(self, tau_ref: Optional[float] = None) -> Dict[str, Any]:
        self.engine.distill_gates()
        tau_ref = tau_ref if tau_ref is not None else (self.engine.config.taus[0] if self.engine.config.taus else 2.5)
        pdf = self.engine.dt_pdf(self.engine.time_vector, tau=tau_ref)
        irf = self.engine.dt_excitation(self.engine.time_vector)
        return {
            "time": self.engine.time_vector.tolist(),
            "gate_shapes": self.engine.gate_shapes.tolist(),
            "irf": irf.tolist(),
            "pdf": pdf.tolist(),
            "tau_ref": tau_ref,
        }

    def simulate_basic(self, params: Dict[str, Any]) -> Dict[str, Any]:
        a = float(params.get("a", 2000.0))
        tau1 = float(params.get("tau1", 1.0))
        tau2 = float(params.get("tau2", 5.0))
        b = float(params.get("b", 10.0))
        res = int(params.get("res", 64))
        fit_method = str(params.get("fit_method", "gridded_mle"))

        self.engine.distill_gates()
        self.engine.simulate_data(a, tau1, tau2, b, res, res)
        self.engine.run_fit(method=fit_method)
        return {
            "status": "success",
            "mean_tau": float(np.nanmean(self.engine.tau_map)),
            "results": self.get_results_snapshot(),
        }

    def simulate_advanced(self, params: Dict[str, Any]) -> Dict[str, Any]:
        a = float(params.get("a", 2000.0))
        tau1 = float(params.get("tau1", 1.0))
        tau2 = float(params.get("tau2", 5.0))
        b = float(params.get("b", 10.0))
        res = int(params.get("res", 64))
        fit_method = str(params.get("fit_method", "gridded_mle"))

        ny, nx = res, res
        tau_vals = np.linspace(tau1, tau2, nx)
        tau_grid = np.tile(tau_vals, (ny, 1))
        self.engine.distill_gates()
        self.engine.advanced_instrument_simulation(a, tau_grid, b)
        self.engine.run_fit(method=fit_method)
        return {
            "status": "advanced_simulation_complete",
            "results": self.get_results_snapshot(),
        }

    def run_precision(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        cfg = copy.deepcopy(self.engine.config)
        if params:
            cfg_dict = cfg.model_dump() if hasattr(cfg, "model_dump") else cfg.dict()
            cfg_dict.update(params)
            cfg = PhysicsConfig(**cfg_dict)

        if cfg.f_x_scale == "log":
            x_range = np.logspace(np.log10(cfg.f_x_min), np.log10(cfg.f_x_max), cfg.f_x_steps)
        elif cfg.f_x_scale == "linear":
            x_range = np.linspace(cfg.f_x_min, cfg.f_x_max, cfg.f_x_steps)
        else:
            x_range = np.geomspace(cfg.f_x_min, cfg.f_x_max, cfg.f_x_steps)

        baseline = self.engine.config
        self.engine.config = cfg
        self.engine.invalidate_grid()
        try:
            ideal_fi, ideal_f = self.engine.compute_ideal_reference(x_range, int(cfg.precision_photons))
            theory_fi, theory_f = self.engine.compute_fisher_info(x_range, int(cfg.precision_photons))
            payload = {
                "x_range": x_range.tolist(),
                "ideal": {
                    "fisher_info": ideal_fi.tolist(),
                    "f_value": ideal_f.tolist(),
                },
                "theory": {
                    "fisher_info": theory_fi.tolist(),
                    "f_value": theory_f.tolist(),
                },
            }
            if cfg.precision_validate_mc and cfg.f_x_param == "tau1" and cfg.n_components == 1 and cfg.decay_model == "exponential":
                payload["monte_carlo"] = self.engine.monte_carlo_precision_curve(
                    x_range,
                    int(cfg.precision_photons),
                    int(cfg.precision_mc_repeats),
                )
            return payload
        finally:
            self.engine.config = baseline

    def run_optimization(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        cfg = copy.deepcopy(self.engine.config)
        if params:
            cfg_dict = cfg.model_dump() if hasattr(cfg, "model_dump") else cfg.dict()
            cfg_dict.update(params)
            cfg = PhysicsConfig(**cfg_dict)

        if not cfg.optimize_detection_gates:
            if not cfg.optimize_excitation_profile:
                return {"status": "invalid_request", "detail": "Enable at least one optimisation target to run optimisation."}

        x_range = (
            np.logspace(np.log10(cfg.f_x_min), np.log10(cfg.f_x_max), cfg.f_x_steps)
            if cfg.f_x_scale == "log"
            else np.linspace(cfg.f_x_min, cfg.f_x_max, cfg.f_x_steps)
            if cfg.f_x_scale == "linear"
            else np.geomspace(cfg.f_x_min, cfg.f_x_max, cfg.f_x_steps)
        )

        baseline = self.engine.config
        self.engine.config = copy.deepcopy(cfg)
        self.engine.invalidate_grid()
        try:
            objective_history = []
            min_f_history = []

            def on_progress(progress):
                objective_history.append(float(progress["objective"]))
                min_f_history.append(float(progress["min_f"]))

            info = self.engine.run_optimization_workflow(progress_callback=on_progress)
            final_cfg = PhysicsConfig(**info["final_config"])
            best_edges = np.asarray(final_cfg.gate_edges, dtype=float)
            best_j = float(info["best_objective"])
            self.engine.config = copy.deepcopy(final_cfg)
            self.engine.invalidate_grid()
            theory_fi, theory_f = self.engine.compute_fisher_info(x_range, int(cfg.precision_photons))
            return {
                "status": "success",
                "algorithm": str(
                    cfg.detection_optimization_algorithm
                    if cfg.optimize_detection_gates
                    else f"excitation_{cfg.excitation_optimization_profile}"
                ),
                "workflow": (
                    "joint"
                    if cfg.optimize_detection_gates and cfg.optimize_excitation_profile
                    else "detection"
                    if cfg.optimize_detection_gates
                    else "excitation"
                ),
                "x_range": x_range.tolist(),
                "best_edges": np.asarray(best_edges, dtype=float).tolist(),
                "final_gate_count": int(max(0, len(np.asarray(best_edges, dtype=float)) - 1)),
                "best_objective": float(best_j),
                "objective_history": objective_history,
                "min_f_history": min_f_history,
                "final_theory": {
                    "fisher_info": np.asarray(theory_fi, dtype=float).tolist(),
                    "f_value": np.asarray(theory_f, dtype=float).tolist(),
                },
                "window_start": float(info["window_start"]),
                "window_end": float(info["window_end"]),
                "optimization_config": {
                    "optimize_detection_gates": bool(cfg.optimize_detection_gates),
                    "optimize_excitation_profile": bool(cfg.optimize_excitation_profile),
                    "optimization_objective": str(getattr(cfg, "optimization_objective", "fisher_information")),
                    "optimization_max_fi_loss_pct": float(getattr(cfg, "optimization_max_fi_loss_pct", 5.0)),
                    "optimization_mode": str(getattr(cfg, "optimization_mode", "sequential")),
                    "optimization_first": str(getattr(cfg, "optimization_first", "detection")),
                    "optimization_iterations": int(getattr(cfg, "optimization_iterations", 3)),
                    "detection_optimization_algorithm": str(cfg.detection_optimization_algorithm),
                    "detection_opt_restarts": int(getattr(cfg, "detection_opt_restarts", 20)),
                    "detection_opt_ftol": float(getattr(cfg, "detection_opt_ftol", 1e-4)),
                    "detection_opt_maxiter": int(getattr(cfg, "detection_opt_maxiter", 50)),
                    "detection_opt_fine_bins_per_gate": int(getattr(cfg, "detection_opt_fine_bins_per_gate", 12)),
                    "detection_opt_fine_bin_cap": int(getattr(cfg, "detection_opt_fine_bin_cap", 256)),
                    "detection_opt_fc_nuisance_aware": bool(getattr(cfg, "detection_opt_fc_nuisance_aware", True)),
                    "detection_opt_fc_auto_compress": bool(getattr(cfg, "detection_opt_fc_auto_compress", False)),
                    "detection_opt_fc_initial_gates": int(getattr(cfg, "detection_opt_fc_initial_gates", 16)),
                    "detection_opt_fc_min_gates": int(getattr(cfg, "detection_opt_fc_min_gates", 2)),
                    "detection_opt_fc_max_f_loss_pct": float(getattr(cfg, "detection_opt_fc_max_f_loss_pct", 5.0)),
                    "detection_opt_start_anchor": str(cfg.detection_opt_start_anchor),
                    "detection_opt_start_time": float(cfg.detection_opt_start_time),
                    "detection_opt_end_anchor": str(cfg.detection_opt_end_anchor),
                    "detection_opt_end_time": float(cfg.detection_opt_end_time),
                    "excitation_optimization_profile": str(getattr(cfg, "excitation_optimization_profile", "gaussian")),
                    "excitation_optimization_constraint": str(getattr(cfg, "excitation_optimization_constraint", "fixed_dose")),
                    "excitation_optimization_width_min": float(getattr(cfg, "excitation_optimization_width_min", 0.05)),
                    "excitation_optimization_width_max": float(getattr(cfg, "excitation_optimization_width_max", 10.0)),
                    "excitation_optimization_control_points": int(getattr(cfg, "excitation_optimization_control_points", 8)),
                },
                "final_config": final_cfg.model_dump() if hasattr(final_cfg, "model_dump") else final_cfg.dict(),
            }
        finally:
            self.engine.config = baseline

    def get_tau_map(self) -> Dict[str, Any]:
        if self.engine.tau_map is None:
            return {"data": None, "shape": None}
        return {"data": self.engine.tau_map.tolist(), "shape": list(self.engine.tau_map.shape)}

    def get_phasor_map(self, harmonic: int = 1) -> Dict[str, Any]:
        if self.engine.raw_data is None:
            return {"g": None, "s": None, "shape": None}
        g_map, s_map = self.engine.calculate_phasor(harmonic=harmonic)
        return {"g": g_map.tolist(), "s": s_map.tolist(), "shape": list(g_map.shape)}

    def get_theoretical_locus(self) -> Dict[str, Any]:
        g, s = self.engine.get_theoretical_locus()
        return {"g": g.tolist(), "s": s.tolist()}

    def get_pixel_analysis(self, y: int, x: int) -> Dict[str, Any]:
        if self.engine.raw_data is None:
            return {"status": "no_data"}

        decay = self.engine.raw_data[y, x, :].tolist()
        edges = np.array(self.engine.config.gate_edges)
        centers = (0.5 * (edges[:-1] + edges[1:])).tolist()
        tau = None
        fit = None
        if self.engine.tau_map is not None:
            tau = float(self.engine.tau_map[y, x])
            if np.isfinite(tau):
                self.engine.distill_gates()
                sig = np.exp(-self.engine.time_vector / tau)
                pj = self.engine.gate_shapes @ sig
                fit = (pj / max(np.sum(pj), 1e-12) * np.sum(self.engine.raw_data[y, x, :])).tolist()
        return {"decay": decay, "centers": centers, "fit": fit, "tau": tau}

    def import_sdt_path(self, file_path: str) -> Dict[str, Any]:
        data, meta = import_sdt(file_path)
        self.engine.raw_data = data
        self.engine.config.gate_edges = np.linspace(0, meta["tac_range"], meta["n_gates"] + 1).tolist()
        self.engine.distill_gates()
        return {"status": "imported", "meta": meta, "data_summary": self.get_data_summary()}

    def import_sdt_bytes(self, filename: str, payload: bytes) -> Dict[str, Any]:
        with tempfile.NamedTemporaryFile(prefix="hilight_", suffix=f"_{os.path.basename(filename)}", delete=False) as tmp:
            tmp.write(payload)
            tmp_path = tmp.name
        try:
            return self.import_sdt_path(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def save_session(self, session_id: str) -> Dict[str, Any]:
        if self.engine.raw_data is None:
            return {"status": "no_data"}
        session_state = UnifiedState()
        session_state.config = self.engine.config  # compatibility with existing storage
        storage.save_state(session_id, session_state, self.engine.raw_data, self.engine.tau_map)
        return {"status": "saved", "session_id": session_id}

    def load_session(self, session_id: str) -> Dict[str, Any]:
        config, raw_data, tau_map = storage.load_state(session_id)
        self.engine.config = config
        self.engine.raw_data = raw_data
        self.engine.tau_map = tau_map
        self.engine.distill_gates()
        return {"status": "loaded", "session_id": session_id, "data_summary": self.get_data_summary()}
