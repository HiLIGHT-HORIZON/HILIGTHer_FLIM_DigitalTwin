# Physics and Maths Audit

This document is a human-review aid for the scientific core of the HILIGHTer Digital Twin. It is intentionally separate from the operator manual. The goal is to let a human inspect the implemented mathematics, compare it with the stated intent, and detect silent semantic drift introduced by iterative agent work.

## Status

- Audit state: Preliminary desktop review prepared by Codex
- Code changes performed as part of this audit: none
- Scientific sign-off: pending human review

## Canonical Sources

Use these files as the primary sources of truth during review:

- `docs/architecture_intent.md`
- `docs/manual/maths.html`
- `docs/optimization_strategy.md`
- `python/backend/twin_engine.py`
- `python/backend/event_driven.py`
- `python/backend/models.py`
- `python/backend/service_api.py`
- `python/tests/test_physics_engine.py`
- `python/tests/test_event_driven.py`
- `python/tests/test_physics_parity.py`
- `python/tests/test_reference_parity.py`
- `python/tests/test_optimizer.py`

## Recommended Review Order

Review in this order so that semantic issues are caught before secondary implementation details:

1. Fisher and precision semantics
2. Monte Carlo versus theory consistency
3. Event-driven detector assumptions
4. Optimisation objective semantics
5. Latent optical model and gating
6. Phasor and image-derived products

## Review Checklist

For each subsystem below, manually answer:

- Is the mathematical claim scientifically correct?
- Does the implementation calculate the same quantity the documentation describes?
- Do tests validate the intended scientific claim, or only a weaker numerical property?
- Could a UI/API label hide a change in semantics?
- Is any approximation acceptable, and is it documented clearly enough?

## Subsystem Audit

### 1. Latent Optical Model

Plain English:
The backend builds a latent decay law, shapes it with the excitation profile or IRF, and then projects that latent timing distribution through gate acceptance and detector effects.

Key maths:

- Exponential branch: `exp(-t / tau)`
- Custom branch: delegated through the decay model store and `evaluate_decay_curve(...)`
- Observation path:
  `latent decay -> excitation / IRF convolution -> gate statistics -> collected photons`

Primary implementation:

- `python/backend/twin_engine.py:500` `_build_tabulated_optical_model`
- `python/backend/twin_engine.py:926` `resolve_gate_edges`
- `python/backend/twin_engine.py:959` `distill_gates`
- `python/backend/twin_engine.py:2006` `dt_pdf`

Primary tests:

- `python/tests/test_physics_engine.py` `test_pdf_normalization`
- `python/tests/test_physics_parity.py`
- `python/tests/test_reference_parity.py`

Preliminary audit:

- The implementation and manual are aligned at a high level: the code clearly separates latent timing from later detector and gate effects.
- `dt_pdf` normalizes aggressively and guards against invalid arrays, which is good operationally but can hide upstream modelling defects if inputs become malformed.
- `dt_pdf` uses FFT circular convolution when wrapping is enabled and clipped linear convolution otherwise. That is scientifically plausible, but it should be manually confirmed that this matches the intended treatment of periodic excitation and finite observation windows for all supported decay families.
- Gate generation is not a trivial rectangular mask. Smoothed edges, wraparound, overlap behavior, and gate distillation all affect the effective observation model. The manual currently explains the concept, but not the full gate semantics.

Manual questions:

- Is the wrapped FFT path the intended physical model, or only a numerical convenience?
- Are gate rise and fall smoothing parameters incorporated in exactly the way the published or internal reference expects?
- Do custom decay models preserve the same normalization and interpretability as the built-in exponential family?

### 2. Fisher and Precision Semantics

Plain English:
The precision workflow estimates how well the chosen parameter can be recovered from the photons that survive the instrument, then optionally rescales that conditional precision onto a different photon basis for reporting.

Key maths:

- Relative precision:
  `sigma(theta_hat) / theta = F / sqrt(N)`
- Conditional efficiency:
  `p = F_cond^-2`
- Survival:
  `eta = N_collected / N_reference`
- Reporting basis rescaling:
  `F_eff = F_cond / sqrt(eta)` when reporting on a larger photon budget than the collected set

Primary implementation:

- `python/backend/twin_engine.py:2050` `compute_fisher_info`
- `python/backend/twin_engine.py:2414` `monte_carlo_precision_curve`
- `python/backend/models.py:133`
- `python/backend/models.py:147`
- `python/backend/service_api.py`

