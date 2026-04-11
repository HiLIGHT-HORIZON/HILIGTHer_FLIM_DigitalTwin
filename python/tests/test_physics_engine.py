import numpy as np
import pytest
from backend.twin_engine import TwinEngine
from backend.models import PhysicsConfig

def test_pdf_normalization():
    """Verify that the decay PDF integrates to approximately 1.0."""
    engine = TwinEngine()
    engine.distill_gates()
    
    t = np.arange(0, 25, 0.05)
    tau = 2.5
    pdf = engine.dt_pdf(t, tau)
    
    assert np.isclose(np.sum(pdf), 1.0, atol=1e-3)

def test_phasor_locus():
    """Verify that the theoretical locus points lie on the universal semicircle."""
    engine = TwinEngine()
    g, s = engine.get_theoretical_locus()
    
    # Universal circle: (g-0.5)^2 + s^2 = 0.5^2
    circle_eqn = (g - 0.5)**2 + s**2
    assert np.allclose(circle_eqn, 0.25, atol=1e-2)

def test_fitting_accuracy():
    """
    Verify that gridded MLE recovers the exact lifetime on noiseless, 
    zero-background exponential data. Note: gridded_mle normalises gate 
    fractions internally, so amplitude and background cannot be independently
    tested from this path — those require the full obj_func path.
    """
    cfg = PhysicsConfig(threshold_min=0, use_eirf=False)
    engine = TwinEngine(cfg)
    engine.distill_gates()
    
    tau_true = 3.2
    t = engine.time_vector
    # Pure noiseless exponential — no background
    decay = np.exp(-t / tau_true)
    raw_data = (engine.gate_shapes @ decay).reshape(1, 1, -1)
    
    # Run fit
    engine.run_fit(data=raw_data, method="gridded_mle")
    
    # Lifetime should be recovered within 5% on noise-free data
    assert np.isclose(engine.tau_map[0, 0], tau_true, rtol=5e-2), (
        f"Expected tau~{tau_true}, got {engine.tau_map[0,0]:.4f}"
    )

def test_fisher_information():
    """Verify Fisher Information increases with photon count."""
    engine = TwinEngine()
    tau_grid = np.array([1.0, 2.0, 3.0])
    
    fi1, _ = engine.compute_fisher_info(tau_grid, n_photons=100)
    fi2, _ = engine.compute_fisher_info(tau_grid, n_photons=1000)
    
    assert np.all(fi2 > fi1)
    assert np.allclose(fi2 / fi1, 10.0, rtol=1e-2)

def test_rectangular_irf_jitter_broadens_excitation():
    """Rectangular excitation should respond to timing jitter, not stay unchanged."""
    base_cfg = PhysicsConfig(
        irf_profile="rectangular",
        irf_fwhm=7.5,
        irf_position=0.0,
        irf_rise_time=0.05,
        irf_fall_time=0.05,
        timing_jitter=0.0,
    )
    jitter_cfg = base_cfg.model_copy(update={"timing_jitter": 1000.0})

    t = np.arange(0.0, 15.0, 0.01)
    base_exc = TwinEngine(base_cfg).dt_excitation(t)
    jitter_exc = TwinEngine(jitter_cfg).dt_excitation(t)

    assert not np.allclose(base_exc, jitter_exc)
    late_tail = t > (base_cfg.irf_fwhm + 0.5)
    assert np.sum(jitter_exc[late_tail]) > np.sum(base_exc[late_tail])

def test_fisher_jitter_sweep_is_not_flat_for_rectangular_irf():
    """The Figure 3 jitter sweep should show measurable deterioration by 1000 ps."""
    cfg = PhysicsConfig(
        period=50.0,
        gate_edges=[0.0, 2.8, 7.5, 12.5, 32.0],
        irf_profile="rectangular",
        irf_fwhm=7.5,
        irf_position=0.0,
    )

    efficiencies = []
    for jitter in [0.0, 500.0, 1000.0]:
        cfg.timing_jitter = jitter
        _, f_val = TwinEngine(cfg).compute_fisher_info(np.array([3.5]))
        efficiencies.append(1.0 / (f_val[0] ** 2))

    eff_0, eff_500, eff_1000 = efficiencies
    assert eff_500 > 0.50
    assert eff_1000 < eff_0 - 0.015

