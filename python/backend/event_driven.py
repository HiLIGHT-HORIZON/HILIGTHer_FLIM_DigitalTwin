from __future__ import annotations
import os
from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np


class OpticalModel(ABC):
    """
    Shared latent optical model interface.

    The ideal Poisson backend and the event-driven backend are expected to use
    the same latent optical model, differing only in the detection model.
    """

    @abstractmethod
    def expected_count_per_frame(self) -> float:
        """Return the expected latent event count per frame."""

    @abstractmethod
    def sample_arrival_times(self, rng: np.random.Generator, n_events: int) -> np.ndarray:
        """Sample latent event arrival times for one frame."""


@dataclass
class ChannelConfig:
    """
    Logical detection channel with a time-dependent acceptance function.

    Acceptance can be defined either as a callable or as a tabulated waveform
    over `acceptance_times`. The returned values are interpreted as Bernoulli
    acceptance probabilities in [0, 1].
    """

    name: str
    acceptance_times: np.ndarray
    acceptance_values: np.ndarray
    resource_group: Optional[str] = None
    priority: int = 0
    acceptance_fn: Optional[Callable[[float], float]] = None
    period_ns: Optional[float] = None

    def acceptance_probability(self, event_time: float) -> float:
        sample_time = float(event_time)
        if self.period_ns is not None and self.period_ns > 0:
            sample_time = float(np.mod(sample_time, float(self.period_ns)))
        if self.acceptance_fn is not None:
            value = float(self.acceptance_fn(sample_time))
        else:
            value = float(
                np.interp(
                    sample_time,
                    np.asarray(self.acceptance_times, dtype=float),
                    np.asarray(self.acceptance_values, dtype=float),
                    left=0.0,
                    right=0.0,
                )
            )
        return float(np.clip(value, 0.0, 1.0))


@dataclass
class ResourceGroupConfig:
    """
    Shared electronics resource group.

    `capacity=None` means no per-frame capacity ceiling.
    """

    name: str
    deadtime_mode: str = "none"  # none, nonparalyzable, paralyzable
    deadtime_ns: float = 0.0
    capacity: Optional[int] = None
    period_ns: Optional[float] = None


@dataclass
class ResourceState:
    """Mutable per-frame state for one resource group."""

    ready_time: float = -np.inf
    accepted_hits: int = 0
    period_index: int = -1


@dataclass
class SimulationConfig:
    """Configuration for one event-driven simulation run."""

    optical_model: OpticalModel
    channels: List[ChannelConfig]
    resource_groups: List[ResourceGroupConfig] = field(default_factory=list)
    routing_mode: str = "exclusive"  # exclusive, nonexclusive
    arbitration_rule: str = "random"  # random, priority, all_if_independent
    n_frames: int = 1
    seed: Optional[int] = None
    return_timestamps: bool = False
    cpu_workers: int = 1


@dataclass
class SimulationResult:
    """Counts per frame per channel, with optional accepted timestamps."""

    counts: np.ndarray
    timestamps: Optional[List[List[np.ndarray]]] = None


@dataclass
class TabulatedOpticalModel(OpticalModel):
    """
    Optical model backed by a tabulated normalized PDF over time.

    This is useful both in tests and as the adapter target for the Digital Twin.
    """

    time_vector: np.ndarray
    pdf: np.ndarray
    lambda_per_frame: float
    period_ns: Optional[float] = None
    frame_duration_ns: Optional[float] = None

    def __post_init__(self) -> None:
        self.time_vector = np.asarray(self.time_vector, dtype=float)
        pdf = np.asarray(self.pdf, dtype=float)
        pdf = np.maximum(pdf, 0.0)
        total = float(np.sum(pdf))
        if total <= 0.0:
            pdf = np.zeros_like(self.time_vector, dtype=float)
            pdf[0] = 1.0
            total = 1.0
        self.pdf = pdf / total
        self._cdf = np.cumsum(self.pdf)
        self._cdf[-1] = 1.0
        self.lambda_per_frame = float(max(self.lambda_per_frame, 0.0))
        if self.period_ns is None:
            self.period_ns = float(self.time_vector[-1] - self.time_vector[0]) if self.time_vector.size > 1 else 0.0
        if self.frame_duration_ns is None or self.frame_duration_ns <= 0.0:
            self.frame_duration_ns = float(max(self.period_ns or 0.0, 0.0))

    def expected_count_per_frame(self) -> float:
        return self.lambda_per_frame

    def sample_arrival_times(self, rng: np.random.Generator, n_events: int) -> np.ndarray:
        n_events = int(max(n_events, 0))
        if n_events <= 0:
            return np.zeros((0,), dtype=float)
        if not self.period_ns or self.frame_duration_ns <= self.period_ns + 1e-12:
            u = rng.random(n_events)
            return np.interp(u, self._cdf, self.time_vector)

        out: List[float] = []
        frame_duration = float(self.frame_duration_ns)
        period = float(self.period_ns)
        n_periods = max(int(np.ceil(frame_duration / max(period, 1e-12))), 1)
        while len(out) < n_events:
            batch = max(n_events - len(out), 1)
            u = rng.random(batch)
            intra = np.interp(u, self._cdf, self.time_vector)
            pulse_idx = rng.integers(0, n_periods, size=batch)
            absolute = (pulse_idx.astype(float) * period) + intra
            valid = absolute <= frame_duration
            if np.any(valid):
                out.extend(absolute[valid].tolist())
        return np.asarray(out[:n_events], dtype=float)


