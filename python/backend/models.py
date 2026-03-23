from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
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
    Unified application state for the Python desktop and service surfaces.
    Manages the current data hierarchy, active selection, and configuration.
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
    irf_freeform_points: List[float] = []
    irf_freeform_times: List[float] = []
    irf_freeform_edit_mode: bool = True
    
    # Burst Excitation (Sub-pulses within the IRF envelope)
    burst_enabled: bool = False
    burst_sub_period: float = 1.0 # [ns]
    burst_sub_fwhm: float = 0.1 # [ns]
    burst_sub_rise_time: Optional[float] = None # [ns] Optional burst edge rise time
    burst_sub_fall_time: Optional[float] = None # [ns] Optional burst edge fall time
    
    # Global fold-over / Fold-train
    b_decay_wrapping: bool = True
    
    # Gating configurations
    gate_type: str = "equal" # equal, custom
    gate_profile: str = "sigmoid" # legacy compatibility field; gate edges are controlled by rise/fall
    gate_widths: List[float] = []
    gate_rise: float = 0.05 # [ns] Sigmoid edge rise time
    gate_fall: float = 0.05 # [ns] Sigmoid edge fall time
    gate_start_mode: str = "start" # irf_3sigma, start, free
    gate_first_start: float = 0.0
    gate_end_mode: str = "period" # period, free
    gate_last_end: float = 12.5
    gate_collection_mode: str = "histogram" # histogram, sequential
    gate_overlap_mode: str = "jitter_only" # jitter_only, never, allow
    gate_overlap_ns: float = 0.0
    gate_overlap_effect: str = "exclusive" # exclusive, duplicate_events, independent_duplicates
    gate_wraparound: bool = True
    expansion_ratio: float = 0.001 # 'r' parameter for exponential gating
    
    # Advanced Noise Models
    timing_jitter: float = 0.0 # [ps] RMS jitter
    dnl_level: float = 0.0 # Differential Non-Linearity [%]
    detector_deadtime: float = 0.0 # [ns]
    detector_afterpulsing_probability: float = 0.0 # [0..1] probability of one afterpulse per accepted event
    detector_dark_count_rate_cps: float = 0.0 # [counts/s]
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
    instr_sweep_vals: List[Any] = []
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
    image_mc_repeats: int = 200
    image_fit_method: str = "gridded_mle"  # gridded_mle, mle, tail
    active_instrument_profile: Optional[str] = None
    dt_override: Optional[float] = None # Manual dt setting
    precision_validate_mc: bool = False
    precision_compute_ci: bool = False
    precision_mc_repeats: int = 400
    precision_photons: int = 2000
    precision_accuracy_pvalue: float = 0.0001
    precision_bootstrap_samples: int = 2000
    precision_ci_level: float = 99.7
    sweep_autoplay: bool = True

    # Optimization Controller
    optimize_detection_gates: bool = False
    optimize_excitation_profile: bool = False
    optimization_mode: str = "sequential"  # legacy compatibility field; joint optimisation now alternates sequentially
    optimization_first: str = "detection"  # detection, excitation
    optimization_iterations: int = 20
    optimization_f_photon_basis: str = "collected"  # collected, period, all
    optimization_objective: str = "fisher_throughput"  # fisher_information, fisher_throughput, photon_efficiency_auc, throughput_auc
    optimization_max_fi_loss_pct: float = 5.0
    optimization_realtime_visualization: bool = False
    optimization_realtime_interval_s: float = 5.0
    optimization_intermediate_steps: int = 6
    optimization_validate_mc_intermediates: bool = False

    detection_optimization_algorithm: str = "fisher_compression"  # direct_slsqp, partition_bottom_up, partition_top_down, fisher_compression
    detection_opt_restarts: int = 20
    detection_opt_ftol: float = 1e-4
    detection_opt_maxiter: int = 50
    detection_opt_fine_bins_per_gate: int = 12
    detection_opt_fine_bin_cap: int = 256
    detection_opt_fc_nuisance_aware: bool = True
    detection_opt_fc_auto_compress: bool = False
    detection_opt_fc_initial_gates: int = 16
    detection_opt_fc_min_gates: int = 2
    detection_opt_fc_max_f_loss_pct: float = 5.0
    detection_opt_start_anchor: str = "zero"  # zero, irf, custom
    detection_opt_start_time: float = 0.0
    detection_opt_end_anchor: str = "period"  # period, custom
    detection_opt_end_time: float = 12.5

    excitation_optimization_profile: str = "gaussian"  # gaussian, rectangular, free_form
    excitation_optimization_constraint: str = "fixed_dose"  # fixed_dose, fixed_peak
    excitation_optimization_width_min: float = 0.05
    excitation_optimization_width_max: float = 10.0
    excitation_optimization_control_points: int = 8

    sim_mode: str = "spatial gradient" # spatial gradient, uniform model
    simulation_mode_preference: str = "auto"  # auto, ideal_poisson, event_driven
    simulation_mode: str = "ideal_poisson"  # ideal_poisson, event_driven
    event_routing_mode: str = "exclusive"  # exclusive, nonexclusive
    event_arbitration_rule: str = "random"  # random, priority, all_if_independent
    event_deadtime_mode: str = "nonparalyzable"  # none, nonparalyzable, paralyzable
    event_multihit_capacity: Optional[int] = None  # None=infinite, 1=first-hit, C=finite multihit
    event_return_timestamps: bool = False
    event_share_resource_group: bool = False
    event_pixel_dwell_time_s: float = 1e-3
    event_cpu_workers: int = 0  # 0=auto, 1=serial, >1 explicit process count
    b_interrupt: bool = False

    # Decay Model Parameters
    decay_model: str = "exponential" # exponential, stretched, or custom model key
    n_components: int = 1
    taus: List[float] = [2.5, 1.0]       # List of lifetimes [ns]
    amplitudes: List[float] = [1.0, 0.0] # Relative amplitudes/weights (e.g. tau1, alpha)
    beta: float = 1.0               # Stretching factor (for KWW)
    background_level: float = 0.0   # Background fraction of the total decay mass [0..1]
    custom_decay_script: str = ""   # Python expression for I(t)
    custom_model_params: Dict[str, float] = {}
    decay_model_sweep_defaults: Dict[str, Dict[str, Dict[str, Any]]] = {}

class MonteCarloParams(BaseModel):
    """Parameters for Monte Carlo photon simulations."""
    n_photons: int = 1000
    n_repeats: int = 100
    tau_true: float = 1.5
    b_true: float = 10.0
    bootstrap_samples: int = 0
    detector_deadtime: float = 0.0
    b_multihit_mode: bool = True
