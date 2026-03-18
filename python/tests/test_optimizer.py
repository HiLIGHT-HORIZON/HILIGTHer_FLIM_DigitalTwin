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
