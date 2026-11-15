import numpy as np
import pytest
pytest.importorskip("astropy")
pytest.importorskip("reproject")
from astropy.io import fits
from astropy.wcs import WCS
from science.alignment import reproject_to_reference


def test_reproject_to_reference_identity_grid(tmp_path):
    w = WCS(naxis=2)
    w.wcs.crpix = [3.0, 3.0]
    w.wcs.cdelt = [-0.001, 0.001]
    w.wcs.crval = [10.0, 20.0]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    path = tmp_path / "input.fits"
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(np.arange(25.).reshape(5, 5), header=w.to_header(), name="IMAGE")]).writeto(path)
    projected, footprint = reproject_to_reference(path, w, (5, 5))
    assert projected.shape == (5, 5)
    assert np.nanmax(footprint) > 0
