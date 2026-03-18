import h5py
import numpy as np
import os
from typing import Dict, Any, Optional, Tuple
from .models import UnifiedState, PhysicsConfig

class HDF5StorageManager:
    """Handles high-performance 4D hypercube storage and state persistence."""
    
    def __init__(self, base_dir: str = "data/sessions"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def save_state(self, session_id: str, state: UnifiedState, raw_data: np.ndarray, tau_map: np.ndarray):
        """Saves the current physics state and data to an HDF5 container."""
        file_path = os.path.join(self.base_dir, f"{session_id}.h5")
        
        with h5py.File(file_path, 'w') as f:
            # Metadata as attributes
            f.attrs["session_id"] = session_id
            
            # Physics Config
            config_group = f.create_group("config")
            config_dict = state.config.model_dump()
            for key, val in config_dict.items():
                if isinstance(val, list):
                    config_group.create_dataset(key, data=np.array(val))
                else:
                    config_group.attrs[key] = val
            
            # 4D Hypercube [Y, X, T, C] - Assuming C=1 for now
            # We map back into [Y, X, T] if C is single
            if raw_data is not None:
                f.create_dataset("raw_data", data=raw_data, compression="gzip", chunks=True)
                
            # Analysis Results
            results_group = f.create_group("results")
            if tau_map is not None:
                results_group.create_dataset("tau_map", data=tau_map, compression="gzip")
                
            # Phasors (if state contains them)
            # Future: add G/S datasets here

    def load_state(self, session_id: str) -> Tuple[PhysicsConfig, np.ndarray, np.ndarray]:
        """Loads a state from an HDF5 container."""
        file_path = os.path.join(self.base_dir, f"{session_id}.h5")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Session {session_id} not found.")

        with h5py.File(file_path, 'r') as f:
            # Load Config
            config_dict = {}
            for key, val in f["config"].attrs.items():
                config_dict[key] = val
            for key in f["config"].keys():
                config_dict[key] = f["config"][key][:].tolist()
            
            config = PhysicsConfig(**config_dict)
            
            # Load Data
            raw_data = None
            if "raw_data" in f:
                raw_data = f["raw_data"][:]
                
            tau_map = None
            if "results/tau_map" in f:
                tau_map = f["results/tau_map"][:]
                
            return config, raw_data, tau_map

storage = HDF5StorageManager()
