import numpy as np
import copy
from math import erfc, sqrt
from scipy.interpolate import interp1d
from scipy.optimize import minimize, fmin
from scipy.signal import convolve
from scipy.special import erf
from typing import Optional, Tuple, List, Callable, Dict, Any
from .models import PhysicsConfig

try:
    from numba import njit
    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


@njit(cache=True)
def _simulate_deadtime_counts_numba(cdf, t_vec, gate_edges, t_rep, n_total, b_rate, td, b_multihit_mode, n_pulses):
    n_gates = len(gate_edges) - 1
    counts = np.zeros(n_gates, dtype=np.float64)
    lam_signal = n_total / n_pulses
    lam_bg = b_rate / n_pulses

    for _ in range(n_pulses):
        n_signals = np.random.poisson(lam_signal)
        n_bg = np.random.poisson(lam_bg)
        total_hits = n_signals + n_bg
        if total_hits <= 0:
            continue

        all_times = np.empty(total_hits, dtype=np.float64)

        for i in range(n_signals):
            u = np.random.random()
            idx = np.searchsorted(cdf, u)
            if idx >= len(t_vec):
                idx = len(t_vec) - 1
            all_times[i] = t_vec[idx]

        for i in range(n_bg):
            all_times[n_signals + i] = np.random.random() * t_rep

        all_times.sort()
        last_hit = -1e18

        for i in range(total_hits):
            t_hit = all_times[i]
            if t_hit < last_hit + td:
                continue

            for g in range(n_gates):
                if gate_edges[g] <= t_hit < gate_edges[g + 1]:
                    counts[g] += 1.0
                    break

            last_hit = t_hit
            if not b_multihit_mode:
                break

    return counts

