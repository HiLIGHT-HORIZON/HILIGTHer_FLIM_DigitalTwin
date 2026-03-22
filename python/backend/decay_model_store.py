import json
import math
import os
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional

import numpy as np

from .models import PhysicsConfig


_ROOT = os.path.dirname(os.path.dirname(__file__))
_STORE_DIR = os.path.join(_ROOT, "profiles", "decay_models")
_STORE_PATH = os.path.join(_STORE_DIR, "custom_models.json")


def _built_in_models() -> Dict[str, Dict[str, Any]]:
    return {
        "exponential": {
            "key": "exponential",
            "name": "Exponential",
            "built_in": True,
            "supports_components": True,
            "description_plain": "One or two exponential fluorescence decays mixed by amplitude.",
            "description_specialist": "The latent fluorescence is a sum of exponentials convolved with the laser profile and detector transfer model.",
            "equation_html": "I(t)=\\sum_i a_i e^{-t/\\tau_i}",
            "parameters": [
                {
                    "name": "tau1",
                    "label": "Tau 1",
                    "unit": "ns",
                    "default": 2.5,
                    "sweep_min": 0.2,
                    "sweep_max": 8.0,
                    "sweep_steps": 30,
                    "scale": "log",
                    "bounds_min": 1e-6,
                    "bounds_max": None,
                    "description": "Primary fluorescence lifetime.",
                },
                {
                    "name": "tau2",
                    "label": "Tau 2",
                    "unit": "ns",
                    "default": 1.0,
                    "sweep_min": 0.2,
                    "sweep_max": 8.0,
                    "sweep_steps": 30,
                    "scale": "log",
                    "bounds_min": 1e-6,
                    "bounds_max": None,
                    "description": "Secondary fluorescence lifetime used when two components are enabled.",
                },
                {
                    "name": "alpha",
                    "label": "Alpha 1",
                    "unit": "fraction",
                    "default": 0.5,
                    "sweep_min": 0.05,
                    "sweep_max": 0.95,
                    "sweep_steps": 20,
                    "scale": "linear",
                    "bounds_min": 0.0,
                    "bounds_max": 1.0,
                    "description": "Fractional weight of the first component in a bi-exponential model.",
                },
            ],
        },
        "stretched": {
            "key": "stretched",
            "name": "Stretched",
            "built_in": True,
            "supports_components": False,
            "description_plain": "A stretched exponential for heterogeneous decays.",
            "description_specialist": "Kohlrausch-Williams-Watts decay with lifetime tau1 and stretch factor beta.",
            "equation_html": "I(t)=e^{-(t/\\tau_1)^\\beta}",
            "parameters": [
                {
                    "name": "tau1",
                    "label": "Tau 1",
                    "unit": "ns",
                    "default": 2.5,
                    "sweep_min": 0.2,
                    "sweep_max": 8.0,
                    "sweep_steps": 30,
                    "scale": "log",
                    "bounds_min": 1e-6,
                    "bounds_max": None,
                    "description": "Characteristic stretched lifetime.",
                },
                {
                    "name": "beta",
                    "label": "Beta",
                    "unit": "",
                    "default": 1.0,
                    "sweep_min": 0.3,
                    "sweep_max": 1.5,
                    "sweep_steps": 24,
                    "scale": "linear",
                    "bounds_min": 1e-6,
                    "bounds_max": 3.0,
                    "description": "Stretching factor. Beta=1 is a single exponential.",
                },
            ],
        },
    }


