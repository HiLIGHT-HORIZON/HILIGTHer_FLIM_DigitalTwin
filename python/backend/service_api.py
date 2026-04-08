import copy
import os
import json
import sys
from typing import Dict, Any, Optional, List

import numpy as np

from .gui_schema import get_gui_schema
from .instrument_spec_ingest import load_instrument_source, infer_instrument_profile_patch
from .models import PhysicsConfig, UnifiedState
from .profile_store import InstrumentProfileStore
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
        self.profile_store = InstrumentProfileStore()
        # Find data directory relative to this service file
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        self.lock_file = os.path.join(self.data_dir, "app_locks.json")

    def _check_access(self, mcp_context=False):
        """Verify if the requested interface is currently locked by the master GUI."""
        if not os.path.exists(self.lock_file):
            return
        try:
            with open(self.lock_file, "r") as f:
                locks = json.load(f)
        except (json.JSONDecodeError, IOError):
            return

        if mcp_context and locks.get("mcp_server_stopped", False):
            raise PermissionError("Access Denied: HiLIGHTer MCP server is STOPPED.")
        if locks.get("backend_api_locked", False):
            raise PermissionError("Access Denied: HiLIGHTer Backend API is LOCKED.")

    def get_status(self) -> Dict[str, Any]:
        self._check_access(mcp_context=True) # Usually called via MCP
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
        self._check_access()
        cfg = self.engine.config
        return cfg.model_dump() if hasattr(cfg, "model_dump") else cfg.dict()

    def update_config(self, config_patch: Dict[str, Any]) -> Dict[str, Any]:
        self._check_access()
        cfg_dict = self.get_config()
        cfg_dict.update(config_patch)
        self.engine.config = PhysicsConfig(**cfg_dict)
        self.engine.invalidate_grid()
        self.engine.distill_gates()
        return self.get_config()

    def get_gui_schema(self) -> Dict[str, Any]:
        return get_gui_schema()

    def _vendors_info_dir(self) -> str:
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "docs", "vendors_info")

    def list_vendor_sources(self) -> Dict[str, Any]:
        self._check_access(mcp_context=True)
        vendors_dir = os.path.abspath(self._vendors_info_dir())
        items = []
        if os.path.isdir(vendors_dir):
            for filename in sorted(os.listdir(vendors_dir)):
                path = os.path.join(vendors_dir, filename)
                if not os.path.isfile(path):
                    continue
                items.append(
                    {
                        "name": filename,
                        "path": path,
                        "size_bytes": int(os.path.getsize(path)),
                    }
                )
        return {"vendors_info_dir": vendors_dir, "sources": items}

    def read_vendor_source(self, source_name: str, max_chars: int = 24000) -> Dict[str, Any]:
        self._check_access(mcp_context=True)
        source_name = os.path.basename(str(source_name).strip())
        if not source_name:
            raise ValueError("source_name cannot be empty.")
        path = os.path.join(os.path.abspath(self._vendors_info_dir()), source_name)
        payload = load_instrument_source(path, max_chars=max_chars)
        inferred = infer_instrument_profile_patch(payload.text)
        return {
            "source": source_name,
            "path": path,
            "source_kind": payload.source_kind,
            "content_type": payload.content_type,
            "suggested_profile_patch": inferred.get("patch", {}),
            "evidence": inferred.get("evidence", {}),
            "text_excerpt": payload.text[:4000],
        }

    def get_instrument_profile_schema(self) -> Dict[str, Any]:
        defaults = PhysicsConfig()
        default_dict = defaults.model_dump() if hasattr(defaults, "model_dump") else defaults.dict()
        focus_fields = {
            "label": "Human-readable instrument profile name.",
            "period": "Laser repetition period in ns.",
            "irf_profile": "Laser/IRF profile family: gaussian, rectangular, ideal (dirac), or free-form.",
            "irf_fwhm": "Laser pulse or IRF width in ns.",
            "irf_position": "Laser/IRF timing offset in ns.",
            "timing_jitter": "Detector/electronics timing jitter in ps.",
            "detector_deadtime": "Detector or electronics dead time in ns.",
            "detector_dark_count_rate_cps": "Detector dark count rate in counts/s.",
            "b_multihit_mode": "Whether multiple events per repetition period are permitted.",
            "event_multihit_capacity": "Optional finite event capacity per period; null means unlimited.",
            "gate_type": "equal or custom.",
            "gate_edges": "Gate boundaries in ns.",
            "gate_collection_mode": "histogram or sequential.",
            "gate_overlap_mode": "jitter_only, never, or allow.",
            "gate_overlap_effect": "exclusive, duplicate_events, or independent_duplicates.",
            "event_pixel_dwell_time_s": "Pixel dwell time in seconds for event-driven rate effects.",
        }
        return {
            "schema_version": 2,
            "profile_type": "instrument_definition",
            "top_level_required": ["schema_version", "profile_type", "name", "config"],
            "top_level_optional": ["description", "metadata", "created_at", "updated_at"],
            "config_focus_fields": focus_fields,
            "default_config_excerpt": {key: default_dict.get(key) for key in focus_fields if key in default_dict},
        }

    def _build_instrument_profile_questions(self, merged_patch: Dict[str, Any]) -> List[Dict[str, Any]]:
        defaults = PhysicsConfig()
        questions: List[Dict[str, Any]] = []

        def add_question(field: str, prompt: str, suggested_value: Any = None, rationale: str = ""):
            if field in merged_patch:
                return
            questions.append(
                {
                    "field": field,
                    "prompt": prompt,
                    "suggested_value": suggested_value,
                    "rationale": rationale,
                }
            )

        add_question("period", "What repetition rate or period should the instrument use?", None, "Needed to define the acquisition window and gate placement.")
        add_question("irf_profile", "Which laser/IRF pulse shape should be assumed?", defaults.irf_profile, "Use a common pulse-family only if the vendor source does not specify it.")
        add_question("irf_fwhm", "What laser pulse width or IRF FWHM should be used?", defaults.irf_fwhm, "Needed to model reconvolution and timing blur.")
        add_question("timing_jitter", "What detector/electronics timing jitter should be used (ps)?", defaults.timing_jitter, "If only a typical TTS/jitter figure is available, confirm that value.")
        add_question("detector_deadtime", "What detector or electronics dead time should be used (ns)?", defaults.detector_deadtime, "Required for rate-dependent losses and distortion.")
        add_question("detector_dark_count_rate_cps", "What detector dark count rate should be used (counts/s)?", defaults.detector_dark_count_rate_cps, "Use a typical value only with user confirmation.")
        add_question("b_multihit_mode", "Should multiple photon events per period be allowed?", defaults.b_multihit_mode, "TCSPC electronics often support multihit, but this should be confirmed.")
        add_question("event_multihit_capacity", "If multihit is finite, what is the maximum events per period?", None, "Leave null for unlimited unless the hardware documents a limit.")
        if "gate_edges" not in merged_patch and "gate_type" not in merged_patch:
            questions.append(
                {
                    "field": "gate_edges",
                    "prompt": "How should the time axis be discretized: equal TCSPC bins or a custom gate set?",
                    "suggested_value": "equal bins across the repetition period",
                    "rationale": "Electronics specs often give channels/bins rather than explicit gate edges.",
                }
            )
        return questions

    def draft_instrument_profile(
        self,
        profile_name: str,
        sources: Optional[List[str]] = None,
        component_names: Optional[List[str]] = None,
        description: str = "",
        max_chars: int = 24000,
    ) -> Dict[str, Any]:
        self._check_access(mcp_context=True)
        source_list = [str(item).strip() for item in (sources or []) if str(item).strip()]
        components = [str(item).strip() for item in (component_names or []) if str(item).strip()]
        if not source_list:
            raise ValueError("Provide at least one source path or vendor document name.")

        vendors_dir = os.path.abspath(self._vendors_info_dir())
        merged_patch: Dict[str, Any] = {}
        evidence_by_source: Dict[str, Any] = {}
        source_summaries: List[Dict[str, Any]] = []
        for source in source_list:
            resolved = source
            if not os.path.isabs(resolved):
                candidate = os.path.join(vendors_dir, os.path.basename(source))
                if os.path.exists(candidate):
                    resolved = candidate
            payload = load_instrument_source(resolved, max_chars=max_chars)
            inferred = infer_instrument_profile_patch(payload.text)
            merged_patch.update(dict(inferred.get("patch") or {}))
            evidence_by_source[os.path.basename(resolved)] = inferred.get("evidence", {})
            source_summaries.append(
                {
                    "source": resolved,
                    "kind": payload.source_kind,
                    "content_type": payload.content_type,
                    "text_excerpt": payload.text[:2500],
                }
            )

        defaults = PhysicsConfig()
        default_dict = defaults.model_dump() if hasattr(defaults, "model_dump") else defaults.dict()
        candidate_dict = copy.deepcopy(default_dict)
        candidate_dict.update(merged_patch)
        candidate_dict["label"] = str(profile_name)
        candidate_dict["active_instrument_profile"] = str(profile_name)
        cfg = PhysicsConfig(**candidate_dict)
        profile_payload = {
            "schema_version": 2,
            "profile_type": "instrument_definition",
            "name": str(profile_name),
            "description": str(description or ""),
            "metadata": {
                "components": components,
                "sources": source_list,
                "workflow": "mcp_draft",
            },
            "config": cfg.model_dump() if hasattr(cfg, "model_dump") else cfg.dict(),
        }
        return {
            "status": "draft_ready",
            "profile_name": str(profile_name),
            "components": components,
            "sources": source_summaries,
            "merged_patch": merged_patch,
            "evidence_by_source": evidence_by_source,
            "draft_profile_json": profile_payload,
            "missing_or_unconfirmed_specs": self._build_instrument_profile_questions(merged_patch),
            "profile_json_schema": self.get_instrument_profile_schema(),
            "notes": [
                "Ask the user to confirm every item in missing_or_unconfirmed_specs before finalizing the profile.",
                "Use common settings only when the vendor sources are silent, and record those assumptions in metadata.",
                "Finalize by calling finalize_instrument_profile with either the completed profile_json or a config_patch.",
            ],
        }

    def finalize_instrument_profile(
        self,
        profile_name: str,
        profile_json: Optional[Dict[str, Any]] = None,
        config_patch: Optional[Dict[str, Any]] = None,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        apply_profile: bool = True,
        save_profile: bool = True,
    ) -> Dict[str, Any]:
        self._check_access(mcp_context=True)
        base_config = {}
        if isinstance(profile_json, dict):
            base_config.update(dict(profile_json.get("config") or {}))
            if not description:
                description = str(profile_json.get("description", ""))
            profile_metadata = profile_json.get("metadata")
            if metadata is None and isinstance(profile_metadata, dict):
                metadata = dict(profile_metadata)
        base_config.update(dict(config_patch or {}))
        sanitized = self.profile_store.sanitize_config_dict(base_config)
        cfg = PhysicsConfig(**sanitized)
        cfg.label = str(profile_name)
        cfg.active_instrument_profile = str(profile_name)

        saved = False
        applied = False
        payload = None
        if save_profile:
            payload = self.profile_store.save_profile(profile_name, cfg, description=description, metadata=metadata)
            saved = True
        if apply_profile:
            self.engine.config = copy.deepcopy(cfg)
            self.engine.invalidate_grid()
            self.engine.distill_gates()
            applied = True

        return {
            "status": "profile_finalized",
            "profile_name": str(profile_name),
            "saved": saved,
            "applied": applied,
            "profile_payload": payload,
            "config_summary": {
                "label": cfg.label,
                "period_ns": float(cfg.period),
                "irf_profile": str(cfg.irf_profile),
                "irf_fwhm_ns": float(cfg.irf_fwhm),
                "timing_jitter_ps": float(cfg.timing_jitter),
                "detector_deadtime_ns": float(cfg.detector_deadtime),
                "dark_count_rate_cps": float(cfg.detector_dark_count_rate_cps),
                "multihit": bool(cfg.b_multihit_mode),
                "event_multihit_capacity": None if cfg.event_multihit_capacity is None else int(cfg.event_multihit_capacity),
                "n_gates": int(max(0, len(cfg.gate_edges) - 1)),
            },
        }

    def ingest_instrument_profile_source(
        self,
        source: str,
        profile_name: str,
        config_patch: Optional[Dict[str, Any]] = None,
        description: str = "",
        apply_profile: bool = True,
        save_profile: bool = True,
        max_chars: int = 24000,
    ) -> Dict[str, Any]:
        self._check_access()
        payload = load_instrument_source(source, max_chars=max_chars)
        inferred = infer_instrument_profile_patch(payload.text)
        suggested_patch = dict(inferred.get("patch") or {})
        merged_patch = dict(suggested_patch)
        merged_patch.update(dict(config_patch or {}))

        defaults = PhysicsConfig()
        default_dict = defaults.model_dump() if hasattr(defaults, "model_dump") else defaults.dict()
        default_dict.update(merged_patch)
        cfg = PhysicsConfig(**default_dict)
        cfg.label = str(profile_name)
        cfg.active_instrument_profile = str(profile_name)

        saved = False
        applied = False
        if save_profile:
            self.profile_store.save_profile(
                profile_name,
                cfg,
                description=description,
                metadata={
                    "source": source,
                    "source_kind": payload.source_kind,
                    "content_type": payload.content_type,
                    "extracted_evidence": inferred.get("evidence", {}),
                    "llm_supplied_patch": dict(config_patch or {}),
                },
            )
            saved = True

        if apply_profile:
            self.engine.config = copy.deepcopy(cfg)
            self.engine.invalidate_grid()
            self.engine.distill_gates()
            applied = True

        return {
            "status": "profile_created" if (saved or applied) else "source_analysed",
            "profile_name": str(profile_name),
            "saved": saved,
            "applied": applied,
            "source": {
                "location": payload.source,
                "kind": payload.source_kind,
                "content_type": payload.content_type,
            },
            "source_excerpt": payload.text[:4000],
            "suggested_profile_patch": suggested_patch,
            "applied_profile_patch": merged_patch,
            "evidence": inferred.get("evidence", {}),
            "config_summary": {
                "label": cfg.label,
                "period_ns": float(cfg.period),
                "laser_profile": str(cfg.irf_profile),
                "laser_width_ns": float(cfg.irf_fwhm),
                "jitter_ps": float(cfg.timing_jitter),
                "deadtime_ns": float(cfg.detector_deadtime),
                "n_gates": int(max(0, len(cfg.gate_edges) - 1)),
                "gate_type": str(cfg.gate_type),
                "multihit": bool(cfg.b_multihit_mode),
                "max_events_per_period": (
                    None if cfg.event_multihit_capacity is None else int(cfg.event_multihit_capacity)
                ),
            },
            "notes": [
                "Call this tool first without a detailed config_patch to inspect the extracted source text and suggested patch.",
                "Then call it again with a refined config_patch from the LLM if the heuristics need correction.",
            ],
        }

    def get_data_summary(self) -> Dict[str, Any]:
        self._check_access()
        raw = self.engine.raw_data
        tau_map = self.engine.tau_map
        return {
            "raw_data_shape": None if raw is None else list(raw.shape),
            "tau_map_shape": None if tau_map is None else list(tau_map.shape),
            "tau_mean": None if tau_map is None else float(np.nanmean(tau_map)),
            "tau_min": None if tau_map is None else float(np.nanmin(tau_map)),
            "tau_max": None if tau_map is None else float(np.nanmax(tau_map)),
            "validation_geometry": copy.deepcopy(self.engine.validation_metadata.get("geometry", {})),
            "analysis_warnings": list(getattr(self.engine, "last_analysis_warnings", [])),
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
        self._check_access()
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
        self._check_access()
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
        self._check_access()
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

    def run_validation_image(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._check_access()
        params = params or {}
        photon_budget = int(params.get("a_photons", self.engine.config.a_photons))
        target_repeats = int(params.get("image_mc_repeats", self.engine.config.image_mc_repeats))
        result = self.engine.generate_validation_image(n_photons=photon_budget, target_repeats=target_repeats)
        return {
            "status": "validation_image_ready",
            "geometry": copy.deepcopy(result["geometry"]),
            "x_values": np.asarray(result["x_values"], dtype=float).tolist(),
            "data_summary": self.get_data_summary(),
        }

    def fit_validation_image(self, method: Optional[str] = None) -> Dict[str, Any]:
        self._check_access()
        method = str(method or getattr(self.engine.config, "image_fit_method", "gridded_mle")).lower()
        self.engine.run_fit(method=method)
        g_map, s_map = self.engine.calculate_phasor()
        return {
            "status": "validation_fit_complete",
            "fit_method": method,
            "data_summary": self.get_data_summary(),
            "tau_map": None if self.engine.tau_map is None else self.engine.tau_map.tolist(),
            "phasor": {
                "g": None if g_map is None else np.asarray(g_map, dtype=float).tolist(),
                "s": None if s_map is None else np.asarray(s_map, dtype=float).tolist(),
            },
        }

    def run_precision(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._check_access()
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
            self.engine.config.a_photons = float(cfg.precision_photons)
            ideal_fi, ideal_f = self.engine.compute_ideal_reference(x_range, int(cfg.precision_photons))
            theory_fi, theory_f = self.engine.compute_fisher_info(
                x_range,
                int(cfg.precision_photons),
                photon_basis_mode=getattr(cfg, "optimization_f_photon_basis", "period"),
            )
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
            if str(getattr(cfg, "deadtime_correction_method", "none")).lower() != "none":
                corrected_fi, corrected_f, correction = self.engine.compute_deadtime_corrected_fisher_info(
                    x_range,
                    int(cfg.precision_photons),
                    correction_method=getattr(cfg, "deadtime_correction_method", "none"),
                )
                payload["deadtime_correction"] = {
                    "method": str(getattr(cfg, "deadtime_correction_method", "none")),
                    "theory": {
                        "fisher_info": np.asarray(corrected_fi, dtype=float).tolist(),
                        "f_value": np.asarray(corrected_f, dtype=float).tolist(),
                    },
                    "summary": {
                        "applied": bool(correction.get("applied", False)),
                        "note": str(correction.get("note", "")),
                    },
                }
            if cfg.precision_validate_mc:
                payload["monte_carlo"] = self.engine.monte_carlo_precision_curve(
                    x_range,
                    int(cfg.precision_photons),
                    int(cfg.precision_mc_repeats),
                )
            return payload
        finally:
            self.engine.config = baseline

    def run_optimization(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._check_access()
        params = params or {}
        cfg = copy.deepcopy(self.engine.config)
        if params:
            cfg_dict = cfg.model_dump() if hasattr(cfg, "model_dump") else cfg.dict()
            cfg_dict.update(params)
            cfg = PhysicsConfig(**cfg_dict)

        if not cfg.optimize_detection_gates:
            if not cfg.optimize_excitation_profile and not bool(getattr(cfg, "optimize_count_rate", False)):
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
            min_eff_history = []
            auc_eff_history = []
            throughput_history = []
            throughput_auc_history = []

            def on_progress(progress):
                objective_history.append(float(progress["objective"]))
                min_f_history.append(float(progress["min_f"]))
                min_eff_history.append(float(progress.get("peak_efficiency", np.nan)))
                auc_eff_history.append(float(progress.get("auc_efficiency", np.nan)))
                throughput_history.append(float(progress.get("throughput_metric", np.nan)))
                throughput_auc_history.append(float(progress.get("throughput_auc", np.nan)))

            info = self.engine.run_optimization_workflow(progress_callback=on_progress)
            final_cfg = PhysicsConfig(**info["final_config"])
            best_edges = np.asarray(final_cfg.gate_edges, dtype=float)
            best_j = float(info["best_objective"])
            self.engine.config = copy.deepcopy(final_cfg)
            self.engine.invalidate_grid()
            theory_fi, theory_f = self.engine.compute_fisher_info(
                x_range,
                int(cfg.precision_photons),
                photon_basis_mode=getattr(cfg, "optimization_f_photon_basis", "period"),
            )
            return {
                "status": "success",
                "algorithm": str(
                    cfg.detection_optimization_algorithm
                    if cfg.optimize_detection_gates and not cfg.optimize_excitation_profile and not bool(getattr(cfg, "optimize_count_rate", False))
                    else f"excitation_{cfg.excitation_optimization_profile}"
                    if cfg.optimize_excitation_profile and not bool(getattr(cfg, "optimize_count_rate", False)) and not cfg.optimize_detection_gates
                    else "count_rate_scan"
                    if bool(getattr(cfg, "optimize_count_rate", False)) and not cfg.optimize_detection_gates and not cfg.optimize_excitation_profile
                    else "joint"
                ),
                "workflow": (
                    "joint"
                    if sum(1 for enabled in (cfg.optimize_detection_gates, cfg.optimize_excitation_profile, bool(getattr(cfg, "optimize_count_rate", False))) if enabled) > 1
                    else "detection"
                    if cfg.optimize_detection_gates
                    else "excitation"
                    if cfg.optimize_excitation_profile
                    else "count_rate"
                    if bool(getattr(cfg, "optimize_count_rate", False))
                    else "detection"
                ),
                "x_range": x_range.tolist(),
                "best_edges": np.asarray(best_edges, dtype=float).tolist(),
                "final_gate_count": int(max(0, len(np.asarray(best_edges, dtype=float)) - 1)),
                "best_objective": float(best_j),
                "objective_history": objective_history,
                "min_f_history": min_f_history,
                "min_eff_history": min_eff_history,
                "auc_eff_history": auc_eff_history,
                "throughput_history": throughput_history,
                "throughput_auc_history": throughput_auc_history,
                "final_theory": {
                    "fisher_info": np.asarray(theory_fi, dtype=float).tolist(),
                    "f_value": np.asarray(theory_f, dtype=float).tolist(),
                },
                "window_start": float(info["window_start"]),
                "window_end": float(info["window_end"]),
                "optimization_config": {
                    "optimize_detection_gates": bool(cfg.optimize_detection_gates),
                    "optimize_excitation_profile": bool(cfg.optimize_excitation_profile),
                    "optimize_count_rate": bool(getattr(cfg, "optimize_count_rate", False)),
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
                    "count_rate_optimization_min_kcps": float(getattr(cfg, "count_rate_optimization_min_kcps", 10.0)),
                    "count_rate_optimization_max_kcps": float(getattr(cfg, "count_rate_optimization_max_kcps", 1000.0)),
                    "count_rate_optimization_steps": int(getattr(cfg, "count_rate_optimization_steps", 24)),
                    "count_rate_optimization_scale": str(getattr(cfg, "count_rate_optimization_scale", "log")),
                    "count_rate_optimization_enforce_accuracy": bool(getattr(cfg, "count_rate_optimization_enforce_accuracy", True)),
                    "count_rate_optimization_max_bias_pct": float(getattr(cfg, "count_rate_optimization_max_bias_pct", 2.0)),
                },
                "final_config": final_cfg.model_dump() if hasattr(final_cfg, "model_dump") else final_cfg.dict(),
            }
        finally:
            self.engine.config = baseline

    def get_tau_map(self) -> Dict[str, Any]:
        self._check_access()
        if self.engine.tau_map is None:
            return {"data": None, "shape": None}
        return {"data": self.engine.tau_map.tolist(), "shape": list(self.engine.tau_map.shape)}

    def get_phasor_map(self, harmonic: int = 1) -> Dict[str, Any]:
        self._check_access()
        if self.engine.raw_data is None:
            return {"g": None, "s": None, "shape": None}
        g_map, s_map = self.engine.calculate_phasor(harmonic=harmonic)
        return {"g": g_map.tolist(), "s": s_map.tolist(), "shape": list(g_map.shape)}

    def get_theoretical_locus(self) -> Dict[str, Any]:
        self._check_access()
        g, s = self.engine.get_theoretical_locus()
        return {"g": g.tolist(), "s": s.tolist()}

    def get_pixel_analysis(self, y: int, x: int) -> Dict[str, Any]:
        self._check_access()
        return self.engine.get_pixel_fit_payload(y, x)

    def clear_workspace(self) -> Dict[str, Any]:
        self._check_access()
        self.engine.clear_workspace_data()
        return {"status": "workspace_cleared", "data_summary": self.get_data_summary()}

    def save_session(self, session_id: str) -> Dict[str, Any]:
        self._check_access()
        if self.engine.raw_data is None:
            return {"status": "no_data"}
        session_state = UnifiedState()
        session_state.config = self.engine.config  # compatibility with existing storage
        storage.save_state(session_id, session_state, self.engine.raw_data, self.engine.tau_map)
        return {"status": "saved", "session_id": session_id}

    def load_session(self, session_id: str) -> Dict[str, Any]:
        self._check_access()
        config, raw_data, tau_map = storage.load_state(session_id)
        self.engine.config = config
        self.engine.raw_data = raw_data
        self.engine.tau_map = tau_map
        self.engine.distill_gates()
        return {"status": "loaded", "session_id": session_id, "data_summary": self.get_data_summary()}
