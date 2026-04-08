# Next Milestones

This document records the next scientific and platform milestones planned after `1.1.0 beta`. It is a roadmap artifact for engineering and scientific review. It does not describe implemented user-facing functionality.

The milestones below are intentionally listed without hard priority ranking. A recommended execution order is provided at the end to reduce semantic drift and implementation risk.

## 1. Pixellated Detector Simulation

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

## 2. Frequency-Domain Support with Digital FD and Sine-Wave Excitation

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

1. Pixellated detector simulation
2. Frequency-domain support with digital FD and sine-wave excitation

This order extends the current time-domain precision core with detector-topology complexity first, and only then introduces a new analysis domain.