def test_bootstrap_accuracy_pvalue_detects_bias():
    """Bootstrap p-values should shrink when the estimator mean is biased."""
    engine = TwinEngine()
    rng = np.random.default_rng(123)

    unbiased = rng.normal(loc=2.0, scale=0.05, size=80)
    biased = rng.normal(loc=2.2, scale=0.05, size=80)

    p_unbiased = engine._bootstrap_accuracy_pvalue(unbiased, 2.0, 1000, rng)
    p_biased = engine._bootstrap_accuracy_pvalue(biased, 2.0, 1000, rng)

    assert p_unbiased > 0.05
    assert p_biased < 1e-5

def test_monte_carlo_precision_returns_bootstrap_confidence_intervals(monkeypatch):
    """MC precision payload should expose bootstrap CIs when requested."""
    cfg = PhysicsConfig(
        precision_compute_ci=True,
        precision_bootstrap_samples=400,
        precision_mc_repeats=24,
        f_x_param="tau1",
    )
    engine = TwinEngine(cfg)

    monkeypatch.setattr(engine, "ensure_grid_current", lambda: None)
    monkeypatch.setattr(
        engine,
        "simulate_gate_histograms",
        lambda tau, n_photons, n_repeats, irf_cached=None: (
            np.zeros((n_repeats, len(engine.config.gate_edges) - 1), dtype=float),
            np.linspace(n_photons - 10, n_photons + 10, n_repeats),
        ),
    )
    monkeypatch.setattr(
        engine,
        "estimate_tau_batch",
        lambda counts_batch: np.linspace(1.85, 2.15, counts_batch.shape[0]),
    )

    payload = engine.monte_carlo_precision_curve(np.array([2.0]), n_photons=200, n_repeats=24)

    assert np.isfinite(payload["p_value"][0])
    assert np.isfinite(payload["f_ci_lower"][0])
    assert np.isfinite(payload["f_ci_upper"][0])
    assert payload["f_ci_lower"][0] < payload["f_value"][0] < payload["f_ci_upper"][0]
    assert payload["efficiency_ci_lower"][0] <= payload["efficiency"][0] <= payload["efficiency_ci_upper"][0]


def test_compute_ideal_reference_forces_zero_to_period_ideal_config(monkeypatch):
    """Ideal reference should always use a zero-to-period ideal wrapped detector configuration."""
    cfg = PhysicsConfig(
        period=17.5,
        b_decay_wrapping=False,
        gate_type="custom",
        gate_edges=[2.0, 5.0, 9.0],
        gate_start_mode="free",
        gate_first_start=2.0,
        gate_end_mode="free",
        gate_last_end=9.0,
        timing_jitter=250.0,
        detector_deadtime=15.0,
        detector_afterpulsing_probability=0.2,
        detector_dark_count_rate_cps=5e4,
        gate_collection_mode="sequential",
        gate_overlap_mode="allow",
        gate_overlap_effect="independent_duplicates",
        gate_overlap_ns=0.5,
        gate_wraparound=False,
        simulation_mode="event_driven",
        simulation_mode_preference="event_driven",
        event_multihit_capacity=1,
    )
    engine = TwinEngine(cfg)
    captured = {}

    def fake_compute_fisher_info(self, tau_grid, n_photons=1, point_callback=None, photon_basis_mode=None):
        captured["period"] = float(self.config.period)
        captured["b_decay_wrapping"] = bool(self.config.b_decay_wrapping)
        captured["gate_type"] = str(self.config.gate_type)
        captured["gate_start_mode"] = str(self.config.gate_start_mode)
        captured["gate_first_start"] = float(self.config.gate_first_start)
        captured["gate_end_mode"] = str(self.config.gate_end_mode)
        captured["gate_last_end"] = float(self.config.gate_last_end)
        captured["gate_edges"] = list(self.config.gate_edges)
        captured["timing_jitter"] = float(self.config.timing_jitter)
        captured["detector_deadtime"] = float(self.config.detector_deadtime)
        captured["afterpulsing"] = float(self.config.detector_afterpulsing_probability)
        captured["dark_counts"] = float(self.config.detector_dark_count_rate_cps)
        captured["gate_collection_mode"] = str(self.config.gate_collection_mode)
        captured["gate_overlap_mode"] = str(self.config.gate_overlap_mode)
        captured["gate_overlap_effect"] = str(self.config.gate_overlap_effect)
        captured["gate_wraparound"] = bool(self.config.gate_wraparound)
        captured["simulation_mode"] = str(self.config.simulation_mode)
        return np.array([1.0]), np.array([1.0])

    monkeypatch.setattr(TwinEngine, "compute_fisher_info", fake_compute_fisher_info)

    engine.compute_ideal_reference(np.array([2.5]), n_photons=1000)

    assert captured["period"] == 17.5
    assert captured["b_decay_wrapping"] is True
    assert captured["gate_type"] == "equal"
    assert captured["gate_start_mode"] == "start"
    assert captured["gate_first_start"] == 0.0
    assert captured["gate_end_mode"] == "period"
    assert captured["gate_last_end"] == 17.5
    assert np.isclose(captured["gate_edges"][0], 0.0)
    assert np.isclose(captured["gate_edges"][-1], 17.5)
    assert captured["timing_jitter"] == 0.0
    assert captured["detector_deadtime"] == 0.0
    assert captured["afterpulsing"] == 0.0
    assert captured["dark_counts"] == 0.0
    assert captured["gate_collection_mode"] == "histogram"
    assert captured["gate_overlap_mode"] == "jitter_only"
    assert captured["gate_overlap_effect"] == "exclusive"
    assert captured["gate_wraparound"] is True
    assert captured["simulation_mode"] == "ideal_poisson"


