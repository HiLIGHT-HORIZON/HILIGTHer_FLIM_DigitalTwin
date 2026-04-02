import numpy as np

from backend.models import PhysicsConfig
from backend.twin_engine import TwinEngine


def _theoretical_gate_fisher(engine: TwinEngine, tau: float, n_photons: int) -> float:
    cfg = engine.config
    engine.distill_gates()
    gate_profiles = engine._statistical_gate_profiles(engine.gate_shapes)
    t = np.array(engine.time_vector, copy=True)
    irf = engine.dt_excitation(t)
    irf_sum = np.sum(irf)
    if irf_sum > 0:
      irf = irf / irf_sum

    eps = max(0.01, 0.01 * tau)
    original_tau = float(cfg.taus[0])
    try:
        cfg.taus[0] = float(tau)
        p_cen_pdf = engine.dt_pdf(t, irf=irf)
        p_cen_gates, collected_fraction = engine._gate_statistics_from_pdf(
            p_cen_pdf,
            float(n_photons),
            gate_profiles,
            cfg,
        )

        cfg.taus[0] = float(tau + eps)
        p_plus_pdf = engine.dt_pdf(t, irf=irf)
        p_plus_gates, _ = engine._gate_statistics_from_pdf(
            p_plus_pdf,
            float(n_photons),
            gate_profiles,
            cfg,
        )

        cfg.taus[0] = float(max(tau - eps, 0.02))
        p_minus_pdf = engine.dt_pdf(t, irf=irf)
        p_minus_gates, _ = engine._gate_statistics_from_pdf(
            p_minus_pdf,
            float(n_photons),
            gate_profiles,
            cfg,
        )
    finally:
        cfg.taus[0] = original_tau

    d_p = (p_plus_gates - p_minus_gates) / (2.0 * eps)
    detected_photons = float(n_photons) * float(collected_fraction)
    return float(detected_photons * np.sum((d_p ** 2) / np.maximum(p_cen_gates, 1e-15)))


def test_tutorial_f_value_efficiency_and_resolution_identities_match_backend_theory():
    cfg = PhysicsConfig(
        f_x_param="tau1",
        taus=[3.0, 1.0],
        amplitudes=[1.0, 0.0],
        precision_photons=5000,
    )
    engine = TwinEngine(cfg)
    tau = 3.0
    photons = 5000

    fisher_values, f_values = engine.compute_fisher_info(np.array([tau]), n_photons=photons)
    f_value = float(f_values[0])
    efficiency = 1.0 / (f_value ** 2)
    effective_photons = photons * efficiency
    resolvability = np.sqrt(photons / (8.0 * f_value * f_value))

    assert np.isfinite(fisher_values[0]) and fisher_values[0] > 0.0
    assert np.isclose(efficiency, 1.0 / (f_value ** 2), rtol=1e-12, atol=0.0)
    assert np.isclose(effective_photons, photons / (f_value ** 2), rtol=1e-12, atol=0.0)
    assert np.isclose(resolvability, np.sqrt(photons * efficiency / 8.0), rtol=1e-12, atol=0.0)


def test_tutorial_mc_sigma_relation_matches_backend_precision_curve():
    cfg = PhysicsConfig(
        f_x_param="tau1",
        taus=[4.0, 1.0],
        amplitudes=[1.0, 0.0],
        precision_mc_repeats=200,
        precision_photons=20000,
    )
    engine = TwinEngine(cfg)
    tau = 4.0
    photons = 20000

    payload = engine.monte_carlo_precision_curve(np.array([tau]), n_photons=photons, n_repeats=200)
    sigma_tau = float(payload["std_tau"][0])
    f_value = float(payload["f_value"][0])
    expected_sigma = (f_value * tau) / np.sqrt(photons)

    assert np.isfinite(sigma_tau) and sigma_tau > 0.0
    assert np.isfinite(f_value) and f_value > 0.0
    assert np.isclose(sigma_tau, expected_sigma, rtol=0.15)
    assert np.isclose(float(payload["efficiency"][0]), 1.0 / (f_value ** 2), rtol=1e-6)


def test_tutorial_gate_two_bin_discrete_fisher_matches_backend_histogram_mode():
    cfg = PhysicsConfig(
        period=25.0,
        gate_type="custom",
        gate_edges=[1.0, 5.0, 9.0],
        gate_start_mode="free",
        gate_first_start=1.0,
        gate_end_mode="free",
        gate_last_end=9.0,
        gate_rise=0.0,
        gate_fall=0.0,
        gate_collection_mode="histogram",
        gate_overlap_mode="jitter_only",
        gate_overlap_effect="exclusive",
        gate_wraparound=True,
        timing_jitter=0.0,
        f_x_param="tau1",
        taus=[3.0, 1.0],
        amplitudes=[1.0, 0.0],
        optimization_f_photon_basis="collected",
    )
    engine = TwinEngine(cfg)
    tau = 3.0
    photons = 4000

    fisher_backend, f_backend = engine.compute_fisher_info(np.array([tau]), n_photons=photons)
    fisher_tutorial = _theoretical_gate_fisher(engine, tau=tau, n_photons=photons)
    gate_profiles = engine._statistical_gate_profiles(engine.gate_shapes)
    t = np.array(engine.time_vector, copy=True)
    irf = engine.dt_excitation(t)
    irf_sum = np.sum(irf)
    if irf_sum > 0:
        irf = irf / irf_sum
    p_cen_pdf = engine.dt_pdf(t, irf=irf)
    _cond_probs, collected_fraction = engine._gate_statistics_from_pdf(
        p_cen_pdf,
        float(photons),
        gate_profiles,
        cfg,
    )
    photon_budget = engine._f_value_reference_budget(
        float(photons),
        float(collected_fraction),
        photon_basis_mode="collected",
        cfg=cfg,
    )
    f_tutorial = (1.0 / np.sqrt(fisher_tutorial)) * (np.sqrt(photon_budget) / tau)

    assert np.isclose(fisher_tutorial, float(fisher_backend[0]), rtol=1e-4, atol=1e-8)
    assert np.isclose(f_tutorial, float(f_backend[0]), rtol=1e-4, atol=1e-8)
