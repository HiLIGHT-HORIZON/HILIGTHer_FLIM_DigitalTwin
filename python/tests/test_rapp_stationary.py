import numpy as np

from backend.rapp_stationary import RappStationaryModel, StationaryRappInputs
from backend.models import PhysicsConfig
from backend.twin_engine import TwinEngine


def _basic_inputs(deadtime_ns: float = 0.0) -> StationaryRappInputs:
    t = np.linspace(0.0, 7.0, 8)
    pdf = np.array([0.30, 0.24, 0.18, 0.12, 0.08, 0.04, 0.025, 0.015], dtype=float)
    pdf /= np.sum(pdf)
    gate_matrix = np.eye(t.size, dtype=float)
    return StationaryRappInputs(
        period_ns=8.0,
        deadtime_ns=deadtime_ns,
        detected_counts=np.zeros_like(pdf),
        time_vector_ns=t,
        latent_pdf=pdf,
        expected_arrivals_per_period=2.5,
        gate_matrix=gate_matrix,
    )


def test_stationary_forward_without_deadtime_matches_binwise_detection_probability():
    model = RappStationaryModel()
    inputs = _basic_inputs(deadtime_ns=0.0)

    masses = model.time_bin_detection_masses(inputs)
    expected = 1.0 - np.exp(-inputs.latent_pdf * inputs.expected_arrivals_per_period)

    assert np.allclose(masses, expected, atol=1e-10)


def test_stationary_deadtime_reduces_total_detected_counts():
    model = RappStationaryModel()
    no_dt = _basic_inputs(deadtime_ns=0.0)
    with_dt = _basic_inputs(deadtime_ns=2.1)

    total_no_dt = float(np.sum(model.time_bin_detection_masses(no_dt)))
    total_with_dt = float(np.sum(model.time_bin_detection_masses(with_dt)))

    assert total_with_dt < total_no_dt


def test_stationary_period_start_distribution_is_fixed_point():
    model = RappStationaryModel()
    inputs = _basic_inputs(deadtime_ns=2.1)

    start = model.stationary_period_start_distribution(inputs)
    propagated = model._propagate_period_state(
        start,
        model._arrival_detection_probability_per_bin(inputs),
        model._deadtime_bins(inputs),
    )

    assert np.allclose(propagated, start, atol=1e-10)


def test_stationary_coarse_gate_probabilities_normalize():
    model = RappStationaryModel()
    t = np.linspace(0.0, 7.0, 8)
    pdf = np.array([0.30, 0.24, 0.18, 0.12, 0.08, 0.04, 0.025, 0.015], dtype=float)
    pdf /= np.sum(pdf)
    gate_matrix = np.array(
        [
            [1, 1, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 1, 1, 0, 0],
            [0, 0, 0, 0, 0, 0, 1, 1],
        ],
        dtype=float,
    )
    inputs = StationaryRappInputs(
        period_ns=8.0,
        deadtime_ns=2.1,
        detected_counts=np.zeros((3,), dtype=float),
        time_vector_ns=t,
        latent_pdf=pdf,
        expected_arrivals_per_period=3.0,
        gate_matrix=gate_matrix,
    )

    probs = model.gated_detection_probabilities(inputs)

    assert probs.shape == (3,)
    assert np.isclose(float(np.sum(probs)), 1.0, atol=1e-12)
    assert np.all(probs >= 0.0)


def test_stationary_log_likelihood_prefers_true_histogram_family():
    model = RappStationaryModel()
    true_inputs = _basic_inputs(deadtime_ns=2.1)
    observed = model.gated_detection_masses(true_inputs)

    ll_true = model.log_likelihood(
        StationaryRappInputs(
            **{**true_inputs.__dict__, "detected_counts": observed}
        )
    )
    shifted_pdf = np.roll(true_inputs.latent_pdf, 2)
    ll_shifted = model.log_likelihood(
        StationaryRappInputs(
            **{**true_inputs.__dict__, "detected_counts": observed, "latent_pdf": shifted_pdf}
        )
    )

    assert ll_true > ll_shifted