def test_log_tau_grid_uses_geometric_axis_and_padding():
    """Log lifetime sweeps should build a geometric MLE axis with extra padding beyond the sweep."""
    cfg = PhysicsConfig(
        f_x_param="tau1",
        f_x_min=0.25,
        f_x_max=9.0,
        f_x_steps=30,
        f_x_scale="log",
        grid_fine_factor=1,
    )
    engine = TwinEngine(cfg)
    engine.distill_gates()
    engine.ensure_grid_current()

    axis = engine.grid_tau_axis
    ratios = axis[1:] / axis[:-1]

    assert axis[0] < cfg.f_x_min
    assert axis[-1] > cfg.f_x_max
    assert np.allclose(ratios, ratios[0], rtol=1e-4, atol=1e-8)


def test_refined_gridded_mle_handles_log_grid_extremes():
    """Sub-grid refinement should keep low and high lifetime estimates accurate on coarse log grids."""
    cfg = PhysicsConfig(
        gate_edges=[0.0, 1.1, 3.4, 9.0, 25.0],
        f_x_param="tau1",
        f_x_min=0.25,
        f_x_max=9.0,
        f_x_steps=30,
        f_x_scale="log",
        grid_fine_factor=1,
    )
    engine = TwinEngine(cfg)
    engine.distill_gates()
    t = engine.time_vector

    for tau_true in [0.28, 0.35, 6.5, 8.5]:
        counts = (engine.gate_shapes @ engine.dt_pdf(t, tau=tau_true)).reshape(1, -1)
        estimate = engine.estimate_tau_batch(counts)[0]
        assert np.isclose(estimate, tau_true, rtol=1.5e-2), (
            f"Expected refined estimate near {tau_true}, got {estimate:.6f}"
        )


def test_resolve_gate_edges_applies_equal_and_custom_anchors():
    cfg = PhysicsConfig(
        gate_type="equal",
        gate_edges=[0.0, 1.0, 2.0, 3.0, 4.0],
        gate_start_mode="free",
        gate_first_start=0.6,
        gate_end_mode="free",
        gate_last_end=8.6,
    )
    engine = TwinEngine(cfg)

    equal_edges = engine.resolve_gate_edges()
    assert np.allclose(equal_edges, np.linspace(0.6, 8.6, 5))

    cfg.gate_type = "custom"
    cfg.gate_start_mode = "start"
    cfg.gate_end_mode = "period"
    cfg.period = 12.5
    cfg.gate_edges = [0.7, 2.0, 4.5, 9.0, 11.8]
    custom_edges = engine.resolve_gate_edges()
    assert np.isclose(custom_edges[0], 0.0)
    assert np.isclose(custom_edges[-1], 12.5)
    assert np.all(np.diff(custom_edges) > 0)


