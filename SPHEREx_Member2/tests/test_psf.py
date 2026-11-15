
import numpy as np
import pytest
from astropy.io import fits

from science.psf import (
    load_epsf_grid,
    select_epsf_model,
    epsf_diagnostics,
)


def make_synthetic_epsf_fits(path):
    """Create a small synthetic FITS file with a 2x2 EPSF grid."""
    primary = fits.PrimaryHDU()

    image = fits.ImageHDU(
        np.ones((29, 29), dtype=float),
        name="IMAGE",
    )

    # Auxiliary linear WCS: zero-based image pixel (0, 0) maps to (50, 50).
    image.header["CRPIX1A"] = 1.0
    image.header["CRPIX2A"] = 1.0
    image.header["CRVAL1A"] = 50.0
    image.header["CRVAL2A"] = 50.0
    image.header["CDELT1A"] = 1.0
    image.header["CDELT2A"] = 1.0
    image.header["CTYPE1A"] = "LINEAR"
    image.header["CTYPE2A"] = "LINEAR"
    image.header["CUNIT1A"] = "pixel"
    image.header["CUNIT2A"] = "pixel"

    # Include celestial SIP keywords to ensure they are not applied to
    # the auxiliary linear WCS.
    image.header["CTYPE1"] = "RA---TAN-SIP"
    image.header["CTYPE2"] = "DEC--TAN-SIP"
    image.header["A_ORDER"] = 2
    image.header["B_ORDER"] = 2
    image.header["A_2_0"] = 0.001
    image.header["B_0_2"] = 0.001

    binx = np.array([0, 1, 0, 1], dtype=np.int32)
    biny = np.array([0, 0, 1, 1], dtype=np.int32)
    xcenter = np.array([50, 150, 50, 150], dtype=np.float32)
    ycenter = np.array([50, 50, 150, 150], dtype=np.float32)

    models = np.zeros((4, 33, 33), dtype=np.float64)
    models[:, 16, 16] = 1.0

    columns = [
        fits.Column(name="BINX", format="J", array=binx),
        fits.Column(name="BINY", format="J", array=biny),
        fits.Column(name="XCENTER", format="E", array=xcenter),
        fits.Column(name="YCENTER", format="E", array=ycenter),
        fits.Column(name="XWIDTH", format="E", array=np.full(4, 100.0)),
        fits.Column(name="YWIDTH", format="E", array=np.full(4, 100.0)),
        fits.Column(name="NSTAR", format="J", array=np.full(4, 100)),
        fits.Column(name="NEFF_MEAN", format="E", array=np.full(4, 5.0)),
        fits.Column(name="CWAVE", format="E", array=np.full(4, 4.8)),
        fits.Column(name="CBAND", format="E", array=np.full(4, 0.04)),
        fits.Column(
            name="EPSF",
            format="1089D",
            dim="(33,33)",
            array=models,
        ),
    ]

    epsf = fits.BinTableHDU.from_columns(columns, name="EPSF")
    epsf.header["OVSMPX"] = 5
    epsf.header["OVSMPY"] = 5
    epsf.header["DETECTOR"] = 6
    epsf.header["DETCOORD"] = "sky"

    fits.HDUList([primary, image, epsf]).writeto(path)


def test_load_epsf_grid_reads_models_and_sampling(tmp_path):
    path = tmp_path / "synthetic_epsf.fits"
    make_synthetic_epsf_fits(path)

    grid = load_epsf_grid(path)

    assert grid["model_count"] == 4
    assert grid["model_shape"] == (33, 33)
    assert grid["oversampling_x"] == 5
    assert grid["oversampling_y"] == 5
    assert grid["detector"] == 6
    assert grid["models"].shape == (4, 33, 33)


def test_select_epsf_model_uses_auxiliary_coordinates(tmp_path):
    path = tmp_path / "synthetic_epsf.fits"
    make_synthetic_epsf_fits(path)

    grid = load_epsf_grid(path)
    selected = select_epsf_model(grid, x=10, y=10)

    assert selected["binx"] == 0
    assert selected["biny"] == 0
    assert selected["aux_x"] == pytest.approx(60.0)
    assert selected["aux_y"] == pytest.approx(60.0)
    assert selected["distance_px"] == pytest.approx(np.sqrt(200))
    assert selected["within_grid_coverage"] is True
    assert selected["cwave_um"] == pytest.approx(4.8)
    assert selected["epsf"].shape == (33, 33)


def test_selection_preserves_original_oversampled_array(tmp_path):
    path = tmp_path / "synthetic_epsf.fits"
    make_synthetic_epsf_fits(path)

    selected = select_epsf_model(load_epsf_grid(path), 10, 10)

    assert selected["epsf"].shape == (33, 33)
    assert selected["oversampling_x"] == 5
    assert selected["oversampling_y"] == 5
    assert selected["epsf"].sum() == pytest.approx(1.0)


def test_selection_reports_position_outside_grid_coverage(tmp_path):
    path = tmp_path / "synthetic_epsf.fits"
    make_synthetic_epsf_fits(path)

    selected = select_epsf_model(load_epsf_grid(path), 1000, 1000)

    assert selected["within_grid_coverage"] is False
    assert selected["warnings"]


def test_selection_rejects_non_finite_pixel_coordinates(tmp_path):
    path = tmp_path / "synthetic_epsf.fits"
    make_synthetic_epsf_fits(path)

    grid = load_epsf_grid(path)

    with pytest.raises(ValueError, match="finite"):
        select_epsf_model(grid, np.nan, 10)


def test_diagnostics_report_sampling_correctly(tmp_path):
    path = tmp_path / "synthetic_epsf.fits"
    make_synthetic_epsf_fits(path)

    selected = select_epsf_model(load_epsf_grid(path), 10, 10)
    report = epsf_diagnostics(selected)

    assert report["shape"] == (33, 33)
    assert report["sum"] == pytest.approx(1.0)
    assert report["oversampling"] == [5, 5]
    assert report["gaussian_equivalent_fwhm_detector_pixels"][0] == 0.0


def test_missing_epsf_extension_is_rejected(tmp_path):
    path = tmp_path / "no_epsf.fits"

    fits.HDUList([
        fits.PrimaryHDU(),
        fits.ImageHDU(np.ones((5, 5)), name="IMAGE"),
    ]).writeto(path)

    with pytest.raises(ValueError, match="EPSF"):
        load_epsf_grid(path)
