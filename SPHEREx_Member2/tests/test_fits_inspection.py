import numpy as np
import pytest
fits = pytest.importorskip("astropy.io.fits")
from astropy.wcs import WCS
from science.inspect_fits import inspect_fits


def test_inspect_fits_selects_image_extension_not_primary(tmp_path):
    w = WCS(naxis=2)
    w.wcs.crpix = [2.0, 2.0]
    w.wcs.cdelt = [-0.001, 0.001]
    w.wcs.crval = [10.0, 20.0]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    primary = fits.PrimaryHDU()
    image = fits.ImageHDU(np.ones((3, 3)), header=w.to_header(), name="IMAGE")
    image.header["BUNIT"] = "MJy / sr"
    path = tmp_path / "synthetic.fits"
    fits.HDUList([primary, image]).writeto(path)
    report = inspect_fits(path)
    assert report[0]["is_selected_science"] is False
    assert report[1]["is_selected_science"] is True
    assert report[1]["wcs_valid"] is True
