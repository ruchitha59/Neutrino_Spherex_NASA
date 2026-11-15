import numpy as np

from science.noise_covariance import (
    component_correlation_factor,
    covariance_factor_for_weights,
    estimate_noise_correlation,
)


def test_empirical_correlation_finds_neighboring_noise_dependence():
    rng = np.random.default_rng(41)
    noise = rng.normal(size=(160, 160))
    smoothed = noise + 0.6 * np.roll(noise, 1, axis=1)
    result = estimate_noise_correlation(smoothed, np.ones_like(noise, dtype=bool))
    center = result["kernel"].shape[0] // 2
    assert result["available"]
    assert result["kernel"][center, center + 1] > 0.2
    assert result["kernel"][center, center - 1] == result["kernel"][center, center + 1]


def test_correlated_aperture_variance_exceeds_diagonal_variance():
    rho = np.zeros((3, 3), dtype=float)
    rho[1, 1] = 1.0
    rho[1, 0] = rho[1, 2] = 0.3
    rho[0, 1] = rho[2, 1] = 0.2
    weights = np.ones((5, 5), dtype=float)
    variance = np.ones_like(weights)
    result = covariance_factor_for_weights(weights, variance, rho)
    assert result["covariance_variance"] > result["diagonal_variance"]
    assert result["correlation_factor"] > 1.0


def test_connected_component_correlation_factor_uses_component_shape():
    rho = np.zeros((3, 3), dtype=float)
    rho[1, 1] = 1.0
    rho[1, 2] = rho[1, 0] = 0.5
    component = np.zeros((7, 7), dtype=bool)
    component[3, 2:5] = True
    assert component_correlation_factor(component, rho) > 1.0


def test_covariance_estimation_reports_insufficient_background():
    result = estimate_noise_correlation(np.ones((3, 3)), np.ones((3, 3), bool))
    assert not result["available"]
