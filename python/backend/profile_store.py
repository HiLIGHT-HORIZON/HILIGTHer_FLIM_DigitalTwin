import copy
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import PhysicsConfig


PROFILE_SCHEMA_VERSION = 2


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalise_profile_key(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("optimised", "optimized")
    return "".join(ch for ch in text if ch.isalnum())


def _simplified_profile_key(value: str) -> str:
    text = _normalise_profile_key(value)
    for token in ("ideal", "profile", "instrument"):
        text = text.replace(token, "")
    return text


def _profile_search_tokens(value: str) -> list[str]:
    raw = str(value or "").strip().lower()
    cleaned = "".join(ch if ch.isalnum() else " " for ch in raw)
    tokens = [token for token in cleaned.split() if token]
    drop = {"ideal", "profile", "instrument", "bins"}
    return [token for token in tokens if token not in drop]


class InstrumentProfileStore:
    """Versioned JSON storage for instrument profiles."""

    def __init__(self, profiles_dir: Optional[str] = None):
        base_dir = os.path.dirname(os.path.dirname(__file__))
        self.profiles_dir = profiles_dir or os.path.join(base_dir, "profiles", "instruments")
        os.makedirs(self.profiles_dir, exist_ok=True)

    def _profile_path(self, name: str) -> str:
        safe_name = "".join(c for c in str(name).strip() if c.isalnum() or c in (" ", ".", "_", "-")).strip()
        if not safe_name:
            raise ValueError("Profile name cannot be empty.")
        return os.path.join(self.profiles_dir, f"{safe_name}.json")

    def _find_profile_path_by_name(self, name: str) -> Optional[str]:
        wanted = str(name).strip()
        if not wanted:
            return None
        wanted_key = _normalise_profile_key(wanted)
        wanted_simple = _simplified_profile_key(wanted)
        wanted_tokens = _profile_search_tokens(wanted)
        best_partial_match: Optional[str] = None
        best_partial_score = -1
        for entry in self.list_profiles():
            entry_name = str(entry.get("name", "")).strip()
            entry_path = str(entry.get("path", "")).strip()
            entry_filename = os.path.splitext(os.path.basename(entry_path))[0]
            entry_tokens = set(_profile_search_tokens(entry_name) + _profile_search_tokens(entry_filename))
            if (
                entry_name == wanted
                or _normalise_profile_key(entry_name) == wanted_key
                or _normalise_profile_key(entry_filename) == wanted_key
                or _simplified_profile_key(entry_name) == wanted_simple
                or _simplified_profile_key(entry_filename) == wanted_simple
            ):
                return entry.get("path")
            if wanted_tokens:
                score = sum(1 for token in wanted_tokens if token in entry_tokens)
                if score > best_partial_score and score > 0:
                    best_partial_score = score
                    best_partial_match = entry.get("path")
        if best_partial_match and best_partial_score >= max(2, len(wanted_tokens) - 1):
            return best_partial_match
        candidate = self._profile_path(wanted)
        return candidate if os.path.exists(candidate) else None

    @staticmethod
    def _model_field_names() -> set[str]:
        fields = getattr(PhysicsConfig, "model_fields", None)
        if isinstance(fields, dict):
            return set(fields.keys())
        legacy_fields = getattr(PhysicsConfig, "__fields__", {})
        return set(legacy_fields.keys())

    def inspect_config_dict(self, config_dict: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        config_dict = dict(config_dict or {})
        field_names = self._model_field_names()
        keys = set(config_dict.keys())
        missing = sorted(field_names - keys)
        extra = sorted(keys - field_names)
        return {
            "missing": missing,
            "extra": extra,
            "has_issues": bool(missing or extra),
        }

    def sanitize_config_dict(self, config_dict: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        config_dict = dict(config_dict or {})
        defaults = PhysicsConfig()
        default_dict = defaults.model_dump() if hasattr(defaults, "model_dump") else defaults.dict()
        sanitized = {k: copy.deepcopy(v) for k, v in default_dict.items()}
        for key in self._model_field_names():
            if key in config_dict:
                sanitized[key] = copy.deepcopy(config_dict[key])
        return sanitized

    def _config_to_payload(self, name: str, config: PhysicsConfig, description: str = "", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config_dict = config.model_dump() if hasattr(config, "model_dump") else config.dict()
        timestamp = _utc_now()
        return {
            "schema_version": PROFILE_SCHEMA_VERSION,
            "profile_type": "instrument_definition",
            "name": str(name),
            "description": str(description or ""),
            "created_at": timestamp,
            "updated_at": timestamp,
            "metadata": copy.deepcopy(metadata or {}),
            "config": config_dict,
        }

    def _translate_legacy_payload(self, payload: Dict[str, Any], fallback_name: str) -> Dict[str, Any]:
        mapping = {
            "T": "period",
            "fwhm": "irf_fwhm",
            "profile": "irf_profile",
            "toff": "period",
            "rise_time": "irf_rise_time",
            "fall_time": "irf_fall_time",
            "bPulseTrain": "b_decay_wrapping",
            "PT_Trep": "period",
            "PT_sigma": "burst_sub_fwhm",
            "r": "expansion_ratio",
            "N_photons": "a_photons",
            "M": "n_repeats",
            "dt": "dt_input",
            "gate_widths": "gate_widths",
            "jitter": "timing_jitter",
            "deadtime": "detector_deadtime",
            "name": "label",
        }

        translated: Dict[str, Any] = {}
        for legacy_key, value in payload.items():
            if legacy_key == "gate_type" and isinstance(value, str):
                value_l = value.lower()
                translated["gate_type"] = "custom" if "custom" in value_l else "equal"
                continue
            if legacy_key not in mapping:
                continue
            translated[mapping[legacy_key]] = value.lower() if legacy_key == "profile" and isinstance(value, str) else value

        if translated.get("gate_widths"):
            edges = [0.0]
            for width in translated["gate_widths"]:
                edges.append(edges[-1] + float(width))
            translated["gate_edges"] = edges

        cfg = PhysicsConfig(**translated)
        if not cfg.label:
            cfg.label = fallback_name
        return self._config_to_payload(fallback_name, cfg, description="Imported legacy profile")

    def ensure_default_profiles(self) -> None:
        defaults = [
            (
                "HiLIGHT",
                PhysicsConfig(
                    label="HiLIGHT",
                    period=50.0,
                    irf_profile="rectangular",
                    irf_fwhm=5.0,
                    irf_position=0.0,
                    irf_rise_time=0.0,
                    irf_fall_time=0.0,
                    gate_type="custom",
                    gate_edges=[0.0, 5.485481831026995, 7.574726682497587, 14.705024114333674, 50.0],
                    a_photons=10000.0,
                    n_repeats=400,
                    dt_input=0.01,
                ),
                "HiLIGHT baseline gated configuration.",
            ),
            (
                "TCSPC (12.5ns - 128 bins)",
                PhysicsConfig(
                    label="TCSPC (12.5ns - 128 bins)",
                    period=12.5,
                    irf_profile="rectangular",
                    irf_fwhm=0.01,
                    irf_position=0.0,
                    irf_rise_time=0.0,
                    irf_fall_time=0.0,
                    gate_type="equal",
                    gate_edges=[float(x) for x in __import__("numpy").linspace(0.0, 12.5, 129)],
                    a_photons=10000.0,
                    dt_input=0.01,
                ),
                "Reference high-bin TCSPC profile.",
            ),
            (
                "TimeGating 4 bins - optimized",
                PhysicsConfig(
                    label="TimeGating 4 bins - optimized",
                    period=12.5,
                    irf_profile="rectangular",
                    irf_fwhm=0.01,
                    irf_position=0.0,
                    irf_rise_time=0.0,
                    irf_fall_time=0.0,
                    gate_type="custom",
                    gate_edges=[0.0, 1.2022312357422731, 2.7726435665102315, 9.413229722811986, 11.95848214166539],
                    a_photons=10000.0,
                    dt_input=0.01,
                ),
                "Four-gate optimized reference profile.",
            ),
        ]

        # Bootstrap defaults only when there are no profile JSON files at all.
        # This prevents deleted defaults from reappearing on every app restart.
        existing_profiles = self.list_profiles()
        if existing_profiles:
            return

        existing = {entry["name"] for entry in existing_profiles}
        for name, cfg, description in defaults:
            if name in existing:
                continue
            self.save_profile(name, cfg, description=description)

    def list_profiles(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for filename in sorted(os.listdir(self.profiles_dir)):
            if not filename.lower().endswith(".json"):
                continue
            path = os.path.join(self.profiles_dir, filename)
            try:
                payload = self.load_profile_payload(path)
                items.append(
                    {
                        "name": payload.get("name", os.path.splitext(filename)[0]),
                        "description": payload.get("description", ""),
                        "updated_at": payload.get("updated_at"),
                        "path": path,
                        "schema_version": int(payload.get("schema_version", 1)),
                    }
                )
            except Exception:
                continue
        return items

    def load_profile_payload(self, path_or_name: str) -> Dict[str, Any]:
        if os.path.isfile(path_or_name):
            path = path_or_name
        else:
            path = self._find_profile_path_by_name(path_or_name) or self._profile_path(path_or_name)
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if "config" not in payload:
            fallback_name = os.path.splitext(os.path.basename(path))[0]
            payload = self._translate_legacy_payload(payload, fallback_name)
        return payload

    def load_profile(self, path_or_name: str, sanitize: bool = True) -> Dict[str, Any]:
        payload = self.load_profile_payload(path_or_name)
        raw_config = dict(payload.get("config") or {})
        inspection = self.inspect_config_dict(raw_config)
        effective_config = self.sanitize_config_dict(raw_config) if sanitize else raw_config
        cfg = PhysicsConfig(**effective_config)
        return {"payload": payload, "config": cfg, "inspection": inspection}

    def save_profile(self, name: str, config: PhysicsConfig, description: str = "", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        path = self._profile_path(name)
        payload = self._config_to_payload(name, config, description=description, metadata=metadata)
        if os.path.exists(path):
            existing = self.load_profile_payload(path)
            payload["created_at"] = existing.get("created_at", payload["created_at"])
        payload["updated_at"] = _utc_now()
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return payload

    def rename_profile(self, old_name: str, new_name: str) -> Dict[str, Any]:
        source = self._find_profile_path_by_name(old_name) or self._profile_path(old_name)
        payload = self.load_profile_payload(source)
        payload["name"] = str(new_name)
        payload["updated_at"] = _utc_now()
        target = self._profile_path(new_name)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        if os.path.abspath(source) != os.path.abspath(target) and os.path.exists(source):
            os.remove(source)
        return payload

    def delete_profile(self, name: str) -> None:
        path = self._find_profile_path_by_name(name) or self._profile_path(name)
        if os.path.exists(path):
            os.remove(path)

    def export_profile(self, name: str, destination_path: str) -> Dict[str, Any]:
        payload = self.load_profile_payload(name)
        with open(destination_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return payload

    def repair_profile(self, path_or_name: str, destination_name: Optional[str] = None) -> Dict[str, Any]:
        payload = self.load_profile_payload(path_or_name)
        name = destination_name or payload.get("name") or os.path.splitext(os.path.basename(str(path_or_name)))[0]
        sanitized = self.sanitize_config_dict(payload.get("config"))
        cfg = PhysicsConfig(**sanitized)
        return self.save_profile(name, cfg, description=payload.get("description", ""), metadata=payload.get("metadata", {}))

    def import_profile(self, source_path: str, rename_to: Optional[str] = None) -> Dict[str, Any]:
        payload = self.load_profile_payload(source_path)
        name = rename_to or payload.get("name") or os.path.splitext(os.path.basename(source_path))[0]
        config = PhysicsConfig(**self.sanitize_config_dict(payload.get("config")))
        return self.save_profile(name, config, description=payload.get("description", ""), metadata=payload.get("metadata", {}))
