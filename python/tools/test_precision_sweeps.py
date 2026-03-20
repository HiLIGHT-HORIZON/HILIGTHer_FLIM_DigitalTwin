"""
Diagnostic test that mirrors the exact batch sweep flow in main_window.py.
This verifies that setattr on PhysicsConfig actually changes values.
"""
import copy
import sys
from pathlib import Path

import numpy as np

PYTHON_ROOT = Path(__file__).resolve().parent.parent
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from backend.twin_engine import TwinEngine
from backend.models import PhysicsConfig

def test_setattr_mutation():
    """Does setattr actually change a Pydantic model field?"""
    cfg = PhysicsConfig()
    original = cfg.timing_jitter
    setattr(cfg, "timing_jitter", 999.0)
    after = cfg.timing_jitter
    print(f"setattr mutation test: before={original}, after={after}, changed={original != after}")
    return original != after

def test_batch_sweep_isolation():
    """Mirrors the exact flow of main_window.run_precision_analysis batch loop."""
    engine = TwinEngine()
    cfg = engine.config
    cfg.taus = [2.5]
    cfg.amplitudes = [1.0]
    cfg.period = 12.5
    cfg.gate_edges = [0.0, 3.0, 6.0, 9.0, 12.5]
    cfg.f_x_param = "tau1"

    x_grid = np.linspace(0.5, 5.0, 5)
    sweep_vals = [50.0, 500.0]  # ps jitter
    param = "timing_jitter"

    results = {}
    for val in sweep_vals:
        orig_state = copy.deepcopy(cfg)
        try:
            setattr(cfg, param, val)
            engine.config = cfg  # Make sure engine sees it
            
            # Confirm the value actually changed
            actual_val = getattr(engine.config, param)
            print(f"  Sweeping {param}={val}, engine sees: {actual_val}")

            _, f_val = engine.compute_fisher_info(x_grid, 1000)
            results[val] = f_val.copy()
        finally:
            engine.config = orig_state
            cfg = orig_state

    print("\n--- Results ---")
    for val, f in results.items():
        print(f"  {param}={val}: {np.round(f, 4)}")

    # Check if curves are distinct
    vals = list(results.values())
    if len(vals) >= 2:
        diff = np.mean(np.abs(vals[0] - vals[1]))
        print(f"\nMean Difference: {diff:.6f}")
        if diff < 1e-6:
            print("FAIL: Curves identical in batch flow!")
        else:
            print("SUCCESS: Batch curves are distinct.")

if __name__ == "__main__":
    print("=== Testing setattr mutation ===")
    ok = test_setattr_mutation()
    if not ok:
        print("CRITICAL: Pydantic model is IMMUTABLE - setattr has no effect!")
    print()
    print("=== Testing batch sweep isolation ===")
    test_batch_sweep_isolation()
