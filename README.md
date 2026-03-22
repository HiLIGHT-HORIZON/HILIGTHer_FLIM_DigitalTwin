# HILIGHTer Digital Twin

HILIGHTer is a Python-first FLIM engineering workspace. The main product is a Qt desktop application backed by a shared numerical engine, with additional HTTP, Python, desktop-automation, and MCP surfaces.

This repository no longer depends on a MATLAB app runtime for normal use.

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

## Quick Start For New Users

1. Clone this repository.
2. Open a terminal in the repository root.
3. Launch the desktop app:

```powershell
python\run_desktop.bat
```

What happens on first launch:

- the launcher switches into `python/`
- it checks whether the required desktop modules are already available
- if modules are missing, it installs them from `python/desktop_requirements.txt`
- it then starts the native Qt workspace

If the first launch needs to install packages, it can take a while.

## Recommended Clean Install

Using a virtual environment is strongly recommended.

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r python\desktop_requirements.txt
python\run_desktop.bat
```

If you also want the non-desktop backend/API toolchain:

```powershell
python -m pip install -r python\requirements.txt
```

## Desktop Launch

Primary launcher:

```powershell
python\run_desktop.bat
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
  - active application code, launchers, tests, profiles, and tools
- `python/backend/`
  - shared physics engine, service layer, storage, API logic
- `python/gui/`
  - Qt desktop workspace and widgets
- `python/profiles/instruments/`
  - saved and generated instrument JSON profiles
- `python/tests/`
  - automated tests
- `python/tools/`
  - smoke tests and developer utilities
- `docs/`
  - architecture notes and the main HTML manual
- `resources/`
  - supporting project files and reference material

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

### `run_desktop.bat` keeps installing packages

That usually means the current Python environment is missing one or more required desktop modules. Creating a dedicated virtual environment usually fixes this.

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

Optimisation notes:

- [docs/optimization_strategy.md](docs/optimization_strategy.md)
