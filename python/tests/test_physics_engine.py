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
    assert eff_500 > 0.60
    assert eff_1000 < eff_0 - 0.03

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
    assert payload["efficiency_ci_lower"][0] < payload["efficiency"][0] < payload["efficiency_ci_upper"][0]


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


def test_histogram_fisher_supports_all_vs_collected_photon_basis():
    """Lossy histogram gating should distinguish full-budget and collected-only Fisher metrics."""
    tau_grid = np.array([2.5])

    all_cfg = PhysicsConfig(
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
        optimization_f_photon_basis="all",
        period=12.5,
    )
    collected_cfg = all_cfg.model_copy(update={"optimization_f_photon_basis": "collected"})

    _, f_all = TwinEngine(all_cfg).compute_fisher_info(
        tau_grid,
        n_photons=2000,
        photon_basis_mode="all",
    )
    _, f_collected = TwinEngine(collected_cfg).compute_fisher_info(
        tau_grid,
        n_photons=2000,
        photon_basis_mode="collected",
    )

    assert np.isfinite(f_all[0])
    assert np.isfinite(f_collected[0])
    assert not np.isclose(f_all[0], f_collected[0], rtol=1e-2)


def test_monte_carlo_precision_respects_photon_basis_selection():
    """MC precision should use the selected photon budget basis when reporting F."""
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
        period=12.5,
    )
    all_cfg = base_cfg.model_copy(update={"optimization_f_photon_basis": "all"})
    collected_cfg = base_cfg.model_copy(update={"optimization_f_photon_basis": "collected"})

    payload_all = TwinEngine(all_cfg).monte_carlo_precision_curve(tau_grid, n_photons=2000, n_repeats=120)
    payload_collected = TwinEngine(collected_cfg).monte_carlo_precision_curve(tau_grid, n_photons=2000, n_repeats=120)

    assert np.isfinite(payload_all["f_value"][0])
    assert np.isfinite(payload_collected["f_value"][0])
    assert not np.isclose(payload_all["f_value"][0], payload_collected["f_value"][0], rtol=5e-2)
