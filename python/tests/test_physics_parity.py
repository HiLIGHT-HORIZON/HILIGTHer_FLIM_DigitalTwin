import os
import numpy as np
import scipy.io as sio
import pytest
from backend.twin_engine import TwinEngine
from backend.models import PhysicsConfig

def test_gate_shapes_parity():
    """
    Verifies that distilled gate shapes match MATLAB 1:1.
    Requires ground_truth/reference_sim.mat
    """
    mat_path = 'python/data/ground_truth/reference_sim.mat'
    if not os.path.exists(mat_path):
        pytest.skip("Reference MAT file not found. Run the legacy export script first.")
        
    mat = sio.loadmat(mat_path)
    
    # Legacy reference properties are direct keys in the results struct.
    # Note: these values are sometimes converted to double arrays.
    ref_gates = mat['GateShapes'] # [nGates x nTime]
    ref_time = mat['TimeVector'].flatten() # [1 x nTime]
    ref_edges = mat['GateEdges'].flatten()
    ref_skew = float(mat['Skewness'])
    
    # Setup Python Engine
    cfg = PhysicsConfig(
        gate_edges=ref_edges.tolist(),
        dt_input=float(mat['DtInput']),
        skewness=ref_skew,
        use_eirf=False
    )
    engine = TwinEngine(cfg)
    engine.distill_gates()
    
    # Check Time Vector
    # Allow for floating point differences in np.arange vs the legacy colon step.
    assert np.allclose(engine.time_vector, ref_time, atol=1e-8)
    
    # Check Gate Shapes
    assert np.allclose(engine.gate_shapes, ref_gates, atol=1e-8)

def test_fit_parity():
    """
    Verifies that the fitting engine yields identical lifetime maps.
    """
    mat_path = 'python/data/ground_truth/reference_sim.mat'
    if not os.path.exists(mat_path):
        pytest.skip("Reference MAT file not found.")
        
    mat = sio.loadmat(mat_path)
    ref_tau = mat['TauMap']
    ref_raw = mat['RawData'] # (nY, nX, nGates)
    
    cfg = PhysicsConfig(
        gate_edges=mat['GateEdges'].flatten().tolist(),
        dt_input=float(mat['DtInput']),
        skewness=float(mat['Skewness']),
        use_eirf=False,
        bg_option='fit'
    )
    
    engine = TwinEngine(cfg)
    engine.distill_gates()
    
    # Run the fit on the same raw data exported from the legacy reference workflow.
    engine.run_fit(ref_raw)
    
    # Validate Parity
    # We use a slightly looser tolerance for Nelder-Mead across languages
    mask = ~np.isnan(ref_tau)
    rmse = np.sqrt(np.mean((engine.tau_map[mask] - ref_tau[mask])**2))
    
    print(f"Parity RMSE: {rmse:.6f} ns")
    assert rmse < 1e-4