_ALLOWED_PARAM_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DecayModelStore:
    """Registry and persistence for hardcoded and custom decay models."""

    def __init__(self):
        self._builtins = _built_in_models()
        self._custom = self._load_custom_models()

    def _load_custom_models(self) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(_STORE_PATH):
            return {}
        try:
            with open(_STORE_PATH, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}
        models = payload.get("models", {}) if isinstance(payload, dict) else {}
        cleaned = {}
        for key, definition in models.items():
            if isinstance(definition, dict):
                model = deepcopy(definition)
                model["key"] = str(model.get("key") or key)
                model["name"] = str(model.get("name") or key)
                model["built_in"] = False
                cleaned[model["key"]] = model
        return cleaned

    def save(self) -> None:
        os.makedirs(_STORE_DIR, exist_ok=True)
        with open(_STORE_PATH, "w", encoding="utf-8") as handle:
            json.dump({"models": self._custom}, handle, indent=2)

    def all_models(self) -> List[Dict[str, Any]]:
        merged = list(self._builtins.values()) + list(self._custom.values())
        return [deepcopy(item) for item in merged]

    def get(self, key: str) -> Dict[str, Any]:
        key_norm = str(key or "exponential").strip()
        if key_norm in self._builtins:
            return deepcopy(self._builtins[key_norm])
        if key_norm in self._custom:
            return deepcopy(self._custom[key_norm])
        return deepcopy(self._builtins["exponential"])

    def upsert_custom_model(self, definition: Dict[str, Any], previous_key: Optional[str] = None) -> Dict[str, Any]:
        key = str(definition.get("key") or "").strip()
        if not key:
            raise ValueError("Custom model key is required.")
        if not _ALLOWED_PARAM_RE.match(key):
            raise ValueError("Model key must use letters, digits, and underscores only.")
        if key in self._builtins:
            raise ValueError("Built-in model keys cannot be overwritten.")
        parameters = definition.get("parameters") or []
        if not parameters:
            raise ValueError("Custom models require at least one parameter.")
        for param in parameters:
            name = str(param.get("name") or "").strip()
            if not _ALLOWED_PARAM_RE.match(name):
                raise ValueError(f"Invalid parameter name: {name!r}")
        expression = str(definition.get("expression") or "").strip()
        if not expression:
            raise ValueError("Custom models require an expression.")
        model = deepcopy(definition)
        model["key"] = key
        model["name"] = str(model.get("name") or key)
        model["built_in"] = False
        if previous_key and previous_key in self._custom and previous_key != key:
            self._custom.pop(previous_key, None)
        self._custom[key] = model
        self.save()
        return deepcopy(model)

    def delete_custom_model(self, key: str) -> None:
        self._custom.pop(str(key), None)
        self.save()

    def duplicate_custom_model(self, key: str, new_key: str, new_name: Optional[str] = None) -> Dict[str, Any]:
        source = self.get(key)
        if source.get("built_in"):
            source["built_in"] = False
        source["key"] = new_key
        source["name"] = new_name or new_key
        return self.upsert_custom_model(source)

    def export_model(self, key: str) -> str:
        return json.dumps(self.get(key), indent=2)

    def import_model(self, text: str) -> Dict[str, Any]:
        payload = json.loads(text)
        return self.upsert_custom_model(payload)

    def runtime_param_defs(self, cfg: PhysicsConfig) -> List[Dict[str, Any]]:
        model = self.get(getattr(cfg, "decay_model", "exponential"))
        defs = []
        for item in model.get("parameters", []):
            include = True
            if model["key"] == "exponential" and item["name"] in {"tau2", "alpha"}:
                include = int(getattr(cfg, "n_components", 1)) > 1
            if include:
                defs.append(self._apply_sweep_override(cfg, model["key"], item))
        defs.append(
            self._apply_sweep_override(
                cfg,
                model["key"],
                {
                    "name": "background",
                    "label": "Background",
                    "unit": "%",
                    "default": float(getattr(cfg, "background_level", 0.0)) * 100.0,
                    "sweep_min": 0.0,
                    "sweep_max": 0.5,
                    "sweep_steps": 20,
                    "scale": "linear",
                    "bounds_min": 0.0,
                    "bounds_max": 100.0,
                    "description": "Background as a fraction of the total decay, expressed in percent.",
                },
            )
        )
        return defs

    def _apply_sweep_override(self, cfg: PhysicsConfig, model_key: str, definition: Dict[str, Any]) -> Dict[str, Any]:
        item = deepcopy(definition)
        overrides = deepcopy(getattr(cfg, "decay_model_sweep_defaults", {}) or {})
        model_overrides = overrides.get(model_key, {}) if isinstance(overrides, dict) else {}
        param_override = model_overrides.get(item["name"], {}) if isinstance(model_overrides, dict) else {}
        for key in ("sweep_min", "sweep_max", "sweep_steps", "scale"):
            if key in param_override:
                item[key] = param_override[key]
        return item

    def set_sweep_override(
        self,
        cfg: PhysicsConfig,
        model_key: str,
        param_name: str,
        *,
        sweep_min: float,
        sweep_max: float,
        sweep_steps: int,
        scale: str,
    ) -> None:
        all_overrides = deepcopy(getattr(cfg, "decay_model_sweep_defaults", {}) or {})
        model_overrides = deepcopy(all_overrides.get(model_key, {}))
        model_overrides[param_name] = {
            "sweep_min": float(sweep_min),
            "sweep_max": float(sweep_max),
            "sweep_steps": int(sweep_steps),
            "scale": str(scale).lower(),
        }
        all_overrides[model_key] = model_overrides
        cfg.decay_model_sweep_defaults = all_overrides


