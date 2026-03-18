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