def test_independent_duplicate_overlap_can_count_same_photon_in_adjacent_gates():
    cfg = PhysicsConfig(
        gate_collection_mode="histogram",
        gate_overlap_mode="allow",
        gate_overlap_ns=1.0,
        gate_overlap_effect="independent_duplicates",
        gate_wraparound=False,
        gate_edges=[0.0, 1.5, 3.0],
        gate_rise=0.0,
        gate_fall=0.0,
        timing_jitter=0.0,
        b_decay_wrapping=False,
        period=6.0,
    )
    engine = TwinEngine(cfg)
    engine.distill_gates()

    original_rand = np.random.rand
    try:
        def fake_rand(*shape):
            if len(shape) == 3:
                return np.zeros(shape, dtype=float)
            return np.full(shape, 0.5, dtype=float)

        np.random.rand = fake_rand
        counts, detections = engine.simulate_gate_histograms(tau=2.0, n_photons=5, n_repeats=2)
    finally:
        np.random.rand = original_rand

    assert counts.shape == (2, 2)
    assert np.all(counts >= 0)
    assert np.all(detections >= 5.0)


def test_sequential_gate_collection_reduces_theoretical_fisher_throughput():
    tau_grid = np.array([2.5])

    hist_cfg = PhysicsConfig(
        gate_collection_mode="histogram",
        gate_edges=np.linspace(0.0, 12.5, 11).tolist(),
        gate_rise=0.0,
        gate_fall=0.0,
        timing_jitter=0.0,
    )
    seq_cfg = hist_cfg.model_copy(update={"gate_collection_mode": "sequential"})

    _, f_hist = TwinEngine(hist_cfg).compute_fisher_info(tau_grid, n_photons=2000)
    _, f_seq = TwinEngine(seq_cfg).compute_fisher_info(tau_grid, n_photons=2000)

    eff_hist = 1.0 / (f_hist[0] ** 2)
    eff_seq = 1.0 / (f_seq[0] ** 2)

    assert np.isclose(eff_seq / eff_hist, 0.1, rtol=0.25)
    assert f_seq[0] > f_hist[0]


def test_sequential_gate_collection_reduces_mc_detected_photons():
    hist_cfg = PhysicsConfig(
        gate_collection_mode="histogram",
        gate_edges=np.linspace(0.0, 12.5, 11).tolist(),
        gate_rise=0.0,
        gate_fall=0.0,
        timing_jitter=0.0,
    )
    seq_cfg = hist_cfg.model_copy(update={"gate_collection_mode": "sequential"})

    hist_engine = TwinEngine(hist_cfg)
    seq_engine = TwinEngine(seq_cfg)

    hist_counts, hist_detected = hist_engine.simulate_gate_histograms(tau=2.5, n_photons=2000, n_repeats=200)
    seq_counts, seq_detected = seq_engine.simulate_gate_histograms(tau=2.5, n_photons=2000, n_repeats=200)

    assert hist_counts.shape == seq_counts.shape
    assert np.mean(seq_detected) < np.mean(hist_detected) * 0.2


def test_sequential_gate_collection_reduces_mc_efficiency_metric():
    tau_grid = np.array([2.5])
    hist_cfg = PhysicsConfig(
        gate_collection_mode="histogram",
        gate_edges=np.linspace(0.0, 12.5, 11).tolist(),
        gate_rise=0.0,
        gate_fall=0.0,
        timing_jitter=0.0,
        precision_mc_repeats=200,
        precision_photons=2000,
    )
    seq_cfg = hist_cfg.model_copy(update={"gate_collection_mode": "sequential"})

    hist_payload = TwinEngine(hist_cfg).monte_carlo_precision_curve(tau_grid, n_photons=2000, n_repeats=200)
    seq_payload = TwinEngine(seq_cfg).monte_carlo_precision_curve(tau_grid, n_photons=2000, n_repeats=200)

    assert seq_payload["f_value"][0] > hist_payload["f_value"][0]
    assert seq_payload["efficiency"][0] < hist_payload["efficiency"][0] * 0.2


