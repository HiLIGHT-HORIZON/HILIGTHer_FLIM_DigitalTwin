import json

import numpy as np

from backend.models import PhysicsConfig
from backend.profile_store import InstrumentProfileStore
from backend.twin_engine import TwinEngine


def test_validation_geometry_matches_requested_banding_example():
    cfg = PhysicsConfig(f_x_steps=30, image_mc_repeats=200)
    engine = TwinEngine(cfg)

    geometry = engine.plan_validation_image_geometry()

    assert geometry["band_width"] == 3
    assert geometry["x_pixels"] == 90
    assert geometry["y_pixels"] == 70
    assert geometry["replicates_per_value"] == 210


def test_validation_image_generates_vertical_parameter_bands():
    cfg = PhysicsConfig(
        f_x_param="tau1",
        f_x_min=1.0,
        f_x_max=3.0,
        f_x_steps=4,
        f_x_scale="linear",
        image_mc_repeats=12,
        a_photons=500,
        threshold_min=0,
    )
    engine = TwinEngine(cfg)

    payload = engine.generate_validation_image()
    geometry = payload["geometry"]

    assert engine.raw_data.shape == (geometry["y_pixels"], geometry["x_pixels"], len(cfg.gate_edges) - 1)
    assert engine.validation_param_map.shape == engine.raw_data.shape[:2]

    first_row = engine.validation_param_map[0]
    for idx, x_val in enumerate(payload["x_values"]):
        start = idx * geometry["band_width"]
        end = start + geometry["band_width"]
        assert np.allclose(first_row[start:end], x_val)


def test_profile_store_round_trip_and_schema(tmp_path):
    store = InstrumentProfileStore(str(tmp_path))
    cfg = PhysicsConfig(label="RoundTrip", period=25.0, gate_edges=[0.0, 2.0, 5.0, 25.0])

    saved = store.save_profile("RoundTrip", cfg, description="test profile")
    loaded = store.load_profile("RoundTrip")

    assert saved["schema_version"] == 2
    assert loaded["payload"]["description"] == "test profile"
    assert loaded["config"].period == 25.0
    assert loaded["config"].gate_edges == [0.0, 2.0, 5.0, 25.0]

    exported_path = tmp_path / "exported_profile.json"
    store.export_profile("RoundTrip", str(exported_path))
    exported = json.loads(exported_path.read_text(encoding="utf-8"))
    assert exported["name"] == "RoundTrip"
    assert exported["config"]["period"] == 25.0
