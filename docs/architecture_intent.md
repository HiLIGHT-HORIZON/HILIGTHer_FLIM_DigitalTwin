# Architecture Intent Map: HILIGHTer Digital Twin

## Product Intent
The Python Digital Twin is the main engineering platform for the project. It is no longer framed as a full experimental-data analysis clone of the MATLAB application. Its primary purpose is to model and benchmark virtual FLIM instruments, quantify estimator performance, and expose that capability through stable software interfaces.

The core product goals are:

- Numerical Fisher Information and CRLB estimation.
- Monte Carlo validation of those precision estimates.
- Bootstrap-based estimator-accuracy testing and confidence intervals.
- Rich virtual-instrument configuration across excitation, detection, gating, and acquisition parameters.
- Synthetic image generation and testing workflows.
- Validation-image workspaces with synthetic banded images driven by the same X-axis parameter used for precision sweeps.
- Controller-driven optimisation integrated directly into the desktop workspace, with live objective history, retained intermediate states, optional post-run Monte Carlo validation, excitation-profile optimisation, Fisher-throughput selection, joint detection-plus-excitation workflows, and four selectable detection-gate strategies with Fisher Compression as the default.
- API-first interoperability for other software and LLM agents through Python APIs, HTTP APIs, and MCP.
- Exportable, publication-oriented HTML reports with SVG plot assets, CSV data assets, and theme-aware presentation.

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
| Physics Engine | `python/backend/twin_engine.py` | Time-domain excitation, decay PDFs, gate distillation, Fisher estimation, gridded MLE, Monte Carlo workflows, bootstrap statistics, diagnostics, synthetic image generation, validation-image sizing, pixel fitting payloads, and phasor fallback/calibration support. |
| Shared State Models | `python/backend/models.py` | Validated configuration and state objects used across the backend and desktop. |
| Service Layer | `python/backend/service_api.py` | Stable orchestration surface for workflows, data access, configuration changes, diagnostics, validation-image fitting, and sessions. |
| Profile Store | `python/backend/profile_store.py` | Versioned instrument-profile storage, migration, and import/export helpers. |
| HTTP API | `python/backend/main.py` | Remote programmatic access to the shared service layer. |
| Desktop Workspace | `python/gui/main_window.py` and widgets | Interactive engineering environment for precision, diagnostics, validation-image testing, integrated optimisation mode, view presets, workspace save/load, and plot inspection. |
| Desktop Automation | `python/gui/automation_api.py` | In-process control of the live desktop, including controller state, optimisation state, and plot payload access. |
| MCP Server | `python/mcp_server.py` | Stdio MCP bridge exposing tools, resources, and prompts to LLM hosts. |
| Documentation and Reports | `docs/` and HTML exporters | Human-readable manuals, parity reports, and precision-session outputs with SVG/CSV asset packages. |

## State Model Intent
The validated configuration object is the single source of truth for simulation and precision workflows.

Important state categories include:

- decay model and component parameters,
- excitation model, width, timing, rise/fall behaviour, burst settings,
- detection and gate geometry, including backend-resolved equal/custom edge definition, start/end anchoring, collection mode, overlap policy, overlap effect, and gate-tail wraparound,
- sweep definitions for parameter studies,
- precision execution settings such as photon budget, Monte Carlo repeats, bootstrap samples, CI level, and estimator-accuracy threshold,
- plotting and reporting options used by the desktop workspace and exports, including light/dark theming and asset generation.
- optimisation-execution options such as graphical real-time updates, retained intermediate states, and optional post-run Monte Carlo validation.
- validation-image execution options such as photon budget, target repeats, fitting backend, and workspace persistence metadata.

The GUI must synchronize to this model rather than holding independent hidden state.

The backend engine must also be able to resolve the effective gate geometry from that state without relying on GUI-side preprocessing. That is especially important for API, HTTP, and MCP-driven use where the controller may not be present.

Sequential gate collection is also a backend concern, not just a label. Under a fixed total acquisition budget, sequential collection reduces the effective detected-photon throughput by the number of sequential gate acquisitions, which must feed through both Fisher and Monte Carlo precision calculations.

Explicit overlap is split into two layers:

- geometric gate definition used for diagnostics and gate visualization,
- statistical overlap handling used for Fisher and Monte Carlo counting rules.

That separation is intentional so the diagnostics view shows the physical gate geometry, while the estimator math applies exclusivity or duplicate-event semantics separately.

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
- PDF ensembles corresponding to the swept X-axis parameter,
- exportable HTML report with SVG figures, CSV tables, and theme toggle support.

### Optimisation Workflow
The optimisation workflow is now part of the main desktop workspace, not a separate legacy optimiser dialog.

Expected behaviour:

- entering optimisation mode whenever detection-gate or excitation optimisation is enabled,
- red visual emphasis on the optimisation workspace docks,
- live use of Precision, MLE Accuracy, and Instrument Diagnostics as the optimisation display surfaces,
- numerical-theory-only updates during the optimisation loop,
- retained intermediate states including start and finish,
- optional post-run Monte Carlo validation for those retained states,
- export of optimisation options, history curves, retained states, and final instrument definitions.

The currently implemented optimisation workspace supports:

- detection-gate optimisation,
- excitation-profile optimisation,
- Fisher Information and Fisher-throughput objectives,
- joint sequential alternating detection-plus-excitation optimisation with a configurable maximum number of alternating rounds.

The implemented detection-gate strategies are:

- Fisher Compression: dynamic-programming compression of a fine contiguous histogram into an optimal gate partition, with an optional nuisance-aware Schur-complement score and optional automatic gate-count reduction until a user-defined peak photon-efficiency loss is reached.
- Direct Mean F Minimisation: continuous SLSQP edge optimisation over the current design grid.
- Partition Theorem Bottom-Up: constructive split-based partition growth on a fine reference histogram.
- Partition Theorem Top-Down: merge-based compression on a fine reference histogram.

The Fisher Compression auto-compression loss test is referenced to the initial finer optimised partition, not to the unoptimised equal-gate starting point. When auto-compress is enabled, the optimisation start state is therefore the configured finer equal-width partition rather than the main GUI gate count.

The implemented excitation-profile strategies are:

- Gaussian width optimisation over the configured width range,
- square / rectangular width optimisation over the configured width range,
- free-form optimisation over a configurable number of non-negative control points.

The implemented optimisation objectives are:

- Fisher Information: choose the candidate with the best mean F-value over the active X-axis sweep,
- Fisher Throughput: first enforce the configured peak F^-2 loss budget against the appropriate Dirac-based reference design, then choose the candidate with the best throughput metric. The configured percentage is interpreted as an absolute photon-efficiency loss in percentage points at the efficiency peak. For excitation, fixed-dose mode assumes no photon-budget gain from pulse area, so throughput changes are driven by the achieved information efficiency of the excitation and detection shapes. Under fixed-peak mode, the throughput metric also scales with the relative excitation area because photon count is assumed to grow proportionally to pulse area. For detection it is most meaningful for strategies that can change gate count, especially Fisher Compression auto-compress.

Optimisation outputs should explicitly report the final gate count and, when excitation optimisation is active, the final excitation-profile summary including profile family, constraint, equivalent width, and either width or free-form control points.

### Synthetic Image Workflow
The synthetic image workflow exists to test estimators and visualization paths on simulated datasets produced by the same instrument model.

Expected outputs:

- synthetic gated data,
- parameter-band validation images derived from the active precision X-axis sweep,
- fit maps,
- phasor products,
- pixel-level inspection payloads,
- data summaries for software integration.

The desktop workspace should expose two focused view presets:

- simulation workspace: controller plus precision, accuracy, and diagnostics,
- image validation workspace: controller plus image validation, pixel inspector, and phasor space.

## MCP and LLM Intent
The MCP server is intended to let external LLM systems use the Digital Twin as a structured reasoning backend.

MCP should expose:

- configuration inspection and mutation,
- workflow execution,
- optimisation workflow execution,
- detection-optimisation strategy selection and strategy-specific settings,
- precision and diagnostics access,
- data and result snapshots,
- GUI schema metadata so an LLM can reference the desktop consistently,
- reusable prompts that encode good operating patterns.

The MCP layer currently targets backend and workspace-schema access. Live Qt widget driving remains the responsibility of the in-process desktop automation API unless a future dedicated desktop MCP bridge is introduced.

Because some gating modes are still being stabilized, LLM-facing guidance should treat these options cautiously:

- sequential gate collection,
- explicit overlap mode,
- duplicate-event overlap effects.

These can be inspected and configured through APIs and MCP, but they should currently be surfaced to users as under development.

## Documentation Intent
The HTML manual must stay synchronized with the actual implementation and cover:

- product scope,
- architecture,
- shared service API,
- HTTP API,
- desktop automation API,
- MCP tools, resources, and prompts,
- integrated optimisation-mode behaviour and current scope limits,
- setup instructions for supported LLM hosts,
- mathematical definitions of F, photon efficiency, Fisher scaling, and bootstrap outputs,
- current scope limits and compatibility notes.

## Validation Intent
The Python Digital Twin should be validated against:

- focused backend tests,
- parity checks against known MATLAB or report benchmarks where applicable,
- smoke tests of the MCP server,
- interactive validation in the Qt workspace for plotting, legends, and diagnostics.

Parity with MATLAB is important for core physics and benchmark trends, but the Python product is intentionally narrower in scope and more integration-oriented.