def evaluate_decay_curve(cfg: PhysicsConfig, t: np.ndarray, model_def: Optional[Dict[str, Any]] = None) -> np.ndarray:
    """Evaluate the latent fluorescence decay before background and IRF convolution."""
    model_store = DecayModelStore()
    model = model_def or model_store.get(getattr(cfg, "decay_model", "exponential"))
    key = str(model.get("key", "exponential"))
    t_nonneg = np.maximum(np.asarray(t, dtype=float), 0.0)
    if key == "exponential":
        decay = np.zeros_like(t_nonneg, dtype=float)
        n_components = max(int(getattr(cfg, "n_components", 1)), 1)
        taus = list(getattr(cfg, "taus", [2.5, 1.0]) or [2.5, 1.0])
        if n_components <= 1:
            decay = np.exp(-t_nonneg / max(float(taus[0]), 1e-6))
        else:
            tau1 = max(float(taus[0]), 1e-6)
            tau2 = max(float(taus[1] if len(taus) > 1 else taus[0]), 1e-6)
            alpha = float((getattr(cfg, "amplitudes", [0.5]) or [0.5])[0])
            alpha = min(max(alpha, 0.0), 1.0)
            decay = alpha * np.exp(-t_nonneg / tau1) + (1.0 - alpha) * np.exp(-t_nonneg / tau2)
        return np.maximum(decay, 0.0)
    if key == "stretched":
        tau1 = max(float((getattr(cfg, "taus", [2.5]) or [2.5])[0]), 1e-6)
        beta = max(float(getattr(cfg, "beta", 1.0)), 1e-6)
        return np.maximum(np.exp(-((t_nonneg / tau1) ** beta)), 0.0)

    values = dict(getattr(cfg, "custom_model_params", {}) or {})
    safe_env = {
        "np": np,
        "math": math,
        "t": t_nonneg,
        "exp": np.exp,
        "log": np.log,
        "sqrt": np.sqrt,
        "sin": np.sin,
        "cos": np.cos,
        "where": np.where,
        "maximum": np.maximum,
        "minimum": np.minimum,
        "clip": np.clip,
        "power": np.power,
        "abs": np.abs,
    }
    safe_env.update(values)
    expression = str(model.get("expression") or "np.exp(-t / 2.5)")
    decay = eval(expression, {"__builtins__": {}}, safe_env)  # noqa: S307 - controlled editor input
    decay = np.asarray(decay, dtype=float)
    if decay.shape != t_nonneg.shape:
        decay = np.broadcast_to(decay, t_nonneg.shape).astype(float)
    decay = np.nan_to_num(decay, nan=0.0, posinf=0.0, neginf=0.0)
    return np.maximum(decay, 0.0)
