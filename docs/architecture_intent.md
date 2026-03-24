# Architecture Intent Map: HILIGHTer Digital Twin

## Product Intent
HILIGHTer is now a Python-first desktop engineering workspace for virtual FLIM instrument design, precision benchmarking, synthetic-image validation, and automation. The repository no longer carries active MATLAB application code. The desktop Qt workspace, backend service layer, HTTP API, MCP server, and export/reporting features all share one computational engine.

The core product goals are:

- configure virtual excitation, decay, detection, and gating models,
- compute numerical Fisher-information and relative-precision curves,
- validate those predictions with Monte Carlo simulation,
- generate synthetic validation images tied to the active sweep axis,
- fit and inspect those images through pixel, map, and phasor views,
- support optimisation workflows for detection gates and excitation profiles,
- preserve and restore complete workspaces and instrument profiles,
- expose the same functionality through Python, HTTP, desktop automation, and MCP surfaces.

The current product intent also includes:

- explicit separation of collected-photon conditional precision from photon survival,
- a fast Poisson core that can include a detector transfer function,
- a slower event-driven detector core used as the explicit chronological reference,
- structured MCP-assisted instrument-profile drafting and finalisation,
- publication-oriented clipboard/report export without changing the live widget layout.

## Sanitised Workspace Layout
The repository is organised around the active Python application:

- `python/`
  The application root. Contains the backend, GUI, launchers, profiles, tests, and utility scripts.
- `python/backend/`
  Shared numerical engine, storage, importers, schemas, and service orchestration.
- `python/gui/`
  Desktop Qt workspace and widgets.
- `python/profiles/instruments/`
  Versioned JSON instrument definitions and generators.
- `python/tools/`
  Developer and reporting utilities such as MCP smoke tests and benchmark-report replication helpers.
- `python/tests/`
  Automated Python validation for physics, controls, optimisation, and image-validation flows.
- `docs/`
  Architecture, manual, and engineering documentation.
- `resources/`
  Static supporting assets retained for reporting and project context.
- `tests/`
  Reserved top-level test area. After cleanup it should only contain non-MATLAB content.

There should be no active MATLAB source trees, `.m` launchers, or MATLAB project metadata in the main workspace.

## Architectural Principles

### 1. One Core Engine
All physics, fitting, phasor, optimisation, and storage logic should live in the Python backend once and be reused everywhere else.

### 2. Simulation-First
The main workflows are synthetic precision studies, validation-image studies, and instrument optimisation. File import remains a compatibility utility, not the product center.

### 3. Desktop-First, API-Complete
The Qt workspace is the primary operator experience, but every major workflow must remain scriptable through the service API, HTTP API, desktop automation API, and MCP server.

### 4. Workspace Persistence
Users should be able to save and load full workspaces, not only export plots. Instrument profiles, controller state, generated data, and derived maps must persist in a forward-compatible format.

## Layered Architecture

| Layer | Main Module | Intent |
| :--- | :--- | :--- |
| Physics Engine | `python/backend/twin_engine.py` | Excitation modelling, decay PDFs, gate distillation, Fisher estimation, Monte Carlo, validation-image generation, fitting, pixel payloads, and phasor products. |
| Shared Models | `python/backend/models.py` | Configuration and lightweight application state objects shared across the stack. |
| Decay Model Registry | `python/backend/decay_model_store.py` | Built-in and custom decay-model metadata, parameter definitions, sweep defaults, and persisted custom expressions. |
| Service Layer | `python/backend/service_api.py` | Stable workflow orchestration for scripts, tests, APIs, and automation. |
| Storage Layer | `python/backend/storage.py` | Workspace persistence and restoration. |
| Profile Store | `python/backend/profile_store.py` | Instrument profile load/save/import/export/migration helpers. |
| HTTP API | `python/backend/main.py` | Remote REST access to backend workflows and data products. |
| Desktop Workspace | `python/gui/main_window.py` and widgets | Controller-driven Qt application for simulation, validation, optimisation, and export. |
| Desktop Automation | `python/gui/automation_api.py` | Programmatic control of the live Qt workspace. |
| MCP Server | `python/mcp_server.py` | Tool/resource/prompt bridge for LLM hosts. |
| Documentation | `docs/` | Architecture, operator manual, API guidance, and benchmark notes. |

## Workflow Intent

### Precision Workflow
The precision workflow produces:

- ideal-reference precision curves,
- configured-instrument theory curves,
- optional Monte Carlo validation,
- optional bootstrap confidence intervals and estimator checks,
- conditional-F, survival, and photon-basis-aware reporting semantics,
- diagnostics payloads aligned to the same sweep axis,
- exportable HTML reports and CSV/SVG assets.

### Validation-Image Workflow
The validation-image workflow produces:

- synthetic gated images driven by the active sweep parameter,
- image geometry sized from sweep length and requested repeats,
- intensity and fitted-parameter maps,
- pixel-inspector payloads with decay, fit, residuals, IRF, and statistics,
- phasor products suitable for image-level inspection.

The desktop view preset for this workflow is:

- controller on the left,
- image validation, pixel inspector, and phasor space on the right.

### Optimisation Workflow
The optimisation workflow is integrated into the main desktop workspace. It should support:

- detection-gate optimisation,
- excitation-profile optimisation,
- sequential joint optimisation,
- live objective/minimum-F displays,
- retained intermediate states,
- optional post-run Monte Carlo validation,
- export of optimisation settings and outcomes.

## State Intent
The backend configuration object is the single source of truth for:

- decay-model settings,
- laser-profile and excitation settings,
- gate geometry and overlap semantics,
- detector event artefacts such as deadtime, dark counts, afterpulsing, and per-period capacity,
- Fisher-information photon-basis semantics, with collected-photon estimation as the canonical basis and optional rescaling to acquisition-period or full-budget references,
- sweep definitions,
- Monte Carlo and fitting settings,
- validation-image settings,
- optimisation settings,
- custom decay-model parameter values and sweep defaults,
- persistence metadata.

The GUI must mirror this state rather than maintaining a separate hidden model.

Batch-sweep default value sets are persisted as profile-style JSON data under `python/profiles/batch_sweeps/`. The installation snapshot in `defaults.install.json` is the immutable reset target, while `defaults.current.json` is the editable runtime copy used by the Batch Sweep tab for load, save, import, export, and reset operations.

## Testing Intent
The cleaned repository should be validated with:

- Python compile checks,
- backend and widget smoke tests,
- `pytest` coverage for physics, controls, optimisation, and validation images,
- MCP smoke testing from `python/tools/mcp_smoke_test.py`,
- offscreen Qt startup testing for the desktop workspace.

Benchmark comparisons against legacy reports can still exist as documentation or optional utility scripts, but they are not a separate application tier.

## Documentation Intent
The HTML manual should always describe the current Python workspace, including:

- repo layout and launch paths,
- the canonical multi-page manual rooted at `docs/manual/index.html`,
- the floating support browser opened by `Ctrl+H`,
- desktop workflow usage,
- the compact controller layout and simulation-core badge semantics,
- the current terminology for simulation cores: `Poisson`, `Poisson (+DTF)`, and `Event-driven`,
- the distinction between conditional precision and photon survival,
- the current clipboard-export workflow including export-only aspect/font/theme handling,
- the MCP-driven instrument-profile workflow using vendor sources, draft questions, and finalisation,
- workspace persistence,
- service, HTTP, automation, and MCP interfaces,
- optimisation scope and current limitations,
- test and smoke-check commands.
