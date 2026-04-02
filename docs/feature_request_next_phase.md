# Feature Request: Next Scientific Phase

This document is the combined implementation-facing feature request for the next three scientific milestones. It is a planning artifact for future engineering work. Nothing in this file should be interpreted as already implemented behavior.

## 1. Dead-Time Correction Methods with Fisher Analysis

### Goal

Add correction-aware precision analysis for detector deadtime so the product can compare detector-limited measurements, correction-aware reporting, and ideal-reference behavior within one workflow.

### Scientific Intent

The feature must preserve the distinction between:

- raw detected-photon statistics
- corrected count interpretation
- conditional collected-photon Fisher semantics

It must not silently redefine `F`, `eta`, or photon-basis reporting.

### In-Scope Behavior

- support correction-aware reporting in the precision workflow when detector deadtime is active
- support at least these comparison modes:
  - uncorrected measurement behavior
  - corrected estimate or reporting behavior
  - ideal reference behavior
- state explicitly whether each correction method modifies:
  - the estimator only
  - the Fisher model only
  - both
- expose enough diagnostics to let a user understand what quantity is raw, corrected, conditional, or reference-based

### Out of Scope for the First Implementation

- exhaustive support for every detector correction method in the literature
- GUI-only correction logic without backend ownership
- undocumented changes to the meaning of existing precision metrics

### Backend Changes Required

- extend the precision workflow to model correction-aware deadtime reporting
- define correction-aware outputs in the shared engine and service layer
- preserve comparability with the existing event-driven and ideal-reference workflows
- ensure Monte Carlo validation can distinguish uncorrected and corrected interpretations where applicable

### Config and Model Changes Required

- add explicit deadtime-correction settings to the backend configuration model
- keep correction mode separate from deadtime simulation mode
- ensure defaults preserve current behavior until the feature is explicitly enabled

### Service, API, MCP, and Documentation Impacts

- update service-layer payloads if corrected outputs are exposed publicly
- update HTTP and MCP surfaces only if they surface the new corrected quantities
- update `docs/manual/maths.html`, `docs/manual/apis.html`, and `docs/manual/mcp.html` when behavior becomes visible
- require explicit scientific sign-off before changing the interpretation of `F`, `eta`, or photon basis

### Required Tests

- theoretical versus Monte Carlo consistency for at least one deadtime-corrected configuration
- regression tests showing unchanged outputs when correction is disabled
- tests distinguishing raw and corrected reporting paths
- documentation and payload-key consistency checks if new public fields are introduced

### Risks and Open Scientific Review Points

- whether correction belongs in the estimator, the Fisher model, or both
- how corrected photon accounting maps onto current collected-photon semantics
- whether ideal-reference comparisons remain scientifically meaningful under the chosen correction model

## 2. Pixellated Detector Simulation

### Goal

Add pixellated detector simulation, including SPAD-array-style detector behavior, as a first-class detector-topology feature.

### Scientific Intent

The feature should extend the current event-driven detector model rather than bypass it. Detector arrays must remain grounded in the same latent optical model used elsewhere in the application.

### In-Scope Behavior

- support detector arrays as a backend simulation concept
- support SPAD-array-like behavior as the first target topology
- support per-pixel or grouped resource constraints where scientifically meaningful
- support comparisons between:
  - single-channel detector behavior
  - independent pixel arrays
  - shared-resource or partially coupled arrays
- provide array-level aggregation outputs needed by precision and validation-image workflows

### Out of Scope for the First Implementation

- full sensor-physics realism beyond the chosen SPAD-array abstraction
- hardware-vendor-specific array models
- UI-first detector-array design without backend semantics being defined first

### Backend Changes Required

- extend the event-driven detector model to represent detector arrays
- add array-aware resource-group and routing behavior
- preserve the shared latent optical model and compatibility with current precision workflows
- ensure validation-image generation remains interpretable when array detectors are active

### Config and Model Changes Required

- add detector-array configuration to the shared backend model
- define whether array topology is described by pixel count, geometry, grouping, or resource-coupling presets
- ensure default settings preserve the current single-channel workflow

### Service, API, MCP, and Documentation Impacts

- service outputs must distinguish single-channel and array-level detector semantics
- HTTP and MCP surfaces should only expose array controls once backend semantics are stable
- update architecture and maths documentation when detector arrays become a public feature
- ensure API and MCP wording does not imply unsupported detector realism

### Required Tests

- regression tests preserving current outputs when array mode is disabled
- event-driven tests for independent versus shared-resource pixel behavior
- validation tests for array-level aggregation outputs
- precision-workflow tests demonstrating interpretable comparison between single-channel and array configurations

### Risks and Open Scientific Review Points

- how much array coupling should be present in the first model
- whether image and precision outputs should be per-pixel, aggregated, or both
- how to document the boundary between useful abstraction and physical realism

## 3. Frequency-Domain Support with Digital FD and Sine-Wave Excitation

### Goal

Add a frequency-domain branch to the digital twin, beginning with digital FD support and sine-wave excitation.

### Scientific Intent

This feature must coexist with the current time-domain workflow without pretending the two domains are identical. Where terminology can be shared safely, it should be. Where the scientific quantities differ, the distinction must remain explicit.

### In-Scope Behavior

- add digital FD as the first supported frequency-domain workflow
- add sine-wave excitation simulation
- define FD observables that are explicit, documented, and mappable to backend outputs
- allow at least one comparison path between FD and time-domain results without collapsing their meanings
- keep time-domain outputs, FD outputs, and any cross-domain comparison mode distinct

### Out of Scope for the First Implementation

- analog-hardware realism beyond the digital FD abstraction
- a full analog instrument emulation stack
- undocumented reuse of time-domain labels for distinct FD quantities

### Backend Changes Required

- add FD configuration and excitation support to the backend model
- add FD computation paths to the shared engine
- keep FD logic out of UI callbacks and place it in backend workflows
- define how FD outputs relate to, but remain distinct from, phasor-style products

### Config and Model Changes Required

- add explicit FD mode and sine-wave excitation configuration fields
- keep existing time-domain defaults unchanged unless FD is enabled
- define the minimal configuration required to compute digital FD outputs reproducibly

### Service, API, MCP, and Documentation Impacts

- service outputs must distinguish FD products from time-domain products
- HTTP and MCP exposure should follow only after backend semantics are stable
- update maths, API, and MCP docs when FD becomes user-visible
- document the relationship between FD outputs and current phasor representations

### Required Tests

- regression tests proving unchanged time-domain outputs when FD mode is disabled
- backend tests for sine-wave excitation generation and FD output stability
- tests verifying distinct payload semantics for FD versus time-domain workflows
- documentation checks preventing manual pages from describing unsupported analog realism

### Risks and Open Scientific Review Points

- exact definition of digital FD observables and their precision semantics
- how FD metrics relate to current Fisher-based reporting
- the extent to which phasor products can be reused without misrepresenting FD behavior

## Implementation Notes Shared Across All Three Requests

- Define backend semantics first, then expose them through desktop, HTTP, automation, and MCP surfaces.
- Do not place scientific logic directly inside Qt callbacks.
- Any change to public scientific meaning must update:
  - `docs/architecture_intent.md`
  - `docs/manual/maths.html`
  - `docs/manual/apis.html`
  - `docs/manual/mcp.html`
  - `docs/audit_matrix.md`
- Future implementation work should preserve current behavior by default until new modes are explicitly enabled.