Primary tests:

- `python/tests/test_physics_engine.py` `test_fisher_information`
- `python/tests/test_physics_engine.py` `test_compute_ideal_reference_forces_zero_to_period_ideal_config`
- `python/tests/test_physics_engine.py` `test_monte_carlo_precision_returns_bootstrap_confidence_intervals`

Preliminary audit:

- The code appears consistent with the documented distinction between conditional collected-photon precision and survival-based rescaling.
- `compute_fisher_info` forms gate probabilities from the same distilled gate model used elsewhere, computes a scalar Fisher quantity from finite differences, then rescales the resulting `F` using `_f_value_reference_budget(...)`. This is consistent with the manual statement that "Compute F-value on" changes reporting basis rather than estimator semantics.
- The ideal-reference path is explicitly tested to force a zero-to-period, no-artifact configuration. That is a strong guard against accidental semantic drift in the reference curve.
- The current dead-time correction surface is no longer a single generic mode. `Isbaner-lite` and `Rapp (MCHC-lite)` are histogram-correction companions that refit with the standard detector-free gridded MLE, `Rapp (MCPDF-lite)` is a detector-aware surrogate companion fit on observed gated histograms, `Rapp (MCPDF-full)` is the promoted stationary detected-histogram fit, and `Rapp (MCHC-full)` is the promoted stationary histogram-correction-plus-standard-MLE fit.
- `Isbaner-lite` should not yet be treated as a paper-faithful implementation of Isbaner et al. The original paper estimates the mean photon-hit rate from raw photon timestamps using the inter-photon-time distribution and then applies a recursive correction. The current code instead applies a gated-histogram gate-activity surrogate selected from the raw detector-limited estimate.
- The corrected Fisher paths are method-matched surrogates derived from the same backend model family, not yet a human-audited proof that each corrected curve satisfies all expected physical invariants.
- The main manual-review risk is not the headline formula; it is whether every code path uses the same photon accounting assumptions when overlap, sequential collection, or detector distortions are active.

Manual questions:

- Does every reported `F` correspond to the same estimator target and the same interpretation of `N`?
- Is `collected_fraction` always the scientifically correct survival term when detector transfer or event-driven logic is active?
- Are finite-difference parameter steps stable and scientifically acceptable near bounds and on log-scaled axes?
- Should the corrected Fisher companions be documented and interpreted as estimator-matched surrogates rather than literature-faithful bounds until a human scientific audit is complete?

### 3. Monte Carlo Versus Theory

Plain English:
Monte Carlo should be a validation layer for the same latent physics and estimator semantics used by theory, not an alternate model with different assumptions.

Key maths:

- Draw latent event times from the same underlying PDF used by theory.
- Convert counts into parameter estimates with the configured estimator.
- Compare empirical spread, confidence intervals, and optional p-values against theory-derived precision metrics.

Primary implementation:

- `python/backend/twin_engine.py:1629` `simulate_gate_histograms`
- `python/backend/twin_engine.py:2414` `monte_carlo_precision_curve`
- fitting and estimation methods in `python/backend/twin_engine.py`

Primary tests:

- `python/tests/test_physics_engine.py` `test_monte_carlo_precision_returns_bootstrap_confidence_intervals`
- `python/tests/test_reference_parity.py`
- `python/tests/test_physics_parity.py`

Preliminary audit:

- The Monte Carlo path uses the same `dt_pdf(...)` latent distribution as theory, which is the correct architectural pattern.
- Histogram generation contains multiple branches: sequential acquisition, duplicate-overlap counting, exclusive overlap, optional uniform background injection, and optional detector-transfer distortion. This is powerful, but it means theoretical and empirical outputs can silently drift if one branch changes semantics without a matching documentation update.
- The raw Monte Carlo baseline is now intentionally kept distinct from any corrected companion estimate when a dead-time correction family is enabled. That is the right semantic separation, but it should continue to be regression-tested because it is easy to break accidentally.
- The corrected Monte Carlo companion is estimator-specific, so agreement or disagreement must be judged against the matching companion theory rather than against the raw detector-limited theory curve.
- Current tests verify payload structure, confidence interval emission, and some parity behavior, but do not yet prove full semantic parity across all detector and overlap modes.

Manual questions:

- Is every Monte Carlo branch expected to match the same theoretical Fisher curve, or only a subset?
- When background is injected, does the theoretical Fisher path use an identical background interpretation?
- Are bootstrap p-values and CI bands attached to the same estimator quantity the UI labels imply?
- For corrected companions, which mismatches should be interpreted as acceptable surrogate error and which ones should be treated as implementation defects?

### 4. Event-Driven Detector Model

Plain English:
The event-driven backend is meant to be the explicit chronological detector reference. It uses the same latent optical model as the fast Poisson path but replaces direct count generation with event-by-event routing, arbitration, deadtime, and capacity constraints.

Key maths and semantics:

- Shared latent arrivals
- Time-varying acceptance probabilities per channel
- Resource-group deadtime and per-frame capacity constraints
- Exclusive or nonexclusive routing and arbitration rules

Primary implementation:

- `python/backend/event_driven.py`
- `python/backend/twin_engine.py:524` `_build_event_driven_resource_groups`
- `python/backend/twin_engine.py:540` `_build_event_driven_channels`

Primary tests:

- `python/tests/test_event_driven.py`

Preliminary audit:

- The architecture is sound: the event-driven layer is structurally separate from the optical model, which reduces the risk of duplicated physics.
- The tests are meaningful. They check bridge behavior to the ideal Poisson backend at zero deadtime, monotonicity with deadtime and multihit capacity, and the effect of shared resources.
- The current evidence is strong for internal consistency, but not yet a proof of physical correctness. Most tests are monotonic or comparative rather than analytical.
- Auto-mode switching between ideal Poisson and event-driven is tested, but the human review should confirm the exact rule for "event model required" is scientifically justified and not merely computationally convenient.

Manual questions:

- Are resource-group abstractions and arbitration rules faithful enough to the intended detector model?
- Does zero-deadtime bridging remain valid under all overlap and routing combinations?
- Is the event-driven backend the ground-truth reference, or only one plausible detector realization?

### 5. Optimisation Semantics

Plain English:
Optimisation should search over gate or excitation settings using objective functions whose scientific meaning is explicit and consistent with the precision-reporting semantics elsewhere in the app.

Key maths and semantics:

- Gate optimisation objective selection
- Fisher-information versus Fisher-throughput tradeoff
- Photon-efficiency and throughput AUC objectives
- Excitation throughput reference and sweep-range construction

Primary implementation:

- `python/backend/twin_engine.py:2822` `_build_gate_optimization_payload`
- `python/backend/twin_engine.py:2904` `_build_fine_bin_scores`
- `python/backend/twin_engine.py:3423` `optimize_gates`
- `python/backend/twin_engine.py:3595` `_build_excitation_throughput_reference_peak_efficiency`
- `python/backend/twin_engine.py:3665` `_build_optimization_x_range`
- `python/backend/twin_engine.py:3852` `run_optimization_workflow`
- `python/backend/models.py:147`

Primary tests:

- `python/tests/test_optimizer.py`
- `docs/optimization_strategy.md`

Preliminary audit:

- The optimisation surface is broad and touches some of the same semantics as the precision workflow, especially photon basis and throughput interpretation.
- This area is the highest documentation-drift risk after the Fisher semantics, because objective names can remain stable while the underlying quantity changes.
- The code structure is centralized inside `twin_engine.py`, which is good, but it also means subtle coupling between optimisation and reporting semantics can accumulate unnoticed.

Manual questions:

- Does each objective label correspond to the quantity a scientist would infer from the name?
- Is throughput treated as a reporting normalization, a physical penalty, or both?
- When photon basis is changed for optimisation, does that preserve compatibility with the main precision workflow?

### 6. Phasor and Derived Image Products

Plain English:
The phasor outputs should be another representation of the same decay and gating physics, not an independent model.

Key maths:

- Theoretical locus on the universal semicircle for ideal single-exponential behavior
- Measured phasors derived from the same timing model and harmonic assumptions used elsewhere

Primary implementation:

- phasor-related methods in `python/backend/twin_engine.py`

Primary tests:

- `python/tests/test_physics_engine.py` `test_phasor_locus`

Preliminary audit:

- The current test confirms the theoretical locus lies on the expected semicircle. That is a useful invariant.
- More manual review is still needed for the connection between gated data, harmonic selection, IRF calibration, and displayed phasor interpretation.

Manual questions:

- Is the discrete locus shown in the UI exactly the one implied by the current gate scheme?
- Are IRF calibration and gate-distorted phasors documented with enough precision for scientific users?

