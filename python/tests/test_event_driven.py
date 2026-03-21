import numpy as np

from backend.event_driven import (
    ChannelConfig,
    EventDrivenSimulator,
    ResourceGroupConfig,
    SimulationConfig,
    TabulatedOpticalModel,
)
from backend.models import PhysicsConfig
from backend.twin_engine import TwinEngine


def _uniform_optical_model(lambda_per_frame: float = 12.0) -> TabulatedOpticalModel:
    t = np.linspace(0.0, 1.0, 1001)
    pdf = np.ones_like(t, dtype=float)
    return TabulatedOpticalModel(time_vector=t, pdf=pdf, lambda_per_frame=lambda_per_frame)


def _step_channel(name: str, start: float, end: float, group: str | None = None, priority: int = 0) -> ChannelConfig:
    eps = 1e-9
    times = np.array([0.0, max(start - eps, 0.0), start, end, min(end + eps, 1.0), 1.0], dtype=float)
    values = np.array([0.0, 0.0, 1.0, 1.0, 0.0, 0.0], dtype=float)
    return ChannelConfig(
        name=name,
        acceptance_times=times,
        acceptance_values=values,
        resource_group=group,
        priority=priority,
    )


def test_ideal_poisson_mode_preserves_historical_backend_behavior():
    cfg = PhysicsConfig(
        gate_edges=np.linspace(0.0, 12.5, 5).tolist(),
        gate_rise=0.0,
        gate_fall=0.0,
        timing_jitter=0.0,
    )
    explicit_cfg = cfg.model_copy(update={"simulation_mode": "ideal_poisson"})

    np.random.seed(123)
    counts_default, detections_default = TwinEngine(cfg).simulate_gate_histograms(tau=2.5, n_photons=120, n_repeats=48)
    np.random.seed(123)
    counts_explicit, detections_explicit = TwinEngine(explicit_cfg).simulate_gate_histograms(tau=2.5, n_photons=120, n_repeats=48)

    assert np.array_equal(counts_default, counts_explicit)
    assert np.array_equal(detections_default, detections_explicit)


def test_event_driven_zero_deadtime_bridges_to_ideal_poisson_gate_statistics():
    base_cfg = PhysicsConfig(
        simulation_mode="ideal_poisson",
        gate_edges=np.linspace(0.0, 12.5, 5).tolist(),
        gate_rise=0.0,
        gate_fall=0.0,
        timing_jitter=0.0,
        gate_collection_mode="histogram",
    )
    event_cfg = base_cfg.model_copy(
        update={
            "simulation_mode": "event_driven",
            "event_routing_mode": "exclusive",
            "event_arbitration_rule": "random",
            "event_share_resource_group": False,
            "detector_deadtime": 0.0,
            "b_multihit_mode": True,
        }
    )

    n_repeats = 600
    n_photons = 200
    ideal_counts, _ = TwinEngine(base_cfg).simulate_gate_histograms(tau=2.5, n_photons=n_photons, n_repeats=n_repeats)
    event_counts, _ = TwinEngine(event_cfg).simulate_gate_histograms(tau=2.5, n_photons=n_photons, n_repeats=n_repeats)

    ideal_mean = np.mean(ideal_counts, axis=0)
    event_mean = np.mean(event_counts, axis=0)

    assert np.allclose(event_mean, ideal_mean, rtol=0.2, atol=3.0)


def test_first_hit_capacity_ceiling():
    sim_cfg = SimulationConfig(
        optical_model=_uniform_optical_model(lambda_per_frame=18.0),
        channels=[_step_channel("gate", 0.0, 1.0, group="rg")],
        resource_groups=[ResourceGroupConfig(name="rg", deadtime_mode="none", capacity=1)],
        routing_mode="exclusive",
        arbitration_rule="random",
        n_frames=500,
        seed=7,
    )

    result = EventDrivenSimulator(sim_cfg).run()

    assert np.max(result.counts) <= 1


def test_multihit_capacity_is_monotonic():
    means = []
    for capacity in (1, 2, None):
        sim_cfg = SimulationConfig(
            optical_model=_uniform_optical_model(lambda_per_frame=12.0),
            channels=[_step_channel("gate", 0.0, 1.0, group="rg")],
            resource_groups=[ResourceGroupConfig(name="rg", deadtime_mode="none", capacity=capacity)],
            routing_mode="exclusive",
            arbitration_rule="random",
            n_frames=1200,
            seed=11,
        )
        result = EventDrivenSimulator(sim_cfg).run()
        means.append(float(np.mean(result.counts[:, 0])))

    assert means[0] <= means[1] <= means[2]