def test_histogram_fisher_photon_basis_only_rescales_collected_metric():
    """Photon-basis modes should rescale the same collected-photon Fisher estimate."""
    tau_grid = np.array([2.5])

    cfg = PhysicsConfig(
        gate_type="custom",
        gate_edges=[8.0, 10.0, 11.0, 12.5],
        gate_start_mode="free",
        gate_first_start=8.0,
        gate_end_mode="free",
        gate_last_end=12.5,
        gate_collection_mode="histogram",
        gate_rise=0.0,
        gate_fall=0.0,
        timing_jitter=0.0,
        optimization_f_photon_basis="collected",
        b_decay_wrapping=False,
        period=12.5,
    )
    engine = TwinEngine(cfg)

    fi_collected, f_collected = engine.compute_fisher_info(
        tau_grid,
        n_photons=2000,
        photon_basis_mode="collected",
    )
    _, f_period = engine.compute_fisher_info(
        tau_grid,
        n_photons=2000,
        photon_basis_mode="period",
    )
    _, f_all = engine.compute_fisher_info(
        tau_grid,
        n_photons=2000,
        photon_basis_mode="all",
    )

    denom = max(abs(tau_grid[0]), 1e-12)
    collected_budget = fi_collected[0] * ((f_collected[0] * denom) ** 2)
    period_budget = 2000.0 * engine._acquisition_period_fraction(cfg)

    assert np.isfinite(fi_collected[0])
    assert np.isfinite(f_all[0])
    assert np.isfinite(f_period[0])
    assert np.isfinite(f_collected[0])
    assert np.isclose(
        f_period[0] / f_collected[0],
        np.sqrt(period_budget / collected_budget),
        rtol=3e-2,
    )
    assert np.isclose(
        f_all[0] / f_collected[0],
        np.sqrt(2000.0 / collected_budget),
        rtol=3e-2,
    )


def test_monte_carlo_precision_rescales_f_by_selected_budget(monkeypatch):
    """MC validation should fit collected photons and only rescale F by the chosen budget."""
    tau_grid = np.array([2.5])
    base_cfg = PhysicsConfig(
        gate_type="custom",
        gate_edges=[8.0, 10.0, 11.0, 12.5],
        gate_start_mode="free",
        gate_first_start=8.0,
        gate_end_mode="free",
        gate_last_end=12.5,
        gate_collection_mode="histogram",
        gate_rise=0.0,
        gate_fall=0.0,
        timing_jitter=0.0,
        precision_mc_repeats=120,
        precision_photons=2000,
        b_decay_wrapping=False,
        period=12.5,
    )
    collected_cfg = base_cfg.model_copy(update={"optimization_f_photon_basis": "collected"})
    period_cfg = base_cfg.model_copy(update={"optimization_f_photon_basis": "period"})
    all_cfg = base_cfg.model_copy(update={"optimization_f_photon_basis": "all"})

    detections = np.array([60.0, 70.0, 80.0, 90.0], dtype=float)
    estimates = np.array([2.3, 2.4, 2.6, 2.7], dtype=float)

    def fake_simulate_gate_histograms(self, tau, n_photons, n_repeats, irf_cached=None):
        counts = np.tile(np.array([[10.0, 20.0, 30.0]], dtype=float), (len(detections), 1))
        return counts, np.array(detections, copy=True)

    def fake_estimate_tau_batch(self, counts_batch, photon_budget=None, correction_method=None):
        return np.array(estimates, copy=True)

    monkeypatch.setattr(TwinEngine, "simulate_gate_histograms", fake_simulate_gate_histograms)
    monkeypatch.setattr(TwinEngine, "estimate_tau_batch", fake_estimate_tau_batch)

    payload_all = TwinEngine(all_cfg).monte_carlo_precision_curve(tau_grid, n_photons=2000, n_repeats=120)
    payload_period = TwinEngine(period_cfg).monte_carlo_precision_curve(tau_grid, n_photons=2000, n_repeats=120)
    payload_collected = TwinEngine(collected_cfg).monte_carlo_precision_curve(tau_grid, n_photons=2000, n_repeats=120)
    probe_engine = TwinEngine(base_cfg)
    mean_detected = float(np.mean(detections))
    period_budget = 2000.0 * probe_engine._acquisition_period_fraction(base_cfg)

    assert np.isfinite(payload_all["f_value"][0])
    assert np.isfinite(payload_period["f_value"][0])
    assert np.isfinite(payload_collected["f_value"][0])
    assert np.isclose(
        payload_period["f_value"][0] / payload_collected["f_value"][0],
        np.sqrt(period_budget / mean_detected),
        rtol=0.12,
    )
    assert np.isclose(
        payload_all["f_value"][0] / payload_collected["f_value"][0],
        np.sqrt(2000.0 / mean_detected),
        rtol=0.12,
    )
    assert np.isclose(payload_collected["f_value_conditional"][0], payload_collected["f_value"][0], rtol=1e-12)
    assert np.isclose(payload_period["f_value_conditional"][0], payload_collected["f_value_conditional"][0], rtol=1e-12)
    assert np.isclose(payload_all["f_value_conditional"][0], payload_collected["f_value_conditional"][0], rtol=1e-12)
    assert np.isclose(payload_collected["survival_eta"][0], mean_detected / 2000.0, rtol=1e-12)


