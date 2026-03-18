# Architecture Intent Map: HILIGHTer Digital Twin

## Product Intent
The Python Digital Twin is the main engineering platform for the project. It is no longer framed as a full experimental-data analysis clone of the MATLAB application. Its primary purpose is to model and benchmark virtual FLIM instruments, quantify estimator performance, and expose that capability through stable software interfaces.

The core product goals are:

- Numerical Fisher Information and CRLB estimation.
- Monte Carlo validation of those precision estimates.
- Bootstrap-based estimator-accuracy testing and confidence intervals.
- Rich virtual-instrument configuration across excitation, detection, gating, and acquisition parameters.
- Synthetic image generation and testing workflows.
- API-first interoperability for other software and LLM agents through Python APIs, HTTP APIs, and MCP.

## Architectural Principles

### 1. Simulation-First
The Digital Twin is built around synthetic acquisition, not experimental import. Simulation, precision analysis, and diagnostics are the primary workflows.

Experimental import endpoints may still exist as compatibility utilities, but they are not the central product scope and should not drive the architecture.

### 2. Precision-First
The main benchmark is estimator quality under a configurable virtual instrument.

This means the platform must support:

- ideal-reference precision curves,
- numerical Fisher / F-value curves under non-ideal instrumentation,
- Monte Carlo validation against the same sweep,
- bootstrap p-value testing for estimator accuracy,
- bootstrap confidence intervals for Monte Carlo precision metrics.

### 3. API-First
All major functionality should be reachable without manual GUI interaction.

The intended control surfaces are:

- shared Python service API for application and workflow integration,
- FastAPI HTTP surface for remote or web-driven use,
- desktop automation API for in-process control of the live Qt workspace,
- MCP server for LLM tooling, data access, and prompt injection.

### 4. One Core Engine, Many Frontends
Physics logic should live once in the backend engine and be reused by every interface. The GUI, HTTP API, reports, tests, and MCP server should all depend on the same computational implementation rather than duplicating model logic.

## Layered Architecture

| Layer | Main Module | Intent |
| :--- | :--- | :--- |
| Physics Engine | `python/backend/twin_engine.py` | Time-domain excitation, decay PDFs, gate distillation, Fisher estimation, gridded MLE, Monte Carlo workflows, bootstrap statistics, diagnostics, synthetic image generation. |
| Shared State Models | `python/backend/models.py` | Validated configuration and state objects used across the backend and desktop. |
| Service Layer | `python/backend/service_api.py` | Stable orchestration surface for workflows, data access, configuration changes, diagnostics, and sessions. |
| HTTP API | `python/backend/main.py` | Remote programmatic access to the shared service layer. |
| Desktop Workspace | `python/gui/main_window.py` and widgets | Interactive engineering environment for precision, diagnostics, image simulation, and plot inspection. |
| Desktop Automation | `python/gui/automation_api.py` | In-process control of the live desktop, including controller state and plot payload access. |
| MCP Server | `python/mcp_server.py` | Stdio MCP bridge exposing tools, resources, and prompts to LLM hosts. |
| Documentation and Reports | `docs/` and HTML exporters | Human-readable manuals, parity reports, and precision-session outputs. |

## State Model Intent
The validated configuration object is the single source of truth for simulation and precision workflows.

Important state categories include:

- decay model and component parameters,
- excitation model, width, timing, rise/fall behavior, burst settings,
- detection and gate geometry,
- sweep definitions for parameter studies,
- precision execution settings such as photon budget, Monte Carlo repeats, bootstrap samples, CI level, and estimator-accuracy threshold,
- plotting and reporting options used by the desktop workspace and exports.

The GUI must synchronize to this model rather than holding independent hidden state.

## Workflow Intent

### Precision Workflow
The precision workflow is the main engineering benchmark loop.

Expected outputs:

- ideal Fisher reference,
- theory curve for the configured instrument,
- optional Monte Carlo validation,
- optional bootstrap confidence intervals,
- compatibility statistics for estimator-accuracy checks,
- diagnostics frames for the swept configurations,
- exportable HTML report.

### Synthetic Image Workflow
The synthetic image workflow exists to test estimators and visualization paths on simulated datasets produced by the same instrument model.

Expected outputs:

- synthetic gated data,
- fit maps,
- phasor products,
- pixel-level inspection payloads,
- data summaries for software integration.

## MCP and LLM Intent
The MCP server is intended to let external LLM systems use the Digital Twin as a structured reasoning backend.

MCP should expose:

- configuration inspection and mutation,
- workflow execution,
- precision and diagnostics access,
- data and result snapshots,
- GUI schema metadata so an LLM can reference the desktop consistently,
- reusable prompts that encode good operating patterns.

The MCP layer currently targets backend and workspace-schema access. Live Qt widget driving remains the responsibility of the in-process desktop automation API unless a future dedicated desktop MCP bridge is introduced.

## Documentation Intent
The HTML manual must stay synchronized with the actual implementation and cover:

- product scope,
- architecture,
- shared service API,
- HTTP API,
- desktop automation API,
- MCP tools, resources, and prompts,
- setup instructions for supported LLM hosts,
- current scope limits and compatibility notes.

## Validation Intent
The Python Digital Twin should be validated against:

- focused backend tests,
- parity checks against known MATLAB or report benchmarks where applicable,
- smoke tests of the MCP server,
- interactive validation in the Qt workspace for plotting, legends, and diagnostics.

Parity with MATLAB is important for core physics and benchmark trends, but the Python product is intentionally narrower in scope and more integration-oriented.
