import numpy as np
import pytest
from backend.twin_engine import TwinEngine
from backend.models import PhysicsConfig

def test_median_filter_raw_data():
    """Verifies that the median filter correctly removes salt-and-pepper noise from raw data."""
    cfg = PhysicsConfig()
    engine = TwinEngine(cfg)
    
    # Create a 10x10 dataset with 4 gates
    ny, nx, ng = 10, 10, 4
    data = np.zeros((ny, nx, ng))
    
    # Add a "hot pixel" in the middle of the first gate
    data[5, 5, 0] = 1000.0
    engine.raw_data = data.copy()
    
    # Apply 3x3 median filter
    engine.apply_median_filter(size=3)
    
    # The hot pixel should be gone (median of one 1000 and eight 0s is 0)
    assert engine.raw_data[5, 5, 0] == 0.0
    # Other pixels should remain zero
    assert np.all(engine.raw_data == 0.0)

def test_median_filter_tau_map():
    """Verifies that the median filter correctly smooths the lifetime map."""
    cfg = PhysicsConfig()
    engine = TwinEngine(cfg)
    
    # Create a 5x5 lifetime map with an outlier
    tau_map = np.ones((5, 5)) * 2.5
    tau_map[2, 2] = 10.0 # Outlier
    engine.tau_map = tau_map.copy()
    
    # Apply 3x3 median filter
    engine.apply_median_filter(size=3)
    
    # The outlier should be smoothed out to the background value
    assert engine.tau_map[2, 2] == 2.5
    assert np.all(engine.tau_map == 2.5)

def test_median_filter_no_data():
    """Ensures the filter handles None gracefully."""
    engine = TwinEngine()
    engine.raw_data = None
    engine.tau_map = None
    
    # Should not raise exception
    engine.apply_median_filter(size=3)
