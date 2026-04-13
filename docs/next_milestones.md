# Next Milestones

This document records the next scientific and platform milestones planned after `1.2.1 beta`. It is a roadmap artifact for engineering and scientific review. It does not describe implemented user-facing functionality.

The milestones below are intentionally listed without hard priority ranking. A recommended execution order is provided at the end to reduce semantic drift and implementation risk.

## 1. Paper-Faithful Stationary Dead-Time Correction

Problem statement:
The current dead-time correction surface is mixed. `Rapp (MCPDF-full)` and `Rapp (MCHC-full)` are now the promoted stationary-model paths, while `Isbaner-lite`, `Rapp (MCPDF-lite)`, and `Rapp (MCHC-lite)` remain useful surrogate companions that do not yet implement the raw-timestamp or full inverse procedures described in the original literature.

User and scientific value:
This milestone would make dead-time-corrected benchmarking more trustworthy at high count rates and would let HILIGHTer compare corrected Monte Carlo, corrected Fisher, and detector-aware estimators against a defensible physical model rather than only against a shared surrogate family.

Intended outcome:
The backend should expose a paper-faithful stationary-process forward model for dead-time-distorted detection histograms and use it to implement:

- a faithful Isbaner reimplementation that works from raw photon timestamps and the inter-photon-time distribution rather than from the current gated-histogram surrogate
- a faithful MCPDF path that matches measured detection histograms against the stationary detection distribution
- a faithful MCHC path that reconstructs an arrival histogram from the detected histogram and then reuses the standard low-flux estimator
- method-specific corrected Fisher calculations and diagnostics that are documented as stationary-model outputs rather than surrogate companions
- a user-facing relabel that keeps the current surrogate exposed as `Isbaner-lite` until the faithful Isbaner method is available for side-by-side comparison

Dependencies on existing backend semantics:

- shared backend ownership of detector, gate, and excitation modelling
- service-layer precision workflow payloads
- diagnostics surfaces for observed versus corrected histograms
- calibration semantics for dead time, IRF, and gate geometry

Main scientific review risks:

- mixing gated-histogram surrogates with raw-timestamp methods without making the distinction explicit
- renaming the current Isbaner surface without also documenting the reimplementation path, which would still leave users unsure what is lite versus faithful
- under-specifying which experimentally available measurements are required for faithful MCPDF versus faithful MCHC
- introducing a stationary detector model that is internally consistent but too expensive for practical sweeps or Monte Carlo validation

Suggested acceptance signal:
The milestone is reached when the backend can ingest experimentally realistic detection histograms plus calibrated detector settings, reproduce the stationary forward model, expose paper-faithful MCPDF and MCHC estimators beside the existing lite surrogates, and show corrected theory/Monte Carlo agreement without violating basic physical expectations such as the ideal `F >= 1` floor.

## 2. Pixellated Detector Simulation

Problem statement:
The current detector model is channel- and resource-based, but it does not yet expose pixellated detector arrays as a first-class simulation concept.

User and scientific value:
This will enable exploration of SPAD-array-like detectors, detector topology tradeoffs, and array-level resource effects within the same digital twin.

Intended outcome:
The backend should support detector arrays with meaningful per-pixel or grouped resource semantics, while preserving comparability with the current single-channel model.

Dependencies on existing backend semantics:

- shared latent optical model
- event-driven routing, arbitration, deadtime, and capacity handling
- validation-image and precision workflows that consume detector outputs
- service-layer orchestration of simulation settings

Main scientific review risks:

- unclear distinction between independent pixels and shared-resource arrays
- UI or API terminology that hides the actual detector topology being simulated
- introducing array behavior that breaks interpretability of existing image or precision outputs

Suggested acceptance signal:
The milestone is reached when users can simulate single-channel and pixellated detector cases under consistent backend semantics, compare independent and shared-resource array behaviors, and obtain array-aware outputs that remain scientifically interpretable.

## 3. Frequency-Domain Support with Digital FD and Sine-Wave Excitation

Problem statement:
The current application is time-domain centered. The next milestone is to add a frequency-domain branch, starting with a digital FD workflow and sine-wave excitation.

User and scientific value:
This will broaden the digital twin beyond gated time-domain analysis and allow comparison between time-domain and FD-style virtual instrument configurations.

Intended outcome:
The backend should support digital FD observables and sine-wave excitation definitions while keeping the new domain scientifically separate from, but comparable to, the existing time-domain workflow.

Dependencies on existing backend semantics:

- central backend ownership of excitation modelling
- shared configuration model
- phasor-adjacent mathematical representations
- service/API/documentation alignment rules for new scientific outputs

Main scientific review risks:

- forcing false equivalence between time-domain precision outputs and FD observables
- under-specifying what "digital FD" means at the modelling level
- conflating FD outputs with existing phasor products without documenting the distinction

Suggested acceptance signal:
The milestone is reached when the backend supports sine-wave excitation and digital FD outputs with explicit mathematical documentation, separate reporting semantics, and at least one clear comparison path against the time-domain workflow.

NOTE: sinewave excitaton shoudl accept parameters as initial phaseshift (default 0) and modulation depth (default 1.0) in degrees and unitless respectively.

## Cross-Cutting Guarded Areas

These milestones all touch guarded scientific and architectural areas:

- Fisher and precision semantics
- optimisation semantics
- detector modelling semantics
- API, MCP, and documentation alignment

For any implementation work in these areas:

- backend semantics must be defined before UI behavior
- public docs must be updated in the same task when behavior becomes user-visible
- scientific meaning changes require explicit human confirmation

## Recommended Execution Order

The milestones are roadmap items rather than strict priorities, but the recommended implementation order is:

1. Paper-faithful stationary dead-time correction
2. Pixellated detector simulation
3. Frequency-domain support with digital FD and sine-wave excitation

This order first stabilizes the scientific meaning of the existing high-flux precision stack, then extends detector-topology complexity, and only then introduces a new analysis domain.
