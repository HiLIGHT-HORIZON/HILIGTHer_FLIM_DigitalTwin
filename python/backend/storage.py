import numpy as np
import os
import json
from typing import Dict, Any, Optional, Tuple
from .models import UnifiedState, PhysicsConfig

try:
    import h5py
except ImportError:  # pragma: no cover - depends on local environment
    h5py = None

class HDF5StorageManager:
    """Handles high-performance 4D hypercube storage and state persistence."""
    
    def __init__(self, base_dir: str = "data/sessions"):
        self.base_dir = base_dir
        try:
            os.makedirs(self.base_dir, exist_ok=True)
        except (FileNotFoundError, PermissionError, OSError) as e:
            # Fallback to user home if repository directory is not writable (e.g. OneDrive issues)
            fallback_dir = os.path.join(os.path.expanduser("~"), ".hilight", "sessions")
            print(f"Warning: Could not create session directory at {self.base_dir} ({e}).")
            print(f"Falling back to user-local storage: {fallback_dir}")
            try:
                os.makedirs(fallback_dir, exist_ok=True)
                self.base_dir = fallback_dir
            except Exception as e2:
                print(f"Critical: Could not create fallback storage at {fallback_dir} ({e2}).")
                # At this point, we just continue and let it fail later if they try to save

    def _require_h5py(self):
        if h5py is None:
            raise RuntimeError("Workspace/session persistence requires the 'h5py' package.")

    def save_state(self, session_id: str, state: UnifiedState, raw_data: np.ndarray, tau_map: np.ndarray):
        """Saves the current physics state and data to an HDF5 container."""
        self._require_h5py()
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

    def save_workspace(self, file_path: str, metadata: Dict[str, Any], arrays: Optional[Dict[str, Optional[np.ndarray]]] = None):
        """Save a full GUI/backend workspace with versioned JSON metadata plus numeric arrays."""
        self._require_h5py()
        arrays = arrays or {}
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)

        with h5py.File(file_path, "w") as handle:
            handle.attrs["schema_version"] = 2
            handle.create_dataset("metadata_json", data=np.bytes_(json.dumps(metadata)))
            arrays_group = handle.create_group("arrays")
            for key, value in arrays.items():
                if value is None:
                    continue
                arrays_group.create_dataset(key, data=np.asarray(value), compression="gzip")

    def load_workspace(self, file_path: str) -> Tuple[Dict[str, Any], Dict[str, np.ndarray]]:
        """Load a previously saved workspace container."""
        self._require_h5py()
        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)

        with h5py.File(file_path, "r") as handle:
            metadata_raw = handle["metadata_json"][()]
            if isinstance(metadata_raw, bytes):
                metadata_raw = metadata_raw.decode("utf-8")
            metadata = json.loads(metadata_raw)
            arrays = {}
            if "arrays" in handle:
                for key, dataset in handle["arrays"].items():
                    arrays[key] = dataset[()]
            return metadata, arrays

    def load_state(self, session_id: str) -> Tuple[PhysicsConfig, np.ndarray, np.ndarray]:
        """Loads a state from an HDF5 container."""
        self._require_h5py()
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
