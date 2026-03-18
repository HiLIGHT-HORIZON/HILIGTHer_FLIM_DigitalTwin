# Optimization Strategy

## Inputs Analysed

This strategy is based on three sources already present in the project:

- The current Python backend gate optimizer in `python/backend/twin_engine.py`.
- The published PLOS ONE paper "Maximizing the Biochemical Resolving Power of Fluorescence Microscopy" (2013), especially the photon-partitioning and iterative gate-optimization sections.
- The new local document `resources/FisherCompression.docx`.

## What The Existing Backend Already Does

The current backend already contains one valid detection-gate optimizer:

- `TwinEngine.optimize_gates(...)`
- Continuous gate-edge optimization with SLSQP.
- Objective: minimize the mean F-value over a lifetime design grid.
- Constraints: monotonic internal edges, first gate at `0`, last gate at `t_max`.

This should be preserved and exposed as one selectable optimization algorithm, not removed.

## What The 2013 Paper Adds

The published paper adds two algorithmic ideas that are not yet represented properly in the current backend:

1. Partition-theorem iterative optimization
- A bottom-up strategy that increases channel count by splitting a gate only when the Fisher-information gain is non-trivial.
- A top-down strategy that decreases channel count by merging channels while minimizing information loss.

2. Full optimization after partition-theorem initialization
- The paper distinguishes between a fast iterative partitioning strategy and a later direct optimization/refinement step.
- In practical terms, the current SLSQP optimizer is a good match for the refinement stage, but not for the partition-theorem stage.

So for detection gates the backend should eventually expose:

- `direct_slsqp`
- `partition_bottom_up`
- `partition_top_down`
- `partition_plus_refine`

The current backend already covers the direct-refinement family.

## What The FisherCompression Document Adds

The Fisher Compression note is materially different from the current optimizer.

It proposes:

- starting from a fine histogram with many contiguous bins,
- defining a compression operator that aggregates those bins into fewer contiguous gates,
- computing information loss segment by segment from score vectors,
- solving the optimal partition by dynamic programming,
- optionally averaging segment costs over multiple design points,
- optionally accounting for nuisance parameters using the Schur complement of the Fisher matrix.

This is not just another SLSQP parameterization. It is a separate algorithm family:

- fine-grid, loss-aware, dynamic-programming compression,
- explicitly suited to "lossless Fisher compression" and digital re-binning,
- naturally generalizable to multi-parameter fitting and nuisance robustness.

So this should be implemented as a distinct detection optimizer:

- `fisher_compression_dp`

## Recommended Backend Architecture

Do not keep growing all optimization logic inside `TwinEngine`.

Create a small optimization layer under the backend, for example:

- `python/backend/optimization/objectives.py`
- `python/backend/optimization/detection.py`
- `python/backend/optimization/excitation.py`
- `python/backend/optimization/coordinator.py`

Suggested responsibilities:

- `objectives.py`
  - Fisher-information objective helpers.
  - Fisher-throughput objective helpers.
  - Design-grid aggregation rules.
  - Nuisance-parameter Schur complement utilities.

- `detection.py`
  - Existing direct SLSQP wrapper.
  - Partition-theorem bottom-up splitter.
  - Partition-theorem top-down merger.
  - Fisher compression dynamic programming.

- `excitation.py`
  - Gaussian-width optimization.
  - Rectangular-width optimization.
  - Free-form excitation optimization.

- `coordinator.py`
  - Sequential optimization orchestration.
  - Alternating iterative optimization.
  - Convergence and stop criteria.

`TwinEngine` should remain the source of forward physics, Fisher evaluation, and simulation, while the optimization layer becomes the consumer of those primitives.

## Controller Model To Support

The controller now needs to represent four separate concerns:

1. Scope
- optimize detection gates
- optimize excitation profile

2. Execution mode
- one target only
- sequential
- iterative alternating
- if sequential, choose which one runs first

3. Objective
- Fisher Information
- Fisher Throughput
- if throughput, define the maximum permitted FI loss

4. Algorithm family
- detection algorithm
- excitation algorithm
- constraint rules for starts, ends, dose, and peak

These settings belong in `PhysicsConfig` because they affect reproducible optimization behavior and should be accessible through GUI, API, and MCP.

## Detection Optimization Strategy

### A. Legacy direct optimizer

Use the current backend implementation as:

- objective: aggregate F or FI over the selected design set,
- variables: internal gate edges,
- constraints:
  - monotonicity,
  - first gate start anchor,
  - last gate end anchor,
  - optional custom end time.

This is the best match to:

- "Preserve what we have now"

### B. Partition-theorem bottom-up

Implementation idea:

1. Start from a minimal valid partition.
2. For every current segment, evaluate all admissible splits.
3. Score each split by Fisher-information gain or information-loss reduction.
4. Add the best non-trivial split.
5. Repeat until the requested number of gates or until marginal gain falls below threshold.

Benefits:

- fast,
- interpretable,
- naturally aligned with the paper.

### C. Partition-theorem top-down

Implementation idea:

