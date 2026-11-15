import numpy as np
from astropy.wcs import WCS

from science.pipeline import _frame_covers_center, _make_requested_center_grid


def _frame(shape=(20, 20)):
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [120.0, 20.0]
    wcs.wcs.crpix = [10.5, 10.5]
    wcs.wcs.cdelt = [-0.001, 0.001]
    return {"wcs": wcs, "image": np.ones(shape), "metadata": {
        "requested_center": {"ra_deg": 120.0, "dec_deg": 20.0}
    }}


def test_frame_coverage_rejects_archive_intersection_without_target():
    assert _frame_covers_center(_frame(), 120.0, 20.0)
    assert not _frame_covers_center(_frame(), 120.1, 20.0)


def test_requested_grid_uses_search_center_and_requested_field_size():
    frame = _frame()
    grid, shape = _make_requested_center_grid(frame, 0.1)

    assert shape == (100, 100)
    assert grid.wcs.crval.tolist() == [120.0, 20.0]
    x, y = grid.world_to_pixel_values(120.0, 20.0)
    assert np.isclose(x, 49.5)
    assert np.isclose(y, 49.5)
    # Grid construction leaves the source frame's WCS untouched.
    assert frame["wcs"].wcs.crpix.tolist() == [10.5, 10.5]
