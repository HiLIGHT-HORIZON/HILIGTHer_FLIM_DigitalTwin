from typing import Any, Dict

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .service_api import DigitalTwinService


app = FastAPI(
    title="HILIGHTer Digital Twin API",
    version="1.1.0",
    description="Programmatic backend, data, workflow, optimisation, and GUI-schema APIs for the HILIGHTer Digital Twin.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

service = DigitalTwinService()


class ConfigPatchRequest(BaseModel):
    config_patch: Dict[str, Any] = Field(default_factory=dict)


class SimulationRequest(BaseModel):
    a: float = 2000.0
    tau1: float = 1.0
    tau2: float = 5.0
    b: float = 10.0
    res: int = 64
    fit_method: str = "gridded_mle"


class PrecisionRequest(BaseModel):
    config_patch: Dict[str, Any] = Field(default_factory=dict)


@app.get("/")
async def root():
    return {
        "message": "HILIGHTer Digital Twin API is active",
        "docs": {
            "openapi": "/openapi.json",
            "backend_status": "/api/v1/backend/status",
            "manual": "See docs/digital_twin_manual.html for the full API and MCP reference.",
        },
    }


@app.get("/api/v1/backend/status")
async def get_backend_status():
    return service.get_status()


@app.get("/api/v1/backend/config")
async def get_backend_config():
    return service.get_config()


@app.post("/api/v1/backend/config")
async def patch_backend_config(req: ConfigPatchRequest):
    return service.update_config(req.config_patch)


@app.get("/api/v1/backend/gui/schema")
async def get_backend_gui_schema():
    return service.get_gui_schema()


@app.post("/api/v1/workflows/simulate/basic")
async def run_basic_simulation(req: SimulationRequest):
    return service.simulate_basic(req.model_dump())


@app.post("/api/v1/workflows/simulate/advanced")
async def run_advanced_simulation(req: SimulationRequest):
    return service.simulate_advanced(req.model_dump())


@app.post("/api/v1/workflows/precision")
async def run_precision_workflow(req: PrecisionRequest):
    return service.run_precision(req.config_patch)


@app.post("/api/v1/workflows/optimisation")
async def run_optimisation_workflow(req: PrecisionRequest):
    return service.run_optimization(req.config_patch)


@app.get("/api/v1/data/summary")
async def get_data_summary():
    return service.get_data_summary()


@app.get("/api/v1/data/results")
async def get_results_snapshot():
    return service.get_results_snapshot()


@app.get("/api/v1/data/tau-map")
async def get_tau_map():
    return service.get_tau_map()


@app.get("/api/v1/data/phasor")
async def get_phasor_map(harmonic: int = 1):
    return service.get_phasor_map(harmonic=harmonic)


@app.get("/api/v1/data/pixel/{y}/{x}")
async def get_pixel_analysis(y: int, x: int):
    return service.get_pixel_analysis(y, x)


@app.get("/api/v1/data/diagnostics")
async def get_diagnostics_snapshot(tau_ref: float | None = None):
    return service.get_diagnostics_snapshot(tau_ref=tau_ref)


@app.get("/api/v1/theory/locus")
async def get_theory_locus():
    return service.get_theoretical_locus()


@app.post("/api/v1/data/import/sdt")
async def import_sdt_upload(file: UploadFile = File(...)):
    payload = await file.read()
    try:
        return service.import_sdt_bytes(file.filename, payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SDT import failed: {exc}") from exc


@app.post("/api/v1/session/save/{session_id}")
async def save_session(session_id: str):
    result = service.save_session(session_id)
    if result["status"] == "no_data":
        raise HTTPException(status_code=404, detail="No data to save.")
    return result


@app.post("/api/v1/session/load/{session_id}")
async def load_session(session_id: str):
    try:
        return service.load_session(session_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# Legacy compatibility aliases
@app.post("/simulate")
async def legacy_simulate(req: SimulationRequest):
    return service.simulate_basic(req.model_dump())


@app.post("/simulate/advanced")
async def legacy_simulate_advanced(req: SimulationRequest):
    return service.simulate_advanced(req.model_dump())


@app.get("/results/fisher/{n_photons}")
async def legacy_fisher(n_photons: int):
    payload = service.run_precision({"precision_photons": n_photons, "precision_validate_mc": False})
    return {
        "tau": payload["x_range"],
        "fisher_info": payload["theory"]["fisher_info"],
        "f_value": payload["theory"]["f_value"],
    }