class EventDrivenSimulator:
    """
    Chronological event-driven detection backend.

    This backend shares the same latent optical model as the ideal Poisson
    backend, but replaces the count-generation stage with an explicit
    event-by-event detection model including routing, arbitration, deadtime,
    and shared resource constraints.
    """

    def __init__(self, config: SimulationConfig):
        self.config = config
        self._channels = list(config.channels)
        self._resource_configs = self._build_resource_config_map()
        self._channel_resource_keys = [
            channel.resource_group if channel.resource_group else f"__channel_{idx}"
            for idx, channel in enumerate(self._channels)
        ]

    def _build_resource_config_map(self) -> Dict[str, ResourceGroupConfig]:
        config_map = {group.name: group for group in self.config.resource_groups}
        for idx, channel in enumerate(self._channels):
            key = channel.resource_group if channel.resource_group else f"__channel_{idx}"
            if key not in config_map:
                config_map[key] = ResourceGroupConfig(name=key)
        return config_map

    def _pick_channel(self, candidates: Sequence[int], rng: np.random.Generator) -> int:
        if len(candidates) == 1:
            return int(candidates[0])
        rule = str(self.config.arbitration_rule).lower()
        if rule == "random":
            return int(rng.choice(np.asarray(candidates, dtype=int)))
        ranked = sorted(
            (self._channels[idx].priority, idx)
            for idx in candidates
        )
        return int(ranked[0][1])

    def _resolve_candidates(self, candidate_indices: Sequence[int], rng: np.random.Generator) -> List[int]:
        if not candidate_indices:
            return []

        grouped: Dict[str, List[int]] = {}
        for idx in candidate_indices:
            grouped.setdefault(self._channel_resource_keys[idx], []).append(int(idx))

        selected_per_group = [self._pick_channel(indices, rng) for indices in grouped.values()]
        routing_mode = str(self.config.routing_mode).lower()
        arbitration_rule = str(self.config.arbitration_rule).lower()

        if routing_mode == "nonexclusive":
            return selected_per_group

        if arbitration_rule == "all_if_independent":
            return selected_per_group

        return [self._pick_channel(selected_per_group, rng)]

    @staticmethod
    def _attempt_resource_accept(
        event_time: float,
        resource_cfg: ResourceGroupConfig,
        resource_state: ResourceState,
    ) -> bool:
        period_ns = float(resource_cfg.period_ns) if resource_cfg.period_ns is not None else 0.0
        if period_ns > 0.0:
            current_period = int(np.floor(float(event_time) / period_ns))
            if current_period != int(resource_state.period_index):
                resource_state.period_index = current_period
                resource_state.accepted_hits = 0

        capacity_ok = (
            resource_cfg.capacity is None
            or resource_state.accepted_hits < int(resource_cfg.capacity)
        )
        deadtime_mode = str(resource_cfg.deadtime_mode).lower()
        deadtime_ns = float(max(resource_cfg.deadtime_ns, 0.0))
        deadtime_ok = True if deadtime_mode == "none" else float(event_time) >= float(resource_state.ready_time)
        accepted = bool(capacity_ok and deadtime_ok)

        if deadtime_mode == "paralyzable":
            resource_state.ready_time = float(event_time) + deadtime_ns
        elif accepted and deadtime_mode == "nonparalyzable":
            resource_state.ready_time = float(event_time) + deadtime_ns

        if accepted:
            resource_state.accepted_hits += 1

        return accepted

    def _run_serial(self) -> SimulationResult:
        rng = np.random.default_rng(self.config.seed)
        n_frames = int(max(self.config.n_frames, 0))
        n_channels = len(self._channels)
        counts = np.zeros((n_frames, n_channels), dtype=np.int64)
        timestamps: Optional[List[List[List[float]]]] = None
        if self.config.return_timestamps:
            timestamps = [[[] for _ in range(n_channels)] for _ in range(n_frames)]

        lambda_per_frame = float(max(self.config.optical_model.expected_count_per_frame(), 0.0))

        for frame_idx in range(n_frames):
            resource_states = {name: ResourceState() for name in self._resource_configs}
            n_events = int(rng.poisson(lambda_per_frame))
            if n_events <= 0:
                continue

            arrival_times = np.asarray(
                self.config.optical_model.sample_arrival_times(rng, n_events),
                dtype=float,
            )
            if arrival_times.size == 0:
                continue
            arrival_times.sort()

            for event_time in arrival_times:
                candidate_indices: List[int] = []
                for channel_idx, channel in enumerate(self._channels):
                    accept_prob = channel.acceptance_probability(float(event_time))
                    if accept_prob <= 0.0:
                        continue
                    if accept_prob >= 1.0 or rng.random() < accept_prob:
                        candidate_indices.append(channel_idx)

                for channel_idx in self._resolve_candidates(candidate_indices, rng):
                    resource_key = self._channel_resource_keys[channel_idx]
                    resource_cfg = self._resource_configs[resource_key]
                    if self._attempt_resource_accept(float(event_time), resource_cfg, resource_states[resource_key]):
                        counts[frame_idx, channel_idx] += 1
                        if timestamps is not None:
                            timestamps[frame_idx][channel_idx].append(float(event_time))

        finalized_timestamps: Optional[List[List[np.ndarray]]] = None
        if timestamps is not None:
            finalized_timestamps = [
                [np.asarray(channel_times, dtype=float) for channel_times in frame_times]
                for frame_times in timestamps
            ]

        return SimulationResult(counts=counts, timestamps=finalized_timestamps)

    def run(self) -> SimulationResult:
        n_frames = int(max(self.config.n_frames, 0))
        requested_workers = int(max(getattr(self.config, "cpu_workers", 1), 1))
        if n_frames <= 1 or requested_workers <= 1:
            return self._run_serial()

        max_workers = min(requested_workers, max(os.cpu_count() or 1, 1), n_frames)
        if max_workers <= 1 or n_frames < 32:
            return self._run_serial()

        base_seed = int(self.config.seed) if self.config.seed is not None else int(np.random.SeedSequence().entropy)
        chunk_sizes = [n_frames // max_workers] * max_workers
        for idx in range(n_frames % max_workers):
            chunk_sizes[idx] += 1
        chunk_sizes = [size for size in chunk_sizes if size > 0]
        child_sequences = np.random.SeedSequence(base_seed).spawn(len(chunk_sizes))

        chunk_cfgs: List[SimulationConfig] = []
        for chunk_size, seed_seq in zip(chunk_sizes, child_sequences):
            cfg = deepcopy(self.config)
            cfg.n_frames = int(chunk_size)
            cfg.seed = int(seed_seq.generate_state(1, dtype=np.uint32)[0])
            cfg.cpu_workers = 1
            chunk_cfgs.append(cfg)

        try:
            with ProcessPoolExecutor(max_workers=len(chunk_cfgs)) as pool:
                chunk_results = list(pool.map(_run_event_driven_chunk, chunk_cfgs))
        except Exception:
            return self._run_serial()

        counts = np.vstack([result.counts for result in chunk_results]) if chunk_results else np.zeros((0, len(self._channels)), dtype=np.int64)
        timestamps: Optional[List[List[np.ndarray]]] = None
        if self.config.return_timestamps:
            timestamps = []
            for result in chunk_results:
                timestamps.extend(result.timestamps or [])
        return SimulationResult(counts=counts, timestamps=timestamps)


def _run_event_driven_chunk(config: SimulationConfig) -> SimulationResult:
    return EventDrivenSimulator(config)._run_serial()
