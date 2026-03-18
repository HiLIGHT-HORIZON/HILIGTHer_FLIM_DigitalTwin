from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import numpy as np

class ChannelMetadata(BaseModel):
    name: str
    index: int
    wavelength: Optional[float] = None

class FileAnalysis(BaseModel):
    filename: str
    metadata: Dict = {}
    
class ConditionGroup(BaseModel):
    name: str
    files: List[FileAnalysis] = []

class UnifiedState(BaseModel):
    """
    Python equivalent of d.Conditions structure in MATLAB.
    Manages the overall app state and data hierarchy.
    """
    conditions: List[ConditionGroup] = []
    current_group_idx: int = 0
    current_file_idx: int = 0
    current_chan_idx: int = 0
    config: Optional["PhysicsConfig"] = None
    
    class Config:
        arbitrary_types_allowed = True

class PhysicsConfig(BaseModel):
    """Configuration for mathematical models and instrument parameters."""
    gate_edges: List[float] = [0.0, 1.1, 3.4, 9.0, 25.0]
    dt_input: float = 0.01
    skewness: float = 0.0  # [ps]
    use_eirf: bool = True
    bg_option: str = "fit"  # fit, fix_manual, gate4, measurement
    fixed_bg_value: float = 0.0
    a_photons: float = 2000.0  # Average photons for simulation
    
    threshold_min: float = 10.0
    threshold_max: float = float('inf')
    
    # Laser & IRF Configuration
    period: float = 12.5 # [ns] Repetition period / Measurement window
    
    irf_profile: str = "gaussian" # gaussian, rectangular, ideal
    irf_fwhm: float = 0.25 # [ns] Width or duration
    irf_position: float = 0.0 # [ns] Center if Gaussian, Start if Rectangular
    irf_rise_time: float = 0.05
    irf_fall_time: float = 0.05
    
    # Burst Excitation (Sub-pulses within the IRF envelope)
    burst_enabled: bool = False
    burst_sub_period: float = 1.0 # [ns]
    burst_sub_fwhm: float = 0.1 # [ns]
    burst_sub_rise_time: Optional[float] = None # [ns] Optional burst edge rise time
    burst_sub_fall_time: Optional[float] = None # [ns] Optional burst edge fall time
    
    # Global fold-over / Fold-train
    b_decay_wrapping: bool = True
    
    # Gating configurations
    gate_type: str = "equal" # equal, custom, adaptive
    gate_profile: str = "sigmoid" # legacy compatibility field; gate edges are controlled by rise/fall
    gate_widths: List[float] = [] # Only used if gate_type == "custom"
    gate_rise: float = 0.05 # [ns] Sigmoid edge rise time
    gate_fall: float = 0.05 # [ns] Sigmoid edge fall time
    gate_stick_to_end: bool = True
    gate_start_mode: str = "start" # irf_3sigma, start, free
    gate_first_start: float = 0.0
    expansion_ratio: float = 0.001 # 'r' parameter for exponential gating
    
    # Advanced Noise Models
    timing_jitter: float = 0.0 # [ps] RMS jitter
    dnl_level: float = 0.0 # Differential Non-Linearity [%]
    detector_deadtime: float = 0.0 # [ns]
    b_multihit_mode: bool = True # Can track multiple photons per laser pulse
    
    # Instrument Identity (for management)
    label: str = "Default"
    metadata: dict = {}

    # Gridded MLE Optimization
    grid_tau_min: float = 0.05
    grid_tau_max: float = 30.0
    grid_steps: int = 2000
    grid_fine_factor: int = 100
    
    # Sweeping Logic for F-Value Measurements
    # F-Value X-Axis Parameter (Model Parameter)
    f_x_param: str = "tau1"  # tau1, tau2, alpha, background, beta
    f_x_min: float = 0.5
    f_x_max: float = 7.5
    f_x_steps: int = 30
    f_x_scale: str = "log"  # linear, log, exp
    
    # Secondary Instrument Parameter Sweep (Generates Multiple Curves)
    instr_sweep_active: bool = False
    instr_sweep_param: str = "laser_pulse_fwhm_ns"
    instr_sweep_vals: List[float] = []
    instr_sweep_gate_sharp_edge: str = "sharp_rise"
    instr_sweep_burst_sharp_edge: str = "sharp_rise"
    instr_sweep_fixed_countrate_kcps: float = 100.0
    instr_sweep_fixed_deadtime_ns: float = 45.0

    # Parameter Fixing (Simplifies the inverse problem / gridded MLE)
    # Dictionary mapping parameter name to whether it's fixed
    fixed_params: Dict[str, bool] = {
        "tau1": False, "tau2": True, "alpha": True, 
        "background": True, "beta": True
    }
    
    # Simulation Logic for Images
    n_repeats: int = 1 
    dt_override: Optional[float] = None # Manual dt setting
    precision_validate_mc: bool = True
    precision_mc_repeats: int = 400
    precision_photons: int = 200
    precision_accuracy_pvalue: float = 0.01
    sweep_autoplay: bool = True
    
    sim_mode: str = "spatial gradient" # spatial gradient, uniform model
    b_interrupt: bool = False

    # Decay Model Parameters
    decay_model: str = "exponential" # exponential, stretched, custom
    n_components: int = 1
    taus: List[float] = [2.5, 1.0]       # List of lifetimes [ns]
    amplitudes: List[float] = [1.0, 0.0] # Relative amplitudes/weights (e.g. tau1, alpha)
    beta: float = 1.0               # Stretching factor (for KWW)
    background_level: float = 0.0   # Constant background per bin
    custom_decay_script: str = ""   # Python expression for I(t)

class MonteCarloParams(BaseModel):
    """Parameters for Monte Carlo photon simulations."""
    n_photons: int = 1000
    n_repeats: int = 100
    tau_true: float = 1.5
    b_true: float = 10.0
    bootstrap_samples: int = 0
    detector_deadtime: float = 0.0
    b_multihit_mode: bool = True