## Semantic Control Points

These configuration fields are the highest-risk places for semantic drift because the labels are user-facing and changes here can alter the scientific meaning of the whole workflow:

- `python/backend/models.py:77` `gate_collection_mode`
- `python/backend/models.py:78` `gate_overlap_mode`
- `python/backend/models.py:133` `precision_compute_ci`
- `python/backend/models.py:138` `precision_ci_level`
- `python/backend/models.py:147` `optimization_f_photon_basis`
- `python/backend/models.py:148` `optimization_objective`
- `python/backend/models.py:178` `simulation_mode_preference`
- `python/backend/models.py:179` `simulation_mode`
- `python/backend/models.py:182` `event_deadtime_mode`
- `python/backend/models.py:191` `decay_model`
- `python/backend/models.py:196` `background_level`

## Preliminary Findings Summary

This is not a sign-off. It is a structured first-pass audit based on code and test inspection.

### Aligned Areas

- The repository still follows the intended architecture of one shared backend engine reused across theory, Monte Carlo, desktop, API, and MCP surfaces.
- The distinction between conditional collected-photon precision and survival-based rescaling appears to be implemented consistently at a high level.
- The ideal-reference workflow has explicit test coverage guarding against accidental carry-over of detector artefacts.
- The event-driven backend is genuinely distinct from the ideal Poisson path and is not merely a renamed wrapper.

### Review Risks

- Gate semantics are richer than the current manual prose. Sequential collection, overlap effects, and detector-transfer branches need explicit human inspection.
- Monte Carlo and theory share the same latent PDF, but they also contain branch-specific logic that could drift independently.
- The dead-time correction companions mix histogram-correction and detector-aware-fit semantics, so a label staying stable does not guarantee that the underlying scientific claim stayed stable.
- Optimisation semantics likely need the deepest human review after Fisher semantics because objective labels can mask subtle changes in quantity definition.
- Current tests are strongest on invariants, bridge checks, and monotonicity. They are weaker on full analytical validation across all supported detector and background modes.

### Suggested Human Verdict Targets

After manual review, mark each subsystem as one of:

- `Audited and aligned`
- `Scientifically acceptable approximation`
- `Needs documentation clarification`
- `Needs implementation correction`

## Proposed Automatic Consistency Audit

Do not treat this as a proof of correctness. It is a drift detector that should flag cases needing human review.

### Suggested future script

Recommended path:

- `python/tools/audit_physics_consistency.py`

### Checks the script should perform

1. Documentation terminology checks
- confirm that `docs/manual/maths.html`, `docs/manual/apis.html`, and `docs/manual/mcp.html` still use the same terminology as the implementation for:
  - `f_value_conditional`
  - `survival_eta`
  - photon basis
  - optimisation objective names
  - simulation core names

2. Config-field drift checks
- confirm that the guarded semantic fields in `PhysicsConfig` still exist
- warn when field names, allowed values, or defaults change

3. API and payload checks
- confirm that service and API payloads still expose the scientific quantities the docs claim
- warn when renamed keys appear without doc updates

4. Test coverage presence checks
- confirm that each subsystem has at least one targeted test file or test function
- warn when physics-critical modules change without nearby tests

5. Manual-review trigger checks
- flag any edits touching:
  - Fisher semantics
  - optimisation objectives
  - persistence semantics for physics outputs
  - event-driven detector rules
  - phasor computation

### Suggested output format

- `PASS`: no obvious drift detected
- `WARN`: terminology or coverage drift detected
- `REVIEW REQUIRED`: guarded scientific area changed and needs human sign-off

## Suggestions Before Any Code Changes

- Review `compute_fisher_info(...)` and `monte_carlo_precision_curve(...)` first. These functions anchor most downstream semantics.
- Manually trace one representative configuration through theory, Monte Carlo, and event-driven paths to confirm that `N`, `F`, and survival are interpreted consistently.
- Decide whether the current manual should be expanded to document overlap and sequential gate semantics explicitly.
- After human inspection, implement the automatic audit script and update `docs/audit_matrix.md` with signed findings.

## Human Sign-Off Notes

Use this section during review.

### Backend precision workflow

- Verdict:
- Notes:

### Monte Carlo consistency

- Verdict:
- Notes:

### Event-driven detector model

- Verdict:
- Notes:

### Optimisation semantics

- Verdict:
- Notes:

### Latent optical and phasor model

- Verdict:
- Notes:
