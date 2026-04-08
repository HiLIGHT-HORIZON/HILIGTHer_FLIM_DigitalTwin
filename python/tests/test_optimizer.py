import numpy as np
import pytest
from backend.twin_engine import TwinEngine
from backend.models import PhysicsConfig

def test_optimize_gates_logic():
    """
    Verifies that the gate optimization engine finds valid, monotonic edges
    and improves (or maintains) the objective function J.
    """
    engine = TwinEngine()
    
    n_gates = 4
    t_max = 12.5
    tau_range = (0.5, 5.0)
    n_restarts = 3 # Small for testing
    
    # Run optimization
    best_edges, best_j, info = engine.optimize_gates(
        n_gates=n_gates,
        t_max=t_max,
        tau_range=tau_range,
        n_restarts=n_restarts
    )
    
    # 1. Check number of edges
    assert len(best_edges) == n_gates + 1
    
    # 2. Check monotonicity
    assert np.all(np.diff(best_edges) > 0)
    
    # 3. Check boundaries
    assert np.isclose(best_edges[0], 0.0)
    assert np.isclose(best_edges[-1], t_max)
    
    # 4. Check results info
    assert "fisher_info" in info
    assert "tau_grid" in info
    assert len(info["tau_grid"]) == 50 # Default n_tau
    assert info["fisher_info"].shape == (50,)

def test_optimization_improvement():
    """
    Ensures that the optimizer finds a solution at least as good as 
    the starting point (equal gates).
    """
    engine = TwinEngine()
    t_max = 20.0
    n_gates = 3
    
    # Calculate baseline (equal spacing)
    equal_edges = np.linspace(0, t_max, n_gates + 1)
    engine.config.gate_edges = equal_edges.tolist()
    tau_grid = np.logspace(np.log10(0.5), np.log10(5.0), 20)
    _, f_baseline = engine.compute_fisher_info(tau_grid)
    j_baseline = np.mean(f_baseline)
    
    # Run Optimization
    best_edges, best_j, _ = engine.optimize_gates(
        n_gates=n_gates,
        t_max=t_max,
        tau_range=(0.5, 5.0),
        n_tau=20,
        n_restarts=5
    )
    
    # J should be <= baseline (minimization)
    assert best_j <= j_baseline + 1e-9


@pytest.mark.parametrize(
    "algorithm",
    ["partition_bottom_up", "partition_top_down", "fisher_compression"],
)
def test_additional_detection_algorithms_return_valid_edges(algorithm):
    engine = TwinEngine(PhysicsConfig(period=12.5))
    best_edges, best_j, info = engine.optimize_gates(
        n_gates=4,
        t_max=12.5,
        tau_range=(0.5, 5.0),
        n_tau=12,
        n_restarts=2,
        algorithm=algorithm,
    )

    assert len(best_edges) == 5
    assert np.all(np.diff(best_edges) > 0)
    assert np.isclose(best_edges[0], 0.0)
    assert np.isclose(best_edges[-1], 12.5)
    assert np.isfinite(best_j)
    assert info["algorithm"] == algorithm
    assert info["f_val"].shape == (12,)


def test_additional_detection_algorithms_honor_custom_window():
    engine = TwinEngine(PhysicsConfig(period=12.5))
    best_edges, best_j, info = engine.optimize_gates(
        n_gates=3,
        t_max=12.5,
        tau_range=(0.5, 5.0),
        n_tau=10,
        algorithm="fisher_compression",
        start_anchor="custom",
        start_time=1.5,
        end_anchor="custom",
        end_time=10.0,
    )

    assert len(best_edges) == 4
    assert np.all(np.diff(best_edges) > 0)
    assert np.isclose(best_edges[0], 1.5)
    assert np.isclose(best_edges[-1], 10.0)
    assert np.isfinite(best_j)
    assert np.isclose(info["window_start"], 1.5)
    assert np.isclose(info["window_end"], 10.0)


def test_direct_gate_optimization_responds_to_photon_basis_mode():
    all_cfg = PhysicsConfig(
        period=12.5,
        gate_type="custom",
        gate_start_mode="free",
        gate_first_start=6.0,
        gate_end_mode="free",
        gate_last_end=12.5,
        optimization_f_photon_basis="all",
        detection_opt_restarts=2,
        detection_opt_maxiter=20,
        detection_opt_ftol=1e-3,
    )
    collected_cfg = all_cfg.model_copy(update={"optimization_f_photon_basis": "collected"})

    all_edges, all_j, _ = TwinEngine(all_cfg).optimize_gates(
        n_gates=3,
        t_max=12.5,
        tau_range=(0.5, 7.5),
        n_tau=10,
        n_restarts=2,
        algorithm="direct_slsqp",
        start_anchor="custom",
        start_time=6.0,
        end_anchor="custom",
        end_time=12.5,
    )
    collected_edges, collected_j, _ = TwinEngine(collected_cfg).optimize_gates(
        n_gates=3,
        t_max=12.5,
        tau_range=(0.5, 7.5),
        n_tau=10,
        n_restarts=2,
        algorithm="direct_slsqp",
        start_anchor="custom",
        start_time=6.0,
        end_anchor="custom",
        end_time=12.5,
    )

    assert np.isfinite(all_j)
    assert np.isfinite(collected_j)
    assert not np.allclose(all_edges, collected_edges, atol=1e-3)
    assert not np.isclose(all_j, collected_j, rtol=1e-2)


def test_optimization_summary_uses_all_photon_basis_for_throughput(monkeypatch):
    engine = TwinEngine(PhysicsConfig(optimization_f_photon_basis="collected"))
    seen_modes = []

    def fake_compute_fisher_info(x_range, n_photons, photon_basis_mode="all"):
        seen_modes.append(str(photon_basis_mode))
        if photon_basis_mode == "all":
            return np.ones_like(x_range, dtype=float), np.ones_like(x_range, dtype=float)
        return np.ones_like(x_range, dtype=float), np.full_like(x_range, 2.0, dtype=float)

    monkeypatch.setattr(engine, "compute_fisher_info", fake_compute_fisher_info)

    summary = engine._optimization_efficiency_summary(
        engine.config,
        np.array([1.0, 2.0, 3.0]),
        objective_mode="fisher_throughput",
        n_photons=1000,
        reference_excitation_area=1.0,
        reference_precision_rate_hz=1000.0,
    )

    assert seen_modes == ["collected", "all"]
    assert summary["display_photon_basis"] == "collected"
    assert summary["objective_photon_basis"] == "all"
    assert np.isclose(summary["display_peak_efficiency"], 0.25)
    assert np.isclose(summary["peak_efficiency"], 1.0)


def test_count_rate_optimization_respects_accuracy_guard(monkeypatch):
    cfg = PhysicsConfig(
        optimize_count_rate=True,
        optimization_objective="fisher_throughput",
        count_rate_optimization_min_kcps=1.0,
        count_rate_optimization_max_kcps=100.0,
        count_rate_optimization_steps=3,
        count_rate_optimization_scale="log",
        count_rate_optimization_enforce_accuracy=True,
        count_rate_optimization_max_bias_pct=5.0,
        precision_photons=1000,
    )
    engine = TwinEngine(cfg)

    def fake_evaluate(candidate_cfg, x_range, algorithm, step, callback, progress_callback, objective_mode, reference_excitation_area, reference_precision_rate_hz=None, note=""):
        rate_kcps = candidate_cfg.precision_photons / candidate_cfg.event_pixel_dwell_time_s / 1000.0
        return {
            "objective": 1.0 / max(rate_kcps, 1e-12),
            "throughput_metric": float(rate_kcps),
            "throughput_auc": float(rate_kcps),
            "peak_efficiency": 1.0,
            "auc_efficiency": 1.0,
            "min_f": 1.0,
            "edges": np.array([0.0, 1.0]),
            "f_val": np.array([1.0, 1.0]),
            "fisher_info": np.array([1.0, 1.0]),
            "config": candidate_cfg.model_dump(),
            "note": note,
        }

    def fake_bias(candidate_cfg, x_range, n_photons):
        rate_kcps = candidate_cfg.precision_photons / candidate_cfg.event_pixel_dwell_time_s / 1000.0
        max_bias = 1.0 if rate_kcps <= 10.0 + 1e-9 else 12.0
        return {
            "predicted_estimate": np.array([1.0, 2.0]),
            "relative_bias_pct": np.array([max_bias, max_bias]),
            "max_relative_bias_pct": max_bias,
            "rms_relative_bias_pct": max_bias,
        }

    monkeypatch.setattr(engine, "_evaluate_optimization_config", fake_evaluate)
    monkeypatch.setattr(engine, "_predicted_accuracy_bias_summary", fake_bias)

    best_cfg, _best_j, _info = engine.optimize_count_rate((1.0, 3.0), n_tau=2)
    best_rate_kcps = best_cfg.precision_photons / best_cfg.event_pixel_dwell_time_s / 1000.0

    assert np.isclose(best_rate_kcps, 10.0, rtol=1e-6)
    assert np.all(np.asarray(_info["coarse_candidate_kcps"], dtype=float) >= 1.0)
    assert np.all(np.asarray(_info["coarse_candidate_kcps"], dtype=float) <= 100.0)
    assert np.all(np.asarray(_info["refined_candidate_kcps"], dtype=float) >= 1.0)
    assert np.all(np.asarray(_info["refined_candidate_kcps"], dtype=float) <= 100.0)


def test_optimization_summary_uses_corrected_fisher_when_deadtime_correction_enabled(monkeypatch):
    cfg = PhysicsConfig(
        optimization_f_photon_basis="collected",
        deadtime_correction_method="isbaner_histogram",
    )
    engine = TwinEngine(cfg)
    seen = []

    def fail_raw(*args, **kwargs):
        raise AssertionError("raw compute_fisher_info should not be used for corrected summary")

    def fake_corrected(x_range, n_photons, correction_method=None, photon_basis_mode=None):
        seen.append((str(correction_method), str(photon_basis_mode)))
        if photon_basis_mode == "all":
            return np.ones_like(x_range), np.ones_like(x_range), {"method": correction_method}
        return np.ones_like(x_range), np.full_like(x_range, 2.0), {"method": correction_method}

    monkeypatch.setattr(engine, "compute_fisher_info", fail_raw)
    monkeypatch.setattr(engine, "compute_deadtime_corrected_fisher_info", fake_corrected)

    summary = engine._optimization_efficiency_summary(
        cfg,
        np.array([1.0, 2.0, 3.0]),
        objective_mode="fisher_throughput",
        n_photons=1000,
        reference_excitation_area=1.0,
        reference_precision_rate_hz=1000.0,
    )

    assert seen == [("isbaner_histogram", "collected"), ("isbaner_histogram", "all")]
    assert summary["deadtime_correction_enabled"] is True
    assert summary["objective_photon_basis"] == "all"
