
import numpy as np

from science.detection import (
    _aperture_coverage,
    measure_aperture_photometry,
    compare_source_catalogues,
)


class IdentityWCS:
    def pixel_to_world_values(self, x, y):
        return x, y


def make_source(x=12.0, y=12.0):
    return [{"x": x, "y": y}]


def test_aperture_fully_inside_image_has_complete_coverage():
    valid = np.ones((25, 25), dtype=bool)

    result = _aperture_coverage(valid, 12.0, 12.0, 3.0)

    assert result["image_coverage_fraction"] == 1.0
    assert result["valid_coverage_fraction"] == 1.0


def test_aperture_crossing_image_boundary_has_incomplete_coverage():
    valid = np.ones((25, 25), dtype=bool)

    result = _aperture_coverage(valid, 0.0, 12.0, 3.0)

    assert result["image_coverage_fraction"] < 0.99
    assert result["valid_coverage_fraction"] < 0.99


def test_aperture_with_masked_pixels_has_incomplete_valid_coverage():
    valid = np.ones((25, 25), dtype=bool)
    valid[12, 12] = False

    result = _aperture_coverage(valid, 12.0, 12.0, 3.0)

    assert result["image_coverage_fraction"] == 1.0
    assert result["valid_coverage_fraction"] < 0.99


def test_complete_aperture_returns_flux_and_uncertainty():
    image = np.ones((25, 25), dtype=float) * 10.0
    variance = np.ones((25, 25), dtype=float)
    valid = np.ones((25, 25), dtype=bool)

    result = measure_aperture_photometry(
        image,
        make_source(),
        valid,
        variance=variance,
        aperture_radius_px=3.0,
    )

    assert len(result) == 1
    assert result[0]["aperture_flux"] is not None
    assert result[0]["aperture_flux_error"] is not None
    assert result[0]["aperture_incomplete"] is False
    assert result[0]["aperture_valid_coverage_fraction"] >= 0.99


def test_boundary_truncated_aperture_withholds_flux_and_uncertainty():
    image = np.ones((25, 25), dtype=float) * 10.0
    variance = np.ones((25, 25), dtype=float)
    valid = np.ones((25, 25), dtype=bool)

    result = measure_aperture_photometry(
        image,
        make_source(x=0.0, y=12.0),
        valid,
        variance=variance,
        aperture_radius_px=3.0,
    )

    measurement = result[0]

    assert measurement["aperture_incomplete"] is True
    assert measurement["aperture_truncated_by_image_boundary"] is True
    assert measurement["aperture_flux"] is None
    assert measurement["aperture_flux_error"] is None
    assert measurement["aperture_flux_partial"] is not None


def test_masked_aperture_withholds_flux_and_uncertainty():
    image = np.ones((25, 25), dtype=float) * 10.0
    variance = np.ones((25, 25), dtype=float)
    valid = np.ones((25, 25), dtype=bool)
    valid[12, 12] = False

    result = measure_aperture_photometry(
        image,
        make_source(),
        valid,
        variance=variance,
        aperture_radius_px=3.0,
    )

    measurement = result[0]

    assert measurement["aperture_incomplete"] is True
    assert measurement["aperture_flux"] is None
    assert measurement["aperture_flux_error"] is None
    assert measurement["aperture_valid_coverage_fraction"] < 0.99


def test_incomplete_aperture_prevents_variability_classification():
    reference = [{
        "x": 12.0,
        "y": 12.0,
        "aperture_flux": None,
        "aperture_flux_error": None,
        "aperture_incomplete": True,
        "aperture_coverage_fraction": 0.75,
        "aperture_image_coverage_fraction": 0.75,
        "aperture_truncated_by_image_boundary": True,
    }]

    comparison = [{
        "x": 12.1,
        "y": 12.0,
        "aperture_flux": 100.0,
        "aperture_flux_error": 1.0,
        "aperture_incomplete": False,
        "aperture_coverage_fraction": 1.0,
        "aperture_image_coverage_fraction": 1.0,
        "aperture_truncated_by_image_boundary": False,
    }]

    result = compare_source_catalogues(
        reference,
        comparison,
        IdentityWCS(),
        {"observation_id": "reference"},
        {"observation_id": "comparison"},
    )

    assert len(result) == 1
    candidate = result[0]

    assert candidate["classification"] == "ambiguous/uncertain"
    assert candidate["aperture_incomplete"] is True
    assert candidate["reference_flux"] is None
    assert candidate["flux_change"] is None
    assert candidate["flux_change_significance"] is None
    assert candidate["review_required"] is True
    assert candidate["near_image_boundary"] is True


def test_source_candidate_requires_human_review():
    reference = [{
        "x": 12.0,
        "y": 12.0,
        "aperture_flux": 10.0,
        "aperture_flux_error": 1.0,
    }]

    comparison = [{
        "x": 12.1,
        "y": 12.0,
        "aperture_flux": 16.0,
        "aperture_flux_error": 1.0,
    }]

    result = compare_source_catalogues(
        reference,
        comparison,
        IdentityWCS(),
        {"observation_id": "reference"},
        {"observation_id": "comparison"},
    )

    assert len(result) == 1
    assert result[0]["review_required"] is True
    assert "human validation" in result[0]["scientific_caveat"]
