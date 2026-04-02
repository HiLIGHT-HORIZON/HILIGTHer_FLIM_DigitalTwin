# HILIGHTer Digital Twin

HILIGHTer is a Python-first FLIM engineering workspace. The main product is a Qt desktop application backed by a shared numerical engine, with additional HTTP, Python, desktop-automation, MCP (Model Context Protocol), and browser-frontend surfaces.

## What You Get

- A desktop workspace for:
  - decay, excitation, detection, and gating design
  - Fisher-information precision studies
  - Monte Carlo image validation
  - gate and excitation optimisation
  - HTML/SVG/CSV reporting
- A shared backend used by:
  - the desktop app
  - Python scripts
  - the FastAPI service
  - the MCP server

## Requirements

For the smoothest desktop install:

- Windows 10 or 11
- Python 3.10
- `pip`

The desktop app also needs Qt/WebEngine dependencies, which are installed from `python/desktop_requirements.txt`.

The desktop launcher installs missing desktop dependencies into the active Python environment on first run. Using a dedicated virtual environment is strongly recommended.

## Quick Start

1. Clone this repository.
2. Open a terminal in the repository root.
3. Optional but recommended: create and activate a virtual environment.
4. Launch the desktop app:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

```powershell
python -m pip install --upgrade pip
run_desktop.bat
```

If you prefer to preinstall desktop dependencies instead of letting the launcher do it:

```powershell
python -m pip install -r python\desktop_requirements.txt
run_desktop.bat
```

What happens on first launch:

- the launcher switches into `python/`
- it starts `desktop_app.py`
- the desktop bootstrap checks whether required Qt and scientific modules are importable
- if modules are missing, it installs them from `python/desktop_requirements.txt`
- it then opens the Qt workspace

If the first launch needs to install packages, it can take a while.

## Installation Profiles

### Desktop-only install

Use this when you only need the main Qt application.

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r python\desktop_requirements.txt
run_desktop.bat
```

### Backend and API install

Use this when you want the FastAPI backend, scripts, or test toolchain without the full desktop stack.

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r python\requirements.txt
```

### Full local development install

Use this when you want the desktop app, backend/API tooling, and the browser frontend.

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r python\desktop_requirements.txt
python -m pip install -r python\requirements.txt
cd python\frontend
npm install
cd ..\..
run_desktop.bat
```

## Desktop Launch

Primary launcher:

```powershell
run_desktop.bat
```

Direct launcher:

```powershell
cd python
python desktop_app.py
```

The desktop manual is available from inside the app with `Ctrl+H`.

## HTTP API

From the repository root:

```powershell
python -m uvicorn python.backend.main:app --reload
```

Useful endpoints:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/openapi.json`
- `http://127.0.0.1:8000/api/v1/backend/status`

If you want the browser frontend as well:

```powershell
cd python\frontend
npm run dev
```

The current frontend targets `http://localhost:8000` and still uses a small set of compatibility routes in addition to the `/api/v1/...` endpoints.

## MCP Server

The MCP server lives at:

- `python/mcp_server.py`

It is a stdio server intended to be launched by an MCP host, not by opening it in a browser.

Smoke test:

```powershell
python python\tools\mcp_smoke_test.py
```

## Repository Layout

- `python/`
  - active application code, launchers, profiles, tests, and tools
- `python/backend/`
  - shared physics engine, service layer, storage, API logic
- `python/gui/`
  - Qt desktop workspace and widgets
- `python/frontend/`
  - React/Vite browser client backed by the HTTP API
- `python/profiles/instruments/`
  - saved and generated instrument JSON profiles
- `python/tests/`
  - automated tests
- `python/tools/`
  - smoke tests and developer utilities
- `python/tools/dev/`
  - local helper scripts kept outside the supported runtime path
- `docs/`
  - architecture notes and the main HTML manual
- `resources/`
  - supporting project files and reference material

The repository no longer includes active MATLAB application code. The maintained runtime lives under `python/`.

## Useful Commands

Syntax check:

```powershell
python -m py_compile python\desktop_app.py python\gui\main_window.py python\backend\*.py
```

Run tests:

```powershell
pytest python/tests
```

Run only the event-driven backend tests:

```powershell
pytest python/tests/test_event_driven.py
```

MCP smoke test:

```powershell
python python\tools\mcp_smoke_test.py
```

## Installation Troubleshooting

### The desktop app crashes during dependency import

Make sure the desktop environment matches the pinned requirements:

- `numpy<2`
- `matplotlib<3.9`

The current requirements files already pin those versions.

## Versioning

The single source of truth for the project version is:

- `python/metadata.py`

Policy:

- `x.y.z` is the product version.
- `x` changes only when explicitly directed by the project lead.
- `y` changes when a milestone is reached.
- `z` is derived from the git build count relative to the current milestone baseline.
- `build` is the total git commit count for the repository.

### `run_desktop.bat` keeps installing packages

That usually means the current Python environment is missing one or more required desktop modules. Creating a dedicated virtual environment usually fixes this.

### `uvicorn` or FastAPI imports fail

Install the backend requirements into the same environment:

```powershell
python -m pip install -r python\requirements.txt
```

### The browser frontend cannot talk to the backend

Make sure both services are running from the repository root:

```powershell
python -m uvicorn python.backend.main:app --reload
cd python\frontend
npm run dev
```

The frontend currently expects the backend at `http://localhost:8000`.

### The app starts but feels slow

Possible causes:

- first launch after dependency installation
- large Monte Carlo repeat counts
- event-driven detector core

The event-driven core is slower than the ideal Poisson core. Use modest image sizes and repeat counts when testing event-driven detector effects.

## Notes For Detector/Event-Driven Users

- The default workflow remains the legacy ideal-Poisson core.
- Detector event effects can also be approximated on the Poisson core through the detector-transfer model.
- The event-driven core is available when you need explicit chronological detector physics, but it is slower.

## Documentation

Main operator manual:

- [docs/manual/index.html](docs/manual/index.html)

Architecture notes:

- [docs/architecture_intent.md](docs/architecture_intent.md)

Module overview:

- [docs/manual/assets/module-overview.svg](docs/manual/assets/module-overview.svg)

Optimisation notes:

- [docs/optimization_strategy.md](docs/optimization_strategy.md)

## Engineering Notes

This package originated as a MATLAB-to-Python port, but the active workspace is now fully Python-based. Some parity tests, replication reports, and compatibility shims still reference the earlier MATLAB baseline because they are validation artifacts rather than runtime dependencies.

We have used CODEX extensively for porting, improving the GUI, and adding many features. The users are expected to verify the results also with known cases and eventually measurements. However, here are the steps we implement for quality assurance:

- The Fisher Information analysis is based on two independent techniques.
  
  1) Numerical estimation of derivatives. The instrument samples the probability density function, and the derivatives of the resulting histograms are evaluated numerically. These numerical estimations are fast and used to evaluate Fisher Information.
  2) To ensure the numerical estimations are accurate, and also to introduce a secondary way to verify that agents did not introduce artefacts into the numerical estimations of FI, HILIGHTer verifies results with independent Monte Carlo simulations.
 
- Agent-based verification. When we introduce new features, agents are asked to run independent diagnostic tests
  
- Human-in-the-loop. All modules are periodically audited to ensure the Digital Twin remains grounded in the correct physics and maths.
  
Current status of auditing. We are proceeding with a new auditing cycle. At its completion, we will release the first beta version. However, the alpha version is currently already stable and publicly shared. It behaves correctly but we want to implement a final manual audit.
