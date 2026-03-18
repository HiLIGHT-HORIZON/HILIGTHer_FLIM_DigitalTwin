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
