
import numpy as np
import copy
from backend.twin_engine import TwinEngine
from backend.models import PhysicsConfig

def debug_batch_physics():
    engine = TwinEngine()
    cfg = engine.config
    
    # Force a known-good configuration
    cfg.period = 12.5
    cfg.irf_position = 2.0  # Put IRF in the middle of the first few ns
    cfg.irf_profile = "gaussian"
    cfg.irf_fwhm = 0.25
    cfg.timing_jitter = 0.0
    cfg.gate_edges = [0.0, 1.0, 2.0, 4.0, 8.0, 12.5]
    cfg.a_photons = 2000
    cfg.f_x_param = "tau1"
    
    x_grid = np.array([0.5, 1.0, 2.0, 4.0])
    
    # Parameter to sweep: irf_fwhm
    sweep_vals = [0.1, 0.5, 1.0]
    
    print(f"=== Debugging Fisher Physics ===")
    print(f"Baseline: IRF Pos={cfg.irf_position}, Period={cfg.period}, Gates={cfg.gate_edges}")
    
    for val in sweep_vals:
        cfg.irf_fwhm = val
        # In TwinEngine, we need to ensure the engine sees the updated config
        engine.config = cfg
        
        _, f_val = engine.compute_fisher_info(x_grid, 2000)
        
        # Check internal signal strength
        t = np.arange(0, 20, 0.01)
        irf = engine.dt_excitation(t)
        pdf = engine.dt_pdf(t, tau=2.0) # at tau=2ns
        
        print(f"\n[Sweep irf_fwhm={val}]")
        print(f"  IRF peak: {np.max(irf):.4f}, IRF sum: {np.sum(irf):.4f}")
        print(f"  PDF peak: {np.max(pdf):.4f}, PDF sum: {np.sum(pdf):.4f}")
        print(f"  Result F: {f_val}")
        
if __name__ == "__main__":
    debug_batch_physics()