def test_deadtime_is_monotonic():
    means = []
    for deadtime in (0.0, 0.03, 0.08):
        sim_cfg = SimulationConfig(
            optical_model=_uniform_optical_model(lambda_per_frame=30.0),
            channels=[_step_channel("gate", 0.0, 1.0, group="rg")],
            resource_groups=[
                ResourceGroupConfig(
                    name="rg",
                    deadtime_mode="none" if deadtime == 0.0 else "nonparalyzable",
                    deadtime_ns=deadtime,
                    capacity=None,
                )
            ],
            routing_mode="exclusive",
            arbitration_rule="random",
            n_frames=1200,
            seed=19,
        )
        result = EventDrivenSimulator(sim_cfg).run()
        means.append(float(np.mean(result.counts[:, 0])))

    assert means[0] >= means[1] >= means[2]


def test_shared_resource_group_reduces_total_counts():
    optical_model = _uniform_optical_model(lambda_per_frame=10.0)
    independent_cfg = SimulationConfig(
        optical_model=optical_model,
        channels=[
            _step_channel("a", 0.0, 1.0, group="a", priority=0),
            _step_channel("b", 0.0, 1.0, group="b", priority=1),
        ],
        resource_groups=[
            ResourceGroupConfig(name="a", deadtime_mode="none", capacity=1),
            ResourceGroupConfig(name="b", deadtime_mode="none", capacity=1),
        ],
        routing_mode="nonexclusive",
        arbitration_rule="all_if_independent",
        n_frames=800,
        seed=23,
    )
    shared_cfg = SimulationConfig(
        optical_model=optical_model,
        channels=[
            _step_channel("a", 0.0, 1.0, group="shared", priority=0),
            _step_channel("b", 0.0, 1.0, group="shared", priority=1),
        ],
        resource_groups=[ResourceGroupConfig(name="shared", deadtime_mode="none", capacity=1)],
        routing_mode="nonexclusive",
        arbitration_rule="all_if_independent",
        n_frames=800,
        seed=23,
    )

    independent = EventDrivenSimulator(independent_cfg).run()
    shared = EventDrivenSimulator(shared_cfg).run()

    independent_total = np.mean(np.sum(independent.counts, axis=1))
    shared_total = np.mean(np.sum(shared.counts, axis=1))

    assert shared_total < independent_total


def test_twin_engine_event_driven_honors_finite_multihit_capacity():
    cfg = PhysicsConfig(
        simulation_mode="event_driven",
        gate_edges=[0.0, 12.5],
        gate_rise=0.0,
        gate_fall=0.0,
        timing_jitter=0.0,
        event_multihit_capacity=1,
        detector_deadtime=0.0,
        event_deadtime_mode="none",
        event_pixel_dwell_time_s=12.5e-9,
    )

    counts, detections = TwinEngine(cfg).simulate_gate_histograms(tau=2.5, n_photons=50, n_repeats=200)

    assert int(np.max(counts)) <= 1
    assert int(np.max(detections)) <= 1


def test_event_driven_parallel_run_returns_valid_shape():
    sim_cfg = SimulationConfig(
        optical_model=_uniform_optical_model(lambda_per_frame=10.0),
        channels=[_step_channel("gate", 0.0, 1.0, group="rg")],
        resource_groups=[ResourceGroupConfig(name="rg", deadtime_mode="none", capacity=None)],
        routing_mode="exclusive",
        arbitration_rule="random",
        n_frames=64,
        seed=101,
        cpu_workers=2,
    )

    result = EventDrivenSimulator(sim_cfg).run()

    assert result.counts.shape == (64, 1)
    assert np.all(result.counts >= 0)


def test_twin_engine_auto_mode_prefers_legacy_when_event_model_not_needed():
    cfg = PhysicsConfig(
        simulation_mode="ideal_poisson",
        simulation_mode_preference="auto",
        detector_deadtime=0.0,
        b_multihit_mode=True,
        event_multihit_capacity=None,
        event_deadtime_mode="nonparalyzable",
    )
    engine = TwinEngine(cfg)
    status = engine.get_simulation_mode_status()

    assert status["effective_mode"] == "ideal_poisson"
    assert status["requires_event_driven"] is False


def test_twin_engine_auto_mode_switches_to_event_driven_for_deadtime():
    cfg = PhysicsConfig(
        simulation_mode="ideal_poisson",
        simulation_mode_preference="auto",
        detector_deadtime=1.0,
        b_multihit_mode=True,
    )
    engine = TwinEngine(cfg)
    status = engine.get_simulation_mode_status()

    assert status["effective_mode"] == "event_driven"
    assert status["requires_event_driven"] is True


def test_twin_engine_manual_event_preference_forces_event_driven():
    cfg = PhysicsConfig(
        simulation_mode="ideal_poisson",
        simulation_mode_preference="event_driven",
        detector_deadtime=0.0,
        b_multihit_mode=True,
    )
    engine = TwinEngine(cfg)
    status = engine.get_simulation_mode_status()

    assert status["effective_mode"] == "event_driven"
    assert status["forced_event_driven"] is True