def test_stationary_mchc_inverse_reproduces_observed_gate_histogram():
    model = RappStationaryModel()
    true_inputs = _basic_inputs(deadtime_ns=2.1)
    observed = model.gated_detection_masses(true_inputs)
    inverse_inputs = StationaryRappInputs(
        **{**true_inputs.__dict__, "detected_counts": observed, "latent_pdf": np.full_like(true_inputs.latent_pdf, 1.0 / true_inputs.latent_pdf.size)}
    )

    reconstructed_arrival = model.reconstruct_arrival_histogram(inverse_inputs, max_iter=120)
    predicted = model.gated_detection_masses(
        inverse_inputs,
        latent_pdf=reconstructed_arrival,
        expected_arrivals_per_period=float(np.sum(reconstructed_arrival)),
    )

    assert np.allclose(predicted, observed, atol=5e-2)


def test_stationary_mchc_inverse_handles_short_lifetime_high_flux_with_coarse_gates():
    model = RappStationaryModel()
    t = np.linspace(0.0, 3.5, 8)
    pdf = np.exp(-t / 0.45)
    pdf /= np.sum(pdf)
    gate_matrix = np.array(
        [
            [1, 1, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 1, 0, 0, 0],
            [0, 0, 0, 0, 0, 1, 1, 1],
        ],
        dtype=float,
    )
    true_inputs = StationaryRappInputs(
        period_ns=4.0,
        deadtime_ns=1.0,
        detected_counts=np.zeros((3,), dtype=float),
        time_vector_ns=t,
        latent_pdf=pdf,
        expected_arrivals_per_period=12.0,
        gate_matrix=gate_matrix,
    )
    observed = model.gated_detection_masses(true_inputs)
    inverse_inputs = StationaryRappInputs(
        period_ns=4.0,
        deadtime_ns=1.0,
        detected_counts=observed,
        time_vector_ns=t,
        latent_pdf=np.full_like(pdf, 1.0 / pdf.size),
        expected_arrivals_per_period=12.0,
        gate_matrix=gate_matrix,
    )

    reconstructed_arrival = model.reconstruct_arrival_histogram(inverse_inputs, max_iter=160, smoothness=1e-3)
    predicted = model.gated_detection_masses(
        inverse_inputs,
        latent_pdf=reconstructed_arrival,
        expected_arrivals_per_period=float(np.sum(reconstructed_arrival)),
    )

    assert np.all(np.isfinite(reconstructed_arrival))
    assert float(np.sum(reconstructed_arrival)) > 0.0
    assert np.allclose(predicted, observed, atol=8e-2)


def test_stationary_fisher_information_is_finite_with_explicit_param_delta():
    model = RappStationaryModel()
    inputs = _basic_inputs(deadtime_ns=2.1)
    plus = np.roll(inputs.latent_pdf, -1)
    plus /= np.sum(plus)
    minus = np.roll(inputs.latent_pdf, 1)
    minus /= np.sum(minus)
    fisher_inputs = StationaryRappInputs(
        **{
            **inputs.__dict__,
            "latent_pdf_plus": plus,
            "latent_pdf_minus": minus,
            "param_delta": 0.05,
        }
    )

    fi = model.fisher_information(fisher_inputs, param_value=2.0)

    assert fi is not None
    assert np.isfinite(fi)
    assert fi >= 0.0


def test_twin_engine_exposes_stationary_helpers():
    cfg = PhysicsConfig(
        period=8.0,
        gate_edges=[0.0, 2.0, 4.0, 6.0, 8.0],
        detector_deadtime=1.5,
        dt_override=0.5,
        taus=[1.2],
        use_eirf=False,
    )
    engine = TwinEngine(cfg)
    engine.distill_gates()
    pdf = engine.dt_pdf(engine.time_vector)

    probs, frac = engine._stationary_gate_statistics_from_pdf(pdf, 50.0)
    observed_counts = probs * 40.0
    ll = engine.stationary_mcpdf_log_likelihood(observed_counts, pdf, 50.0)
    arrival = engine.stationary_mchc_reconstruct_arrival_histogram(observed_counts, n_photons=50.0, reference_pdf=pdf)

    assert np.isclose(np.sum(probs), 1.0, atol=1e-9)
    assert frac >= 0.0
    assert np.isfinite(ll)
    assert np.all(np.isfinite(arrival))
    assert np.sum(arrival) > 0.0
