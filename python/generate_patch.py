import json
import numpy as np

edges = np.linspace(0, 25, 257).tolist()
patch = {
    "gate_edges": edges,
    "gate_last_end": 25.0,
    "detection_opt_end_time": 25.0
}
with open('tmp_patch.json', 'w') as f:
    json.dump(patch, f)
