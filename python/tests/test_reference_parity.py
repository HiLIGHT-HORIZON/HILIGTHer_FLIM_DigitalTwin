import numpy as np
import pytest
from backend.twin_engine import TwinEngine
from backend.models import PhysicsConfig

def test_benchmark_4gate_baseline():
    """
    Verifies parity with the legacy baseline:
    4 gates, edges [0, 8, 16, 24, 32], tau=2.0ns.
    Target: ~40% efficiency.
    """
    cfg = PhysicsConfig()
    cfg.period = 50.0
    cfg.gate_edges = [0.0, 8.0, 16.0, 24.0, 32.0]
    
    # 7.5ns Rectangular Burst
    cfg.irf_profile = "rectangular"
    cfg.irf_fwhm = 7.5
    cfg.irf_position = 0.0
    
    engine = TwinEngine(cfg)
    tau_grid = np.array([2.0])
    
    # Theoretical Fisher Info
    fi, f_val = engine.compute_fisher_info(tau_grid)
    
    # Photon Efficiency = 1 / F^2 (approximate for multi-parameter)
    # But F in the doc is the fold increase in noise.
    # The doc says "4 even gates indeed exhibit only a ~40% efficiency at 2 ns."
    # Efficiency in the context of F = 1 / F^2.
    efficiency = 1.0 / (f_val[0]**2)
    
    # Assert within expected range (40% +/- 5%)
    assert 0.35 <= efficiency <= 0.45

def test_benchmark_4gate_optimized():
    """
    Verifies parity with the legacy optimized config:
    Edges [0.0, 2.8, 7.5, 12.5, 32.0], tau=2.0ns.
    Target: ~50% efficiency.
    """
    cfg = PhysicsConfig()
    cfg.period = 50.0
    cfg.gate_edges = [0.0, 2.8, 7.5, 12.5, 32.0]
    
    # 7.5ns Rectangular Burst
    cfg.irf_profile = "rectangular"
    cfg.irf_fwhm = 7.5
    cfg.irf_position = 0.0
    
    engine = TwinEngine(cfg)
    tau_grid = np.array([2.0])
    
    # Theoretical Fisher Info
    fi, f_val = engine.compute_fisher_info(tau_grid)
    efficiency = 1.0 / (f_val[0]**2)
    
    # Assert improvement over baseline (Target 50%)
    assert 0.45 <= efficiency <= 0.55

def test_hardware_jitter_tolerance():
    """
    Verifies that system performance remains robust up to 500ps jitter (std).
    Target: High efficiency maintained.
    """
    cfg = PhysicsConfig()
    cfg.period = 50.0
    cfg.gate_edges = [0.0, 2.8, 7.5, 12.5, 32.0]
    cfg.irf_fwhm = 7.5
    
    # 500ps (0.5ns) standard deviation jitter
    cfg.timing_jitter = 500.0 
    
    engine = TwinEngine(cfg)
    tau_grid = np.array([3.5]) # Peak efficiency region
    
    fi, f_val = engine.compute_fisher_info(tau_grid)
    efficiency = 1.0 / (f_val[0]**2)
    
    # Benchmark says efficiency remains high (>60%)
    assert efficiency > 0.60