def test_monte_carlo_precision_curve_keeps_raw_and_corrected_estimates_separate(monkeypatch):
    tau_grid = np.array([2.0], dtype=float)
    cfg = PhysicsConfig(
        detector_deadtime=60.0,
        precision_photons=2000,
        a_photons=2000.0,
        precision_mc_repeats=2,
        deadtime_correction_method="isbaner_histogram",
        gate_edges=[0.0, 0.8, 2.0, 4.0, 12.5],
        event_pixel_dwell_time_s=2e-5,
        f_x_param="tau1",
        f_x_min=0.5,
        f_x_max=4.0,
        f_x_steps=20,
        f_x_scale="linear",
    )
    counts = np.array([[10.0, 20.0, 30.0], [12.0, 18.0, 30.0]], dtype=float)
    detections = np.array([60.0, 60.0], dtype=float)
    raw_estimates = np.array([1.2, 1.4], dtype=float)
    corrected_estimates = np.array([2.2, 2.4], dtype=float)
    seen = []

    def fake_simulate_gate_histograms(self, tau, n_photons, n_repeats, irf_cached=None):
        return np.array(counts, copy=True), np.array(detections, copy=True)

    def fake_estimate_tau_batch(self, counts_batch, photon_budget=None, correction_method=None):
        seen.append(correction_method)
        if correction_method == "none":
            return np.array(raw_estimates[: counts_batch.shape[0]], copy=True)
        if correction_method == "isbaner_histogram":
            return np.array(corrected_estimates[: counts_batch.shape[0]], copy=True)
        raise AssertionError(f"Unexpected correction method: {correction_method}")

    monkeypatch.setattr(TwinEngine, "simulate_gate_histograms", fake_simulate_gate_histograms)
    monkeypatch.setattr(TwinEngine, "estimate_tau_batch", fake_estimate_tau_batch)

    payload = TwinEngine(cfg).monte_carlo_precision_curve(tau_grid, n_photons=2000, n_repeats=2)

    assert seen == ["none", "isbaner_histogram"]
    assert np.isclose(payload["mean_tau"][0], np.mean(raw_estimates), rtol=1e-12, atol=1e-12)
    corrected = payload["deadtime_correction"]["monte_carlo_corrected"]
    assert np.isclose(corrected["mean_tau"][0], np.mean(corrected_estimates), rtol=1e-12, atol=1e-12)


def test_event_driven_fisher_path_keeps_detector_transfer_active():
    tau_grid = np.array([2.5])
    base_cfg = PhysicsConfig(
        gate_collection_mode="histogram",
        gate_edges=np.linspace(0.0, 12.5, 11).tolist(),
        gate_rise=0.0,
        gate_fall=0.0,
        timing_jitter=0.0,
        detector_deadtime=0.0,
        optimization_f_photon_basis="collected",
    )
    deadtime_cfg = base_cfg.model_copy(update={"detector_deadtime": 1.0})

    fi_base, f_base = TwinEngine(base_cfg).compute_fisher_info(tau_grid, n_photons=2000)
    fi_dead, f_dead = TwinEngine(deadtime_cfg).compute_fisher_info(tau_grid, n_photons=2000)

    assert np.isfinite(fi_base[0])
    assert np.isfinite(fi_dead[0])
    assert fi_dead[0] < fi_base[0]
    assert f_dead[0] > f_base[0]


