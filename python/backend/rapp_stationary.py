"""
Scaffold for a future paper-faithful Rapp et al. stationary dead-time model.

The currently exposed Rapp-family correction in HILIGHTer is a practical
`Rapp (MCPDF)` companion fit implemented in `twin_engine.py` for gated
histogram observations. This module reserves the backend surface for a future
stationary-process implementation without overclaiming that it already exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class StationaryRappInputs:
    period_ns: float
    deadtime_ns: float
    detected_counts: np.ndarray
    gate_edges_ns: np.ndarray
    dwell_s: float
    time_vector_ns: np.ndarray
    latent_pdf: np.ndarray


class RappStationaryModelScaffold:
    """Reserved interface for a future stationary dead-time observation model."""

    def gated_detection_probabilities(self, inputs: StationaryRappInputs) -> np.ndarray:
        raise NotImplementedError(
            "The paper-faithful Rapp stationary model has not been implemented yet. "
            "Use the current 'rapp_mcpdf' path in twin_engine.py instead."
        )

    def log_likelihood(self, inputs: StationaryRappInputs) -> float:
        raise NotImplementedError(
            "The paper-faithful Rapp stationary likelihood has not been implemented yet."
        )

    def fisher_information(self, inputs: StationaryRappInputs, param_value: float) -> Optional[float]:
        raise NotImplementedError(
            "The paper-faithful Rapp stationary Fisher calculation has not been implemented yet."
        )
