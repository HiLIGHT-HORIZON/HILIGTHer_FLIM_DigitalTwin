import json
import os
import shutil
from copy import deepcopy
from typing import Any, Dict, List


_ROOT = os.path.dirname(os.path.dirname(__file__))
_STORE_DIR = os.path.join(_ROOT, "profiles", "batch_sweeps")
_INSTALL_PATH = os.path.join(_STORE_DIR, "defaults.install.json")
_CURRENT_PATH = os.path.join(_STORE_DIR, "defaults.current.json")


def _default_sweep_payload() -> Dict[str, Dict[str, Any]]:
    return {
        "laser_pulse_fwhm_ns": {
            "title": "Laser Pulse (FWHM, ns)",
            "values": [0.1, 0.2, 0.5],
        },
        "gate_edge_symmetric_ps": {
            "title": "Gate Rise/Fall Time (ps) - Symmetric Values",
            "values": [25, 50, 100],
        },
        "gate_edge_one_sharp_ps": {
            "title": "Gate Rise/Fall Time (ps) - One Fixed to Sharp Rise or Fall",
            "values": [25, 50, 100],
            "extra": {"mode": "Sharp Rise, Sweep Fall"},
        },
        "number_of_gates": {
            "title": "Number of Gates",
            "values": [2, 4, 8, 16],
        },
        "detector_jitter_ps": {
            "title": "Detector Jitter (ps)",
            "values": [0, 25, 50, 100, 150],
        },
        "deadtime_fixed_countrate_ns": {
            "title": "Detector Deadtime (ns)",
            "values": [0, 10, 25, 45, 90],
            "extra": {"count_rate_kcps": 100.0},
        },
        "multihit_capabilities": {
            "title": "Max events/period",
            "values": [1, 2, 4, 8],
        },
        "afterpulsing_probability_pct": {
            "title": "Afterpulsing Probability (%)",
            "values": [0, 0.5, 1.0, 2.0, 5.0],
        },
        "dark_count_rate_cps": {
            "title": "Detector Dark Count Rate (cps)",
            "values": [0, 100, 1000, 10000, 100000],
        },
        "instrument_profile": {
            "title": "Instrument Profiles",
            "values": ["HiLIGHT"],
        },
        "burst_edge_symmetric_ns": {
            "title": "Burst Rise/Fall Time (ns) - Symmetric Values",
            "values": [0.05, 0.1, 0.2],
        },
        "burst_edge_one_sharp_ns": {
            "title": "Burst Rise/Fall Time (ns) - One Fixed to Sharp Rise or Fall",
            "values": [0.05, 0.1, 0.2],
            "extra": {"mode": "Sharp Rise, Sweep Fall"},
        },
    }


class BatchSweepStore:
    """Persistence layer for batch-sweep default values."""

    def __init__(self):
        os.makedirs(_STORE_DIR, exist_ok=True)
        self._ensure_install_defaults()
        self._ensure_current_defaults()

    @property
    def install_path(self) -> str:
        return _INSTALL_PATH

    @property
    def current_path(self) -> str:
        return _CURRENT_PATH

    def _ensure_install_defaults(self) -> None:
        if not os.path.exists(_INSTALL_PATH):
            with open(_INSTALL_PATH, "w", encoding="utf-8") as handle:
                json.dump(_default_sweep_payload(), handle, indent=2)

    def _ensure_current_defaults(self) -> None:
        if not os.path.exists(_CURRENT_PATH):
            shutil.copyfile(_INSTALL_PATH, _CURRENT_PATH)

    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        defaults = _default_sweep_payload()
        merged = deepcopy(defaults)
        for key, default_spec in defaults.items():
            incoming = payload.get(key, {}) if isinstance(payload, dict) else {}
            if isinstance(incoming, dict):
                values = incoming.get("values", default_spec.get("values", []))
                if not isinstance(values, list):
                    values = default_spec.get("values", [])
                merged[key]["values"] = values
                extra_default = default_spec.get("extra")
                if extra_default is not None:
                    incoming_extra = incoming.get("extra", {})
                    if not isinstance(incoming_extra, dict):
                        incoming_extra = {}
                    merged[key]["extra"] = deepcopy(extra_default)
                    merged[key]["extra"].update(incoming_extra)
        return merged

    def _load_path(self, path: str) -> Dict[str, Dict[str, Any]]:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            payload = _default_sweep_payload()
        return self._sanitize_payload(payload)

    def load_current(self) -> Dict[str, Dict[str, Any]]:
        self._ensure_current_defaults()
        return self._load_path(_CURRENT_PATH)

    def save_current(self, payload: Dict[str, Any]) -> None:
        os.makedirs(_STORE_DIR, exist_ok=True)
        sanitized = self._sanitize_payload(payload)
        with open(_CURRENT_PATH, "w", encoding="utf-8") as handle:
            json.dump(sanitized, handle, indent=2)

    def import_file(self, source_path: str) -> Dict[str, Dict[str, Any]]:
        payload = self._load_path(source_path)
        self.save_current(payload)
        return payload

    def export_current(self, destination_path: str) -> None:
        self._ensure_current_defaults()
        shutil.copyfile(_CURRENT_PATH, destination_path)

    def reset_current(self) -> Dict[str, Dict[str, Any]]:
        shutil.copyfile(_INSTALL_PATH, _CURRENT_PATH)
        return self.load_current()