@pytest.mark.parametrize(
    "method",
    ["isbaner_histogram", "rapp_mcpdf", "rapp_mchc"],
)
def test_deadtime_correction_methods_return_finite_corrected_fisher(method):
    cfg = PhysicsConfig(
        detector_deadtime=45.0,
        precision_photons=2000,
        a_photons=2000.0,
        deadtime_correction_method=method,
        gate_edges=[0.0, 1.1, 3.4, 9.0, 12.5],
        event_pixel_dwell_time_s=1e-3,
    )
    engine = TwinEngine(cfg)
    tau_grid = np.array([1.0, 2.5, 5.0], dtype=float)

    fi, f_val, correction = engine.compute_deadtime_corrected_fisher_info(
        tau_grid,
        n_photons=2000,
        correction_method=method,
        photon_basis_mode="all",
    )

    assert fi.shape == tau_grid.shape
    assert f_val.shape == tau_grid.shape
    assert np.all(np.isfinite(f_val))
    assert correction["method"] == method
    assert isinstance(correction.get("note", ""), str)
    assert np.allclose(
        np.asarray(correction["corrected_budget"], dtype=float),
        np.asarray(correction["observed_budget"], dtype=float),
        rtol=1e-12,
        atol=1e-12,
    )


def test_deadtime_correction_methods_produce_distinct_corrected_curves():
    cfg = PhysicsConfig(
        detector_deadtime=60.0,
        precision_photons=2000,
        a_photons=2000.0,
        gate_edges=[0.0, 0.8, 2.0, 4.0, 12.5],
        event_pixel_dwell_time_s=2e-5,
    )
    engine = TwinEngine(cfg)
    tau_grid = np.array([0.9, 1.7, 3.2], dtype=float)

    _, f_isbaner, _ = engine.compute_deadtime_corrected_fisher_info(
        tau_grid,
        n_photons=2000,
        correction_method="isbaner_histogram",
        photon_basis_mode="all",
    )
    _, f_rapp_mcpdf, _ = engine.compute_deadtime_corrected_fisher_info(
        tau_grid,
        n_photons=2000,
        correction_method="rapp_mcpdf",
        photon_basis_mode="all",
    )
    _, f_rapp_mchc, _ = engine.compute_deadtime_corrected_fisher_info(
        tau_grid,
        n_photons=2000,
        correction_method="rapp_mchc",
        photon_basis_mode="all",
    )
    assert not np.allclose(f_rapp_mcpdf, f_isbaner, rtol=1e-5, atol=1e-8)
    assert not np.allclose(f_rapp_mcpdf, f_rapp_mchc, rtol=1e-5, atol=1e-8)


def test_deadtime_free_baseline_mle_shows_bias_and_isbaner_histogram_recovers_toward_truth():
    cfg = PhysicsConfig(
        detector_deadtime=60.0,
        precision_photons=2000,
        a_photons=2000.0,
        gate_edges=[0.0, 0.8, 2.0, 4.0, 12.5],
        event_pixel_dwell_time_s=2e-5,
        f_x_param="tau1",
        f_x_min=0.5,
        f_x_max=4.0,
        f_x_steps=20,
        f_x_scale="linear",
    )
    engine = TwinEngine(cfg)
    engine.distill_gates()
    engine.ensure_grid_current()

    truth = 1.7
    pdf = engine.dt_pdf(engine.time_vector, tau=truth)
    gate_profiles = engine._statistical_gate_profiles(engine.gate_shapes)
    probs, frac = engine._gate_statistics_from_pdf(pdf, float(cfg.precision_photons), gate_profiles, cfg)
    observed = (probs * frac * float(cfg.precision_photons)).reshape(1, -1)

    baseline = float(engine.estimate_tau_batch(observed)[0])
    isbaner = float(
        engine.estimate_tau_batch(
            observed,
            correction_method="isbaner_histogram",
        )[0]
    )

    assert baseline < truth
    assert abs(isbaner - truth) < abs(baseline - truth)