1. Start from a fine partition or dense reference partition.
2. Evaluate the information loss from merging adjacent segments.
3. Repeatedly perform the least harmful merge.
4. Stop at the requested number of gates or loss threshold.

Benefits:

- complements the bottom-up method,
- naturally useful when the target is compression rather than synthesis.

### D. Fisher compression dynamic programming

Implementation idea:

1. Build a fine reference histogram grid.
2. Evaluate per-bin probabilities and score vectors on one or more design points.
3. Precompute segment costs for every contiguous interval.
4. Solve optimal contiguous K-segment partition by dynamic programming.
5. Recover boundaries from the backpointer table.

Important extensions from the note:

- average segment costs over multiple design points,
- replace full Fisher matrix with effective Fisher matrix when nuisance parameters matter,
- allow optimization of both fixed `K` and "smallest `K` within acceptable loss".

This is the best match to:

- "implement the one in the Fisher Compression file"

## Excitation Optimization Strategy

### A. Gaussian width

Variables:

- pulse width only

Implementation:

- 1D bounded search over width
- objective computed through the existing Fisher pipeline

### B. Square width

Variables:

- pulse duration only

Implementation:

- 1D bounded search over duration
- use existing rectangular excitation model

### C. Free-form excitation

Variables:

- amplitude control points over time

Constraints:

- non-negative waveform
- optional normalization to fixed area
- or fixed peak amplitude
- optional smoothness regularization

Implementation:

- represent waveform on a low-dimensional control-point basis,
- upsample to the time grid,
- optimize with SLSQP or L-BFGS-B,
- enforce either:
  - fixed dose: normalize area,
  - fixed peak: normalize to fixed maximum.

This should not start as a fully unconstrained pointwise optimization. A low-dimensional spline or control-point basis is safer and easier to regularize.

## Objective Definitions

### Fisher Information objective

This should optimize on the parameter already selected as the active X parameter in the Decay Model tab.

Recommended aggregate objectives:

- maximize mean FI over the design grid,
- or equivalently minimize mean F,
- optionally use weighted averages over the lifetime range.

### Fisher Throughput objective

This should optimize:

- information per unit time, not just information per photon.

Recommended definition:

- `throughput_objective = effective_fisher_per_photon * detected_photon_rate`

where detected photon rate depends on the excitation constraint model:

- fixed dose / fixed average power,
- fixed peak amplitude.

The FisherCompression note already gives the correct conceptual split:

- narrower pulses tend to maximize per-photon FI,
- broader pulses can improve photon rate under peak-limited operation,
- the useful optimum depends on which constraint is active.

To implement the requested "without sacrificing too much FI":

- introduce a permitted FI-loss threshold,
- optimize throughput only over candidates whose FI remains above the tolerated fraction of the best-FI solution.

## Joint Optimization Modes

### Detection only

Run the chosen detection algorithm and leave excitation unchanged.

### Excitation only

Run the chosen excitation algorithm and leave detection unchanged.

### Sequential

Run both, once, in the chosen order.

Recommended defaults:

- detection first for compression-style workflows,
- excitation first for throughput-limited laser-design workflows.

### Iterative alternating

Run:

1. detection optimization,
2. excitation optimization,
3. repeat until:
   - objective change is below tolerance,
   - boundaries and excitation parameters stabilize,
   - or iteration count limit is hit.

Recommended stop criteria:

- relative objective improvement below `1e-3`,
- or max iterations from the controller.

## Boundary and Anchor Rules

All detection algorithms should share the same anchor abstraction:

- first gate start:
  - `zero`
  - `after_irf`
  - `custom`

- last gate end:
  - `period`
  - `custom`

This should be translated into absolute time bounds before each algorithm runs, so the algorithms themselves only handle contiguous segments inside a bounded interval.

## Recommended Implementation Order

Phase 1
- Move optimization settings into config and controller.
- Remove the old Detection-tab button.
- Preserve the existing backend optimizer.
- Add a coordinator entry point that can dispatch by algorithm name.

Phase 2
- Wrap the current SLSQP optimizer as `direct_slsqp`.
- Add gate-start and gate-end anchor support.
- Add the Fisher-throughput objective for Gaussian and square width sweeps.

Phase 3
- Implement partition-theorem bottom-up and top-down gate optimization.
- Reuse the same objective and anchor layer.

Phase 4
- Implement Fisher compression dynamic programming on fine reference histograms.
- Add multi-design-point averaging.
- Add nuisance-aware effective Fisher via Schur complement.

Phase 5
- Implement free-form excitation optimization with control points and constraints.
- Add alternating sequential/iterative joint optimization.

## Recommendation

The right strategy is not to replace the current optimizer. It should become one algorithm in a broader optimization framework.

Concretely:

- keep the current SLSQP gate optimizer,
- add the two published partition-theorem algorithms,
- add Fisher-compression dynamic programming as a separate family,
- add 1D excitation-width optimizers first,
- add free-form excitation only after the objective and constraint layer is stable,
- coordinate everything through one optimization tab and one backend dispatcher.
