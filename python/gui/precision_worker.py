import copy
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from backend.models import PhysicsConfig
from backend.profile_store import InstrumentProfileStore
from backend.twin_engine import TwinEngine
from gui.diagnostics_worker import DiagnosticsRefreshWorker


class PrecisionAnalysisWorker(QThread):
    progress_ready = pyqtSignal(object)
    result_ready = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, config: PhysicsConfig, target_label: str):
        super().__init__()
        self.config = copy.deepcopy(config)
        self.target_label = str(target_label)
        self.profile_store = InstrumentProfileStore()
        self._engine: Optional[TwinEngine] = None

    def request_interrupt(self):
        self.config.b_interrupt = True
        if self._engine is not None:
            self._engine.config.b_interrupt = True

    def _emit_progress(self, completed: int, total: int, message: str) -> None:
        self.progress_ready.emit(
            {
                "completed": int(completed),
                "total": int(max(total, 1)),
                "message": str(message),
            }
        )

    @staticmethod
    def _build_precision_x_range(cfg: PhysicsConfig) -> np.ndarray:
        engine = TwinEngine(copy.deepcopy(cfg))
        lower_bound, upper_bound = engine._get_cfg_param_bounds(getattr(cfg, "f_x_param", "tau1"))
        x_min = float(cfg.f_x_min)
        x_max = float(cfg.f_x_max)
        if lower_bound is not None:
            x_min = max(x_min, float(lower_bound))
            x_max = max(x_max, float(lower_bound))
        if upper_bound is not None:
            x_min = min(x_min, float(upper_bound))
            x_max = min(x_max, float(upper_bound))
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
    def _resolvability_enabled(cfg: PhysicsConfig) -> bool:
        return (
            str(getattr(cfg, "decay_model", "exponential")).lower() == "exponential"
            and int(getattr(cfg, "n_components", 1)) == 1
            and str(getattr(cfg, "f_x_param", "tau1")).lower() == "tau1"
        )

    @staticmethod
    def _format_rate_hz(rate_hz: float) -> str:
        rate = float(rate_hz)
        if rate >= 1e9:
            return f"{rate / 1e9:g} GHz"
        if rate >= 1e6:
            return f"{rate / 1e6:g} MHz"
        if rate >= 1e3:
            return f"{rate / 1e3:g} kHz"
        return f"{rate:g} Hz"

    def _format_sweep_label(self, param: str, value: Any, cfg: PhysicsConfig) -> str:
        if param == "laser_pulse_fwhm_ns":
            return f"Laser Pulse = {value:g} ns"
        if param == "detector_jitter_ps":
            return f"Detector Jitter = {value:g} ps"
        if param == "gate_edge_symmetric_ps":
            return f"Gate Rise/Fall = {value:g} ps"
        if param == "gate_edge_one_sharp_ps":
            mode = "sharp rise" if cfg.instr_sweep_gate_sharp_edge == "sharp_rise" else "sharp fall"
            return f"Gate Edge = {value:g} ps ({mode})"
        if param == "number_of_gates":
            return f"Number of Gates = {int(round(value))}"
        if param == "deadtime_fixed_countrate_ns":
            return f"Deadtime = {value:g} ns @ {cfg.instr_sweep_fixed_countrate_kcps:g} Kphotons/s"
        if param == "countrate_via_dwell_hz":
            return f"Count Rate = {self._format_rate_hz(value)}"
        if param == "countrate_fixed_deadtime_kcps":
            return f"Countrate = {value:g} Kphotons/s @ {cfg.instr_sweep_fixed_deadtime_ns:g} ns"
        if param == "multihit_capabilities":
            return f"Max events/period = {int(round(value))}"
        if param == "afterpulsing_probability_pct":
            return f"Afterpulsing = {value:g}%"
        if param == "dark_count_rate_cps":
            return f"Dark count rate = {value:g} cps"
        if param == "instrument_profile":
            return f"Profile = {value}"
        if param == "burst_edge_symmetric_ns":
            return f"Burst Rise/Fall = {value:g} ns"
        if param == "burst_edge_one_sharp_ns":
            mode = "sharp rise" if cfg.instr_sweep_burst_sharp_edge == "sharp_rise" else "sharp fall"
            return f"Burst Edge = {value:g} ns ({mode})"
        return f"{param} = {value:g}"

    def _apply_sweep_value(self, cfg: PhysicsConfig, param: str, value: Any) -> PhysicsConfig:
        cfg.metadata = dict(getattr(cfg, "metadata", {}))
        cfg.metadata.pop("force_precision_deadtime_mc", None)
        if param == "number_of_gates":
            t_start = 0.0
            if cfg.gate_start_mode == "irf_3sigma":
                jitter_ns = cfg.timing_jitter / 1000.0
                if cfg.irf_profile == "gaussian":
                    sigma_total = np.sqrt((cfg.irf_fwhm / 2.355) ** 2 + jitter_ns ** 2)
                    t_start = cfg.irf_position + 3.0 * sigma_total
                elif cfg.irf_profile == "ideal (dirac)":
                    t_start = cfg.irf_position + 3.0 * jitter_ns
                else:
                    t_start = cfg.irf_position + cfg.irf_fwhm + 3.0 * jitter_ns
            elif cfg.gate_start_mode == "free":
                t_start = cfg.gate_first_start
            t_end = cfg.period if getattr(cfg, "gate_end_mode", "period") == "period" else getattr(cfg, "gate_last_end", cfg.gate_edges[-1])
            edges = np.linspace(t_start, t_end, int(value) + 1)
            cfg.gate_edges = edges.tolist()
            cfg.gate_widths = np.diff(edges).tolist()
        elif param == "laser_pulse_fwhm_ns":
            cfg.irf_fwhm = float(value)
        elif param == "detector_jitter_ps":
            cfg.timing_jitter = float(value)
        elif param == "gate_edge_symmetric_ps":
            edge_ns = float(value) / 1000.0
            cfg.gate_rise = edge_ns
            cfg.gate_fall = edge_ns
        elif param == "gate_edge_one_sharp_ps":
            edge_ns = float(value) / 1000.0
            if cfg.instr_sweep_gate_sharp_edge == "sharp_rise":
                cfg.gate_rise = 0.0
                cfg.gate_fall = edge_ns
            else:
                cfg.gate_rise = edge_ns
                cfg.gate_fall = 0.0
        elif param == "deadtime_fixed_countrate_ns":
            cfg.detector_deadtime = float(value)
            cfg.metadata["force_precision_deadtime_mc"] = True
            target_rate_hz = max(float(cfg.instr_sweep_fixed_countrate_kcps) * 1000.0, 1.0)
            cfg.event_pixel_dwell_time_s = float(cfg.precision_photons) / target_rate_hz
            cfg.metadata["countrate_kcps"] = float(cfg.instr_sweep_fixed_countrate_kcps)
            cfg.metadata["target_countrate_hz"] = target_rate_hz
        elif param == "countrate_via_dwell_hz":
            target_rate_hz = max(float(value), 1.0)
            cfg.precision_photons = 1000
            cfg.a_photons = 1000.0
            cfg.event_pixel_dwell_time_s = float(cfg.precision_photons) / target_rate_hz
            cfg.metadata["target_countrate_hz"] = target_rate_hz
        elif param == "countrate_fixed_deadtime_kcps":
            cfg.detector_deadtime = float(cfg.instr_sweep_fixed_deadtime_ns)
            cfg.metadata["force_precision_deadtime_mc"] = True
            target_rate_hz = max(float(value) * 1000.0, 1.0)
            cfg.event_pixel_dwell_time_s = float(cfg.precision_photons) / target_rate_hz
            cfg.metadata["countrate_kcps"] = float(value)
            cfg.metadata["target_countrate_hz"] = target_rate_hz
        elif param == "multihit_capabilities":
            cfg.metadata["force_precision_deadtime_mc"] = True
            capacity = max(int(round(value)), 1)
            cfg.event_multihit_capacity = capacity
            cfg.b_multihit_mode = capacity > 1
        elif param == "afterpulsing_probability_pct":
            cfg.detector_afterpulsing_probability = max(float(value), 0.0) / 100.0
        elif param == "dark_count_rate_cps":
            cfg.detector_dark_count_rate_cps = max(float(value), 0.0)
        elif param == "instrument_profile":
            loaded = self.profile_store.load_profile(str(value), sanitize=True)
            loaded_cfg = loaded["config"]
            preserved = {
                "f_x_param": cfg.f_x_param,
                "f_x_min": cfg.f_x_min,
                "f_x_max": cfg.f_x_max,
                "f_x_steps": cfg.f_x_steps,
                "f_x_scale": cfg.f_x_scale,
                "precision_photons": cfg.precision_photons,
                "precision_validate_mc": cfg.precision_validate_mc,
                "precision_mc_repeats": cfg.precision_mc_repeats,
                "precision_compute_ci": cfg.precision_compute_ci,
                "precision_accuracy_pvalue": cfg.precision_accuracy_pvalue,
                "precision_bootstrap_samples": cfg.precision_bootstrap_samples,
                "precision_ci_level": cfg.precision_ci_level,
                "instr_sweep_active": cfg.instr_sweep_active,
                "instr_sweep_param": cfg.instr_sweep_param,
                "instr_sweep_vals": list(cfg.instr_sweep_vals),
            }
            new_cfg = PhysicsConfig(**(loaded_cfg.model_dump() if hasattr(loaded_cfg, "model_dump") else loaded_cfg.dict()))
            for key, val in preserved.items():
                setattr(new_cfg, key, val)
            new_cfg.active_instrument_profile = str(value)
            cfg.__dict__.update(new_cfg.__dict__)
        elif param == "burst_edge_symmetric_ns":
            cfg.burst_enabled = True
            cfg.burst_sub_rise_time = float(value)
            cfg.burst_sub_fall_time = float(value)
        elif param == "burst_edge_one_sharp_ns":
            cfg.burst_enabled = True
            edge_ns = float(value)
            if cfg.instr_sweep_burst_sharp_edge == "sharp_rise":
                cfg.burst_sub_rise_time = 0.0
                cfg.burst_sub_fall_time = edge_ns
            else:
                cfg.burst_sub_rise_time = edge_ns
                cfg.burst_sub_fall_time = 0.0
        elif hasattr(cfg, param):
            setattr(cfg, param, value)
        else:
            raise ValueError(f"Unsupported sweep parameter: {param}")
        return cfg

    def _build_precision_pdf_ensemble(self, engine: TwinEngine, cfg: PhysicsConfig, x_range: np.ndarray):
        original_config = engine.config
        try:
            curves = []
            for x_val in x_range:
                pdf_cfg = copy.deepcopy(cfg)
                engine.config = pdf_cfg
                engine._set_cfg_param(pdf_cfg.f_x_param, float(x_val))
                engine.distill_gates()
                pdf = np.array(engine.dt_pdf(engine.time_vector), copy=True)
                pdf = engine._effective_detected_pdf(
                    pdf,
                    float(getattr(pdf_cfg, "a_photons", 0.0)),
                    pdf_cfg,
                )
                curves.append(pdf)
            return curves
        finally:
            engine.config = original_config

    @staticmethod
    def _deadtime_method_display_name(cfg_like) -> str:
        method = str(getattr(cfg_like, "deadtime_correction_method", "none")).lower()
        method_map = {
            "isbaner_histogram": "Isbaner-lite",
            "isbaner_lite": "Isbaner-lite",
            "rapp_mcpdf": "Rapp (MCPDF-lite)",
            "rapp_inspired_inverse": "Rapp (MCPDF-lite)",
            "rapp_mcpdf_full": "Rapp (MCPDF-full)",
            "rapp_stationary": "Rapp (MCPDF-full)",
            "rapp_mchc": "Rapp (MCHC-lite)",
            "rapp_mchc_full": "Rapp (MCHC-full)",
        }
        return method_map.get(method, "Dead-time")

    def _deadtime_corrected_series_label(self, cfg_like, base_label: str) -> str:
        return f"{base_label} ({self._deadtime_method_display_name(cfg_like)} corrected)"

    @staticmethod
    def _selected_photon_budget(cfg: PhysicsConfig, collected_budget, engine: TwinEngine):
        total_budget = float(max(getattr(cfg, "precision_photons", 0), 0.0))
        mode = str(getattr(cfg, "optimization_f_photon_basis", "period")).lower()
        collected = np.asarray(collected_budget, dtype=float)
        if mode == "collected":
            return np.maximum(collected, 0.0)
        if mode == "all":
            return total_budget
        return total_budget * float(engine._acquisition_period_fraction(cfg))

    @classmethod
    def _rescale_f_from_conditional(cls, x_range, f_conditional, collected_budget, cfg: PhysicsConfig, engine: TwinEngine):
        f_cond = np.asarray(f_conditional, dtype=float)
        collected = np.asarray(collected_budget, dtype=float)
        target_budget = np.asarray(cls._selected_photon_budget(cfg, collected, engine), dtype=float)
        if target_budget.ndim == 0:
            target_budget = np.full_like(collected, float(target_budget))
        scale = np.full_like(f_cond, np.nan, dtype=float)
        valid = np.isfinite(f_cond) & np.isfinite(collected) & (collected > 0.0) & np.isfinite(target_budget) & (target_budget >= 0.0)
        scale[valid] = np.sqrt(target_budget[valid] / collected[valid])
        out = np.full_like(f_cond, np.nan, dtype=float)
        out[valid] = f_cond[valid] * scale[valid]
        return out

    @classmethod
    def _display_mc_payload(cls, mc_payload, cfg: PhysicsConfig, engine: TwinEngine):
        if mc_payload is None:
            return None
        payload = copy.deepcopy(mc_payload)
        f_cond = payload.get("f_value_conditional")
        survival = payload.get("survival_eta")
        if f_cond is None or survival is None:
            return payload
        f_cond_arr = np.asarray(f_cond, dtype=float)
        survival_arr = np.asarray(survival, dtype=float)
        total_budget = float(max(getattr(cfg, "precision_photons", 0), 0.0))
        collected_budget = total_budget * survival_arr
        f_eff = cls._rescale_f_from_conditional(
            np.arange(len(f_cond_arr), dtype=float),
            f_cond_arr,
            collected_budget,
            cfg,
            engine,
        )
        payload["f_value"] = f_eff
        payload["f_value_effective"] = np.array(f_eff, copy=True)
        with np.errstate(divide="ignore", invalid="ignore"):
            payload["efficiency"] = np.clip(1.0 / np.square(np.maximum(f_eff, 1e-12)), 0.0, 1.0)
        if payload.get("f_ci_lower") is not None and payload.get("f_ci_upper") is not None:
            f_ci_lower = np.asarray(payload["f_ci_lower"], dtype=float)
            f_ci_upper = np.asarray(payload["f_ci_upper"], dtype=float)
            valid = np.isfinite(f_cond_arr) & (f_cond_arr > 0)
            scale = np.full_like(f_cond_arr, np.nan, dtype=float)
            scale[valid] = f_eff[valid] / f_cond_arr[valid]
            payload["f_ci_lower"] = f_ci_lower * scale
            payload["f_ci_upper"] = f_ci_upper * scale
            with np.errstate(divide="ignore", invalid="ignore"):
                payload["efficiency_ci_lower"] = np.clip(1.0 / np.square(np.maximum(np.asarray(payload["f_ci_upper"], dtype=float), 1e-12)), 0.0, 1.0)
                payload["efficiency_ci_upper"] = np.clip(1.0 / np.square(np.maximum(np.asarray(payload["f_ci_lower"], dtype=float), 1e-12)), 0.0, 1.0)
        return payload

    def run(self):
        try:
            baseline_cfg = copy.deepcopy(self.config)
            self._engine = TwinEngine(copy.deepcopy(baseline_cfg))
            self._engine.config.b_interrupt = False
            x_range = self._build_precision_x_range(baseline_cfg)
            run_mc = bool(baseline_cfg.precision_validate_mc)
            sweep_values = baseline_cfg.instr_sweep_vals if (baseline_cfg.instr_sweep_active and baseline_cfg.instr_sweep_vals) else [None]
            total_steps = len(sweep_values) * len(x_range) * (1 + (1 if run_mc else 0))
            completed_steps = 0
            self._emit_progress(0, total_steps, "Preparing precision analysis...")

            _, f_ideal = self._engine.compute_ideal_reference(x_range, int(baseline_cfg.precision_photons))
            if str(getattr(baseline_cfg, "optimization_f_photon_basis", "collected")).lower() == "collected":
                f_ideal_conditional = np.array(f_ideal, copy=True)
            else:
                _, f_ideal_conditional = self._engine.compute_ideal_reference(
                    x_range,
                    int(baseline_cfg.precision_photons),
                    photon_basis_mode="collected",
                )
            baseline_reference_area, _ = self._engine._excitation_area_and_peak(baseline_cfg)
            baseline_reference_rate_hz = self._engine._configured_precision_rate_hz(baseline_cfg)

            plot_results: Dict[str, Dict[str, Any]] = {}
            accuracy_results: Dict[str, Dict[str, np.ndarray]] = {}
            run_series = []
            frames = []

            for raw_value in sweep_values:
                if self._engine.config.b_interrupt:
                    raise RuntimeError("Precision analysis interrupted.")

                sweep_cfg = copy.deepcopy(baseline_cfg)
                if raw_value is None:
                    label = "Current Configuration"
                else:
                    self._apply_sweep_value(sweep_cfg, baseline_cfg.instr_sweep_param, raw_value)
                    label = self._format_sweep_label(baseline_cfg.instr_sweep_param, raw_value, sweep_cfg)

                frame = DiagnosticsRefreshWorker._build_frame(sweep_cfg, label)
                frame["background_curves"] = self._build_precision_pdf_ensemble(self._engine, sweep_cfg, x_range)
                frames.append(copy.deepcopy(frame))

                self._engine.config = copy.deepcopy(sweep_cfg)
                self._engine.grid_templates = None
                self._engine.grid_tau_axis = None

                theory_f = np.full(len(x_range), np.nan)
                theory_fi = np.full(len(x_range), np.nan)
                throughput_scale = float(
                    self._engine._throughput_metric(
                        sweep_cfg,
                        float(baseline_reference_area),
                        reference_precision_rate_hz=baseline_reference_rate_hz,
                    )
                )
                theory_label = "Theory" if raw_value is None else f"Theory | {label}"

                def theory_callback(point_idx, fisher_val, f_val):
                    nonlocal completed_steps
                    theory_fi[point_idx] = fisher_val
                    theory_f[point_idx] = f_val
                    completed_steps += 1
                    self._emit_progress(
                        completed_steps,
                        total_steps,
                        f"Precision theory: {label} ({point_idx + 1}/{len(x_range)})",
                    )

                _, theory_final = self._engine.compute_fisher_info(
                    x_range,
                    int(sweep_cfg.precision_photons),
                    point_callback=theory_callback,
                    photon_basis_mode=getattr(sweep_cfg, "optimization_f_photon_basis", "period"),
                )
                theory_f = np.array(theory_final, copy=True)
                if str(getattr(sweep_cfg, "optimization_f_photon_basis", "collected")).lower() == "collected":
                    theory_f_conditional = np.array(theory_f, copy=True)
                else:
                    _, theory_conditional = self._engine.compute_fisher_info(
                        x_range,
                        int(sweep_cfg.precision_photons),
                        photon_basis_mode="collected",
                    )
                    theory_f_conditional = np.array(theory_conditional, copy=True)

                plot_results[theory_label] = {
                    "y": theory_f,
                    "conditional_f": np.array(theory_f_conditional, copy=True),
                    "photon_count": float(getattr(sweep_cfg, "precision_photons", 0.0)),
                    "resolvability_enabled": self._resolvability_enabled(sweep_cfg),
                    "throughput_scale": throughput_scale,
                }

                corrected_theory = None
                method = str(getattr(sweep_cfg, "deadtime_correction_method", "none")).lower()
                if method != "none":
                    corrected_fi, corrected_f, correction = self._engine.compute_deadtime_corrected_fisher_info(
                        np.asarray(x_range, dtype=float),
                        int(sweep_cfg.precision_photons),
                        correction_method=method,
                    )
                    if bool(correction.get("applied", False)):
                        corrected_theory = {
                            "fisher_info": np.asarray(corrected_fi, dtype=float),
                            "f_value": np.asarray(corrected_f, dtype=float),
                            "correction": correction,
                        }
                        corrected_label = self._deadtime_corrected_series_label(sweep_cfg, theory_label)
                        plot_results[corrected_label] = {
                            "y": np.asarray(corrected_theory["f_value"], dtype=float),
                            "conditional_f": np.asarray(corrected_theory["f_value"], dtype=float),
                            "photon_count": float(getattr(sweep_cfg, "precision_photons", 0.0)),
                            "resolvability_enabled": self._resolvability_enabled(sweep_cfg),
                            "throughput_scale": throughput_scale,
                        }

                mc_payload = None
                if run_mc and not self._engine.config.b_interrupt:
                    mc_label = "Monte Carlo" if raw_value is None else f"Monte Carlo | {label}"

                    def mc_callback(point_idx, mean_tau, std_tau, f_val, p_eff, p_value, compatible,
                                    f_ci_low, f_ci_high, eff_ci_low, eff_ci_high):
                        nonlocal completed_steps
                        completed_steps += 1
                        self._emit_progress(
                            completed_steps,
                            total_steps,
                            f"Monte Carlo validation: {label} ({point_idx + 1}/{len(x_range)})",
                        )

                    mc_payload = self._engine.monte_carlo_precision_curve(
                        x_range,
                        int(sweep_cfg.precision_photons),
                        int(sweep_cfg.precision_mc_repeats),
                        point_callback=mc_callback,
                    )
                    plot_results[mc_label] = {
                        "y": np.array(mc_payload["f_value"], copy=True),
                        "conditional_f": np.array(mc_payload.get("f_value_conditional", mc_payload["f_value"]), copy=True),
                        "conditional_f_ci_lower": np.array(mc_payload.get("f_ci_lower_conditional", np.full(len(x_range), np.nan)), copy=True),
                        "conditional_f_ci_upper": np.array(mc_payload.get("f_ci_upper_conditional", np.full(len(x_range), np.nan)), copy=True),
                        "photon_count": float(getattr(sweep_cfg, "precision_photons", 0.0)),
                        "resolvability_enabled": self._resolvability_enabled(sweep_cfg),
                        "compatible": np.array(mc_payload["compatible"], copy=True),
                        "f_ci_lower": np.array(mc_payload["f_ci_lower"], copy=True),
                        "f_ci_upper": np.array(mc_payload["f_ci_upper"], copy=True),
                        "efficiency_ci_lower": np.array(mc_payload["efficiency_ci_lower"], copy=True),
                        "efficiency_ci_upper": np.array(mc_payload["efficiency_ci_upper"], copy=True),
                        "throughput_scale": throughput_scale,
                    }
                    accuracy_results[label] = {
                        "mean": np.array(mc_payload["mean_tau"], copy=True),
                        "std": np.array(mc_payload["std_tau"], copy=True),
                    }
                    corrected_mc_payload = (mc_payload.get("deadtime_correction") or {}).get("monte_carlo_corrected")
                    if corrected_mc_payload is not None:
                        corrected_mc_display = self._display_mc_payload(corrected_mc_payload, sweep_cfg, self._engine)
                        corrected_mc_label = self._deadtime_corrected_series_label(sweep_cfg, mc_label)
                        plot_results[corrected_mc_label] = {
                            "y": np.asarray(corrected_mc_display["f_value"], dtype=float),
                            "conditional_f": np.asarray(corrected_mc_display.get("f_value_conditional", corrected_mc_display["f_value"]), dtype=float),
                            "conditional_f_ci_lower": np.asarray(corrected_mc_display.get("f_ci_lower_conditional", np.full(len(x_range), np.nan)), dtype=float),
                            "conditional_f_ci_upper": np.asarray(corrected_mc_display.get("f_ci_upper_conditional", np.full(len(x_range), np.nan)), dtype=float),
                            "photon_count": float(getattr(sweep_cfg, "precision_photons", 0.0)),
                            "resolvability_enabled": self._resolvability_enabled(sweep_cfg),
                            "compatible": np.asarray(corrected_mc_display["compatible"], dtype=bool),
                            "f_ci_lower": np.asarray(corrected_mc_display["f_ci_lower"], dtype=float),
                            "f_ci_upper": np.asarray(corrected_mc_display["f_ci_upper"], dtype=float),
                            "efficiency_ci_lower": np.asarray(corrected_mc_display["efficiency_ci_lower"], dtype=float),
                            "efficiency_ci_upper": np.asarray(corrected_mc_display["efficiency_ci_upper"], dtype=float),
                            "throughput_scale": throughput_scale,
                        }
                        accuracy_results[self._deadtime_corrected_series_label(sweep_cfg, label)] = {
                            "mean": np.asarray(corrected_mc_display["mean_tau"], dtype=float),
                            "std": np.asarray(corrected_mc_display["std_tau"], dtype=float),
                        }

                run_series.append(
                    {
                        "label": label,
                        "theory_fisher": np.array(theory_fi, copy=True),
                        "theory_f": np.array(theory_f, copy=True),
                        "theory_f_conditional": np.array(theory_f_conditional, copy=True),
                        "throughput_scale": throughput_scale,
                        "mc": mc_payload,
                        "diagnostics_frame": copy.deepcopy(frame),
                        "config": copy.deepcopy(sweep_cfg),
                        "corrected_theory": copy.deepcopy(corrected_theory),
                    }
                )

            report = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "x_range": np.array(x_range, copy=True),
                "ideal_f": np.array(f_ideal, copy=True),
                "ideal_f_conditional": np.array(f_ideal_conditional, copy=True),
                "series": run_series,
                "x_label": self.target_label,
                "config": copy.deepcopy(baseline_cfg),
            }
            self.result_ready.emit(
                {
                    "report": report,
                    "plot_results": plot_results,
                    "accuracy_results": accuracy_results,
                    "frames": frames,
                    "x_range": np.array(x_range, copy=True),
                    "ideal_f": np.array(f_ideal, copy=True),
                    "ideal_f_conditional": np.array(f_ideal_conditional, copy=True),
                    "target_label": self.target_label,
                    "ci_level": float(getattr(baseline_cfg, "precision_ci_level", 99.7)),
                    "precision_photons": float(getattr(baseline_cfg, "precision_photons", 0.0)),
                }
            )
        except Exception as exc:
            self.failed.emit(str(exc))
