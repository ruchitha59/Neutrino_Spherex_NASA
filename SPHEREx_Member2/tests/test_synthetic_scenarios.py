import numpy as np

from science.alignment import measure_alignment_residuals, _bilinear_variance_to_reference
from science.calibration import estimate_background_offset
from science.detection import extract_difference_candidates, compare_source_catalogues, annotate_candidate_flags
from science.difference import make_difference, significance_difference
from science.quality import build_valid_mask


class IdentityWCS:
    def pixel_to_world_values(self, x, y):
        return x, y


def star_field(shape=(50, 50)):
    image = np.zeros(shape, dtype=float)
    for x, y, amp in [(8, 8, 20), (20, 10, 18), (35, 8, 25),
                      (10, 30, 22), (30, 32, 19), (42, 40, 21)]:
        image[y, x] = amp
    return image


def test_synthetic_identical_and_stationary_sources_have_zero_difference():
    image = star_field()
    difference = make_difference(image, image.copy())
    assert np.nanmax(np.abs(difference)) == 0.0


def test_synthetic_known_one_pixel_shift_fails_registration_gate():
    reference = star_field()
    comparison = np.roll(reference, shift=1, axis=1)
    result = measure_alignment_residuals(
        reference, comparison,
        threshold_sigma=2.0,
        max_match_distance_px=3.0,
        min_matches=4,
    )
    assert result["matches"] >= 4
    assert result["passed"] is False
    assert result["median_offset_px"] >= 0.9


def test_synthetic_unshifted_background_stars_pass_registration_gate():
    reference = star_field()
    comparison = reference.copy()
    result = measure_alignment_residuals(
        reference, comparison,
        threshold_sigma=2.0,
        min_matches=4,
    )
    assert result["passed"] is True
    assert result["median_offset_px"] == 0.0


def test_synthetic_brightness_increase_and_decrease_have_expected_sign():
    reference = np.zeros((9, 9), dtype=float)
    comparison = reference.copy()
    reference[4, 4] = 10.0
    comparison[4, 4] = 15.0
    comparison[2, 2] = -3.0
    reference[2, 2] = 0.0
    diff = make_difference(reference, comparison)
    assert diff[4, 4] > 0
    assert diff[2, 2] < 0


def test_synthetic_noise_significance_uses_variance():
    ref = np.ones((4, 4))
    cmp = ref + 2.0
    var_ref = np.ones((4, 4))
    var_cmp = np.ones((4, 4))
    sig = significance_difference(ref, cmp, var_ref, var_cmp)
    np.testing.assert_allclose(sig, np.ones((4, 4)) * np.sqrt(2))


def test_synthetic_nan_bad_pixel_and_incomplete_coverage_are_masked():
    science = np.ones((5, 5))
    science[1, 1] = np.nan
    flags = np.zeros((5, 5), dtype=np.int32)
    flags[2, 2] = 1
    footprint = np.ones((5, 5))
    footprint[3, 3] = 0
    mask, counts = build_valid_mask(
        science, flags=flags, footprint=footprint,
        flag_definitions={"TRANSIENT": {"mask": 1, "description": "transient"}},
    )
    assert not mask[1, 1]
    assert not mask[2, 2]
    assert not mask[3, 3]
    assert counts["excluded_pixels"] == 3


def test_synthetic_background_offset_is_diagnostic_only():
    ref = np.zeros((8, 8), dtype=float)
    cmp = np.full((8, 8), 2.5, dtype=float)
    mask = np.ones((8, 8), dtype=bool)
    result = estimate_background_offset(ref, cmp, mask)
    assert result["available"] is True
    assert result["offset"] == 2.5
    assert result["applied"] is False


def test_synthetic_difference_component_is_only_ambiguous_candidate():
    significance = np.zeros((12, 12), dtype=float)
    difference = np.zeros((12, 12), dtype=float)
    significance[5:7, 5:7] = 6.0
    difference[5:7, 5:7] = 4.0
    valid = np.ones((12, 12), dtype=bool)
    candidates = extract_difference_candidates(
        significance, difference, valid, IdentityWCS(), ["ref", "cmp"],
        threshold_sigma=5.0, min_pixels=2,
    )
    assert len(candidates) == 1
    assert candidates[0]["classification"] == "ambiguous/uncertain"
    assert "not a confirmed discovery" in candidates[0]["scientific_caveat"]


def test_synthetic_source_catalogue_classifies_fixed_centroid_flux_change():
    ref = [{"x": 5.0, "y": 6.0, "aperture_flux": 10.0, "aperture_flux_error": 1.0}]
    cmp = [{"x": 5.1, "y": 6.0, "aperture_flux": 16.0, "aperture_flux_error": 1.0}]
    rows = compare_source_catalogues(
        ref, cmp, IdentityWCS(), {"observation_id": "r"}, {"observation_id": "c"}
    )
    assert rows[0]["classification"] == "possible brightness variability"
    assert rows[0]["flux_change"] == 6.0
    assert rows[0]["flux_change_significance"] > 3.0


def test_synthetic_source_catalogue_marks_centroid_shift_as_possible_motion():
    ref = [{"x": 5.0, "y": 6.0, "aperture_flux": 10.0, "aperture_flux_error": 2.0}]
    cmp = [{"x": 6.5, "y": 6.0, "aperture_flux": 10.0, "aperture_flux_error": 2.0}]
    rows = compare_source_catalogues(
        ref, cmp, IdentityWCS(), {"observation_id": "r"}, {"observation_id": "c"}
    )
    assert rows[0]["classification"] == "possible motion"
    assert rows[0]["position_change_px"] == 1.5


def test_candidate_quality_flags_are_attached_from_actual_bit_masks():
    candidate = {"pixel_x": 1.0, "pixel_y": 1.0, "quality_flags": []}
    frame = {
        "flags": np.array([[0, 0], [0, 1]], dtype=np.int32),
        "flag_definitions": {"TRANSIENT": {"mask": 1, "description": "transient"}},
    }
    result = annotate_candidate_flags([candidate], frame, frame)
    assert result[0]["quality_flags"] == ["comparison:TRANSIENT", "reference:TRANSIENT"]


class HalfPixelShiftWCS:
    def pixel_to_world_values(self, x, y):
        return x + 0.5, y + 0.5

    def world_to_pixel_values(self, ra, dec):
        return ra, dec


def test_synthetic_variance_reprojection_uses_squared_bilinear_weights():
    variance = np.full((3, 3), 4.0)
    projected = _bilinear_variance_to_reference(
        variance, HalfPixelShiftWCS(), HalfPixelShiftWCS(), (3, 3)
    )
    # For an equal four-pixel interpolation, sum(w_i^2 * variance_i)
    # = 4 * (0.25^2 * 4) = 1.
    assert projected[0, 0] == 1.0
