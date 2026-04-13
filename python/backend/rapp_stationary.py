"""
Stationary dead-time observation model inspired by Rapp et al.

This module implements the first paper-facing backend slice of the stationary
nonparalyzable detector model on a discretized repetition period. It is meant
to replace the previous pure scaffold without overclaiming that every detail of
the original literature has already been wired into the public UI surface.

Implemented here:

- stationary forward model for fine-bin detected histograms
- gated detection masses/probabilities derived from that stationary model
- MCPDF-style log likelihood on stationary detected histograms
- a practical MCHC-style inverse that reconstructs an arrival histogram by
  numerically inverting the stationary forward model
- Fisher helper based on stationary plus/minus probability perturbations
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.optimize import minimize


@dataclass(frozen=True)
class StationaryRappInputs:
    period_ns: float
    deadtime_ns: float
    detected_counts: np.ndarray
    time_vector_ns: np.ndarray
    latent_pdf: np.ndarray
    expected_arrivals_per_period: float
    gate_edges_ns: Optional[np.ndarray] = None
    gate_matrix: Optional[np.ndarray] = None
    dwell_s: float = 0.0
    dark_counts_per_period: float = 0.0
    latent_pdf_plus: Optional[np.ndarray] = None
    latent_pdf_minus: Optional[np.ndarray] = None
    param_delta: float = 1.0


class RappStationaryModel:
    """Discrete stationary nonparalyzable detector model over one repetition period."""

    @staticmethod
    def _normalize_pdf(values: np.ndarray) -> np.ndarray:
        values = np.maximum(np.asarray(values, dtype=float).reshape(-1), 0.0)
        total = float(np.sum(values))
        if total <= 0.0:
            if values.size == 0:
                return np.zeros((0,), dtype=float)
            return np.full(values.shape, 1.0 / values.size, dtype=float)
        return values / total

    @staticmethod
    def _softmax(logits: np.ndarray) -> np.ndarray:
        logits = np.asarray(logits, dtype=float).reshape(-1)
        if logits.size == 0:
            return np.zeros((0,), dtype=float)
        logits = logits - float(np.max(logits))
        weights = np.exp(logits)
        return weights / max(float(np.sum(weights)), 1e-15)

    def _build_inverse_basis(
        self,
        inputs: StationaryRappInputs,
        gate_matrix: np.ndarray,
        init_arrival: np.ndarray,
        max_basis: int = 8,
    ) -> Optional[np.ndarray]:
        n_bins = init_arrival.size
        if gate_matrix.shape[0] >= n_bins:
            return None

        candidates = []

        def add_candidate(vec: np.ndarray) -> None:
            vec = np.maximum(np.asarray(vec, dtype=float).reshape(-1), 0.0)
            if vec.size != n_bins or float(np.sum(vec)) <= 0.0:
                return
            vec = vec / float(np.sum(vec))
            for existing in candidates:
                if np.max(np.abs(existing - vec)) <= 1e-6:
                    return
            candidates.append(vec)

        add_candidate(init_arrival)
        add_candidate(inputs.latent_pdf)
        add_candidate(np.ones((n_bins,), dtype=float))

        pseudo = np.linalg.pinv(gate_matrix, rcond=1e-6)
        for col_idx in range(pseudo.shape[1]):
            add_candidate(pseudo[:, col_idx])
        for row_idx in range(gate_matrix.shape[0]):
            add_candidate(gate_matrix[row_idx, :])

        if len(candidates) < 2:
            return None
        basis = np.column_stack(candidates[: max(2, min(max_basis, len(candidates)))])
        return np.asarray(basis, dtype=float)

    def _effective_gate_matrix(self, inputs: StationaryRappInputs) -> np.ndarray:
        if inputs.gate_matrix is not None:
            gate_matrix = np.asarray(inputs.gate_matrix, dtype=float)
            if gate_matrix.ndim != 2:
                raise ValueError("gate_matrix must be 2D when provided.")
            if gate_matrix.shape[1] != np.asarray(inputs.time_vector_ns).reshape(-1).size:
                raise ValueError("gate_matrix width must match time_vector_ns size.")
            return np.maximum(gate_matrix, 0.0)

        edges = None if inputs.gate_edges_ns is None else np.asarray(inputs.gate_edges_ns, dtype=float).reshape(-1)
        t = np.asarray(inputs.time_vector_ns, dtype=float).reshape(-1)
        if edges is None or edges.size < 2:
            return np.eye(t.size, dtype=float)
        gate_matrix = np.zeros((edges.size - 1, t.size), dtype=float)
        for gate_idx in range(edges.size - 1):
            lo = float(edges[gate_idx])
            hi = float(edges[gate_idx + 1])
            mask = (t >= lo) & (t < hi)
            if gate_idx == edges.size - 2:
                mask = (t >= lo) & (t <= hi)
            gate_matrix[gate_idx, mask] = 1.0
        return gate_matrix

    def _bin_width_ns(self, inputs: StationaryRappInputs) -> float:
        t = np.asarray(inputs.time_vector_ns, dtype=float).reshape(-1)
        if t.size < 2:
            return max(float(inputs.period_ns), 1e-6)
        diffs = np.diff(t)
        positive = diffs[diffs > 0.0]
        if positive.size == 0:
            return max(float(inputs.period_ns), 1e-6)
        return float(np.median(positive))

    def _deadtime_bins(self, inputs: StationaryRappInputs) -> int:
        dt_ns = self._bin_width_ns(inputs)
        deadtime_ns = max(float(inputs.deadtime_ns), 0.0)
        if deadtime_ns <= 0.0:
            return 0
        return int(np.ceil(deadtime_ns / max(dt_ns, 1e-12)))

    def _arrival_mass_per_bin(
        self,
        inputs: StationaryRappInputs,
        latent_pdf: Optional[np.ndarray] = None,
        expected_arrivals_per_period: Optional[float] = None,
    ) -> np.ndarray:
        pdf = self._normalize_pdf(inputs.latent_pdf if latent_pdf is None else latent_pdf)
        total_arrivals = float(
            max(
                inputs.expected_arrivals_per_period if expected_arrivals_per_period is None else expected_arrivals_per_period,
                0.0,
            )
        )
        arrival = pdf * total_arrivals
        dark_counts = float(max(getattr(inputs, "dark_counts_per_period", 0.0), 0.0))
        if dark_counts > 0.0 and arrival.size > 0:
            arrival = arrival + (dark_counts / arrival.size)
        return np.maximum(arrival, 0.0)

    def _arrival_detection_probability_per_bin(
        self,
        inputs: StationaryRappInputs,
        latent_pdf: Optional[np.ndarray] = None,
        expected_arrivals_per_period: Optional[float] = None,
    ) -> np.ndarray:
        arrival_mass = self._arrival_mass_per_bin(
            inputs,
            latent_pdf=latent_pdf,
            expected_arrivals_per_period=expected_arrivals_per_period,
        )
        return 1.0 - np.exp(-np.maximum(arrival_mass, 0.0))

    def _advance_state(self, state: np.ndarray, detect_prob: float, dead_bins: int) -> np.ndarray:
        state = np.asarray(state, dtype=float).reshape(-1)
        next_state = np.zeros_like(state)
        if state.size == 0:
            return next_state
        if state.size > 1:
            next_state[:-1] += state[1:]
        available = float(state[0])
        next_state[0] += available * (1.0 - detect_prob)
        next_state[min(dead_bins, state.size - 1)] += available * detect_prob
        return next_state

    def _period_transition_matrix(self, detect_probs: np.ndarray, dead_bins: int) -> np.ndarray:
        n_states = dead_bins + 1
        transition = np.eye(n_states, dtype=float)
        for prob in np.asarray(detect_probs, dtype=float).reshape(-1):
            step = np.zeros((n_states, n_states), dtype=float)
            for state_idx in range(n_states):
                basis = np.zeros((n_states,), dtype=float)
                basis[state_idx] = 1.0
                step[state_idx, :] = self._advance_state(basis, float(prob), dead_bins)
            transition = transition @ step
        return transition

    def _propagate_period_state(
        self,
        state: np.ndarray,
        detect_probs: np.ndarray,
        dead_bins: int,
    ) -> np.ndarray:
        state = np.asarray(state, dtype=float).reshape(-1)
        for prob in np.asarray(detect_probs, dtype=float).reshape(-1):
            state = self._advance_state(state, float(prob), dead_bins)
        return state

    def _stationary_period_start_distribution_from_detect_probs(
        self,
        detect_probs: np.ndarray,
        dead_bins: int,
        max_iter: int = 2000,
        tol: float = 1e-12,
    ) -> np.ndarray:
        n_states = dead_bins + 1
        state = np.zeros((n_states,), dtype=float)
        state[0] = 1.0
        for _ in range(max_iter):
            new_state = self._propagate_period_state(state, detect_probs, dead_bins)
            new_state /= max(float(np.sum(new_state)), 1e-15)
            if float(np.sum(np.abs(new_state - state))) < tol:
                return new_state
            state = new_state
        return state / max(float(np.sum(state)), 1e-15)

    def stationary_period_start_distribution(
        self,
        inputs: StationaryRappInputs,
        latent_pdf: Optional[np.ndarray] = None,
        expected_arrivals_per_period: Optional[float] = None,
        max_iter: int = 2000,
        tol: float = 1e-12,
    ) -> np.ndarray:
        detect_probs = self._arrival_detection_probability_per_bin(
            inputs,
            latent_pdf=latent_pdf,
            expected_arrivals_per_period=expected_arrivals_per_period,
        )
        dead_bins = self._deadtime_bins(inputs)
        return self._stationary_period_start_distribution_from_detect_probs(
            detect_probs,
            dead_bins,
            max_iter=max_iter,
            tol=tol,
        )

    def time_bin_detection_masses(
        self,
        inputs: StationaryRappInputs,
        latent_pdf: Optional[np.ndarray] = None,
        expected_arrivals_per_period: Optional[float] = None,
    ) -> np.ndarray:
        detect_probs = self._arrival_detection_probability_per_bin(
            inputs,
            latent_pdf=latent_pdf,
            expected_arrivals_per_period=expected_arrivals_per_period,
        )
        dead_bins = self._deadtime_bins(inputs)
        state = self._stationary_period_start_distribution_from_detect_probs(
            detect_probs,
            dead_bins,
        )
        detected = np.zeros_like(detect_probs, dtype=float)
        for bin_idx, detect_prob in enumerate(detect_probs):
            available = float(state[0]) if state.size > 0 else 0.0
            detected[bin_idx] = available * float(detect_prob)
            state = self._advance_state(state, float(detect_prob), dead_bins)
        return np.maximum(detected, 0.0)

    def gated_detection_masses(
        self,
        inputs: StationaryRappInputs,
        latent_pdf: Optional[np.ndarray] = None,
        expected_arrivals_per_period: Optional[float] = None,
    ) -> np.ndarray:
        time_detected = self.time_bin_detection_masses(
            inputs,
            latent_pdf=latent_pdf,
            expected_arrivals_per_period=expected_arrivals_per_period,
        )
        gate_matrix = self._effective_gate_matrix(inputs)
        return np.maximum(np.asarray(gate_matrix @ time_detected, dtype=float), 0.0)

    def gated_detection_probabilities(
        self,
        inputs: StationaryRappInputs,
        latent_pdf: Optional[np.ndarray] = None,
        expected_arrivals_per_period: Optional[float] = None,
    ) -> np.ndarray:
        masses = self.gated_detection_masses(
            inputs,
            latent_pdf=latent_pdf,
            expected_arrivals_per_period=expected_arrivals_per_period,
        )
        total = float(np.sum(masses))
        if total <= 0.0:
            return np.full(masses.shape, 1.0 / max(masses.size, 1), dtype=float)
        return masses / total

    def log_likelihood(self, inputs: StationaryRappInputs) -> float:
        observed = np.maximum(np.asarray(inputs.detected_counts, dtype=float).reshape(-1), 0.0)
        if observed.size == 0 or float(np.sum(observed)) <= 0.0:
            return float("-inf")
        probs = self.gated_detection_probabilities(inputs)
        return float(np.sum(observed * np.log(np.maximum(probs, 1e-300))))

    def reconstruct_arrival_histogram(
        self,
        inputs: StationaryRappInputs,
        max_iter: int = 200,
        smoothness: float = 1e-4,
    ) -> np.ndarray:
        observed = np.maximum(np.asarray(inputs.detected_counts, dtype=float).reshape(-1), 0.0)
        if observed.size == 0 or float(np.sum(observed)) <= 0.0:
            return np.zeros_like(np.asarray(inputs.latent_pdf, dtype=float).reshape(-1))

        obs_total = float(np.sum(observed))
        obs_norm = observed / obs_total
        gate_matrix = self._effective_gate_matrix(inputs)
        init_arrival = np.maximum(np.asarray(inputs.latent_pdf, dtype=float).reshape(-1), 0.0)
        if gate_matrix.size > 0 and observed.size == gate_matrix.shape[0]:
            pseudo = np.linalg.pinv(gate_matrix, rcond=1e-6)
            backprojected = np.maximum(np.asarray(pseudo @ observed, dtype=float).reshape(-1), 0.0)
            if float(np.sum(backprojected)) > 0.0:
                init_arrival = backprojected
        init_pdf = self._normalize_pdf(init_arrival)
        inverse_basis = self._build_inverse_basis(inputs, gate_matrix, init_arrival)
        init_total = max(
            float(inputs.expected_arrivals_per_period),
            float(np.sum(init_arrival)),
            float(np.sum(observed)),
            1e-6,
        )
        init_pred = self.gated_detection_masses(
            inputs,
            latent_pdf=init_pdf,
            expected_arrivals_per_period=init_total,
        )
        init_pred_total = float(np.sum(init_pred))
        if init_pred_total > 0.0:
            init_pred_norm = init_pred / init_pred_total
            init_match_error = float(np.max(np.abs(init_pred_norm - obs_norm)))
            total_log_error = abs(np.log(max(init_pred_total, 1e-300)) - np.log(max(obs_total, 1e-300)))
            if init_match_error <= 5e-3 and total_log_error <= 5e-2:
                return init_pdf * init_total
        if inverse_basis is None:
            init_shape_params = np.log(np.maximum(init_pdf, 1e-12))
        else:
            basis_scores = inverse_basis.T @ init_pdf
            init_shape_params = np.log(np.maximum(basis_scores, 1e-12))
        x0 = np.concatenate([init_shape_params, [np.log(init_total)]])
        logit_bounds = [(-25.0, 25.0)] * init_pdf.size
        if inverse_basis is not None:
            logit_bounds = [(-25.0, 25.0)] * inverse_basis.shape[1]
        total_lower = np.log(max(init_total * 1e-3, 1e-9))
        total_upper = np.log(max(init_total * 1e3, init_total + 1e-9))
        bounds = logit_bounds + [(total_lower, total_upper)]

        def objective(params: np.ndarray) -> float:
            weights = self._softmax(params[:-1])
            if inverse_basis is None:
                shape = weights
            else:
                shape = np.asarray(inverse_basis @ weights, dtype=float).reshape(-1)
                shape = self._normalize_pdf(shape)
            total_arrivals = float(np.exp(params[-1]))
            pred_masses = self.gated_detection_masses(
                inputs,
                latent_pdf=shape,
                expected_arrivals_per_period=total_arrivals,
            )
            pred_total = float(np.sum(pred_masses))
            if pred_total <= 0.0:
                return 1e12
            pred_norm = pred_masses / pred_total
            kl = float(np.sum(obs_norm * (np.log(np.maximum(obs_norm, 1e-300)) - np.log(np.maximum(pred_norm, 1e-300)))))
            total_penalty = (np.log(max(pred_total, 1e-300)) - np.log(max(obs_total, 1e-300))) ** 2
            curvature = np.diff(np.log(np.maximum(shape, 1e-12)), 2)
            smooth_penalty = float(np.sum(curvature ** 2))
            return kl + 0.25 * total_penalty + float(smoothness) * smooth_penalty

        result = minimize(
            objective,
            x0,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": int(max_iter)},
        )
        params = np.asarray(result.x if result.success else x0, dtype=float)
        weights = self._softmax(params[:-1])
        if inverse_basis is None:
            shape = weights
        else:
            shape = np.asarray(inverse_basis @ weights, dtype=float).reshape(-1)
            shape = self._normalize_pdf(shape)
        total_arrivals = float(np.exp(params[-1]))
        return shape * total_arrivals

    def fisher_information(self, inputs: StationaryRappInputs, param_value: float) -> Optional[float]:
        del param_value  # The caller supplies the local plus/minus PDFs around the parameter of interest.
        if inputs.latent_pdf_plus is None or inputs.latent_pdf_minus is None:
            return None

        p_cen = self.gated_detection_probabilities(inputs)
        p_plus = self.gated_detection_probabilities(inputs, latent_pdf=inputs.latent_pdf_plus)
        p_minus = self.gated_detection_probabilities(inputs, latent_pdf=inputs.latent_pdf_minus)
        delta = float(max(abs(getattr(inputs, "param_delta", 1.0)), 1e-15))
        dP = (p_plus - p_minus) / max(2.0 * delta, 1e-15)
        p_safe = np.maximum(p_cen, 1e-15)
        expected_detected = float(
            np.sum(
                self.gated_detection_masses(
                    inputs,
                    latent_pdf=inputs.latent_pdf,
                    expected_arrivals_per_period=inputs.expected_arrivals_per_period,
                )
            )
        )
        return float(max(expected_detected, 0.0) * np.sum((dP ** 2) / p_safe))