@pytest.mark.parametrize("method", ["isbaner_histogram", "rapp_mcpdf", "rapp_mchc"])
def test_deadtime_corrections_do_not_require_known_total_photon_budget(method):
    cfg = PhysicsConfig(
        detector_deadtime=60.0,
        precision_photons=2000,
        a_photons=2000.0,
        gate_edges=[0.0, 0.8, 2.0, 4.0, 12.5],
        event_pixel_dwell_time_s=2e-5,
        f_x_param="tau1",
        f_x_min=0.5,
        f_x_max=4.0,
        f_x_steps=20,
        f_x_scale="linear",
    )
    engine = TwinEngine(cfg)
    engine.distill_gates()
    engine.ensure_grid_current()

    truth = 1.7
    pdf = engine.dt_pdf(engine.time_vector, tau=truth)
    gate_profiles = engine._statistical_gate_profiles(engine.gate_shapes)
    probs, frac = engine._gate_statistics_from_pdf(pdf, float(cfg.precision_photons), gate_profiles, cfg)
    observed = (probs * frac * float(cfg.precision_photons)).reshape(1, -1)

    estimate_default = float(engine.estimate_tau_batch(observed, correction_method=method)[0])
    estimate_low = float(engine.estimate_tau_batch(observed, photon_budget=500.0, correction_method=method)[0])
    estimate_high = float(engine.estimate_tau_batch(observed, photon_budget=5000.0, correction_method=method)[0])

    assert np.isclose(estimate_default, estimate_low, rtol=1e-12, atol=1e-12)
    assert np.isclose(estimate_default, estimate_high, rtol=1e-12, atol=1e-12)


def test_deadtime_method_template_families_match_cached_grid_semantics():
    cfg = PhysicsConfig(
        detector_deadtime=80.0,
        precision_photons=2000,
        a_photons=2000.0,
        gate_edges=[0.0, 0.8, 2.0, 4.0, 6.0, 8.0, 10.0, 12.5],
        event_pixel_dwell_time_s=1e-5,
        f_x_param="tau1",
        f_x_min=1.0,
        f_x_max=4.0,
        f_x_steps=7,
        f_x_scale="linear",
    )
    engine = TwinEngine(cfg)
    engine.distill_gates()
    engine.ensure_grid_current()

    raw_mass_expected = np.asarray(engine.grid_templates, dtype=float) * np.asarray(engine.grid_collected_fractions, dtype=float)[:, None]
    observed_mass_expected = np.asarray(engine.grid_raw_templates, dtype=float) * np.asarray(engine.grid_raw_collected_fractions, dtype=float)[:, None]

    isbaner_mass, _, _ = engine._corrected_template_masses_for_method("isbaner_histogram")
    rapp_mcpdf_mass, _, _ = engine._corrected_template_masses_for_method("rapp_mcpdf")
    rapp_mchc_mass, _, _ = engine._corrected_template_masses_for_method("rapp_mchc")

    assert np.allclose(isbaner_mass, raw_mass_expected, rtol=1e-12, atol=1e-12)
    assert np.allclose(rapp_mcpdf_mass, observed_mass_expected, rtol=1e-12, atol=1e-12)
    assert np.allclose(rapp_mchc_mass, raw_mass_expected, rtol=1e-12, atol=1e-12)


def test_ideal_poisson_detector_effects_follow_distorted_gate_distribution():
    np.random.seed(0)
    cfg = PhysicsConfig(
        detector_deadtime=120.0,
        precision_photons=1200,
        a_photons=1200.0,
        gate_edges=[0.0, 0.8, 2.0, 4.0, 6.0, 8.0, 10.0, 12.5],
        event_pixel_dwell_time_s=1e-5,
        simulation_mode="ideal_poisson",
        simulation_mode_preference="ideal_poisson",
        f_x_param="tau1",
    )
    engine = TwinEngine(cfg)
    engine.distill_gates()

    truth = 4.0
    pdf = engine.dt_pdf(engine.time_vector, tau=truth)
    gate_profiles = engine._statistical_gate_profiles(engine.gate_shapes)
    raw_cond, raw_frac = engine._gate_statistics_without_detector_from_pdf(pdf, float(cfg.precision_photons), gate_profiles, cfg)
    obs_cond, obs_frac = engine._gate_statistics_from_pdf(pdf, float(cfg.precision_photons), gate_profiles, cfg)

    counts, _ = engine.simulate_gate_histograms(truth, cfg.precision_photons, 200)
    mean_counts = np.mean(counts, axis=0)
    mean_total = float(np.sum(mean_counts))
    observed_cond = mean_counts / max(mean_total, 1e-12)
    raw_cond = np.asarray(raw_cond, dtype=float)
    distorted_cond = np.asarray(obs_cond, dtype=float)

    raw_error = float(np.linalg.norm(observed_cond - raw_cond))
    distorted_error = float(np.linalg.norm(observed_cond - distorted_cond))

    assert distorted_error < raw_error
    assert np.isclose(mean_total, float(cfg.precision_photons) * float(obs_frac), rtol=0.2, atol=5.0)
