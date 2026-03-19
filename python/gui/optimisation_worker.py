import copy
from typing import Any, Dict, List

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from backend.models import PhysicsConfig
from backend.twin_engine import TwinEngine


class DetectionOptimisationWorker(QThread):
    baseline_ready = pyqtSignal(object)
    progress_ready = pyqtSignal(object)
    result_ready = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, config: PhysicsConfig):
        super().__init__()
        self.config = copy.deepcopy(config)

    def request_interrupt(self):
        self.config.b_interrupt = True
        worker_engine = getattr(self, "_opt_engine", None)
        if worker_engine is not None:
            worker_engine.config.b_interrupt = True

    @staticmethod
    def _build_x_range(cfg: PhysicsConfig) -> np.ndarray:
        x_min = float(cfg.f_x_min)
        x_max = float(cfg.f_x_max)
        n_steps = max(int(cfg.f_x_steps), 2)
        scale = str(cfg.f_x_scale).lower()

        if x_max < x_min:
            x_min, x_max = x_max, x_min
        if np.isclose(x_max, x_min):
            return np.full(n_steps, x_min, dtype=float)
        if scale in {"log", "exp"} and (x_min <= 0 or x_max <= 0):
            scale = "linear"

        if scale == "log":
            return np.logspace(np.log10(x_min), np.log10(x_max), n_steps)
        if scale == "linear":
            return np.linspace(x_min, x_max, n_steps)
        return np.geomspace(x_min, x_max, n_steps)

    @staticmethod
    def _clone_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
        cloned: Dict[str, Any] = {}
        for key, value in snapshot.items():
            if isinstance(value, np.ndarray):
                cloned[key] = np.array(value, copy=True)
            elif isinstance(value, dict):
                cloned[key] = DetectionOptimisationWorker._clone_snapshot(value)
            elif isinstance(value, list):
                cloned[key] = copy.deepcopy(value)
            else:
                cloned[key] = copy.deepcopy(value)
        return cloned

    @staticmethod
    def _config_with_edges(base_cfg: PhysicsConfig, edges: np.ndarray) -> PhysicsConfig:
        cfg = copy.deepcopy(base_cfg)
        cfg.gate_type = "custom"
        cfg.gate_edges = np.asarray(edges, dtype=float).tolist()
        cfg.gate_widths = np.diff(np.asarray(edges, dtype=float)).tolist()
        return cfg

    @staticmethod
    def _resolve_start_partition_cfg(base_cfg: PhysicsConfig) -> PhysicsConfig:
        cfg = copy.deepcopy(base_cfg)
        algorithm = str(getattr(cfg, "detection_optimization_algorithm", "fisher_compression")).lower()
        auto_compress = bool(getattr(cfg, "detection_opt_fc_auto_compress", False))
        if algorithm != "fisher_compression" or not auto_compress:
            return cfg

        start = 0.0
        start_anchor = str(getattr(cfg, "detection_opt_start_anchor", "zero")).lower()
        if start_anchor == "irf":
            jitter_ns = float(getattr(cfg, "timing_jitter", 0.0)) / 1000.0
            irf_profile = str(getattr(cfg, "irf_profile", "gaussian")).lower()
            if irf_profile == "gaussian":
                sigma_total = np.sqrt((float(cfg.irf_fwhm) / 2.355) ** 2 + jitter_ns ** 2)
                start = float(cfg.irf_position) + 3.0 * sigma_total
            elif irf_profile == "ideal (dirac)":
                start = float(cfg.irf_position) + 3.0 * jitter_ns
            else:
                start = float(cfg.irf_position) + float(cfg.irf_fwhm) + 3.0 * jitter_ns
        elif start_anchor == "custom":
            start = float(getattr(cfg, "detection_opt_start_time", 0.0))

        end_anchor = str(getattr(cfg, "detection_opt_end_anchor", "period")).lower()
        if end_anchor == "custom":
            end = float(getattr(cfg, "detection_opt_end_time", cfg.period))
        else:
            end = float(cfg.period)
        if end <= start:
            end = start + 1e-3

        n_gates = max(1, int(getattr(cfg, "detection_opt_fc_initial_gates", max(2, len(cfg.gate_edges) - 1))))
        edges = np.linspace(start, end, n_gates + 1)
        cfg.gate_type = "custom"
        cfg.gate_edges = edges.tolist()
        cfg.gate_widths = np.diff(edges).tolist()
        return cfg

    @staticmethod
    def _build_progress_record(payload: Dict[str, Any], step: int) -> Dict[str, Any]:
        return {
            "label": f"Iteration {int(step)}",
            "step": int(step),
            "objective": float(payload["objective"]),
            "min_f": float(payload["min_f"]),
            "note": str(payload.get("note", "")),
            "edges": np.asarray(payload["edges"], dtype=float).copy(),
            "theory_f": np.asarray(payload["f_val"], dtype=float).copy(),
            "theory_fisher": np.asarray(payload["fisher_info"], dtype=float).copy(),
            "config": copy.deepcopy(payload.get("config", {})),
            "excitation_summary": copy.deepcopy(payload.get("excitation_summary", {})),
        }

    @staticmethod
    def _predict_accuracy(x_range: np.ndarray, f_values: np.ndarray, n_photons: int) -> Dict[str, np.ndarray]:
        denom = np.maximum(np.abs(np.asarray(x_range, dtype=float)), 1e-12)
        sigma = np.asarray(f_values, dtype=float) * denom / np.sqrt(max(int(n_photons), 1))
        return {
            "mean": np.asarray(x_range, dtype=float),
            "std": sigma,
        }

    def _build_pdf_ensemble(self, engine: TwinEngine, cfg: PhysicsConfig, x_range: np.ndarray) -> List[np.ndarray]:
        curves = []
        original_cfg = engine.config
        try:
            engine.config = copy.deepcopy(cfg)
            original_param_value = engine._get_cfg_param(cfg.f_x_param)
            for x_val in x_range:
                engine._set_cfg_param(cfg.f_x_param, float(x_val))
                engine.invalidate_grid()
                engine.distill_gates()
                curves.append(np.array(engine.dt_pdf(engine.time_vector), copy=True))
            engine._set_cfg_param(cfg.f_x_param, original_param_value)
        finally:
            engine.config = original_cfg
        return curves

    def _build_diagnostics_frame(self, engine: TwinEngine, cfg: PhysicsConfig, label: str,
                                 x_range: np.ndarray, include_background_curves: bool = True) -> Dict[str, Any]:
        original_cfg = engine.config
        try:
            engine.config = copy.deepcopy(cfg)
            engine.invalidate_grid()
            engine.distill_gates()
            tau_ref = engine.config.taus[0] if engine.config.taus else 2.5
            pdf_ref = engine.dt_pdf(engine.time_vector, tau_ref)
            irf_ref = engine.dt_excitation(engine.time_vector)
            return {
                "label": label,
                "time_vec": np.array(engine.time_vector, copy=True),
                "gate_shapes": np.array(engine.gate_shapes, copy=True),
                "irf": np.array(irf_ref, copy=True),
                "pdf": np.array(pdf_ref, copy=True),
                "background_curves": self._build_pdf_ensemble(engine, engine.config, x_range) if include_background_curves else [],
            }
        finally:
            engine.config = original_cfg

    def _build_snapshot(self, preview_engine: TwinEngine, base_cfg: PhysicsConfig, x_range: np.ndarray,
                        label: str, edges: np.ndarray, theory_f: np.ndarray, theory_fi: np.ndarray,
                        objective: float, min_f: float, step: int, note: str = "",
                        include_background_curves: bool = True) -> Dict[str, Any]:
        cfg = copy.deepcopy(base_cfg)
        cfg.gate_type = "custom"
        cfg.gate_edges = np.asarray(edges, dtype=float).tolist()
        cfg.gate_widths = np.diff(np.asarray(edges, dtype=float)).tolist()
        gate_count = max(0, len(np.asarray(edges, dtype=float)) - 1)
        return {
            "label": label,
            "step": int(step),
            "objective": float(objective),
            "min_f": float(min_f),
            "note": note or "",
            "gate_count": int(gate_count),
            "config": cfg.model_dump() if hasattr(cfg, "model_dump") else cfg.dict(),
            "theory_f": np.array(theory_f, copy=True),
            "theory_fisher": np.array(theory_fi, copy=True),
            "accuracy": self._predict_accuracy(x_range, theory_f, int(cfg.precision_photons)),
            "diagnostics_frame": self._build_diagnostics_frame(
                preview_engine,
                cfg,
                label,
                x_range,
                include_background_curves=include_background_curves,
            ),
        }

    @staticmethod
    def _sample_snapshots(snapshots: List[Dict[str, Any]], n_keep: int) -> List[Dict[str, Any]]:
        if not snapshots:
            return []
        if len(snapshots) <= n_keep:
            return snapshots
        raw_idx = np.linspace(0, len(snapshots) - 1, max(int(n_keep), 2))
        selected_idx = []
        seen = set()
        for idx in np.round(raw_idx).astype(int).tolist():
            if idx not in seen:
                selected_idx.append(idx)
                seen.add(idx)
        if selected_idx[-1] != len(snapshots) - 1:
            selected_idx[-1] = len(snapshots) - 1
        return [snapshots[idx] for idx in selected_idx]

    def _attach_mc_validation(self, snapshots: List[Dict[str, Any]], x_range: np.ndarray) -> None:
        for snapshot in snapshots:
            cfg_dict = copy.deepcopy(snapshot["config"])
            cfg = PhysicsConfig(**cfg_dict)
            mc_engine = TwinEngine(copy.deepcopy(cfg))
            mc_engine.invalidate_grid()
            mc_engine.distill_gates()
            mc_payload = mc_engine.monte_carlo_precision_curve(
                x_range,
                int(cfg.precision_photons),
                int(cfg.precision_mc_repeats),
            )
            snapshot["mc"] = {
                "f_value": np.array(mc_payload["f_value"], copy=True),
                "efficiency": np.array(mc_payload["efficiency"], copy=True),
                "mean_tau": np.array(mc_payload["mean_tau"], copy=True),
                "std_tau": np.array(mc_payload["std_tau"], copy=True),
                "compatible": np.array(mc_payload["compatible"], copy=True),
                "f_ci_lower": np.array(mc_payload["f_ci_lower"], copy=True),
                "f_ci_upper": np.array(mc_payload["f_ci_upper"], copy=True),
                "efficiency_ci_lower": np.array(mc_payload["efficiency_ci_lower"], copy=True),
                "efficiency_ci_upper": np.array(mc_payload["efficiency_ci_upper"], copy=True),
            }
            snapshot["accuracy"] = {
                "mean": np.array(mc_payload["mean_tau"], copy=True),
                "std": np.array(mc_payload["std_tau"], copy=True),
            }

    def run(self):
        try:
            cfg = copy.deepcopy(self.config)
            cfg.b_interrupt = False
            opt_engine = TwinEngine(copy.deepcopy(cfg))
            self._opt_engine = opt_engine
            preview_engine = TwinEngine(copy.deepcopy(cfg))
            x_range = self._build_x_range(cfg)
            _, ideal_f = preview_engine.compute_ideal_reference(x_range, int(cfg.precision_photons))
            objective_mode = str(getattr(cfg, "optimization_objective", "fisher_information")).lower()
            reference_area, _ = preview_engine._excitation_area_and_peak(cfg)

            baseline_cfg = self._resolve_start_partition_cfg(cfg)
            baseline_engine = TwinEngine(copy.deepcopy(baseline_cfg))
            baseline_fi, baseline_f = baseline_engine.compute_fisher_info(x_range, int(baseline_cfg.precision_photons))
            baseline_objective = (
                float(np.nanmean(baseline_f)) if np.any(np.isfinite(baseline_f)) else np.inf
            )
            if objective_mode != "fisher_information":
                baseline_peak_eff = baseline_engine._peak_efficiency_from_f_values(baseline_f)
                baseline_objective = 1.0 / max(
                    baseline_peak_eff * baseline_engine._throughput_metric(baseline_cfg, reference_area),
                    1e-12,
                )
            baseline_snapshot = self._build_snapshot(
                preview_engine,
                baseline_cfg,
                x_range,
                "Step 1: Start",
                np.asarray(baseline_cfg.gate_edges, dtype=float),
                baseline_f,
                baseline_fi,
                objective=baseline_objective,
                min_f=float(np.nanmin(baseline_f)) if np.any(np.isfinite(baseline_f)) else np.nan,
                step=0,
                note="baseline",
            )
            self.baseline_ready.emit({
                "x_range": np.array(x_range, copy=True),
                "ideal_f": np.array(ideal_f, copy=True),
                "baseline": self._clone_snapshot(baseline_snapshot),
            })

            progress_records: List[Dict[str, Any]] = []
            objective_history = [baseline_snapshot["objective"]]
            min_f_history = [baseline_snapshot["min_f"]]
            realtime_enabled = bool(getattr(cfg, "optimization_realtime_visualization", False))

            def on_progress(payload: Dict[str, Any]):
                step_number = len(progress_records) + 1
                record = self._build_progress_record(payload, step_number)
                progress_records.append(record)
                objective_history.append(record["objective"])
                min_f_history.append(record["min_f"])
                current_snapshot = None
                if realtime_enabled:
                    current_snapshot = self._build_snapshot(
                        preview_engine,
                        PhysicsConfig(**record["config"]) if record.get("config") else cfg,
                        x_range,
                        record["label"],
                        record["edges"],
                        record["theory_f"],
                        record["theory_fisher"],
                        objective=record["objective"],
                        min_f=record["min_f"],
                        step=record["step"],
                        note=record["note"],
                        include_background_curves=False,
                    )
                self.progress_ready.emit({
                    "iterations": np.arange(0, len(objective_history), dtype=int),
                    "objective_history": np.array(objective_history, copy=True),
                    "min_f_history": np.array(min_f_history, copy=True),
                    "current": self._clone_snapshot(current_snapshot) if current_snapshot is not None else None,
                })

            workflow_result = opt_engine.run_optimization_workflow(progress_callback=on_progress)
            final_cfg = PhysicsConfig(**workflow_result["final_config"])
            best_edges = np.asarray(final_cfg.gate_edges, dtype=float)
            best_j = float(workflow_result["best_objective"])
            final_engine = TwinEngine(copy.deepcopy(final_cfg))
            final_fi, final_f = final_engine.compute_fisher_info(x_range, int(final_cfg.precision_photons))
            final_snapshot = self._build_snapshot(
                preview_engine,
                final_cfg,
                x_range,
                "Final",
                np.asarray(best_edges, dtype=float),
                final_f,
                final_fi,
                objective=float(best_j),
                min_f=float(np.nanmin(final_f)) if np.any(np.isfinite(final_f)) else np.nan,
                step=len(progress_records) + 1,
                note="final",
            )

            selected_progress_records = self._sample_snapshots(
                progress_records,
                max(0, int(getattr(cfg, "optimization_intermediate_steps", 6)) - 2),
            )
            selected_progress_snapshots = [
                self._build_snapshot(
                    preview_engine,
                    PhysicsConfig(**record["config"]) if record.get("config") else cfg,
                    x_range,
                    record["label"],
                    record["edges"],
                    record["theory_f"],
                    record["theory_fisher"],
                    objective=record["objective"],
                    min_f=record["min_f"],
                    step=record["step"],
                    note=record["note"],
                )
                for record in selected_progress_records
            ]
            if selected_progress_snapshots:
                final_edges = np.asarray(best_edges, dtype=float)
                if np.allclose(
                    np.asarray(selected_progress_snapshots[-1]["config"]["gate_edges"], dtype=float),
                    final_edges,
                    rtol=1e-9,
                    atol=1e-9,
                ):
                    selected_progress_snapshots.pop()
            selected = [baseline_snapshot] + selected_progress_snapshots + [final_snapshot]
            if bool(getattr(cfg, "optimization_validate_mc_intermediates", False)):
                self._attach_mc_validation(selected, x_range)

            objective_series = list(objective_history)
            min_f_series = list(min_f_history)
            if not progress_records or not np.allclose(np.asarray(progress_records[-1]["edges"], dtype=float), np.asarray(best_edges, dtype=float), rtol=1e-9, atol=1e-9):
                objective_series.append(final_snapshot["objective"])
                min_f_series.append(final_snapshot["min_f"])

            self.result_ready.emit({
                "x_range": np.array(x_range, copy=True),
                "ideal_f": np.array(ideal_f, copy=True),
                "objective_history": np.array(objective_series, copy=True),
                "min_f_history": np.array(min_f_series, copy=True),
                "snapshots": [self._clone_snapshot(item) for item in selected],
                "final_snapshot": self._clone_snapshot(final_snapshot),
                "final_config": copy.deepcopy(final_cfg.model_dump() if hasattr(final_cfg, "model_dump") else final_cfg.dict()),
                "best_edges": np.asarray(best_edges, dtype=float),
                "best_objective": float(best_j),
                "final_gate_count": int(max(0, len(np.asarray(best_edges, dtype=float)) - 1)),
                "final_excitation_summary": copy.deepcopy(workflow_result.get("final_excitation_summary", {})),
            })
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self._opt_engine = None