class TwinEngine:
    """
    Core mathematical engine for the HILIGHTer Digital Twin.
    Handles gate distillation, gridded MLE fitting,
    and hardware non-ideality modeling.
    """
    def __init__(self, config: Optional[PhysicsConfig] = None):
        self.config = config or PhysicsConfig()
        self.raw_data = None  # (nY, nX, nGates)
        self.gate_shapes = None  # (nGates, nTime)
        self.time_vector = None  # (nTime,)
        self.laser_pulse = None  # {"t": [], "p": []}
        
        # Result Maps
        self.tau_map = None
        self.a_map = None
        self.b_map = None
        self.chi2_map = None
        
        # Calibration Data
        self.sweep_data = None # List of [t, counts] arrays
        self.fitted_sigma = 0.1 # [ns]
        
        # Fast Fitting Grid
        self.grid_templates = None # Pre-calculated gate signatures
        self.grid_tau_axis = None
        self.grid_signature = None

    def invalidate_grid(self):
        self.grid_templates = None
        self.grid_tau_axis = None
        self.grid_signature = None

    def _sync_grid_definition_from_precision_config(self):
        cfg = self.config
        f_min = float(cfg.f_x_min)
        f_max = float(cfg.f_x_max)
        n_steps = max(int(cfg.f_x_steps), 2)
        fine_factor = max(int(getattr(cfg, "grid_fine_factor", 100)), 1)
        use_log_grid = (
            str(cfg.f_x_scale).lower() == "log"
            and cfg.f_x_param in {"tau1", "tau2", "beta"}
            and f_min > 0
            and f_max > 0
        )

        if use_log_grid:
            step_ratio = (f_max / f_min) ** (1.0 / max(n_steps - 1, 1)) if f_max > f_min else 1.0
            pad_factor = max(step_ratio, 1.25)
            cfg.grid_tau_min = max(1e-6, f_min / pad_factor)
            cfg.grid_tau_max = max(cfg.grid_tau_min * 1.0001, f_max * pad_factor)
        else:
            coarse_step = (f_max - f_min) / max(n_steps - 1, 1)
            lower_pad = coarse_step if coarse_step > 0 else max(abs(f_min) * 0.1, 1e-6)
            upper_pad = coarse_step if coarse_step > 0 else max(abs(f_max) * 0.1, 1e-6)
            cfg.grid_tau_min = max(1e-6, f_min - lower_pad)
            cfg.grid_tau_max = f_max + upper_pad
        cfg.grid_steps = max(3, ((n_steps - 1) + 2) * fine_factor + 1)

    def _grid_signature(self):
        cfg = self.config
        return (
            cfg.grid_tau_min,
            cfg.grid_tau_max,
            cfg.grid_steps,
            cfg.grid_fine_factor,
            cfg.f_x_param,
            cfg.decay_model,
            cfg.n_components,
            tuple(cfg.taus[1:]),
            tuple(cfg.amplitudes),
            cfg.beta,
            cfg.background_level,
            cfg.use_eirf,
            cfg.irf_profile,
            cfg.irf_fwhm,
            cfg.irf_position,
            cfg.irf_rise_time,
            cfg.irf_fall_time,
            tuple(getattr(cfg, "irf_freeform_points", [])),
            cfg.burst_enabled,
            cfg.burst_sub_period,
            cfg.burst_sub_fwhm,
            cfg.burst_sub_rise_time,
            cfg.burst_sub_fall_time,
            cfg.b_decay_wrapping,
            tuple(cfg.gate_edges),
            cfg.gate_profile,
            cfg.gate_rise,
            cfg.gate_fall,
            cfg.gate_collection_mode,
            cfg.gate_overlap_mode,
            cfg.gate_overlap_ns,
            cfg.gate_overlap_effect,
            cfg.gate_wraparound,
            cfg.period,
            cfg.timing_jitter,
            cfg.dt_override,
            cfg.dt_input,
            cfg.f_x_scale,
        )

    def _use_raw_gate_statistics(self) -> bool:
        cfg = self.config
        return bool(
            getattr(cfg, "gate_collection_mode", "histogram") == "sequential"
            or getattr(cfg, "gate_overlap_mode", "jitter_only") == "never"
            or getattr(cfg, "gate_overlap_effect", "exclusive") == "independent_duplicates"
            or not getattr(cfg, "gate_wraparound", True)
        )

    def _collection_efficiency_scale(self, n_gates: Optional[int] = None) -> float:
        cfg = self.config
        if getattr(cfg, "gate_collection_mode", "histogram") == "sequential":
            if n_gates is None:
                n_gates = max(len(getattr(cfg, "gate_edges", [])) - 1, 1)
            return 1.0 / max(int(n_gates), 1)
        return 1.0

    def _exclusive_overlap_weights(self, values: np.ndarray, axis: int = 0) -> np.ndarray:
        values = np.asarray(values, dtype=float)
        sums = np.sum(values, axis=axis, keepdims=True)
        scale = np.ones_like(sums)
        mask = sums > 1.0
        scale[mask] = 1.0 / np.maximum(sums[mask], 1e-12)
        return values * scale

    def _statistical_gate_profiles(self, gate_profiles: Optional[np.ndarray] = None) -> np.ndarray:
        if gate_profiles is None:
            gate_profiles = self.gate_shapes
        overlap_effect = getattr(self.config, "gate_overlap_effect", "exclusive")
        if overlap_effect in {"exclusive", "duplicate_events"}:
            return self._exclusive_overlap_weights(gate_profiles, axis=0)
        return np.array(gate_profiles, copy=True)

    def ensure_grid_current(self):
        self._sync_grid_definition_from_precision_config()
        signature = self._grid_signature()
        if self.grid_templates is None or self.grid_tau_axis is None or self.grid_signature != signature:
            self.precalculate_grid()

    def _gaussian_kernel(self, sigma_ns: float, dt: float) -> Optional[np.ndarray]:
        """Returns a normalized Gaussian kernel sampled on the current time grid."""
        sigma_ns = float(max(sigma_ns, 0.0))
        dt = float(max(dt, 1e-9))
        if sigma_ns <= 0.0:
            return None

        half_width = max(int(np.ceil((4.0 * sigma_ns) / dt)), 1)
        t_kernel = np.arange(-half_width, half_width + 1, dtype=float) * dt
        kernel = np.exp(-(t_kernel ** 2) / (2.0 * sigma_ns ** 2))
        kernel_sum = np.sum(kernel)
        if kernel_sum <= 0:
            return None
        return kernel / kernel_sum

    def _apply_temporal_blur(self, values: np.ndarray, sigma_ns: float, dt: float) -> np.ndarray:
        """Applies Gaussian temporal blurring without changing array length."""
        kernel = self._gaussian_kernel(sigma_ns, dt)
        if kernel is None:
            return np.array(values, copy=True)
        return convolve(values, kernel, mode='same')

    def _gate_jitter_sigma_ns(self) -> float:
        """
        Effective gate-timing uncertainty.
        `timing_jitter` is the primary detector timing term; `skewness` is kept
        for MATLAB/reference compatibility and contributes as an additional RMS term.
        """
        cfg = self.config
        timing_sigma = max(float(getattr(cfg, "timing_jitter", 0.0)), 0.0) / 1000.0
        skew_sigma = max(float(getattr(cfg, "skewness", 0.0)), 0.0) / 1000.0
        return float(np.sqrt(timing_sigma ** 2 + skew_sigma ** 2))

    def _gate_anchor_start_ns(self) -> float:
        cfg = self.config
        jitter_ns = max(float(getattr(cfg, "timing_jitter", 0.0)), 0.0) / 1000.0
        mode = str(getattr(cfg, "gate_start_mode", "start")).lower()
        if mode == "irf_3sigma":
            profile = str(getattr(cfg, "irf_profile", "gaussian")).lower()
            if profile == "gaussian":
                sigma_base = max(float(getattr(cfg, "irf_fwhm", 0.0)), 0.0) / 2.35482
                sigma_total = np.sqrt((sigma_base ** 2) + (jitter_ns ** 2))
                return max(0.0, float(getattr(cfg, "irf_position", 0.0)) + (3.0 * sigma_total))
            if profile == "ideal (dirac)":
                return max(0.0, float(getattr(cfg, "irf_position", 0.0)) + (3.0 * jitter_ns))
            return max(
                0.0,
                float(getattr(cfg, "irf_position", 0.0))
                + float(getattr(cfg, "irf_fwhm", 0.0))
                + (3.0 * jitter_ns),
            )
        if mode == "free":
            return max(0.0, float(getattr(cfg, "gate_first_start", 0.0)))
        return 0.0

    def _gate_anchor_end_ns(self) -> float:
        cfg = self.config
        if str(getattr(cfg, "gate_end_mode", "period")).lower() == "free":
            return max(0.0, float(getattr(cfg, "gate_last_end", getattr(cfg, "period", 0.0))))
        return max(0.0, float(getattr(cfg, "period", 0.0)))

    def resolve_gate_edges(self) -> np.ndarray:
        """
        Resolve the effective gate-edge definition from the high-level gating state.
        This makes equal/custom anchoring a backend behavior rather than a GUI-only one.
        """
        cfg = self.config
        gate_type = str(getattr(cfg, "gate_type", "equal")).lower()
        start = self._gate_anchor_start_ns()
        end = self._gate_anchor_end_ns()
        existing_edges = np.asarray(getattr(cfg, "gate_edges", []) or [], dtype=float)
        n_gates = max(1, existing_edges.size - 1)

        if end <= start:
            end = start + max(float(getattr(cfg, "dt_input", 0.01)), 1e-3)

        if gate_type == "equal":
            edges = np.linspace(start, end, n_gates + 1, dtype=float)
        else:
            if existing_edges.size < 2:
                edges = np.linspace(start, end, n_gates + 1, dtype=float)
            else:
                edges = np.array(existing_edges, copy=True, dtype=float)
                if str(getattr(cfg, "gate_start_mode", "start")).lower() != "free":
                    edges[0] = start
                if str(getattr(cfg, "gate_end_mode", "period")).lower() != "free":
                    edges[-1] = end
                if np.any(np.diff(edges) <= 0):
                    edges = np.linspace(start, end, n_gates + 1, dtype=float)

        cfg.gate_edges = edges.tolist()
        cfg.gate_widths = np.diff(edges).tolist()
        return edges

    def distill_gates(self):
        """Standardizes gate generation within the measurement window defined by cfg.period."""
        cfg = self.config
        edges = self.resolve_gate_edges()
        dt = cfg.dt_override if (cfg.dt_override and cfg.dt_override > 0) else cfg.dt_input
        
        # Strict boundary: 0 to Period
        t_start = 0.0
        t_end = cfg.period
        self.time_vector = np.arange(t_start, t_end, dt)
        
        n_gates = len(edges) - 1
        n_time = len(self.time_vector)
        self.gate_shapes = np.zeros((n_gates, n_time))
        
        t = self.time_vector

        def edge_gate_profile(time_axis: np.ndarray, gate_start: float, gate_end: float) -> np.ndarray:
            rise_sigma = max(float(getattr(cfg, "gate_rise", 0.0)), 0.0)
            fall_sigma = max(float(getattr(cfg, "gate_fall", rise_sigma)), 0.0)

            # Gaussian CDF-based edges (sigma = rise/fall/jitter parameter)
            # The transition follows 0.5 * (1 + erf((t - mu) / (sqrt(2) * sigma)))
            if rise_sigma > 1e-6:
                start_edge = 0.5 * (1.0 + erf((time_axis - gate_start) / (np.sqrt(2.0) * rise_sigma)))
            else:
                start_edge = (time_axis >= gate_start).astype(float)

            if fall_sigma > 1e-6:
                end_edge = 0.5 * (1.0 - erf((time_axis - gate_end) / (np.sqrt(2.0) * fall_sigma)))
            else:
                end_edge = (time_axis < gate_end).astype(float)

            return start_edge * end_edge
        
        for i in range(n_gates):
            a, b = edges[i], edges[i+1]
            if getattr(cfg, "gate_overlap_mode", "jitter_only") == "allow" and i > 0:
                a = a - max(float(getattr(cfg, "gate_overlap_ns", 0.0)), 0.0)
            shape = edge_gate_profile(t, a, b)

            # If wrapping enabled, also check for tails from previous/next cycles
            if getattr(cfg, "gate_wraparound", True):
                trep = cfg.period
                shape += edge_gate_profile(t, a - trep, b - trep)
                shape += edge_gate_profile(t, a + trep, b + trep)

            self.gate_shapes[i, :] = np.clip(shape, 0, 1.0)

        gate_jitter_sigma = self._gate_jitter_sigma_ns()
        if gate_jitter_sigma > 0.0 and n_time > 1:
            dt = float(t[1] - t[0])
            for i in range(n_gates):
                blurred = self._apply_temporal_blur(self.gate_shapes[i, :], gate_jitter_sigma, dt)
                self.gate_shapes[i, :] = np.clip(blurred, 0.0, 1.0)

        overlap_mode = getattr(cfg, "gate_overlap_mode", "jitter_only")
        if overlap_mode == "never":
            support_mask = self.gate_shapes > np.exp(-4.5)
            overlap_columns = np.sum(support_mask, axis=0) > 1
            if np.any(overlap_columns):
                self.gate_shapes[:, overlap_columns] = 0.0

    def obj_func(self, tau: float, obs: np.ndarray, fixed_bg: float) -> Tuple[float, float, float]:
        """
        Calculates SSQ, Amplitude (a), and Background (b) for a given tau.
        Matches mathematical objective for time-gated lifetime estimation.
        """
        if tau <= 0:
            return 1e15, 0.0, 0.0
            
        # 1. Build Signal Profile Pj(tau)
        t = self.time_vector
        decay = np.exp(-t / tau)
        
        if self.config.use_eirf and self.laser_pulse:
            l_interp = interp1d(self.laser_pulse["t"], self.laser_pulse["p"], 
                                kind='linear', fill_value=0, bounds_error=False)(t)
            l_interp /= np.sum(l_interp)
            decay = convolve(decay, l_interp, mode='same')
            
        pj = self.gate_shapes @ decay
        pj /= np.sum(pj)
        
        # 2. Build Background Profile Qj
        wj = np.sum(self.gate_shapes, axis=1)
        w_total = np.sum(wj)
        qj = wj / w_total
        
        d_total = np.sum(obs)
        
        # 3. Determine Background Fraction 'k'
        if self.config.bg_option == "fix_manual":
            k = min(1.0, self.config.fixed_bg_value / max(d_total, 1.0))
        elif self.config.bg_option in ["gate4", "measurement"]:
            k = min(1.0, fixed_bg / max(d_total, 1.0))
        else: # 'fit' mode
            vj = qj - pj
            offset = d_total * pj
            slope = d_total * vj
            
            weights = 1.0 / np.maximum(offset, 1.0)
            k = np.sum(weights * (obs - offset) * slope) / (np.sum(weights * slope**2) + 1e-10)
            k = max(0.0, min(1.0, k))
            
        a = d_total * (1.0 - k)
        b = (d_total * k) / max(w_total, 1e-10)
        
        pred = a * pj + b * wj
        residuals = obs - pred
        weights = 1.0 / np.maximum(pred, 1.0)
        ssq = np.sum(residuals**2 * weights)
        return ssq, a, b
        
    def precalculate_grid(self):
        """Generates a library of gate signatures for fast gridded MLE lookup."""
        cfg = self.config
        self._sync_grid_definition_from_precision_config()
        use_log_grid = (
            str(cfg.f_x_scale).lower() == "log"
            and cfg.f_x_param in {"tau1", "tau2", "beta"}
            and cfg.grid_tau_min > 0
            and cfg.grid_tau_max > 0
        )
        if use_log_grid:
            self.grid_tau_axis = np.geomspace(cfg.grid_tau_min, cfg.grid_tau_max, cfg.grid_steps)
        else:
            self.grid_tau_axis = np.linspace(cfg.grid_tau_min, cfg.grid_tau_max, cfg.grid_steps)
        
        stat_gate_shapes = self._statistical_gate_profiles(self.gate_shapes)
        n_gates = stat_gate_shapes.shape[0]
        self.grid_templates = np.zeros((cfg.grid_steps, n_gates))
        
        t = self.time_vector
        original_param_value = self._get_cfg_param(cfg.f_x_param)
        for i, param_val in enumerate(self.grid_tau_axis):
            self._set_cfg_param(cfg.f_x_param, param_val)
            p_vec = stat_gate_shapes @ self.dt_pdf(t)
            p_sum = np.sum(p_vec)
            self.grid_templates[i, :] = p_vec / p_sum if p_sum > 0 else np.full(n_gates, 1.0 / n_gates)
        self._set_cfg_param(cfg.f_x_param, original_param_value)
        self.grid_signature = self._grid_signature()

    def _gate_probabilities_for_current_config(self, t: np.ndarray, gate_profiles: Optional[np.ndarray] = None,
                                               irf_cached: Optional[np.ndarray] = None) -> np.ndarray:
        if gate_profiles is None:
            gate_profiles = self.gate_shapes
        gate_profiles = self._statistical_gate_profiles(gate_profiles)
        pdf = self.dt_pdf(t, irf=irf_cached)
        probs = gate_profiles @ pdf
        probs = probs * self._collection_efficiency_scale(gate_profiles.shape[0])
        if self._use_raw_gate_statistics():
            return probs
        p_sum = np.sum(probs)
        if p_sum <= 0:
            return np.full(gate_profiles.shape[0], 1.0 / gate_profiles.shape[0])
        return probs / p_sum

    def estimate_tau_batch(self, counts_batch: np.ndarray) -> np.ndarray:
        """Returns gridded-MLE estimates for the currently selected X-axis parameter."""
        self.ensure_grid_current()

        totals = np.sum(counts_batch, axis=1, keepdims=True)
        valid = totals[:, 0] > 0
        estimates = np.full(counts_batch.shape[0], np.nan)
        if not np.any(valid):
            return estimates

        obs_norm = counts_batch[valid] / totals[valid]
        log_templates = np.log(np.maximum(self.grid_templates, 1e-300))
        log_likelihood = obs_norm @ log_templates.T
        best_idx = np.argmax(log_likelihood, axis=1)
        refined = np.array(self.grid_tau_axis[best_idx], copy=True)

        if self.grid_tau_axis.size >= 3:
            interior_rows = np.where((best_idx > 0) & (best_idx < (self.grid_tau_axis.size - 1)))[0]
            if interior_rows.size > 0:
                axis = np.array(self.grid_tau_axis, copy=False, dtype=float)
                use_log_interp = np.all(axis > 0) and (
                    str(self.config.f_x_scale).lower() == "log"
                    and self.config.f_x_param in {"tau1", "tau2", "beta"}
                )
                interp_axis = np.log(axis) if use_log_interp else axis
                axis_steps = np.diff(interp_axis)
                if axis_steps.size > 0 and np.allclose(axis_steps, axis_steps[0], rtol=1e-4, atol=1e-10):
                    h = float(axis_steps[0])
                    row_idx = interior_rows
                    center_idx = best_idx[row_idx]
                    ll_minus = log_likelihood[row_idx, center_idx - 1]
                    ll_center = log_likelihood[row_idx, center_idx]
                    ll_plus = log_likelihood[row_idx, center_idx + 1]
                    denom = ll_minus - (2.0 * ll_center) + ll_plus
                    safe = np.abs(denom) > 1e-12
                    offset = np.zeros(center_idx.shape[0], dtype=float)
                    offset[safe] = 0.5 * (ll_minus[safe] - ll_plus[safe]) / denom[safe]
                    offset = np.clip(offset, -1.0, 1.0)
                    interp_peak = interp_axis[center_idx] + (offset * h)
                    refined[row_idx] = np.exp(interp_peak) if use_log_interp else interp_peak

        estimates[valid] = np.clip(refined, self.grid_tau_axis[0], self.grid_tau_axis[-1])
        return estimates

    def simulate_gate_histograms(self, tau: Optional[float], n_photons: int, n_repeats: int,
                                 irf_cached: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Monte Carlo gate simulation aligned with the MATLAB reference path:
        sample photon times from the PDF, then evaluate per-gate Bernoulli detection
        using the gate transfer functions at those times.
        """
        self.distill_gates()
        t = self.time_vector
        pdf = self.dt_pdf(t, tau=tau, irf=irf_cached) if tau is not None else self.dt_pdf(t, irf=irf_cached)
        cdf = np.cumsum(pdf)
        cdf[-1] = 1.0

        photon_u = np.random.rand(int(n_repeats), int(n_photons))
        photon_times = np.interp(photon_u, cdf, t)

        n_repeats = int(n_repeats)
        n_photons = int(n_photons)
        n_gates = self.gate_shapes.shape[0]
        gate_hist_all = np.zeros((n_repeats, n_gates), dtype=float)
        gate_vals = np.zeros((n_repeats, n_photons, n_gates), dtype=float)
        for gate_idx in range(n_gates):
            gate_vals[:, :, gate_idx] = np.interp(photon_times, t, self.gate_shapes[gate_idx, :], left=0.0, right=0.0)

        if getattr(self.config, "gate_collection_mode", "histogram") == "sequential":
            gate_prob = np.clip(self._statistical_gate_profiles(self.gate_shapes) @ pdf, 0.0, 1.0)
            photons_per_gate = float(n_photons) * self._collection_efficiency_scale(n_gates)
            gate_hist_all = np.random.binomial(
                int(round(photons_per_gate)),
                np.broadcast_to(gate_prob, (n_repeats, n_gates)),
            ).astype(float)
        elif getattr(self.config, "gate_overlap_effect", "exclusive") == "independent_duplicates":
            detected = np.random.rand(n_repeats, n_photons, n_gates) < gate_vals
            gate_hist_all = np.sum(detected, axis=1)
        else:
            stat_gate_vals = self._exclusive_overlap_weights(gate_vals, axis=2)
            total_prob = np.clip(np.sum(stat_gate_vals, axis=2), 0.0, 1.0)
            hit_rand = np.random.rand(n_repeats, n_photons)
            detected_mask = hit_rand < total_prob
            cum_prob = np.cumsum(stat_gate_vals, axis=2)
            choice_rand = np.random.rand(n_repeats, n_photons) * np.maximum(total_prob, 1e-12)
            chosen_gate = np.argmax(choice_rand[:, :, None] <= cum_prob, axis=2)
            rep_idx, photon_idx = np.nonzero(detected_mask)
            for r, p in zip(rep_idx.tolist(), photon_idx.tolist()):
                gate_hist_all[r, chosen_gate[r, p]] += 1.0

        n_detections = np.sum(gate_hist_all, axis=1)
        return gate_hist_all, n_detections

    def run_fit(self, data: Optional[np.ndarray] = None, method: str = "gridded_mle"):
        """Main fitting loop. Performance optimized for large images."""
        if data is None:
            data = self.raw_data
            
        nY, nX, nGates = data.shape
        self.tau_map = np.full((nY, nX), np.nan)
        self.a_map = np.full((nY, nX), np.nan)
        self.b_map = np.full((nY, nX), np.nan)
        self.chi2_map = np.full((nY, nX), np.nan)
        
        flat_data = data.reshape(-1, nGates)
        total_counts = np.sum(flat_data, axis=1)
        valid_idx = np.where(total_counts > self.config.threshold_min)[0]
        
        if len(valid_idx) == 0: return

        if method == "gridded_mle":
            self.ensure_grid_current()
            log_templates = np.log(np.maximum(self.grid_templates, 1e-300))
                
            for idx in valid_idx:
                obs = flat_data[idx].astype(float)
                obs_norm = obs / np.sum(obs)

                log_likelihood = obs_norm @ log_templates.T
                best_idx = np.argmax(log_likelihood)
                tau_est = self.grid_tau_axis[best_idx]
                
                y_coord, x_coord = divmod(idx, nX)
                self.tau_map[y_coord, x_coord] = tau_est
                self.a_map[y_coord, x_coord] = total_counts[idx]
                self.b_map[y_coord, x_coord] = 0.0
                self.chi2_map[y_coord, x_coord] = -log_likelihood[best_idx]
        
        elif method == "tail":
            # ... existing tail fit ...
            pass

    def get_roi_mask(self, g_min: float, g_max: float, s_min: float, s_max: float) -> np.ndarray:
        """Returns a boolean mask for pixels within the specified phasor ROI."""
        if self.raw_data is None:
            return None
        g, s = self.calculate_phasor()
        mask = (g >= g_min) & (g <= g_max) & (s >= s_min) & (s <= s_max)
        return mask

    def calculate_phasor(self, data: Optional[np.ndarray] = None, harmonic: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculates G and S phasor coordinates using PhasorPy.
        """
        import phasorpy.phasor as pp
        
        if data is None:
            data = self.raw_data
        if data is None:
            return None, None
            
        nY, nX, nGates = data.shape
        # Repetition period T (ns)
        T = self.config.period if self.config.period > 0 else 12.5
        frequency = 1e9 / T # Frequency in Hz
        
        # Calculate phasor from signal using PhasorPy
        # signal: array_like, (..., n_samples)
        # We need to ensure the gating axis is the last one
        g, s, _ = pp.phasor_from_signal(data, harmonic=harmonic, axis=-1)
        
        # Note: PhasorPy calculates centered phasor by DFT.
        # If we need absolute phase alignment (e.g. to peak), we could use phasor_calibrate
        # but for simulation parity, raw DFT on the gated histogram is standard.
        
        return g, s

    def get_theoretical_locus(self, tau_range: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculates the theoretical G and S coordinates using PhasorPy.
        """
        import phasorpy.phasor as pp
        
        if tau_range is None:
            tau_range = np.logspace(np.log10(0.05e-9), np.log10(50e-9), 100) # In seconds for PhasorPy
        else:
            tau_range = tau_range * 1e-9 # Convert ns to s for PhasorPy
            
        T = self.config.period if self.config.period > 0 else 12.5
        frequency = 1e9 / T
        
        g, s = pp.phasor_from_lifetime(frequency, tau_range)
        
        return g, s

    def dt_excitation(self, t: np.ndarray) -> np.ndarray:
        """Calculates the excitation IRF (envelope) and optional Burst sub-pulses."""
        cfg = self.config
        profile = cfg.irf_profile.lower()
        dt = float(t[1] - t[0]) if len(t) > 1 else max(float(cfg.dt_input), 1e-3)
        
        # 1. Base IRF Shape (The Envelope)
        mu = cfg.irf_position
        sigma_instr = cfg.irf_fwhm / 2.35482
        jitter_ns = cfg.timing_jitter / 1000.0
        
        if profile == "gaussian":
            sigma = np.sqrt(sigma_instr**2 + jitter_ns**2)
            sigma = max(sigma, 1e-6)
            excitation = np.exp(-((t - mu)**2) / (2.0 * sigma**2))
        elif profile == "free_form":
            width = max(float(cfg.irf_fwhm), dt)
            control = np.asarray(getattr(cfg, "irf_freeform_points", []) or [], dtype=float)
            if control.size < 2:
                control = np.ones(max(int(getattr(cfg, "excitation_optimization_control_points", 8)), 3), dtype=float)
            control = np.maximum(control, 0.0)
            rel_t = t - mu
            knots = np.linspace(0.0, width, control.size)
            excitation = np.zeros_like(t, dtype=float)
            mask = (rel_t >= 0.0) & (rel_t <= width)
            if np.any(mask):
                excitation[mask] = np.interp(rel_t[mask], knots, control)
            if jitter_ns > 1e-5:
                excitation = self._apply_temporal_blur(excitation, jitter_ns, dt)
        elif profile == "ideal (dirac)":
            # Even for Dirac, jitter adds a Gaussian spread
            if jitter_ns > 1e-5:
                excitation = np.exp(-((t - mu)**2) / (2.0 * jitter_ns**2))
            else:
                excitation = np.zeros_like(t)
                idx = np.abs(t - mu).argmin()
                excitation[idx] = 1.0
        else: # rectangular
            tr = max(cfg.irf_rise_time, 1e-6)
            tf = max(cfg.irf_fall_time, 1e-6)
            t_rel = t - mu
            excitation = np.zeros_like(t)
            mask_rise = (t_rel >= 0) & (t_rel < cfg.irf_fwhm)
            excitation[mask_rise] = 1.0 - np.exp(-t_rel[mask_rise] / tr)
            peak_val = 1.0 - np.exp(-cfg.irf_fwhm / tr)
            mask_fall = t_rel >= cfg.irf_fwhm
            excitation[mask_fall] = peak_val * np.exp(-(t_rel[mask_fall] - cfg.irf_fwhm) / tf)
            if jitter_ns > 1e-5:
                excitation = self._apply_temporal_blur(excitation, jitter_ns, dt)
            
        # 2. Burst Sub-structure Modulation
        if cfg.burst_enabled:
            trep_b = max(cfg.burst_sub_period, 1e-4)
            burst_rise = getattr(cfg, "burst_sub_rise_time", None)
            burst_fall = getattr(cfg, "burst_sub_fall_time", None)
            burst = np.zeros_like(t)
            centers = np.arange(0, np.max(t) + trep_b, trep_b)
            if burst_rise is None and burst_fall is None:
                # Legacy Gaussian burst train.
                sigma_b_orig = cfg.burst_sub_fwhm / 2.35482
                sigma_b = np.sqrt(sigma_b_orig**2 + jitter_ns**2)
                sigma_b = max(sigma_b, 1e-6)
                for center in centers:
                    burst += np.exp(-((t - center)**2) / (2.0 * sigma_b**2))
            else:
                width = max(cfg.burst_sub_fwhm, t[1] - t[0] if len(t) > 1 else 1e-3)
                rise = max(float(burst_rise or 0.0), 0.0)
                fall = max(float(burst_fall or 0.0), 0.0)

                def sigmoid(x):
                    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))

                for center in centers:
                    start_edge = sigmoid((t - center) / rise) if rise > 0 else (t >= center).astype(float)
                    end_time = center + width
                    end_edge = (1.0 - sigmoid((t - end_time) / fall)) if fall > 0 else (t < end_time).astype(float)
                    burst += start_edge * end_edge
            excitation *= burst
            
        return excitation

    def dt_pdf(self, t: np.ndarray, tau: Optional[float] = None, irf: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Robust PDF calculation with automated alignment and wrapping.
        """
        cfg = self.config
        dt = t[1] - t[0] if len(t) > 1 else 0.01
        
        # 1. Base Decay Calculation
        if tau is not None:
            decay = np.exp(-t / max(tau, 1e-6))
        else:
            if cfg.decay_model == "exponential":
                decay = np.zeros_like(t)
                for i in range(cfg.n_components):
                    if i < len(cfg.taus) and i < len(cfg.amplitudes):
                        decay += cfg.amplitudes[i] * np.exp(-t / max(cfg.taus[i], 1e-6))
            elif cfg.decay_model == "stretched":
                t0 = cfg.taus[0] if cfg.taus else 1.0
                decay = np.exp(-(np.maximum(t, 0) / max(t0, 1e-6))**cfg.beta)
            else:
                decay = np.exp(-t / 2.5)

        # 2. Simplified Convolution + Wrapping Logic
        # Instead of 'mode=full', we use the fact that IRF is a narrow pulse
        # We perform a circular convolution if wrapping is enabled
        if irf is None:
            irf = self.dt_excitation(t)
            isum = np.sum(irf)
            if isum > 0: irf /= isum

        # Use FFT for robust circular convolution if wrapping is enabled
        if cfg.b_decay_wrapping:
            # Padding to avoid circular artifacts if decay isn't fully gone
            # (Though wrapping specifically intends circularity)
            pdf = np.real(np.fft.ifft(np.fft.fft(irf) * np.fft.fft(decay)))
        else:
            # Standard linear convolution clipped to window
            full = np.convolve(irf, decay, mode='full')
            pdf = full[:len(t)]

        # 3. Normalization & Safety
        pdf = np.nan_to_num(pdf, nan=0.0, posinf=0.0, neginf=0.0)
        pdf = np.maximum(pdf, 1e-20)
        
        # Add background mass
        pdf += cfg.background_level / len(t)
        
        s = np.sum(pdf)
        if s > 0:
            pdf /= s
        else:
            pdf = np.zeros_like(pdf)
            pdf[0] = 1.0
            
        return pdf

    def compute_fisher_info(self, x_grid: np.ndarray, n_photons: int = 1, point_callback: Optional[Callable] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes the CRLB-based F-value using multi-parameter Fisher Matrix inversion.
        Evaluates precision of 'f_x_param' while respecting 'fixed_params'.
        """
        cfg = self.config
        
        # Enforce dt is fine enough to resolve gate sigmoid transitions
        rise = max(float(getattr(cfg, "gate_rise", 0.0)), 0.0)
        fall = max(float(getattr(cfg, "gate_fall", rise)), 0.0)
        dt_user = cfg.dt_override if (cfg.dt_override and cfg.dt_override > 0) else (cfg.dt_input if (cfg.dt_input and cfg.dt_input > 0) else 0.01)
        if rise <= 0.0 and fall <= 0.0:
            dt = dt_user
        else:
            edge_scale = max(rise, fall, 1e-4)
            dt = min(dt_user, edge_scale / 5.0)  # Resolve the sharpest smoothed gate edge when smoothing is used.
            dt = max(dt, 0.005)  # Never finer than 5ps (prevents 100k+ bin arrays)
        
        # Adaptive time window
        t_win = cfg.period if cfg.b_decay_wrapping else cfg.gate_edges[-1] + 5.0
        t = np.arange(0, t_win + dt, dt)
        
        # Prepare gates using the exact same distillation logic as the simulation path.
        n_gates = len(cfg.gate_edges) - 1
        original_dt_override = cfg.dt_override
        try:
            cfg.dt_override = dt
            self.distill_gates()
            gate_profiles = self._statistical_gate_profiles(self.gate_shapes)
            t = np.array(self.time_vector, copy=True)
        finally:
            cfg.dt_override = original_dt_override
        
        fisher_values = np.zeros(len(x_grid))
        f_values = np.zeros(len(x_grid))
        epsilon = 0.01
        
        # Cache the IRF as it doesn't change during parameter sweeps within one call
        irf_cached = self.dt_excitation(t)
        irf_sum = np.sum(irf_cached)
        if irf_sum > 0: irf_cached /= irf_sum
        
        print(f"  [CFG] dt={dt:.4f}ns, gate_rise={rise:.4f}ns, gate_fall={fall:.4f}ns, n_gates={n_gates}, "
              f"irf_fwhm={cfg.irf_fwhm:.3f}, t_win={t_win:.1f}, n_t={len(t)}")

        for k, x_val in enumerate(x_grid):
            orig_x_val = self._get_cfg_param(cfg.f_x_param)
            try:
                param_val = float(x_val)
                lower_bound, upper_bound = self._get_cfg_param_bounds(cfg.f_x_param)
                delta_param = self._get_cfg_param_step(cfg.f_x_param, param_val, dt, epsilon)
                plus_val = param_val + delta_param
                minus_val = param_val - delta_param

                if lower_bound is not None:
                    minus_val = max(lower_bound, minus_val)
                    plus_val = max(lower_bound, plus_val)
                if upper_bound is not None:
                    minus_val = min(upper_bound, minus_val)
                    plus_val = min(upper_bound, plus_val)

                if np.isclose(plus_val, minus_val):
                    if upper_bound is None or param_val + delta_param <= upper_bound:
                        plus_val = param_val + delta_param
                    if lower_bound is None or param_val - delta_param >= lower_bound:
                        minus_val = param_val - delta_param

                # Central value
                self._set_cfg_param(cfg.f_x_param, param_val)
                p_cen_pdf  = self.dt_pdf(t, irf=irf_cached)
                p_cen_gates = gate_profiles @ p_cen_pdf
                p_cen_gates = p_cen_gates * self._collection_efficiency_scale(n_gates)
                p_cen_sum = np.sum(p_cen_gates)
                if (not self._use_raw_gate_statistics()) and p_cen_sum > 0:
                    p_cen_gates = p_cen_gates / p_cen_sum

                # Forward
                self._set_cfg_param(cfg.f_x_param, plus_val)
                p_plus_pdf   = self.dt_pdf(t, irf=irf_cached)
                p_plus_gates = gate_profiles @ p_plus_pdf
                p_plus_gates = p_plus_gates * self._collection_efficiency_scale(n_gates)
                p_plus_sum = np.sum(p_plus_gates)
                if (not self._use_raw_gate_statistics()) and p_plus_sum > 0:
                    p_plus_gates = p_plus_gates / p_plus_sum

                # Backward
                self._set_cfg_param(cfg.f_x_param, minus_val)
                p_minus_pdf   = self.dt_pdf(t, irf=irf_cached)
                p_minus_gates = gate_profiles @ p_minus_pdf
                p_minus_gates = p_minus_gates * self._collection_efficiency_scale(n_gates)
                p_minus_sum = np.sum(p_minus_gates)
                if (not self._use_raw_gate_statistics()) and p_minus_sum > 0:
                    p_minus_gates = p_minus_gates / p_minus_sum

                # Central-difference derivative with respect to the currently targeted parameter.
                dP_dparam = (p_plus_gates - p_minus_gates) / max(plus_val - minus_val, 1e-12)

                # Fisher Information (scalar): FI = N * sum((dP/dtau)^2 / P)
                p_safe = np.maximum(p_cen_gates, 1e-15)
                fi_elem = (dP_dparam ** 2) / p_safe
                fisher_info = n_photons * np.sum(fi_elem)
                fisher_values[k] = fisher_info

                # Signal & sensitivity diagnostics (first point only)
                if k == 0:
                    sig_sum  = np.sum(p_cen_gates)
                    jac_norm = np.linalg.norm(dP_dparam)
                    print(f"  [DIAG] x={x_val:.4f}: Signal={sig_sum:.6f}, dP_norm={jac_norm:.4e}, FI={fisher_info:.4e}")

                # CRLB for the selected parameter. F uses relative precision for the active X-axis parameter.
                if fisher_info > 0:
                    sigma_param = 1.0 / np.sqrt(fisher_info)
                    denom = max(abs(param_val), 1e-12)
                    f_values[k] = (sigma_param / denom) * np.sqrt(n_photons)
                else:
                    f_values[k] = np.nan
                if point_callback is not None:
                    point_callback(k, fisher_values[k], f_values[k])

            except Exception as e:
                print(f"[compute_fisher_info] Error at x={x_val:.4f}: {type(e).__name__}: {e}")
                fisher_values[k] = np.nan
                f_values[k] = np.nan
                if point_callback is not None:
                    point_callback(k, fisher_values[k], f_values[k])
            finally:
                self._set_cfg_param(cfg.f_x_param, orig_x_val)  # Always restore

        if k == len(x_grid) - 1:
            print(f"  DEBUG: f_val[0]={f_values[0]:.6f}, f_val[mid]={f_values[len(f_values)//2]:.6f}")
        return fisher_values, f_values

    def _get_cfg_param(self, name):
        if name == "tau1": return self.config.taus[0]
        if name == "tau2": return self.config.taus[1] if len(self.config.taus) > 1 else 1.0
        if name == "alpha": return self.config.amplitudes[0]
        if name == "background": return self.config.background_level
        if name == "beta": return self.config.beta
        return 0.0

    def _get_cfg_param_bounds(self, name):
        if name in {"tau1", "tau2"}:
            return 1e-6, None
        if name == "alpha":
            return 0.0, 1.0
        if name == "background":
            return 0.0, None
        if name == "beta":
            return 1e-6, None
        return None, None

    def _get_cfg_param_step(self, name, value, dt, epsilon):
        if name in {"tau1", "tau2"}:
            return max(epsilon * max(abs(value), 1e-6), 2.0 * dt)
        if name in {"alpha", "background", "beta"}:
            return max(epsilon * max(abs(value), 1.0), 1e-4)
        return max(epsilon * max(abs(value), 1.0), 1e-4)

    def _set_cfg_param(self, name, val):
        if name == "tau1": self.config.taus[0] = val
        elif name == "tau2" and len(self.config.taus) > 1: self.config.taus[1] = val
        elif name == "alpha" and self.config.amplitudes:
            self.config.amplitudes[0] = val
            if len(self.config.amplitudes) > 1:
                self.config.amplitudes[1] = max(0.0, 1.0 - val)
        elif name == "background": self.config.background_level = val
        elif name == "beta": self.config.beta = val

    def compute_ideal_reference(self, tau_grid: np.ndarray, n_photons: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculates the truly 'Ideal Case' (Theoretical Ceiling):
        - Infinite Time Window (No Truncation / No Wrapping)
        - Dirac excitation (Zero Timing Jitter)
        - 256 High-resolution linear bins
        - Zero Background & No Parameter Coupling
        """
        import copy
        ideal_cfg = copy.deepcopy(self.config)
        ideal_cfg.irf_profile = "ideal (dirac)"
        ideal_cfg.gate_profile = "ideal_rect"
        ideal_cfg.gate_rise = 0.0
        ideal_cfg.gate_fall = 0.0
        ideal_cfg.timing_jitter = 0
        ideal_cfg.detector_deadtime = 0
        ideal_cfg.b_multihit_mode = True
        ideal_cfg.background_level = 0
        ideal_cfg.b_decay_wrapping = False # Establishing the absolute limit without pile-up
        ideal_cfg.period = 100.0 # Use a very wide measurement window to reach F=1.0 limit
        ideal_cfg.gate_collection_mode = "histogram"
        ideal_cfg.gate_overlap_mode = "jitter_only"
        ideal_cfg.gate_overlap_effect = "exclusive"
        ideal_cfg.gate_overlap_ns = 0.0
        ideal_cfg.gate_wraparound = True
        
        # Suppress coupling: Fix all but the parameter under test
        for p in ["tau1", "tau2", "alpha", "background", "beta"]:
            ideal_cfg.fixed_params[p] = True
        
        # Continuous-limit bins
        edges = np.linspace(0, 100.0, 257)
        ideal_cfg.gate_edges = edges.tolist()
        ideal_cfg.dt_input = 0.05
        
        orig_cfg = self.config
        self.config = ideal_cfg
        try:
            fi, f_val = self.compute_fisher_info(tau_grid, n_photons)
        finally:
            self.config = orig_cfg
            
        return fi, f_val

    def _bootstrap_accuracy_pvalue(self, samples: np.ndarray, truth: float,
                                   n_bootstrap: int, rng: np.random.Generator) -> float:
        samples = np.asarray(samples, dtype=float)
        samples = samples[np.isfinite(samples)]
        if samples.size == 0:
            return np.nan
        if samples.size == 1:
            return 1.0 if np.isclose(samples[0], truth) else 0.0

        observed_delta = float(np.mean(samples) - truth)
        centered = samples - np.mean(samples) + truth
        boot_idx = rng.integers(0, samples.size, size=(int(n_bootstrap), samples.size))
        null_means = centered[boot_idx].mean(axis=1)
        abs_delta = abs(observed_delta)
        empirical_p = (np.count_nonzero(np.abs(null_means - truth) >= abs_delta) + 1.0) / (len(null_means) + 1.0)

        null_std = float(np.std(null_means, ddof=1)) if len(null_means) > 1 else 0.0
        if null_std <= 0:
            return 1.0 if np.isclose(observed_delta, 0.0) else 0.0

        approx_p = erfc(abs_delta / (sqrt(2.0) * null_std))
        resolution_floor = 10.0 / max(len(null_means), 1)
        return float(empirical_p if empirical_p >= resolution_floor else approx_p)

    def _bootstrap_precision_intervals(self, estimates: np.ndarray, detections: np.ndarray, truth: float,
                                       n_bootstrap: int, rng: np.random.Generator,
                                       photon_budget: Optional[float] = None) -> dict:
        estimates = np.asarray(estimates, dtype=float)
        detections = np.asarray(detections, dtype=float)
        finite_mask = np.isfinite(estimates) & np.isfinite(detections)
        estimates = estimates[finite_mask]
        detections = detections[finite_mask]
        empty = {
            "f_ci_lower": np.nan,
            "f_ci_upper": np.nan,
            "efficiency_ci_lower": np.nan,
            "efficiency_ci_upper": np.nan,
        }
        if estimates.size < 2:
            return empty

        boot_idx = rng.integers(0, estimates.size, size=(int(n_bootstrap), estimates.size))
        boot_estimates = estimates[boot_idx]
        boot_detections = detections[boot_idx]
        std_boot = np.std(boot_estimates, axis=1, ddof=1)
        photon_budget = float(photon_budget if photon_budget is not None else np.mean(detections))
        denom = max(abs(truth), 1e-12)
        f_boot = (std_boot / denom) * np.sqrt(max(photon_budget, 0.0))
        eff_boot = np.where(f_boot > 0, np.minimum(1.0, 1.0 / (f_boot ** 2)), np.nan)
        ci_level = float(getattr(self.config, "precision_ci_level", 95.0))
        ci_level = min(max(ci_level, 1.0), 99.999)
        alpha = (100.0 - ci_level) / 100.0
        lower_pct = 100.0 * (alpha / 2.0)
        upper_pct = 100.0 * (1.0 - alpha / 2.0)

        return {
            "f_ci_lower": float(np.nanpercentile(f_boot, lower_pct)),
            "f_ci_upper": float(np.nanpercentile(f_boot, upper_pct)),
            "efficiency_ci_lower": float(np.nanpercentile(eff_boot, lower_pct)),
            "efficiency_ci_upper": float(np.nanpercentile(eff_boot, upper_pct)),
        }

    def monte_carlo_precision_curve(self, x_grid: np.ndarray, n_photons: int, n_repeats: int,
                                    point_callback: Optional[Callable] = None) -> dict:
        """
        Monte Carlo validation of the precision curve.
        Simulate gated photon counts repeatedly for the currently selected
        X-axis parameter, estimate that parameter using the gridded MLE,
        then compute mean/std/F and photon efficiency.
        """
        self.distill_gates()
        self.ensure_grid_current()

        t = self.time_vector
        irf_cached = self.dt_excitation(t)
        irf_sum = np.sum(irf_cached)
        if irf_sum > 0:
            irf_cached = irf_cached / irf_sum

        target_param = self.config.f_x_param
        original_param_value = self._get_cfg_param(target_param)
        mean_tau = np.full(len(x_grid), np.nan)
        std_tau = np.full(len(x_grid), np.nan)
        f_values = np.full(len(x_grid), np.nan)
        p_eff = np.full(len(x_grid), np.nan)
        p_values = np.full(len(x_grid), np.nan)
        compatible = np.full(len(x_grid), False, dtype=bool)
        n_valid = np.zeros(len(x_grid), dtype=int)
        alpha_threshold = float(getattr(self.config, "precision_accuracy_pvalue", 0.01))
        compute_ci = bool(getattr(self.config, "precision_compute_ci", False))
        bootstrap_samples = max(200, int(getattr(self.config, "precision_bootstrap_samples", 2000)))
        f_ci_lower = np.full(len(x_grid), np.nan)
        f_ci_upper = np.full(len(x_grid), np.nan)
        eff_ci_lower = np.full(len(x_grid), np.nan)
        eff_ci_upper = np.full(len(x_grid), np.nan)
        rng = np.random.default_rng()

        for idx, param_val in enumerate(x_grid):
            self._set_cfg_param(target_param, param_val)
            force_deadtime_mc = bool(getattr(self.config, "metadata", {}).get("force_precision_deadtime_mc", False))
            if force_deadtime_mc and (self.config.detector_deadtime > 0 or not self.config.b_multihit_mode):
                counts = np.zeros((int(n_repeats), self.gate_shapes.shape[0]), dtype=float)
                for rep_idx in range(int(n_repeats)):
                    counts[rep_idx, :] = self.simulate_photons_with_deadtime(
                        tau=None,
                        n_total=int(n_photons),
                        b_rate=0.0,
                    )
                n_detections = np.sum(counts, axis=1)
            else:
                counts, n_detections = self.simulate_gate_histograms(
                    tau=None,
                    n_photons=int(n_photons),
                    n_repeats=int(n_repeats),
                    irf_cached=irf_cached,
                )
            param_est = self.estimate_tau_batch(counts)
            finite_est = param_est[np.isfinite(param_est)]
            n_valid[idx] = int(finite_est.size)

            mean_tau[idx] = np.nanmean(param_est)
            std_tau[idx] = np.nanstd(param_est, ddof=1) if np.sum(np.isfinite(param_est)) > 1 else 0.0
            mean_detected = float(np.nanmean(n_detections)) if len(n_detections) else 0.0
            photon_budget = float(n_photons)
            denom = max(abs(param_val), 1e-12)
            if np.isfinite(std_tau[idx]) and photon_budget > 0:
                f_values[idx] = (std_tau[idx] / denom) * np.sqrt(photon_budget)
                if f_values[idx] > 0:
                    p_eff[idx] = min(1.0, 1.0 / (f_values[idx] ** 2))
            if n_valid[idx] >= 2:
                p_values[idx] = self._bootstrap_accuracy_pvalue(
                    finite_est,
                    float(param_val),
                    bootstrap_samples,
                    rng,
                )
                compatible[idx] = bool(np.isfinite(p_values[idx]) and p_values[idx] >= alpha_threshold)
            elif n_valid[idx] == 1:
                p_values[idx] = 1.0 if np.isclose(finite_est[0], param_val) else 0.0
                compatible[idx] = bool(p_values[idx] >= alpha_threshold)
            if compute_ci:
                ci_payload = self._bootstrap_precision_intervals(
                    param_est,
                    n_detections,
                    float(param_val),
                    bootstrap_samples,
                    rng,
                    photon_budget=photon_budget,
                )
                f_ci_lower[idx] = ci_payload["f_ci_lower"]
                f_ci_upper[idx] = ci_payload["f_ci_upper"]
                eff_ci_lower[idx] = ci_payload["efficiency_ci_lower"]
                eff_ci_upper[idx] = ci_payload["efficiency_ci_upper"]
            if point_callback is not None:
                point_callback(
                    idx,
                    mean_tau[idx],
                    std_tau[idx],
                    f_values[idx],
                    p_eff[idx],
                    p_values[idx],
                    compatible[idx],
                    f_ci_lower[idx],
                    f_ci_upper[idx],
                    eff_ci_lower[idx],
                    eff_ci_upper[idx],
                )

        self._set_cfg_param(target_param, original_param_value)
        return {
            "estimate_param": target_param,
            "mean_tau": mean_tau,
            "std_tau": std_tau,
            "mean_estimate": mean_tau,
            "std_estimate": std_tau,
            "f_value": f_values,
            "efficiency": p_eff,
            "p_value": p_values,
            "compatible": compatible,
            "n_valid": n_valid,
            "f_ci_lower": f_ci_lower,
            "f_ci_upper": f_ci_upper,
            "efficiency_ci_lower": eff_ci_lower,
            "efficiency_ci_upper": eff_ci_upper,
        }

    def simulate_photons_with_deadtime(self, tau: Optional[float], n_total: int, b_rate: float = 0.0) -> np.ndarray:
        """
        Sophisticated photon-by-photon Monte Carlo simulation.
        Handles detector deadtime and multihit logic.
        """
        cfg = self.config
        t_rep = cfg.period if cfg.period > 0 else cfg.gate_edges[-1] + 5.0
        if (
            getattr(cfg, "gate_collection_mode", "histogram") != "histogram"
            or getattr(cfg, "gate_overlap_mode", "jitter_only") != "jitter_only"
            or getattr(cfg, "gate_overlap_effect", "exclusive") != "exclusive"
            or not getattr(cfg, "gate_wraparound", True)
        ):
            hist, _ = self.simulate_gate_histograms(tau, int(n_total), 1)
            return hist[0]
        
        # Determine number of pulses to simulate
        # Assume total photons are distributed over a 1s acquisition for throughput calc
        # but here we'll just simulate enough pulses to reach n_total on average.
        p_detect_per_pulse = n_total / (1e6) # Dummy scaling
        
        # Time vector for PDF
        t = self.time_vector
        pdf = self.dt_pdf(t, tau=tau) if tau is not None else self.dt_pdf(t)
        cdf = np.cumsum(pdf)
        
        n_pulses = 10000
        gate_edges = np.asarray(cfg.gate_edges, dtype=np.float64)
        counts = _simulate_deadtime_counts_numba(
            cdf.astype(np.float64),
            t.astype(np.float64),
            gate_edges,
            float(t_rep),
            float(n_total),
            float(b_rate),
            float(cfg.detector_deadtime),
            bool(cfg.b_multihit_mode),
            int(n_pulses),
        )
        return counts

    def advanced_instrument_simulation(self, a_sim: float, tau_grid: np.ndarray, b_sim: float):
        """
        Synthesizes a 4D hypercube applying instrument non-idealities:
        - Electronic Jitter (Gaussian smearing of IRF)
        - Differential Non-Linearity (DNL)
        - Poisson Shot Noise
        - Detector Deadtime & Multihit effects
        """
        cfg = self.config
        ny, nx = tau_grid.shape
        n_gates = len(cfg.gate_edges) - 1
        self.raw_data = np.zeros((ny, nx, n_gates))
        
        distilled_shapes = self.gate_shapes.copy()

        # DNL Scaling
        dnl = 1.0 + (np.random.rand(n_gates) - 0.5) * (cfg.dnl_level / 100.0)
        
        for y in range(ny):
            for x in range(nx):
                tau = tau_grid[y, x]
                if np.isnan(tau) or tau <= 0: continue
                
                if cfg.detector_deadtime > 0 or not cfg.b_multihit_mode:
                    # Use full Monte Carlo for deadtime/multihit effects
                    counts = self.simulate_photons_with_deadtime(tau, a_sim, b_sim)
                else:
                    # Use faster expected value + Poisson for ideal detectors
                    t_vec = self.time_vector
                    decay = np.exp(-t_vec / tau)
                    term_a = distilled_shapes @ decay
                    term_a /= (np.sum(term_a) if np.sum(term_a) > 0 else 1.0)
                    term_b = np.sum(distilled_shapes, axis=1)
                    lam = a_sim * term_a + b_sim * term_b
                    counts = np.random.poisson(lam)
                
                self.raw_data[y, x, :] = counts * dnl

    def simulate_data(self, a_sim: float, tau1: float, tau2: float, b_sim: float, ny: int, nx: int):
        """Synthesizes a gradient dataset for validation."""
        n_gates = self.gate_shapes.shape[0]
        self.raw_data = np.zeros((ny, nx, n_gates))
        
        t_vec = self.time_vector
        tau_values = np.linspace(tau1, tau2, nx)
        term_b = np.sum(self.gate_shapes, axis=1)
        
        for x in range(nx):
            tau = tau_values[x]
            decay = np.exp(-t_vec / tau)
            term_a = self.gate_shapes @ decay
            term_a /= np.sum(term_a) # Renormalize
            
            pixel_counts = a_sim * term_a + b_sim * term_b
            
            for g in range(n_gates):
                self.raw_data[:, x, g] = np.random.poisson(pixel_counts[g], (ny,))

    def characterize_hardware(self, sweep_table_data):
        """
        Performs global fitting of detector sigma (jitter) and effective gate widths
        using mirrored sweep data.
        """
        # 1. Mirror and Extract Sweep Data
        t_orig = sweep_table_data['laser_delay']
        t_sweep = (np.max(t_orig) + np.min(t_orig)) - t_orig
        
        widths_labels = np.unique(sweep_table_data['gate_width'])
        self.sweep_data = []
        
        for w in widths_labels:
            mask = sweep_table_data['gate_width'] == w
            td = t_sweep[mask]
            cd = sweep_table_data['counts'][mask]
            # Normalization
            if np.max(cd) > 0: cd /= np.max(cd)
            
            # Sort by time
            idx = np.argsort(td)
            self.sweep_data.append({'w': w, 't': td[idx], 'c': cd[idx]})
            
        # 2. Global Fit (Simplified for Python)
        from scipy.optimize import minimize
        
        def obj(params):
            sigma = abs(params[0])
            widths = abs(params[1:])
            total_err = 0
            
            for i, data in enumerate(self.sweep_data):
                t = data['t']
                obs = data['c']
                w_eff = widths[i]
                
                # Model: Rect(w_eff) convolved with Gaussian(sigma)
                # Analytical Approximation for faster fitting
                from scipy.special import erf
                mid = np.mean(t)
                pred = 0.5 * (erf((t - mid + w_eff/2) / (np.sqrt(2)*sigma)) - 
                             erf((t - mid - w_eff/2) / (np.sqrt(2)*sigma)))
                
                if np.max(pred) > 0: pred /= np.max(pred)
                total_err += np.sum((obs - pred)**2)
            return total_err
            
        p0 = [0.2] + list(widths_labels)
        res = minimize(obj, p0, method='Nelder-Mead', tol=1e-3)
        
        self.fitted_sigma = abs(res.x[0])
        self.config.skewness = self.fitted_sigma * 1000.0 # [ps]
        return res.x[1:] # Fitted effective widths

    def import_laser_csv(self, file_path: str):
        """Imports a laser pulse profile from a CSV file."""
        data = np.genfromtxt(file_path, delimiter=',')
        # Skip header if present or handle NaN
        if np.isnan(data[0,0]): data = data[1:]
        
        idx = np.argsort(data[:, 0])
        self.laser_pulse = {
            "t": data[idx, 0],
            "p": data[idx, 1]
        }

    def apply_median_filter(self, size: int = 3):
        """Applies a 2D median filter to valid data maps."""
        from scipy.ndimage import median_filter
        if self.raw_data is not None:
            for g in range(self.raw_data.shape[2]):
                self.raw_data[:, :, g] = median_filter(self.raw_data[:, :, g], size=size)
        
        if self.tau_map is not None:
            self.tau_map = median_filter(self.tau_map, size=size)

    def _resolve_optimization_window(self, t_max: float,
                                     start_anchor: Optional[str] = None,
                                     start_time: Optional[float] = None,
                                     end_anchor: Optional[str] = None,
                                     end_time: Optional[float] = None) -> Tuple[float, float]:
        cfg = self.config
        start_anchor = start_anchor or getattr(cfg, "detection_opt_start_anchor", "zero")
        end_anchor = end_anchor or getattr(cfg, "detection_opt_end_anchor", "period")
        start_time = float(start_time if start_time is not None else getattr(cfg, "detection_opt_start_time", 0.0))
        end_time = float(end_time if end_time is not None else getattr(cfg, "detection_opt_end_time", t_max))

        if start_anchor == "irf":
            dt = cfg.dt_override if (cfg.dt_override and cfg.dt_override > 0) else cfg.dt_input
            t_irf = np.arange(0.0, max(cfg.period, t_max) + dt, dt)
            irf = self.dt_excitation(t_irf)
            if np.any(irf > 0):
                threshold = np.max(irf) * 1e-3
                nz = np.flatnonzero(irf >= threshold)
                start = float(t_irf[nz[-1]]) if nz.size else 0.0
            else:
                start = 0.0
        elif start_anchor == "custom":
            start = start_time
        else:
            start = 0.0

        if end_anchor == "custom":
            end = end_time
        else:
            end = min(float(t_max), float(cfg.period))

        start = max(0.0, float(start))
        end = max(start + 1e-3, float(end))
        return start, end

    def _build_gate_optimization_payload(self, edges: np.ndarray, tau_grid: np.ndarray,
                                         j_val: float, fi: np.ndarray, f_val: np.ndarray,
                                         algorithm: Optional[str], step: Optional[int] = None,
                                         note: Optional[str] = None) -> Dict[str, Any]:
        t_max = max(float(self.config.period), float(edges[-1]) if len(edges) else float(self.config.period))
        return {
            "step": None if step is None else int(step),
            "algorithm": algorithm or getattr(self.config, "detection_optimization_algorithm", "direct_slsqp"),
            "objective": float(j_val),
            "min_f": float(np.nanmin(f_val)) if np.any(np.isfinite(f_val)) else np.nan,
            "edges": np.array(edges, copy=True),
            "tau_grid": np.array(tau_grid, copy=True),
            "fisher_info": np.array(fi, copy=True),
            "f_val": np.array(f_val, copy=True),
            "gate_profiles": self.get_gate_profiles_vis(t_max),
            "t": np.arange(0, t_max + 0.05, 0.05),
            "note": note or "",
        }

    @staticmethod
    def _clone_gate_optimization_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        cloned: Dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, np.ndarray):
                cloned[key] = np.array(value, copy=True)
            else:
                cloned[key] = copy.deepcopy(value)
        return cloned

    def _emit_gate_optimization_progress(self, callback: Optional[Callable],
                                         progress_callback: Optional[Callable],
                                         payload: Dict[str, Any]) -> None:
        if callback is not None:
            callback(float(payload["objective"]))
        if progress_callback is not None:
            progress_callback(self._clone_gate_optimization_payload(payload))

    def _evaluate_gate_edges(self, edges: np.ndarray, tau_grid: np.ndarray,
                             callback: Optional[Callable] = None,
                             progress_callback: Optional[Callable] = None,
                             algorithm: Optional[str] = None,
                             step: Optional[int] = None,
                             note: Optional[str] = None,
                             emit_progress: bool = True) -> Tuple[float, np.ndarray, np.ndarray, Dict[str, Any]]:
        orig_edges = list(self.config.gate_edges)
        orig_widths = list(getattr(self.config, "gate_widths", []))
        orig_gate_type = getattr(self.config, "gate_type", "equal")
        self.config.gate_edges = edges.tolist()
        self.config.gate_widths = np.diff(np.asarray(edges, dtype=float)).tolist()
        self.config.gate_type = "custom"
        self.distill_gates()
        active_params = None
        if (
            str(algorithm or getattr(self.config, "detection_optimization_algorithm", "")).lower() == "fisher_compression"
            and bool(getattr(self.config, "detection_opt_fc_nuisance_aware", True))
        ):
            candidate_params = self._get_active_compression_params()
            if len(candidate_params) > 1:
                active_params = candidate_params
        if active_params is None:
            fi, f_val = self.compute_fisher_info(tau_grid, n_photons=1e4)
        else:
            fi, f_val = self._compute_effective_fisher_info_for_params(tau_grid, n_photons=1e4, active_params=active_params)
        j_val = float(np.nanmean(f_val)) if np.any(np.isfinite(f_val)) else np.inf
        payload = self._build_gate_optimization_payload(edges, tau_grid, j_val, fi, f_val, algorithm, step=step, note=note)
        if emit_progress and np.isfinite(j_val):
            self._emit_gate_optimization_progress(callback, progress_callback, payload)
        self.config.gate_edges = orig_edges
        self.config.gate_widths = orig_widths
        self.config.gate_type = orig_gate_type
        self.distill_gates()
        return j_val, fi, f_val, payload

    def _build_fine_bin_scores(self, fine_edges: np.ndarray, tau_grid: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        cfg = self.config
        self.distill_gates()
        t = self.time_vector
        target_param = cfg.f_x_param
        original_param_value = self._get_cfg_param(target_param)
        n_bins = len(fine_edges) - 1
        n_design = len(tau_grid)
        probs = np.zeros((n_design, n_bins), dtype=float)
        eff_deriv = np.zeros((n_design, n_bins), dtype=float)
        nuisance_aware = bool(getattr(cfg, "detection_opt_fc_nuisance_aware", True))

        active_params = self._get_active_compression_params()
        original_values = {name: self._get_cfg_param(name) for name in active_params}

        bin_masks = []
        for i in range(n_bins):
            left = fine_edges[i]
            right = fine_edges[i + 1]
            if i == n_bins - 1:
                mask = (t >= left) & (t <= right)
            else:
                mask = (t >= left) & (t < right)
            bin_masks.append(mask)

        irf_cached = self.dt_excitation(t)
        irf_sum = np.sum(irf_cached)
        if irf_sum > 0:
            irf_cached = irf_cached / irf_sum

        for design_idx, param_val in enumerate(tau_grid):
            self._set_cfg_param(target_param, float(param_val))
            pdf_cen = self.dt_pdf(t, irf=irf_cached)
            deriv_rows = np.zeros((len(active_params), n_bins), dtype=float)
            for bin_idx, mask in enumerate(bin_masks):
                p_cen = float(np.sum(pdf_cen[mask]))
                probs[design_idx, bin_idx] = max(p_cen, 0.0)

            for param_idx, param_name in enumerate(active_params):
                base_val = float(param_val) if param_name == target_param else float(original_values[param_name])
                lower_bound, upper_bound = self._get_cfg_param_bounds(param_name)
                delta_param = self._get_cfg_param_step(param_name, base_val, cfg.dt_input, 0.01)
                plus_val = base_val + delta_param
                minus_val = base_val - delta_param

                if lower_bound is not None:
                    plus_val = max(lower_bound, plus_val)
                    minus_val = max(lower_bound, minus_val)
                if upper_bound is not None:
                    plus_val = min(upper_bound, plus_val)
                    minus_val = min(upper_bound, minus_val)
                if np.isclose(plus_val, minus_val):
                    plus_val = base_val + delta_param
                    minus_val = max(lower_bound or 1e-6, base_val - delta_param)

                self._set_cfg_param(param_name, plus_val)
                pdf_plus = self.dt_pdf(t, irf=irf_cached)
                self._set_cfg_param(param_name, minus_val)
                pdf_minus = self.dt_pdf(t, irf=irf_cached)
                self._set_cfg_param(param_name, base_val)

                denom = max(plus_val - minus_val, 1e-12)
                for bin_idx, mask in enumerate(bin_masks):
                    deriv_rows[param_idx, bin_idx] = float(np.sum(pdf_plus[mask]) - np.sum(pdf_minus[mask])) / denom

            p_safe = np.maximum(probs[design_idx], 1e-15)
            projected_deriv = np.array(deriv_rows[0], copy=True)
            if nuisance_aware and len(active_params) > 1:
                nuisance_deriv = deriv_rows[1:]
                fim_eta_eta = (nuisance_deriv / p_safe) @ nuisance_deriv.T
                fim_eta_target = (nuisance_deriv / p_safe) @ deriv_rows[0]
                try:
                    coeff = np.linalg.solve(fim_eta_eta, fim_eta_target)
                except np.linalg.LinAlgError:
                    coeff = np.linalg.pinv(fim_eta_eta) @ fim_eta_target
                projected_deriv = deriv_rows[0] - coeff @ nuisance_deriv
            eff_deriv[design_idx] = projected_deriv

        self._set_cfg_param(target_param, original_param_value)
        for name, value in original_values.items():
            self._set_cfg_param(name, value)

        weights = np.ones(len(tau_grid), dtype=float) / max(len(tau_grid), 1)
        segment_scores = np.full((n_bins, n_bins), -np.inf, dtype=float)
        c_probs = np.concatenate([np.zeros((n_design, 1)), np.cumsum(probs, axis=1)], axis=1)
        c_deriv = np.concatenate([np.zeros((n_design, 1)), np.cumsum(eff_deriv, axis=1)], axis=1)

        for i in range(n_bins):
            for j in range(i, n_bins):
                score = 0.0
                for design_idx in range(n_design):
                    p_seg = c_probs[design_idx, j + 1] - c_probs[design_idx, i]
                    d_seg = c_deriv[design_idx, j + 1] - c_deriv[design_idx, i]
                    if p_seg > 1e-15:
                        score += weights[design_idx] * ((d_seg ** 2) / p_seg)
                segment_scores[i, j] = score
        return probs, segment_scores

    def _is_cfg_param_available(self, name: str) -> bool:
        if name == "tau2":
            return len(getattr(self.config, "taus", [])) > 1
        if name == "alpha":
            return len(getattr(self.config, "amplitudes", [])) > 1
        if name == "beta":
            return str(getattr(self.config, "decay_model", "exponential")).lower() == "stretched"
        if name in {"tau1", "background"}:
            return True
        return False

    def _get_active_compression_params(self) -> List[str]:
        cfg = self.config
        target_param = cfg.f_x_param
        active_params = [target_param]
        for name in ["tau1", "tau2", "alpha", "background", "beta"]:
            if name == target_param:
                continue
            if not bool(getattr(cfg, "fixed_params", {}).get(name, True)) and self._is_cfg_param_available(name):
                active_params.append(name)
        return active_params

    def _compute_effective_fisher_info_for_params(self, x_grid: np.ndarray, n_photons: int,
                                                  active_params: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        cfg = self.config
        target_param = active_params[0]

        rise = max(float(getattr(cfg, "gate_rise", 0.0)), 0.0)
        fall = max(float(getattr(cfg, "gate_fall", rise)), 0.0)
        dt_user = cfg.dt_override if (cfg.dt_override and cfg.dt_override > 0) else (cfg.dt_input if (cfg.dt_input and cfg.dt_input > 0) else 0.01)
        if rise <= 0.0 and fall <= 0.0:
            dt = dt_user
        else:
            edge_scale = max(rise, fall, 1e-4)
            dt = min(dt_user, edge_scale / 5.0)
            dt = max(dt, 0.005)

        n_gates = len(cfg.gate_edges) - 1
        original_dt_override = cfg.dt_override
        try:
            cfg.dt_override = dt
            self.distill_gates()
            gate_profiles = self._statistical_gate_profiles(self.gate_shapes)
            t = np.array(self.time_vector, copy=True)
        finally:
            cfg.dt_override = original_dt_override

        fisher_values = np.zeros(len(x_grid))
        f_values = np.zeros(len(x_grid))
        epsilon = 0.01
        irf_cached = self.dt_excitation(t)
        irf_sum = np.sum(irf_cached)
        if irf_sum > 0:
            irf_cached /= irf_sum

        original_values = {name: self._get_cfg_param(name) for name in active_params}

        for k, x_val in enumerate(x_grid):
            try:
                param_val = float(x_val)
                self._set_cfg_param(target_param, param_val)
                p_cen_pdf = self.dt_pdf(t, irf=irf_cached)
                p_cen_gates = gate_profiles @ p_cen_pdf
                p_cen_gates = p_cen_gates * self._collection_efficiency_scale(n_gates)
                p_cen_sum = np.sum(p_cen_gates)
                if (not self._use_raw_gate_statistics()) and p_cen_sum > 0:
                    p_cen_gates = p_cen_gates / p_cen_sum

                deriv_rows = np.zeros((len(active_params), len(p_cen_gates)), dtype=float)
                for param_idx, param_name in enumerate(active_params):
                    base_val = param_val if param_name == target_param else float(original_values[param_name])
                    lower_bound, upper_bound = self._get_cfg_param_bounds(param_name)
                    delta_param = self._get_cfg_param_step(param_name, base_val, dt, epsilon)
                    plus_val = base_val + delta_param
                    minus_val = base_val - delta_param

                    if lower_bound is not None:
                        minus_val = max(lower_bound, minus_val)
                        plus_val = max(lower_bound, plus_val)
                    if upper_bound is not None:
                        minus_val = min(upper_bound, minus_val)
                        plus_val = min(upper_bound, plus_val)
                    if np.isclose(plus_val, minus_val):
                        plus_val = base_val + delta_param
                        minus_val = max(lower_bound or 1e-6, base_val - delta_param)

                    self._set_cfg_param(param_name, plus_val)
                    p_plus_pdf = self.dt_pdf(t, irf=irf_cached)
                    p_plus_gates = gate_profiles @ p_plus_pdf
                    p_plus_gates = p_plus_gates * self._collection_efficiency_scale(n_gates)
                    p_plus_sum = np.sum(p_plus_gates)
                    if (not self._use_raw_gate_statistics()) and p_plus_sum > 0:
                        p_plus_gates = p_plus_gates / p_plus_sum

                    self._set_cfg_param(param_name, minus_val)
                    p_minus_pdf = self.dt_pdf(t, irf=irf_cached)
                    p_minus_gates = gate_profiles @ p_minus_pdf
                    p_minus_gates = p_minus_gates * self._collection_efficiency_scale(n_gates)
                    p_minus_sum = np.sum(p_minus_gates)
                    if (not self._use_raw_gate_statistics()) and p_minus_sum > 0:
                        p_minus_gates = p_minus_gates / p_minus_sum

                    self._set_cfg_param(param_name, base_val)
                    deriv_rows[param_idx] = (p_plus_gates - p_minus_gates) / max(plus_val - minus_val, 1e-12)

                p_safe = np.maximum(p_cen_gates, 1e-15)
                fim = (deriv_rows / p_safe) @ deriv_rows.T
                if len(active_params) == 1:
                    fisher_info = n_photons * float(fim[0, 0])
                else:
                    a = float(fim[0, 0])
                    b = fim[1:, 0]
                    c = fim[1:, 1:]
                    try:
                        correction = float(b.T @ np.linalg.solve(c, b))
                    except np.linalg.LinAlgError:
                        correction = float(b.T @ (np.linalg.pinv(c) @ b))
                    fisher_info = n_photons * max(a - correction, 0.0)
                fisher_values[k] = fisher_info

                if fisher_info > 0:
                    sigma_param = 1.0 / np.sqrt(fisher_info)
                    denom = max(abs(param_val), 1e-12)
                    f_values[k] = (sigma_param / denom) * np.sqrt(n_photons)
                else:
                    f_values[k] = np.nan
            except Exception:
                fisher_values[k] = np.nan
                f_values[k] = np.nan
            finally:
                for name, value in original_values.items():
                    self._set_cfg_param(name, value)

        return fisher_values, f_values

    def _boundaries_to_edges(self, boundaries: List[int], fine_edges: np.ndarray) -> np.ndarray:
        idx = np.array(sorted(set(boundaries)), dtype=int)
        idx[0] = 0
        idx[-1] = len(fine_edges) - 1
        return fine_edges[idx]

    def _solve_fisher_compression_partition(self, fine_edges: np.ndarray, segment_scores: np.ndarray,
                                            k_target: int) -> np.ndarray:
        n_bins = len(fine_edges) - 1
        k_target = max(1, min(int(k_target), n_bins))
        dp = np.full((k_target + 1, n_bins + 1), -np.inf, dtype=float)
        prev = np.full((k_target + 1, n_bins + 1), -1, dtype=int)
        dp[0, 0] = 0.0

        for k in range(1, k_target + 1):
            if bool(getattr(self.config, "b_interrupt", False)):
                raise InterruptedError("Optimisation interrupted.")
            for j in range(k, n_bins + 1):
                best_val = -np.inf
                best_t = -1
                for t in range(k - 1, j):
                    if not np.isfinite(dp[k - 1, t]):
                        continue
                    cand = dp[k - 1, t] + segment_scores[t, j - 1]
                    if cand > best_val:
                        best_val = cand
                        best_t = t
                dp[k, j] = best_val
                prev[k, j] = best_t

        boundaries = [n_bins]
        j = n_bins
        for k in range(k_target, 0, -1):
            t = prev[k, j]
            if t < 0:
                break
            boundaries.append(t)
            j = t
        boundaries.append(0)
        return self._boundaries_to_edges(sorted(set(boundaries)), fine_edges)

    def _optimize_gates_direct_slsqp(self, start: float, end: float, tau_grid: np.ndarray,
                                     n_gates: int, n_restarts: int,
                                     callback: Optional[Callable],
                                     progress_callback: Optional[Callable],
                                     initial_edges: Optional[np.ndarray] = None) -> Tuple[np.ndarray, float]:
        best_j = np.inf
        best_edges = None
        epsilon = max((end - start) / 1000.0, 1e-4)
        eval_step = 0
        ftol = float(getattr(self.config, "detection_opt_ftol", 1e-4))
        maxiter = int(getattr(self.config, "detection_opt_maxiter", 50))

        def objective(internal_edges):
            nonlocal eval_step
            if bool(getattr(self.config, "b_interrupt", False)):
                raise InterruptedError("Optimisation interrupted.")
            edges = np.concatenate(([start], np.sort(internal_edges), [end]))
            j_val, _, _, _ = self._evaluate_gate_edges(
                edges,
                tau_grid,
                callback=callback,
                progress_callback=progress_callback,
                algorithm="direct_slsqp",
                step=eval_step,
            )
            eval_step += 1
            return j_val

        bounds = [(start + epsilon, end - epsilon)] * max(n_gates - 1, 0)
        for r in range(n_restarts):
            if bool(getattr(self.config, "b_interrupt", False)):
                raise InterruptedError("Optimisation interrupted.")
            if n_gates <= 1:
                best_edges = np.array([start, end], dtype=float)
                best_j, _, _, _ = self._evaluate_gate_edges(
                    best_edges,
                    tau_grid,
                    callback=callback,
                    progress_callback=progress_callback,
                    algorithm="direct_slsqp",
                    step=eval_step,
                    note="single_gate",
                )
                break
            if r == 0:
                if initial_edges is not None and len(initial_edges) == n_gates + 1:
                    initial_edges = np.asarray(initial_edges, dtype=float)
                    if np.all(np.diff(initial_edges) > 0) and np.isclose(initial_edges[0], start, atol=1e-6) and np.isclose(initial_edges[-1], end, atol=1e-6):
                        x0 = np.array(initial_edges[1:-1], copy=True)
                    else:
                        x0 = np.linspace(start, end, n_gates + 1)[1:-1]
                else:
                    x0 = np.linspace(start, end, n_gates + 1)[1:-1]
            else:
                x0 = np.sort(np.random.rand(n_gates - 1) * max(end - start, 1e-6) + start)
            res = minimize(objective, x0, bounds=bounds, method='SLSQP', options={'ftol': ftol, 'maxiter': maxiter})
            if res.success and res.fun < best_j:
                best_j = float(res.fun)
                best_edges = np.concatenate(([start], np.sort(res.x), [end]))

        if best_edges is None:
            best_edges = np.linspace(start, end, n_gates + 1)
            best_j, _, _, _ = self._evaluate_gate_edges(
                best_edges,
                tau_grid,
                callback=None,
                progress_callback=progress_callback,
                algorithm="direct_slsqp",
                step=eval_step,
                note="fallback_equal_edges",
            )
        return best_edges, best_j

    def _optimize_gates_bottom_up(self, fine_edges: np.ndarray, segment_scores: np.ndarray,
                                  n_gates: int, callback: Optional[Callable],
                                  progress_callback: Optional[Callable],
                                  tau_grid: np.ndarray) -> np.ndarray:
        n_bins = len(fine_edges) - 1
        boundaries = [0, n_bins]
        step = 0

        while len(boundaries) - 1 < n_gates:
            if bool(getattr(self.config, "b_interrupt", False)):
                raise InterruptedError("Optimisation interrupted.")
            best_gain = -np.inf
            best_split = None
            for seg_idx in range(len(boundaries) - 1):
                left = boundaries[seg_idx]
                right = boundaries[seg_idx + 1]
                if right - left <= 1:
                    continue
                base_score = segment_scores[left, right - 1]
                for split in range(left + 1, right):
                    new_score = segment_scores[left, split - 1] + segment_scores[split, right - 1]
                    gain = new_score - base_score
                    if gain > best_gain:
                        best_gain = gain
                        best_split = split
            if best_split is None:
                break
            boundaries.append(best_split)
            boundaries.sort()
            edges = self._boundaries_to_edges(boundaries, fine_edges)
            self._evaluate_gate_edges(
                edges,
                tau_grid,
                callback=callback,
                progress_callback=progress_callback,
                algorithm="partition_bottom_up",
                step=step,
            )
            step += 1

        return self._boundaries_to_edges(boundaries, fine_edges)

    def _optimize_gates_top_down(self, fine_edges: np.ndarray, segment_scores: np.ndarray,
                                 n_gates: int, callback: Optional[Callable],
                                 progress_callback: Optional[Callable],
                                 tau_grid: np.ndarray) -> np.ndarray:
        n_bins = len(fine_edges) - 1
        boundaries = list(range(0, n_bins + 1))
        total_score = float(np.sum(np.diag(segment_scores)))
        step = 0

        while len(boundaries) - 1 > n_gates:
            if bool(getattr(self.config, "b_interrupt", False)):
                raise InterruptedError("Optimisation interrupted.")
            best_total = -np.inf
            best_remove_idx = None
            for remove_idx in range(1, len(boundaries) - 1):
                left = boundaries[remove_idx - 1]
                mid = boundaries[remove_idx]
                right = boundaries[remove_idx + 1]
                merged_total = (
                    total_score
                    - segment_scores[left, mid - 1]
                    - segment_scores[mid, right - 1]
                    + segment_scores[left, right - 1]
                )
                if merged_total > best_total:
                    best_total = merged_total
                    best_remove_idx = remove_idx
            if best_remove_idx is None:
                break
            boundaries.pop(best_remove_idx)
            total_score = float(best_total)
            edges = self._boundaries_to_edges(boundaries, fine_edges)
            self._evaluate_gate_edges(
                edges,
                tau_grid,
                callback=callback,
                progress_callback=progress_callback,
                algorithm="partition_top_down",
                step=step,
                note=f"segment_score={total_score:.6g}",
            )
            step += 1

        return self._boundaries_to_edges(boundaries, fine_edges)

    def _optimize_gates_fisher_compression(self, fine_edges: np.ndarray, segment_scores: np.ndarray,
                                           n_gates: int, callback: Optional[Callable],
                                           progress_callback: Optional[Callable],
                                           tau_grid: np.ndarray) -> np.ndarray:
        n_bins = len(fine_edges) - 1
        k_target = max(1, min(int(n_gates), n_bins))
        auto_compress = bool(getattr(self.config, "detection_opt_fc_auto_compress", False))

        if not auto_compress:
            edges = self._solve_fisher_compression_partition(fine_edges, segment_scores, k_target)
            self._evaluate_gate_edges(
                edges,
                tau_grid,
                callback=callback,
                progress_callback=progress_callback,
                algorithm="fisher_compression",
                step=0,
                note=f"target_gates={int(k_target)}",
            )
            return edges

        initial_k = max(k_target, min(int(getattr(self.config, "detection_opt_fc_initial_gates", max(k_target, 2))), n_bins))
        min_k = max(1, min(int(getattr(self.config, "detection_opt_fc_min_gates", 2)), initial_k))
        max_loss_pct = max(0.0, float(getattr(self.config, "detection_opt_fc_max_f_loss_pct", 5.0)))

        baseline_edges = self._solve_fisher_compression_partition(fine_edges, segment_scores, initial_k)
        baseline_j, _, baseline_f, _ = self._evaluate_gate_edges(
            baseline_edges,
            tau_grid,
            callback=callback,
            progress_callback=progress_callback,
            algorithm="fisher_compression",
            step=0,
            note=f"initial_partition_gates={int(initial_k)}",
        )
        baseline_peak_eff = self._peak_efficiency_from_f_values(baseline_f)
        best_edges = baseline_edges

        step = 1
        for k in range(initial_k - 1, min_k - 1, -1):
            if bool(getattr(self.config, "b_interrupt", False)):
                raise InterruptedError("Optimisation interrupted.")
            edges = self._solve_fisher_compression_partition(fine_edges, segment_scores, k)
            j_val, _, f_val, _ = self._evaluate_gate_edges(
                edges,
                tau_grid,
                callback=callback,
                progress_callback=progress_callback,
                algorithm="fisher_compression",
                step=step,
                note=f"compressed_gates={int(k)}",
            )
            peak_eff_loss_pct = max(
                0.0,
                (baseline_peak_eff - self._peak_efficiency_from_f_values(f_val)) * 100.0,
            )
            if peak_eff_loss_pct <= max_loss_pct + 1e-9:
                best_edges = edges
            else:
                break
            step += 1

        return best_edges

    def optimize_gates(self, n_gates: int, t_max: float, tau_range: Tuple[float, float],
                       n_tau: int = 50, n_restarts: int = 20,
                       callback: Optional[Callable] = None,
                       progress_callback: Optional[Callable] = None,
                       keep_history: bool = True,
                       algorithm: Optional[str] = None,
                       start_anchor: Optional[str] = None,
                       start_time: Optional[float] = None,
                       end_anchor: Optional[str] = None,
                       end_time: Optional[float] = None) -> Tuple[np.ndarray, float, dict]:
        """
        Finds optimal gate edges using one of several algorithm families.
        """
        tau_grid = self._build_optimization_x_range(
            self.config,
            float(tau_range[0]),
            float(tau_range[1]),
            int(n_tau),
        )
        orig_edges = list(self.config.gate_edges)
        algorithm = algorithm or getattr(self.config, "detection_optimization_algorithm", "direct_slsqp")
        history: List[Dict[str, Any]] = []

        if bool(getattr(self.config, "b_interrupt", False)):
            raise InterruptedError("Optimisation interrupted.")

        def record_progress(payload: Dict[str, Any]):
            if keep_history:
                history.append(self._clone_gate_optimization_payload(payload))
            if progress_callback is not None:
                progress_callback(self._clone_gate_optimization_payload(payload))

        start, end = self._resolve_optimization_window(
            t_max=t_max,
            start_anchor=start_anchor,
            start_time=start_time,
            end_anchor=end_anchor,
            end_time=end_time,
        )

        if end <= start:
            end = start + 1e-3

        try:
            if algorithm == "direct_slsqp":
                best_edges, best_j = self._optimize_gates_direct_slsqp(
                    start=start,
                    end=end,
                    tau_grid=tau_grid,
                    n_gates=n_gates,
                    n_restarts=n_restarts,
                    callback=callback,
                    progress_callback=record_progress,
                    initial_edges=np.asarray(orig_edges, dtype=float) if len(orig_edges) == n_gates + 1 else None,
                )
            else:
                fine_bins_per_gate = max(2, int(getattr(self.config, "detection_opt_fine_bins_per_gate", 12)))
                fine_bin_cap = max(24, int(getattr(self.config, "detection_opt_fine_bin_cap", 256)))
                reference_gates = int(n_gates)
                if algorithm in {"fisher_compression", "fisher_compression_dp"} and bool(getattr(self.config, "detection_opt_fc_auto_compress", False)):
                    reference_gates = max(reference_gates, int(getattr(self.config, "detection_opt_fc_initial_gates", reference_gates)))
                n_fine = min(max(reference_gates * fine_bins_per_gate, 24), fine_bin_cap)
                fine_edges = np.linspace(start, end, n_fine + 1)
                _, segment_scores = self._build_fine_bin_scores(fine_edges, tau_grid)
                if algorithm == "partition_bottom_up":
                    best_edges = self._optimize_gates_bottom_up(
                        fine_edges, segment_scores, n_gates, callback, record_progress, tau_grid
                    )
                elif algorithm == "partition_top_down":
                    best_edges = self._optimize_gates_top_down(
                        fine_edges, segment_scores, n_gates, callback, record_progress, tau_grid
                    )
                elif algorithm in {"fisher_compression", "fisher_compression_dp"}:
                    best_edges = self._optimize_gates_fisher_compression(
                        fine_edges, segment_scores, n_gates, callback, record_progress, tau_grid
                    )
                else:
                    raise ValueError(f"Unknown gate-optimization algorithm: {algorithm}")
                best_j, _, _, final_payload = self._evaluate_gate_edges(
                    best_edges,
                    tau_grid,
                    callback=None,
                    progress_callback=record_progress,
                    algorithm=algorithm,
                    step=len(history),
                    note="final",
                    emit_progress=not history or not np.array_equal(np.asarray(history[-1].get("edges")), np.asarray(best_edges)),
                )

            self.config.gate_edges = best_edges.tolist()
            self.config.gate_widths = np.diff(np.asarray(best_edges, dtype=float)).tolist()
            self.config.gate_type = "custom"
            self.distill_gates()
            fi, f_val = self.compute_fisher_info(tau_grid, n_photons=1e4)
            info = {
                "algorithm": algorithm,
                "tau_grid": tau_grid,
                "fisher_info": fi,
                "f_val": f_val,
                "gate_profiles": self.get_gate_profiles_vis(max(float(t_max), float(self.config.period))),
                "t": np.arange(0, max(float(t_max), float(self.config.period)) + 0.05, 0.05),
                "window_start": start,
                "window_end": end,
                "history": history,
            }
            return best_edges, best_j, info
        finally:
            self.config.gate_edges = orig_edges
            self.distill_gates()

    def _excitation_area_and_peak(self, cfg: Optional[PhysicsConfig] = None) -> Tuple[float, float]:
        cfg_local = copy.deepcopy(cfg or self.config)
        original_cfg = self.config
        try:
            self.config = cfg_local
            dt = max(float(getattr(cfg_local, "dt_input", 0.01)), 0.005)
            t = np.arange(0.0, max(float(cfg_local.period), float(cfg_local.irf_position + max(cfg_local.irf_fwhm, dt)) + dt), dt)
            excitation = self.dt_excitation(t)
            area = float(np.trapz(excitation, t)) if len(t) > 1 else float(np.sum(excitation) * dt)
            peak = float(np.max(excitation)) if excitation.size else 0.0
            return max(area, 1e-12), max(peak, 1e-12)
        finally:
            self.config = original_cfg

    def _throughput_metric(self, cfg: PhysicsConfig, reference_excitation_area: float) -> float:
        gate_count = max(int(len(getattr(cfg, "gate_edges", [])) - 1), 1)
        area, _ = self._excitation_area_and_peak(cfg)
        constraint = str(getattr(cfg, "excitation_optimization_constraint", "fixed_dose")).lower()
        photon_scale = area / max(float(reference_excitation_area), 1e-12) if constraint == "fixed_peak" else 1.0
        collection_scale = 1.0 / gate_count if str(getattr(cfg, "gate_collection_mode", "histogram")).lower() == "sequential" else 1.0
        return max(photon_scale * collection_scale, 1e-12)

    @staticmethod
    def _peak_efficiency_from_f_values(f_values: np.ndarray) -> float:
        f_arr = np.asarray(f_values, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            efficiency = np.where(np.isfinite(f_arr) & (f_arr > 0.0), 1.0 / np.square(f_arr), np.nan)
        if not np.any(np.isfinite(efficiency)):
            return 0.0
        return float(np.clip(np.nanmax(efficiency), 0.0, 1.0))

    def _compute_mean_f_for_config(self, cfg: PhysicsConfig, x_range: np.ndarray,
                                   n_photons: int = 1e4) -> float:
        original_cfg = self.config
        try:
            self.config = copy.deepcopy(cfg)
            self.invalidate_grid()
            self.distill_gates()
            _, f_val = self.compute_fisher_info(x_range, int(n_photons))
            return float(np.nanmean(f_val)) if np.any(np.isfinite(f_val)) else np.inf
        finally:
            self.config = original_cfg
            self.invalidate_grid()

    def _build_excitation_throughput_reference_peak_efficiency(self, cfg: PhysicsConfig,
                                                               x_range: np.ndarray,
                                                               include_detection_stage: bool) -> float:
        reference_cfg = copy.deepcopy(cfg)
        reference_cfg.irf_profile = "ideal (dirac)"
        reference_cfg.irf_freeform_points = []
        reference_cfg.irf_fwhm = max(float(getattr(reference_cfg, "irf_fwhm", 0.05)), 1e-6)

        if not include_detection_stage:
            original_cfg = self.config
            try:
                self.config = copy.deepcopy(reference_cfg)
                self.invalidate_grid()
                self.distill_gates()
                _, f_val = self.compute_fisher_info(x_range, int(reference_cfg.precision_photons))
                return self._peak_efficiency_from_f_values(f_val)
            finally:
                self.config = original_cfg
                self.invalidate_grid()

        scratch = TwinEngine(copy.deepcopy(reference_cfg))
        best_edges, _, _ = scratch.optimize_gates(
            n_gates=max(1, len(reference_cfg.gate_edges) - 1),
            t_max=float(
                reference_cfg.detection_opt_end_time
                if reference_cfg.detection_opt_end_anchor == "custom"
                else reference_cfg.period
            ),
            tau_range=(float(reference_cfg.f_x_min), float(reference_cfg.f_x_max)),
            n_tau=max(int(reference_cfg.f_x_steps), 10),
            n_restarts=max(1, int(getattr(reference_cfg, "detection_opt_restarts", 20))),
            keep_history=False,
            algorithm=reference_cfg.detection_optimization_algorithm,
            start_anchor=reference_cfg.detection_opt_start_anchor,
            start_time=reference_cfg.detection_opt_start_time,
            end_anchor=reference_cfg.detection_opt_end_anchor,
            end_time=reference_cfg.detection_opt_end_time,
        )
        reference_cfg.gate_type = "custom"
        reference_cfg.gate_edges = np.asarray(best_edges, dtype=float).tolist()
        reference_cfg.gate_widths = np.diff(np.asarray(best_edges, dtype=float)).tolist()
        scratch.config = copy.deepcopy(reference_cfg)
        scratch.invalidate_grid()
        scratch.distill_gates()
        _, f_val = scratch.compute_fisher_info(x_range, int(reference_cfg.precision_photons))
        return scratch._peak_efficiency_from_f_values(f_val)

    def _summarise_excitation_profile(self, cfg: PhysicsConfig) -> Dict[str, Any]:
        area, peak = self._excitation_area_and_peak(cfg)
        summary: Dict[str, Any] = {
            "profile": str(getattr(cfg, "irf_profile", "gaussian")),
            "constraint": str(getattr(cfg, "excitation_optimization_constraint", "fixed_dose")),
            "area_ns": float(area),
            "peak": float(peak),
            "equivalent_width_ns": float(area / max(peak, 1e-12)),
        }
        if str(getattr(cfg, "irf_profile", "")).lower() != "free_form":
            summary["width_ns"] = float(getattr(cfg, "irf_fwhm", 0.0))
        else:
            summary["control_points"] = [float(value) for value in getattr(cfg, "irf_freeform_points", [])]
        return summary

    def _build_optimization_x_range(self, cfg: PhysicsConfig, x_min: float, x_max: float,
                                    n_points: int) -> np.ndarray:
        scale = str(getattr(cfg, "f_x_scale", "log")).lower()
        n_points = max(int(n_points), 2)
        if scale == "log" and x_min > 0.0 and x_max > 0.0:
            return np.logspace(np.log10(x_min), np.log10(x_max), n_points)
        if scale == "exp" and x_min > 0.0 and x_max > 0.0:
            return np.geomspace(x_min, x_max, n_points)
        return np.linspace(x_min, x_max, n_points)

    def _evaluate_optimization_config(self, candidate_cfg: PhysicsConfig, x_range: np.ndarray,
                                      algorithm: str, step: int,
                                      callback: Optional[Callable],
                                      progress_callback: Optional[Callable],
                                      objective_mode: str,
                                      reference_excitation_area: float,
                                      note: str = "") -> Dict[str, Any]:
        original_cfg = self.config
        try:
            self.config = copy.deepcopy(candidate_cfg)
            self.invalidate_grid()
            self.distill_gates()
            fi, f_val = self.compute_fisher_info(x_range, n_photons=1e4)
            mean_f = float(np.nanmean(f_val)) if np.any(np.isfinite(f_val)) else np.inf
            min_f = float(np.nanmin(f_val)) if np.any(np.isfinite(f_val)) else np.nan
            peak_efficiency = self._peak_efficiency_from_f_values(f_val)
            throughput_scale = self._throughput_metric(candidate_cfg, reference_excitation_area)
            throughput_metric = peak_efficiency * throughput_scale
            objective = mean_f if objective_mode == "fisher_information" else (1.0 / throughput_metric)
            payload = self._build_gate_optimization_payload(
                np.asarray(candidate_cfg.gate_edges, dtype=float),
                x_range,
                objective,
                fi,
                f_val,
                algorithm,
                step=step,
                note=note,
            )
            payload["config"] = copy.deepcopy(candidate_cfg.model_dump() if hasattr(candidate_cfg, "model_dump") else candidate_cfg.dict())
            payload["throughput_scale"] = float(throughput_scale)
            payload["throughput_metric"] = float(throughput_metric)
            payload["mean_f"] = float(mean_f)
            payload["min_f"] = float(min_f)
            payload["peak_efficiency"] = float(peak_efficiency)
            payload["excitation_summary"] = self._summarise_excitation_profile(candidate_cfg)
            self._emit_gate_optimization_progress(callback, progress_callback, payload)
            return payload
        finally:
            self.config = original_cfg
            self.invalidate_grid()

    def optimize_excitation(self, tau_range: Tuple[float, float], n_tau: int = 50,
                            callback: Optional[Callable] = None,
                            progress_callback: Optional[Callable] = None,
                            throughput_reference_peak_efficiency: Optional[float] = None) -> Tuple[PhysicsConfig, float, Dict[str, Any]]:
        cfg = copy.deepcopy(self.config)
        x_range = self._build_optimization_x_range(cfg, float(tau_range[0]), float(tau_range[1]), int(n_tau))
        objective_mode = str(getattr(cfg, "optimization_objective", "fisher_information")).lower()
        reference_area, _ = self._excitation_area_and_peak(cfg)
        profile = str(getattr(cfg, "excitation_optimization_profile", "gaussian")).lower()
        history: List[Dict[str, Any]] = []

        def evaluate_candidate(candidate_cfg: PhysicsConfig, step: int, note: str) -> Dict[str, Any]:
            payload = self._evaluate_optimization_config(
                candidate_cfg,
                x_range,
                algorithm=f"excitation_{profile}",
                step=step,
                callback=callback,
                progress_callback=progress_callback,
                objective_mode=objective_mode,
                reference_excitation_area=reference_area,
                note=note,
            )
            history.append(self._clone_gate_optimization_payload(payload))
            return payload

        best_payload = None
        step = 0

        if profile in {"gaussian", "square", "rectangular"}:
            candidate_profile = "rectangular" if profile in {"square", "rectangular"} else "gaussian"
            width_min = max(float(getattr(cfg, "excitation_optimization_width_min", 0.05)), 1e-4)
            width_max = max(width_min, float(getattr(cfg, "excitation_optimization_width_max", max(width_min, 10.0))))
            widths = np.linspace(width_min, width_max, 48)
            candidates = []
            for width in widths:
                if bool(getattr(self.config, "b_interrupt", False)):
                    raise InterruptedError("Optimisation interrupted.")
                candidate_cfg = copy.deepcopy(cfg)
                candidate_cfg.irf_profile = candidate_profile
                candidate_cfg.irf_fwhm = float(width)
                payload = evaluate_candidate(candidate_cfg, step, f"width={float(width):.6g}")
                candidates.append((candidate_cfg, payload))
                step += 1
            if objective_mode == "fisher_throughput":
                ref_peak_eff = float(
                    throughput_reference_peak_efficiency
                    if throughput_reference_peak_efficiency is not None and np.isfinite(throughput_reference_peak_efficiency)
                    else max(float(item[1].get("peak_efficiency", 0.0)) for item in candidates)
                )
                min_allowed = max(0.0, ref_peak_eff - max(float(getattr(cfg, "optimization_max_fi_loss_pct", 5.0)), 0.0) / 100.0)
                feasible = [item for item in candidates if float(item[1].get("peak_efficiency", 0.0)) >= min_allowed - 1e-12]
                choice = max(feasible, key=lambda item: (float(item[1]["throughput_metric"]), float(item[1].get("peak_efficiency", 0.0)))) if feasible else max(candidates, key=lambda item: (float(item[1].get("peak_efficiency", 0.0)), float(item[1]["throughput_metric"])))
            else:
                choice = min(candidates, key=lambda item: float(item[1]["objective"]))
            best_cfg, best_payload = choice
        else:
            n_ctrl = max(int(getattr(cfg, "excitation_optimization_control_points", 8)), 3)
            base_points = np.asarray(getattr(cfg, "irf_freeform_points", []) or [], dtype=float)
            if base_points.size != n_ctrl:
                base_points = np.ones(n_ctrl, dtype=float)
            eval_cache: Dict[Tuple[float, ...], Dict[str, Any]] = {}

            def normalise_points(points: np.ndarray) -> np.ndarray:
                points = np.maximum(np.asarray(points, dtype=float), 0.0)
                max_val = np.max(points) if points.size else 0.0
                if max_val <= 0:
                    return np.ones(n_ctrl, dtype=float)
                return points / max_val

            def objective_fn(points: np.ndarray) -> float:
                nonlocal step
                if bool(getattr(self.config, "b_interrupt", False)):
                    raise InterruptedError("Optimisation interrupted.")
                norm_points = normalise_points(points)
                key = tuple(np.round(norm_points, 8).tolist())
                if key in eval_cache:
                    return float(eval_cache[key]["payload"]["objective"])
                candidate_cfg = copy.deepcopy(cfg)
                candidate_cfg.irf_profile = "free_form"
                candidate_cfg.irf_freeform_points = norm_points.tolist()
                payload = evaluate_candidate(candidate_cfg, step, "free_form")
                step += 1
                eval_cache[key] = {"config": candidate_cfg, "payload": payload}
                return float(payload["objective"])

            initial = normalise_points(base_points)
            bounds = [(0.0, 1.0)] * n_ctrl
            objective_fn(initial)
            result = minimize(objective_fn, initial, method="SLSQP", bounds=bounds, options={"maxiter": 40, "ftol": 1e-3, "disp": False})
            final_points = normalise_points(result.x if result.success else initial)
            final_key = tuple(np.round(final_points, 8).tolist())
            if final_key not in eval_cache:
                candidate_cfg = copy.deepcopy(cfg)
                candidate_cfg.irf_profile = "free_form"
                candidate_cfg.irf_freeform_points = final_points.tolist()
                payload = evaluate_candidate(candidate_cfg, step, "free_form_final")
                eval_cache[final_key] = {"config": candidate_cfg, "payload": payload}
            candidates = [(item["config"], item["payload"]) for item in eval_cache.values()]
            if objective_mode == "fisher_throughput":
                ref_peak_eff = float(
                    throughput_reference_peak_efficiency
                    if throughput_reference_peak_efficiency is not None and np.isfinite(throughput_reference_peak_efficiency)
                    else max(float(item[1].get("peak_efficiency", 0.0)) for item in candidates)
                )
                min_allowed = max(0.0, ref_peak_eff - max(float(getattr(cfg, "optimization_max_fi_loss_pct", 5.0)), 0.0) / 100.0)
                feasible = [item for item in candidates if float(item[1].get("peak_efficiency", 0.0)) >= min_allowed - 1e-12]
                choice = max(feasible, key=lambda item: (float(item[1]["throughput_metric"]), float(item[1].get("peak_efficiency", 0.0)))) if feasible else max(candidates, key=lambda item: (float(item[1].get("peak_efficiency", 0.0)), float(item[1]["throughput_metric"])))
            else:
                choice = min(candidates, key=lambda item: float(item[1]["objective"]))
            best_cfg, best_payload = choice

        info = {
            "history": history,
            "x_range": np.array(x_range, copy=True),
            "algorithm": f"excitation_{profile}",
        }
        return copy.deepcopy(best_cfg), float(best_payload["objective"]), info

    def run_optimization_workflow(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        cfg = copy.deepcopy(self.config)
        x_range = self._build_optimization_x_range(
            cfg,
            float(cfg.f_x_min),
            float(cfg.f_x_max),
            max(int(cfg.f_x_steps), 10),
        )
        history: List[Dict[str, Any]] = []

        def on_progress(payload: Dict[str, Any]):
            history.append(self._clone_gate_optimization_payload(payload))
            if progress_callback is not None:
                progress_callback(self._clone_gate_optimization_payload(payload))

        run_detection = bool(getattr(cfg, "optimize_detection_gates", False))
        run_excitation = bool(getattr(cfg, "optimize_excitation_profile", False))
        objective_mode = str(getattr(cfg, "optimization_objective", "fisher_information")).lower()
        excitation_throughput_reference = None
        if run_excitation and objective_mode == "fisher_throughput":
            excitation_throughput_reference = self._build_excitation_throughput_reference_peak_efficiency(
                cfg,
                x_range,
                include_detection_stage=run_detection,
            )

        def run_detection_stage():
            best_edges, best_j, _ = self.optimize_gates(
                n_gates=max(1, len(self.config.gate_edges) - 1),
                t_max=float(self.config.detection_opt_end_time if self.config.detection_opt_end_anchor == "custom" else self.config.period),
                tau_range=(float(self.config.f_x_min), float(self.config.f_x_max)),
                n_tau=max(int(self.config.f_x_steps), 10),
                n_restarts=max(1, int(getattr(self.config, "detection_opt_restarts", 20))),
                progress_callback=on_progress,
                keep_history=False,
                algorithm=self.config.detection_optimization_algorithm,
                start_anchor=self.config.detection_opt_start_anchor,
                start_time=self.config.detection_opt_start_time,
                end_anchor=self.config.detection_opt_end_anchor,
                end_time=self.config.detection_opt_end_time,
            )
            self.config.gate_type = "custom"
            self.config.gate_edges = np.asarray(best_edges, dtype=float).tolist()
            self.config.gate_widths = np.diff(np.asarray(best_edges, dtype=float)).tolist()
            self.distill_gates()
            return float(best_j)

        def run_excitation_stage():
            best_cfg, best_j, _ = self.optimize_excitation(
                tau_range=(float(self.config.f_x_min), float(self.config.f_x_max)),
                n_tau=max(int(self.config.f_x_steps), 10),
                progress_callback=on_progress,
                throughput_reference_peak_efficiency=excitation_throughput_reference,
            )
            self.config = copy.deepcopy(best_cfg)
            self.invalidate_grid()
            self.distill_gates()
            return float(best_j)

        if not run_detection and not run_excitation:
            raise ValueError("Enable at least one optimisation target.")

        order = []
        if run_detection and run_excitation:
            if str(getattr(cfg, "optimization_first", "detection")).lower() == "excitation":
                order = ["excitation", "detection"]
            else:
                order = ["detection", "excitation"]
        elif run_detection:
            order = ["detection"]
        else:
            order = ["excitation"]

        last_objective = np.nan
        if len(order) == 1:
            last_objective = run_detection_stage() if order[0] == "detection" else run_excitation_stage()
        else:
            iterations = max(int(getattr(cfg, "optimization_iterations", 20)), 1)
            for _ in range(iterations):
                for scope in order:
                    if bool(getattr(self.config, "b_interrupt", False)):
                        raise InterruptedError("Optimisation interrupted.")
                    last_objective = run_detection_stage() if scope == "detection" else run_excitation_stage()

        final_fi, final_f = self.compute_fisher_info(x_range, int(self.config.precision_photons))
        window_start, window_end = self._resolve_optimization_window(
            t_max=float(self.config.period),
            start_anchor=getattr(self.config, "detection_opt_start_anchor", None),
            start_time=getattr(self.config, "detection_opt_start_time", None),
            end_anchor=getattr(self.config, "detection_opt_end_anchor", None),
            end_time=getattr(self.config, "detection_opt_end_time", None),
        )
        return {
            "history": history,
            "x_range": x_range,
            "best_objective": float(last_objective),
            "window_start": float(window_start),
            "window_end": float(window_end),
            "final_config": copy.deepcopy(self.config.model_dump() if hasattr(self.config, "model_dump") else self.config.dict()),
            "final_fisher_info": np.array(final_fi, copy=True),
            "final_f_value": np.array(final_f, copy=True),
            "final_excitation_summary": self._summarise_excitation_profile(self.config),
        }

    def get_gate_profiles_vis(self, t_max: float) -> np.ndarray:
        """Helper for visualization: returns sigmoid gate profiles for a standard time vector."""
        dt = 0.05
        t = np.arange(0, t_max + dt, dt)
        cfg = self.config
        n_gates = len(cfg.gate_edges) - 1
        profiles = np.zeros((n_gates, len(t)))
        
        def sigmoid(x):
            return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))

        rise = max(float(getattr(cfg, "gate_rise", 0.0)), 0.0)
        fall = max(float(getattr(cfg, "gate_fall", rise)), 0.0)

        for i in range(n_gates):
            a = cfg.gate_edges[i]
            b = cfg.gate_edges[i+1]
            gate_start = sigmoid((t - a) / rise) if rise > 0 else (t >= a).astype(float)
            gate_end = sigmoid((t - b) / fall) if fall > 0 else (t >= b).astype(float)
            profiles[i, :] = gate_start * (1.0 - gate_end)
        return profiles
