
import os
import json
import numpy as np

def translate_profile(legacy_data):
    # Mapping table
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

    new_data = {}
    
    # Defaults from PhysicsConfig
    new_data["gate_edges"] = [0.0, 1.1, 3.4, 9.0, 25.0]
    new_data["decay_model"] = "exponential"
    new_data["n_components"] = 1
    new_data["taus"] = [2.5, 1.0]
    new_data["amplitudes"] = [1.0, 0.0]
    new_data["beta"] = 1.0
    new_data["background_level"] = 0.0

    for k, v in legacy_data.items():
        if k in mapping:
            new_key = mapping[k]
            if new_key == "irf_profile" and isinstance(v, str):
                v = v.lower()
            new_data[new_key] = v
        
        # Special gate type logic
        if k == "gate_type" and isinstance(v, str):
            v_low = v.lower()
            if "custom" in v_low: new_data["gate_type"] = "custom"
            elif "equal" in v_low: new_data["gate_type"] = "equal"
            elif "adaptive" in v_low: new_data["gate_type"] = "adaptive"
            else: new_data["gate_type"] = "equal"

    # Post-processing for Gating
    if "gate_widths" in legacy_data and legacy_data["gate_widths"]:
        widths = legacy_data["gate_widths"]
        edges = [0.0]
        for w in widths:
            edges.append(edges[-1] + w)
        new_data["gate_edges"] = edges
        new_data["gate_widths"] = widths
    elif "N_gates" in legacy_data and new_data.get("gate_type") == "equal":
        # Generate equal gates if possible
        trep = new_data.get("pt_trep", 12.5)
        n = legacy_data["N_gates"]
        if n > 0:
            w = trep / n
            new_data["gate_edges"] = np.linspace(0, trep, n+1).tolist()
            new_data["gate_widths"] = [w] * n

    return new_data

# Paths relative to script location
base_dir = os.path.dirname(os.path.abspath(__file__))
legacy_dir = os.path.join(base_dir, "AppProperties", "instruments")
target_dir = os.path.join(base_dir, "python", "profiles", "instruments")

if not os.path.exists(target_dir):
    os.makedirs(target_dir)

if os.path.exists(legacy_dir):
    for f in os.listdir(legacy_dir):
        if f.endswith(".json"):
            legacy_path = os.path.join(legacy_dir, f)
            with open(legacy_path, 'r') as file:
                legacy_data = json.load(file)
            
            translated = translate_profile(legacy_data)
            
            target_path = os.path.join(target_dir, f)
            with open(target_path, 'w') as file:
                json.dump(translated, file, indent=4)
            print(f"Translated: {f}")
else:
    print(f"Legacy dir not found: {legacy_dir}")
