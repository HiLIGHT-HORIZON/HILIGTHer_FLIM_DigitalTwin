
import json
import numpy as np

trep = 12.5
n = 128
edges = np.linspace(0, trep, n+1).tolist()
widths = [trep/n] * n

data = {
    "pt_trep": 12.5,
    "irf_fwhm": 0.01,
    "irf_profile": "rectangular",
    "toff": 12.5,
    "irf_rise_time": 0,
    "irf_fall_time": 0,
    "b_pulse_train": false,
    "pt_sigma": 0.05,
    "gate_type": "equal",
    "expansion_ratio": 0.0001,
    "a_photons": 2000.0,
    "n_repeats": 1,
    "dt_input": 0.05,
    "gate_edges": edges,
    "gate_widths": widths,
    "label": "TCSPC (12.5ns - 128 bins)",
    "decay_model": "exponential",
    "n_components": 1,
    "taus": [2.5, 1.0],
    "amplitudes": [1.0, 0.0],
    "beta": 1.0,
    "background_level": 0.0
}

# The true value for boolean in JSON is 'false' (lowercase)
# But in Python dict it's 'False'. Since I use json.dump it's fine.
data["b_pulse_train"] = False

target_path = r"c:\Users\ae275\OneDrive - Brunel University London\Documents\HILIGHT_DigitalTwin\DigitalTwin_Matlab\python\profiles\instruments\TCSPC (12.5ns - 128 bins).json"
with open(target_path, 'w') as f:
    json.dump(data, f, indent=4)
