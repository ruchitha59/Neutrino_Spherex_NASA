import numpy as np
import pytest

from science.difference import make_difference, significance_difference


def test_difference_uses_comparison_minus_reference():
    ref = np.array([[1.0, 2.0], [3.0, 4.0]])
    cmp = np.array([[2.0, 1.0], [3.0, 6.0]])
    result = make_difference(ref, cmp)
    np.testing.assert_allclose(result, [[1.0, -1.0], [0.0, 2.0]])


def test_difference_preserves_invalid_pixels():
    ref = np.array([[1.0, np.nan], [3.0, 4.0]])
    cmp = np.array([[2.0, 2.0], [np.inf, 5.0]])
    result = make_difference(ref, cmp)
    assert np.isfinite(result[0, 0])
    assert np.isnan(result[0, 1])
    assert np.isnan(result[1, 0])


def test_difference_rejects_shape_mismatch():
    with pytest.raises(ValueError):
        make_difference(np.zeros((2, 2)), np.zeros((3, 2)))


def test_significance_matches_variance_formula():
    ref = np.array([[1.0, 1.0]])
    cmp = np.array([[3.0, 0.0]])
    rv = np.array([[1.0, 1.0]])
    cv = np.array([[3.0, 3.0]])
    result = significance_difference(ref, cmp, rv, cv)
    np.testing.assert_allclose(result, [[1.0, -0.5]])


def test_significance_masks_negative_variance_and_zero_denominator():
    ref = np.array([[1.0, 1.0, 1.0]])
    cmp = np.array([[2.0, 2.0, 2.0]])
    rv = np.array([[1.0, -1.0, 0.0]])
    cv = np.array([[1.0, 1.0, 0.0]])
    result = significance_difference(ref, cmp, rv, cv)
    assert result[0, 0] == pytest.approx(1 / np.sqrt(2))
    assert np.isnan(result[0, 1])
    assert np.isnan(result[0, 2])
