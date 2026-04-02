# Tutorial Content Audit

This note records which tutorial sections are exact backend parity, which are controlled educational simplifications, and what is covered by automated tests.

## Summary

- `Fisher Information (basics)`:
  educational and intentionally simplified.
  It uses a toy continuous-time Fisher-density visualisation to build intuition.
  It is not a strict one-to-one rendering of the backend precision engine.

- `F-value, Photon Efficiency and Lifetime Resolution`:
  backend-consistent at the identity level.
  The tutorial relationships
  `p = F^-2`,
  `N_eff = N / F^2`,
  and
  `R = sqrt(N / (8F^2))`
  are algebraic consequences of the backend F-value definition.

- `FLIM Resolving Power`:
  backend-consistent as an asymptotic precision explainer.
  The displayed Gaussian curves represent the sampling distribution of lifetime estimates, not the photon-arrival PDF.
  The photon-arrival PDF remains the single-exponential decay used by the backend.
  The link
  `sigma_tau = F tau / sqrt(N)`
  is the same CRLB-style relation used in the precision engine.

- `Gate Explorer`:
  backend-consistent for the idealised two-gate discrete-bin Fisher calculation shown in the tutorial.
  It is not a full mirror of every backend gate mode.
  The tutorial fixes the period, IRF, and gate structure to keep the teaching model understandable.

## Existing Unrelated Test Failures

The current repository-wide Python test suite still has pre-existing failures in:

- `python/tests/test_physics_engine.py`
- `python/tests/test_reference_parity.py`

These failures are not caused by the tutorial JavaScript edits.
They concern backend parity/throughput expectations already present in the Python suite.

## Automated Tutorial Checks

Dedicated backend tutorial checks live in:

- `python/tests/test_tutorial_parity.py`

They verify:

- theoretical `F`, `F^-2`, `N_eff`, and `R` identities
- Monte Carlo consistency of `sigma_tau = F tau / sqrt(N)`
- discrete two-gate Fisher-information parity against the backend engine

