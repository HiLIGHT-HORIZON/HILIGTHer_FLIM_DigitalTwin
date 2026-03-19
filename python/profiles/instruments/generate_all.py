
import json
import numpy as np
import os

def generate_profile(legacy_data):
    mapping = {
        "T": "pt_trep",
        "fwhm": "irf_fwhm",
        "profile": "irf_profile",
        "toff": "toff",
        "rise_time": "irf_rise_time",
        "fall_time": "irf_fall_time",
        "bPulseTrain": "b_pulse_train",
        "PT_Trep": "pt_trep",
        "PT_sigma": "pt_sigma",
        "r": "expansion_ratio",
        "N_photons": "a_photons",
        "M": "n_repeats",
        "dt": "dt_input",
        "jitter": "timing_jitter",
        "deadtime": "detector_deadtime",
        "name": "label"
    }
    new_data = {
        "gate_edges": [0.0, 1.1, 3.4, 9.0, 25.0],
        "decay_model": "exponential",
        "n_components": 1,
        "taus": [2.5, 1.0],
        "amplitudes": [1.0, 0.0],
        "beta": 1.0,
        "background_level": 0.0,
        "gate_type": "equal"
    }
    for k, v in legacy_data.items():
        if k in mapping:
            new_key = mapping[k]
            if new_key == "irf_profile" and isinstance(v, str): v = v.lower()
            new_data[new_key] = v
        if k == "gate_type" and isinstance(v, str):
            v_low = v.lower()
            if "custom" in v_low: new_data["gate_type"] = "custom"
            elif "equal" in v_low: new_data["gate_type"] = "equal"
            elif "adaptive" in v_low: new_data["gate_type"] = "custom"

    if "gate_widths" in legacy_data and legacy_data["gate_widths"]:
        widths = legacy_data["gate_widths"]
        edges = [0.0]
        for w in widths: edges.append(edges[-1] + w)
        new_data["gate_edges"] = edges
        new_data["gate_widths"] = widths
    elif "N_gates" in legacy_data:
        n = legacy_data["N_gates"]
        trep = new_data.get("pt_trep", 12.5)
        if n > 0:
            new_data["gate_edges"] = np.linspace(0, trep, n+1).tolist()
            new_data["gate_widths"] = [trep/n] * n
    return new_data

# Data
hilight = {"T": 50, "fwhm": 5, "profile": "Rectangular", "toff": 18, "rise_time": 0, "fall_time": 0, "bPulseTrain": False, "PT_Trep": 0.1, "PT_sigma": 0.05, "gate_type": "Custom (max 8)", "N_gates": 4, "r": 0.001, "N_photons": 10000, "M": 400, "dt": 0.01, "gate_widths": [5.4854818310269948, 2.0892448514705926, 7.1302974318360866, 35.294975883573862], "name": "HiLIGHT"}
tcspc = {"T": 12.5, "fwhm": 0.01, "profile": "Rectangular", "toff": 12.5, "rise_time": 0, "fall_time": 0, "bPulseTrain": False, "PT_Trep": 0.1, "PT_sigma": 0.05, "gate_type": "Equal", "N_gates": 128, "r": 0.0001, "gate_widths": [], "name": "TCSPC (12.5ns - 128 bins)"}
optimized = {"T": 12.5, "fwhm": 0.01, "profile": "Rectangular", "toff": 12.5, "rise_time": 0, "fall_time": 0, "bPulseTrain": False, "PT_Trep": 0.1, "PT_sigma": 0.05, "gate_type": "Custom (max 8)", "N_gates": 4, "r": 0.0001, "gate_widths": [1.2022312357422731, 1.5704123307679585, 6.6405861563017554, 2.5452524188534049], "name": "TimeGating 4 bins - optimized"}

target_dir = r"c:\Users\ae275\OneDrive - Brunel University London\Documents\HILIGHT_DigitalTwin\DigitalTwin_Matlab\python\profiles\instruments"

for name, data in [("HiLIGHT.json", hilight), ("TCSPC (12.5ns - 128 bins).json", tcspc), ("TimeGating 4 bins - optimized.json", optimized)]:
    translated = generate_profile(data)
    with open(os.path.join(target_dir, name), 'w') as f:
        json.dump(translated, f, indent=4)
    print(f"Generated: {name}")
