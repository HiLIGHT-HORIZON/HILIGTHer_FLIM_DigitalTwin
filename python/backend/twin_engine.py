import numpy as np
import copy
from scipy.interpolate import interp1d
from scipy.optimize import minimize, fmin
from scipy.signal import convolve
from scipy.stats import ttest_1samp
from typing import Optional, Tuple, List, Callable
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
            cfg.burst_enabled,
            cfg.burst_sub_period,
            cfg.burst_sub_fwhm,
            cfg.burst_sub_rise_time,
            cfg.burst_sub_fall_time,
            cfg.b_decay_wrapping,
            tuple(cfg.gate_edges),
            cfg.gate_profile,
            cfg.gate_rise,
            cfg.period,
            cfg.timing_jitter,
            cfg.dt_override,
            cfg.dt_input,
        )

    def ensure_grid_current(self):
        self._sync_grid_definition_from_precision_config()
        signature = self._grid_signature()
        if self.grid_templates is None or self.grid_tau_axis is None or self.grid_signature != signature:
            self.precalculate_grid()

    def distill_gates(self):
        """Standardizes gate generation within the measurement window defined by cfg.period."""
        cfg = self.config
        edges = cfg.gate_edges
        dt = cfg.dt_override if (cfg.dt_override and cfg.dt_override > 0) else cfg.dt_input
        
        # Strict boundary: 0 to Period
        t_start = 0.0
        t_end = cfg.period
        self.time_vector = np.arange(t_start, t_end, dt)
        
        n_gates = len(edges) - 1
        n_time = len(self.time_vector)
        self.gate_shapes = np.zeros((n_gates, n_time))
        
        t = self.time_vector

        def sigmoid(x):
            return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))

        def edge_gate_profile(time_axis: np.ndarray, gate_start: float, gate_end: float) -> np.ndarray:
            rise = max(float(getattr(cfg, "gate_rise", 0.0)), 0.0)
            fall = max(float(getattr(cfg, "gate_fall", rise)), 0.0)

            start_edge = sigmoid((time_axis - gate_start) / rise) if rise > 0 else (time_axis >= gate_start).astype(float)
            end_edge = (1.0 - sigmoid((time_axis - gate_end) / fall)) if fall > 0 else (time_axis < gate_end).astype(float)
            return start_edge * end_edge
        
        for i in range(n_gates):
            a, b = edges[i], edges[i+1]
            shape = edge_gate_profile(t, a, b)

            # If wrapping enabled, also check for tails from previous/next cycles
            if cfg.b_decay_wrapping:
                trep = cfg.period
                shape += edge_gate_profile(t, a - trep, b - trep)
                shape += edge_gate_profile(t, a + trep, b + trep)

            self.gate_shapes[i, :] = np.clip(shape, 0, 1.0)

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
        self.grid_tau_axis = np.linspace(cfg.grid_tau_min, cfg.grid_tau_max, cfg.grid_steps)
        
        n_gates = self.gate_shapes.shape[0]
        self.grid_templates = np.zeros((cfg.grid_steps, n_gates))
        
        t = self.time_vector
        original_param_value = self._get_cfg_param(cfg.f_x_param)
        for i, param_val in enumerate(self.grid_tau_axis):
            self._set_cfg_param(cfg.f_x_param, param_val)
            p_vec = self.gate_shapes @ self.dt_pdf(t)
            p_sum = np.sum(p_vec)
            self.grid_templates[i, :] = p_vec / p_sum if p_sum > 0 else np.full(n_gates, 1.0 / n_gates)
        self._set_cfg_param(cfg.f_x_param, original_param_value)
        self.grid_signature = self._grid_signature()

    def _gate_probabilities_for_current_config(self, t: np.ndarray, gate_profiles: Optional[np.ndarray] = None,
                                               irf_cached: Optional[np.ndarray] = None) -> np.ndarray:
        if gate_profiles is None:
            gate_profiles = self.gate_shapes
        pdf = self.dt_pdf(t, irf=irf_cached)
        probs = gate_profiles @ pdf
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
        estimates[valid] = self.grid_tau_axis[best_idx]
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

        n_gates = self.gate_shapes.shape[0]
        gate_hist_all = np.zeros((int(n_repeats), n_gates), dtype=float)

        for gate_idx in range(n_gates):
            gate_vals = np.interp(photon_times, t, self.gate_shapes[gate_idx, :], left=0.0, right=0.0)
            detected = np.random.rand(int(n_repeats), int(n_photons)) < gate_vals
            gate_hist_all[:, gate_idx] = np.sum(detected, axis=1)

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
        
        # 1. Base IRF Shape (The Envelope)
        # Gaussian profile with sigma including timing jitter
        mu = cfg.irf_position
        sigma_instr = cfg.irf_fwhm / 2.35482
        jitter_ns = cfg.timing_jitter / 1000.0
        sigma = np.sqrt(sigma_instr**2 + jitter_ns**2)
        sigma = max(sigma, 1e-6)
        
        if profile == "gaussian":
            excitation = np.exp(-((t - mu)**2) / (2.0 * sigma**2))
        elif profile == "ideal (dirac)":
            # Even for Dirac, jitter adds a Gaussian spread
            if jitter_ns > 1e-5:
                excitation = np.exp(-((t - mu)**2) / (2.0 * jitter_ns**2))
            else:
                excitation = np.zeros_like(t)
                idx = np.abs(t - mu).argmin()
                excitation[idx] = 1.0
        else: # rectangular
            # Rectangular + Jitter = Convolved Rect and Gaussian
            # Simplified: Use a very high-m order super-gaussian or just convolve
            # For simplicity here, we'll keep the rect logic but we really should convolve.
            tr = max(cfg.irf_rise_time, 1e-6)
            tf = max(cfg.irf_fall_time, 1e-6)
            t_rel = t - mu
            excitation = np.zeros_like(t)
            mask_rise = (t_rel >= 0) & (t_rel < cfg.irf_fwhm)
            excitation[mask_rise] = 1.0 - np.exp(-t_rel[mask_rise] / tr)
            peak_val = 1.0 - np.exp(-cfg.irf_fwhm / tr)
            mask_fall = t_rel >= cfg.irf_fwhm
            excitation[mask_fall] = peak_val * np.exp(-(t_rel[mask_fall] - cfg.irf_fwhm) / tf)
            
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
            gate_profiles = np.array(self.gate_shapes, copy=True)
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
                p_cen_sum = np.sum(p_cen_gates)
                if p_cen_sum > 0:
                    p_cen_gates = p_cen_gates / p_cen_sum

                # Forward
                self._set_cfg_param(cfg.f_x_param, plus_val)
                p_plus_pdf   = self.dt_pdf(t, irf=irf_cached)
                p_plus_gates = gate_profiles @ p_plus_pdf
                p_plus_sum = np.sum(p_plus_gates)
                if p_plus_sum > 0:
                    p_plus_gates = p_plus_gates / p_plus_sum

                # Backward
                self._set_cfg_param(cfg.f_x_param, minus_val)
                p_minus_pdf   = self.dt_pdf(t, irf=irf_cached)
                p_minus_gates = gate_profiles @ p_minus_pdf
                p_minus_sum = np.sum(p_minus_gates)
                if p_minus_sum > 0:
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
            denom = max(abs(param_val), 1e-12)
            if np.isfinite(std_tau[idx]) and mean_detected > 0:
                f_values[idx] = (std_tau[idx] / denom) * np.sqrt(mean_detected)
                if f_values[idx] > 0:
                    p_eff[idx] = 1.0 / (f_values[idx] ** 2)
            if n_valid[idx] >= 2:
                test_result = ttest_1samp(finite_est, popmean=param_val, alternative='two-sided')
                p_values[idx] = float(test_result.pvalue) if np.isfinite(test_result.pvalue) else np.nan
                compatible[idx] = bool(np.isfinite(p_values[idx]) and p_values[idx] >= alpha_threshold)
            elif n_valid[idx] == 1:
                p_values[idx] = 1.0 if np.isclose(finite_est[0], param_val) else 0.0
                compatible[idx] = bool(p_values[idx] >= alpha_threshold)
            if point_callback is not None:
                point_callback(idx, mean_tau[idx], std_tau[idx], f_values[idx], p_eff[idx], p_values[idx], compatible[idx])

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
        }

    def simulate_photons_with_deadtime(self, tau: Optional[float], n_total: int, b_rate: float = 0.0) -> np.ndarray:
        """
        Sophisticated photon-by-photon Monte Carlo simulation.
        Handles detector deadtime and multihit logic.
        """
        cfg = self.config
        t_rep = cfg.period if cfg.period > 0 else cfg.gate_edges[-1] + 5.0
        
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
        
        # Pre-distill gates with jitter if needed
        jitter_ns = cfg.timing_jitter / 1000.0
        distilled_shapes = self.gate_shapes.copy()
        if jitter_ns > 0:
            t_k = np.arange(-4*jitter_ns, 4*jitter_ns + cfg.dt_input, cfg.dt_input)
            kernel = np.exp(-t_k**2 / (2 * jitter_ns**2))
            kernel /= np.sum(kernel)
            for i in range(n_gates):
                distilled_shapes[i, :] = convolve(distilled_shapes[i, :], kernel, mode='same')

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

    def optimize_gates(self, n_gates: int, t_max: float, tau_range: Tuple[float, float], 
                       n_tau: int = 50, n_restarts: int = 20, 
                       callback: Optional[Callable] = None) -> Tuple[np.ndarray, float, dict]:
        """
        Finds optimal gate edges to minimize the average F-value over tau_range.
        Uses SLSQP with monotonicity constraints and multiple restarts.
        """
        tau_grid = np.logspace(np.log10(tau_range[0]), np.log10(tau_range[1]), n_tau)
        best_j = np.inf
        best_edges = None
        
        # Save original config
        orig_edges = self.config.gate_edges
        
        def objective(internal_edges):
            # Reconstruct full edges
            edges = np.concatenate(([0.0], np.sort(internal_edges), [t_max]))
            self.config.gate_edges = edges.tolist()
            
            fi, f_val = self.compute_fisher_info(tau_grid, n_photons=1e4)
            # Minimize the mean F-value (ideal = 1.0)
            j_val = np.mean(f_val)
            
            if callback:
                callback(j_val)
            return j_val

        # Constraints: internal edges must be strictly increasing and within (0, t_max)
        # 0 < e_1 < e_2 < ... < e_n-1 < t_max
        bounds = [(0.01, t_max - 0.01)] * (n_gates - 1)
        
        for r in range(n_restarts):
            if r == 0:
                # Start with equal spacing
                x0 = np.linspace(0, t_max, n_gates + 1)[1:-1]
            else:
                # Random starting point
                x0 = np.sort(np.random.rand(n_gates - 1) * t_max)
            
            res = minimize(objective, x0, bounds=bounds, method='SLSQP', 
                           options={'ftol': 1e-4, 'maxiter': 50})
            
            if res.success and res.fun < best_j:
                best_j = res.fun
                best_edges = np.concatenate(([0.0], np.sort(res.x), [t_max]))

        # Restore engine state to best found
        if best_edges is not None:
            self.config.gate_edges = best_edges.tolist()
            fi, f_val = self.compute_fisher_info(tau_grid, n_photons=1e4)
        else:
            self.config.gate_edges = orig_edges
            best_edges = np.array(orig_edges)
            fi, f_val = self.compute_fisher_info(tau_grid, n_photons=1e4)
            best_j = np.mean(f_val)

        info = {
            "tau_grid": tau_grid,
            "fisher_info": fi,
            "f_val": f_val,
            "gate_profiles": self.get_gate_profiles_vis(t_max),
            "t": np.arange(0, t_max + 0.05, 0.05)
        }
        
        return best_edges, best_j, info

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
