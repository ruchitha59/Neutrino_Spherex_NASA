
"""Spatially aware SPHEREx effective-PSF (EPSF) utilities.

The original oversampled EPSF arrays are preserved. This module selects
the nearest spatial EPSF model using the auxiliary detector-coordinate WCS.

Image coordinates passed to select_epsf_model are zero-based pixel
coordinates, matching Astropy's WCS convention.
"""
from __future__ import annotations

from pathlib import Path
import re

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS


_SIP_KEY = re.compile(r"^(A|B|AP|BP)_(ORDER|\d+_\d+)$")


def _auxiliary_wcs(image_header):
    """Build the auxiliary linear WCS without applying celestial SIP terms.

    SIP belongs to the celestial WCS in these files. It must not be applied
    to the separate auxiliary linear detector-coordinate WCS.
    """
    header = image_header.copy()

    for key in list(header.keys()):
        if _SIP_KEY.fullmatch(str(key)):
            del header[key]

    wcs = WCS(header, key="A", relax=True)

    if wcs.pixel_n_dim != 2 or wcs.world_n_dim != 2:
        raise ValueError("EPSF auxiliary WCS must have exactly two axes.")

    return wcs


def load_epsf_grid(fits_path):
    """Load and validate the spatial EPSF grid from a SPHEREx FITS file.

    Returns a dictionary containing the EPSF records, auxiliary WCS,
    oversampling factors, and detector metadata.
    """
    path = Path(fits_path)

    if not path.is_file():
        raise FileNotFoundError(f"FITS file does not exist: {path}")

    with fits.open(path, memmap=False) as hdul:
        names = {
            str(hdu.header.get("EXTNAME", hdu.name)).strip().upper(): i
            for i, hdu in enumerate(hdul)
        }

        if "IMAGE" not in names:
            raise ValueError("FITS file has no IMAGE extension.")
        if "EPSF" not in names:
            raise ValueError("FITS file has no EPSF extension.")

        image_header = hdul[names["IMAGE"]].header.copy()
        epsf_hdu = hdul[names["EPSF"]]
        epsf_header = epsf_hdu.header.copy()
        table = epsf_hdu.data

        if table is None:
            raise ValueError("EPSF extension contains no table data.")

        required = {
            "BINX", "BINY", "XCENTER", "YCENTER",
            "XWIDTH", "YWIDTH", "NSTAR", "NEFF_MEAN",
            "CWAVE", "CBAND", "EPSF",
        }
        available = set(table.names or [])
        missing = required - available

        if missing:
            raise ValueError(
                "EPSF table is missing required columns: "
                + ", ".join(sorted(missing))
            )

        arrays = {
            name: np.array(table[name], copy=True)
            for name in required
        }

        models = np.asarray(arrays["EPSF"], dtype=float)

        if models.ndim != 3 or models.shape[1] != models.shape[2]:
            raise ValueError(
                f"Expected EPSF models with shape (N, H, W); got {models.shape}."
            )

        if models.shape[0] == 0:
            raise ValueError("EPSF table contains no models.")

        if not np.all(np.isfinite(models)):
            raise ValueError("EPSF table contains non-finite model values.")

        sums = np.sum(models, axis=(1, 2))
        if not np.allclose(sums, 1.0, rtol=1e-5, atol=1e-8):
            raise ValueError(
                "EPSF models are not normalized to unit sum."
            )

        bin_pairs = list(zip(
            np.asarray(arrays["BINX"], dtype=int),
            np.asarray(arrays["BINY"], dtype=int),
        ))
        if len(set(bin_pairs)) != len(bin_pairs):
            raise ValueError("EPSF table contains duplicate BINX/BINY records.")

        for name in ("XCENTER", "YCENTER", "XWIDTH", "YWIDTH"):
            values = np.asarray(arrays[name], dtype=float)
            if not np.all(np.isfinite(values)):
                raise ValueError(f"EPSF column {name} contains non-finite values.")

        sampling_x = int(epsf_header.get("OVSMPX", 0))
        sampling_y = int(epsf_header.get("OVSMPY", 0))

        if sampling_x < 1 or sampling_y < 1:
            raise ValueError(
                "EPSF header must provide positive OVSMPX and OVSMPY."
            )

        auxiliary_wcs = _auxiliary_wcs(image_header)

        return {
            "path": str(path),
            "models": models,
            "records": arrays,
            "auxiliary_wcs": auxiliary_wcs,
            "oversampling_x": sampling_x,
            "oversampling_y": sampling_y,
            "detector": epsf_header.get("DETECTOR"),
            "detector_coordinates": epsf_header.get("DETCOORD"),
            "model_count": int(models.shape[0]),
            "model_shape": tuple(int(v) for v in models.shape[1:]),
            "normalization": "unit_sum",
        }


def _grid_spacing(values):
    """Estimate regular grid spacing from unique EPSF model centres."""
    unique = np.unique(np.asarray(values, dtype=float))
    differences = np.diff(np.sort(unique))
    differences = differences[differences > 0]

    if differences.size == 0:
        return None

    return float(np.median(differences))


def select_epsf_model(grid, x, y):
    """Select the nearest spatial EPSF model for an image pixel.

    Parameters
    ----------
    grid : dict
        Result from load_epsf_grid().
    x, y : float
        Zero-based IMAGE pixel coordinates.

    Returns
    -------
    dict
        Selected EPSF array and its spatial, spectral, and sampling metadata.
        The EPSF array remains at its original oversampled resolution.
    """
    x = float(x)
    y = float(y)

    if not np.isfinite(x) or not np.isfinite(y):
        raise ValueError("Image pixel coordinates must be finite.")

    if "auxiliary_wcs" not in grid or "records" not in grid:
        raise ValueError("Invalid EPSF grid object.")

    aux_x, aux_y = grid["auxiliary_wcs"].all_pix2world([[x, y]], 0)[0]

    if not np.isfinite(aux_x) or not np.isfinite(aux_y):
        raise ValueError("Auxiliary WCS returned invalid coordinates.")

    records = grid["records"]
    model_x = np.asarray(records["XCENTER"], dtype=float)
    model_y = np.asarray(records["YCENTER"], dtype=float)

    distances = np.hypot(model_x - aux_x, model_y - aux_y)
    index = int(np.argmin(distances))

    spacing_x = _grid_spacing(model_x)
    spacing_y = _grid_spacing(model_y)

    half_x = spacing_x / 2 if spacing_x else float(
        np.median(records["XWIDTH"]) / 2
    )
    half_y = spacing_y / 2 if spacing_y else float(
        np.median(records["YWIDTH"]) / 2
    )

    within_coverage = (
        model_x.min() - half_x <= aux_x <= model_x.max() + half_x
        and model_y.min() - half_y <= aux_y <= model_y.max() + half_y
    )

    def value(name):
        item = records[name][index]
        return item.item() if hasattr(item, "item") else item

    return {
        "epsf": np.array(grid["models"][index], copy=True),
        "record_index": index,
        "binx": int(value("BINX")),
        "biny": int(value("BINY")),
        "xcenter": float(value("XCENTER")),
        "ycenter": float(value("YCENTER")),
        "xwidth": float(value("XWIDTH")),
        "ywidth": float(value("YWIDTH")),
        "aux_x": float(aux_x),
        "aux_y": float(aux_y),
        "distance_px": float(distances[index]),
        "within_grid_coverage": bool(within_coverage),
        "nstar": int(value("NSTAR")),
        "neff_mean": float(value("NEFF_MEAN")),
        "cwave_um": float(value("CWAVE")),
        "cband_um": float(value("CBAND")),
        "oversampling_x": int(grid["oversampling_x"]),
        "oversampling_y": int(grid["oversampling_y"]),
        "detector": grid.get("detector"),
        "detector_coordinates": grid.get("detector_coordinates"),
        "epsf_shape": tuple(int(v) for v in grid["model_shape"]),
        "epsf_normalization": "unit_sum",
        "warnings": (
            [] if within_coverage else
            ["Requested position is outside EPSF grid coverage."]
        ),
    }


def epsf_diagnostics(selected_model):
    """Return basic diagnostics without modifying or resampling the EPSF.

    FWHM values are Gaussian-equivalent moment estimates, not direct
    profile-fit measurements.
    """
    epsf = np.asarray(selected_model["epsf"], dtype=float)

    if epsf.ndim != 2 or not np.all(np.isfinite(epsf)):
        raise ValueError("Selected EPSF must be a finite 2D array.")

    positive = np.clip(epsf, 0.0, None)
    total = float(positive.sum())

    if total <= 0:
        raise ValueError("EPSF has no positive integrated weight.")

    yy, xx = np.indices(positive.shape, dtype=float)
    cx = float((positive * xx).sum() / total)
    cy = float((positive * yy).sum() / total)

    var_x = float((positive * (xx - cx) ** 2).sum() / total)
    var_y = float((positive * (yy - cy) ** 2).sum() / total)

    sx = np.sqrt(max(var_x, 0.0))
    sy = np.sqrt(max(var_y, 0.0))

    ox = int(selected_model["oversampling_x"])
    oy = int(selected_model["oversampling_y"])

    factor = 2.0 * np.sqrt(2.0 * np.log(2.0))

    return {
        "shape": tuple(int(v) for v in epsf.shape),
        "sum": float(epsf.sum()),
        "minimum": float(epsf.min()),
        "maximum": float(epsf.max()),
        "finite_pixels": int(np.isfinite(epsf).sum()),
        "positive_weight_centroid_samples": [cx, cy],
        "gaussian_equivalent_fwhm_samples": [
            float(factor * sx),
            float(factor * sy),
        ],
        "gaussian_equivalent_fwhm_detector_pixels": [
            float(factor * sx / ox),
            float(factor * sy / oy),
        ],
        "oversampling": [ox, oy],
        "measurement_note": (
            "Positive-weight second-moment estimate; not a PSF fit."
        ),
    }


def load_psf_cube(fits_path):
    """Load a spatial PSF image cube and its detector-coordinate grid.

    Supports the newer SPHEREx PSF extension containing a cube
    of spatially varying, oversampled PSF models.
    """
    path = Path(fits_path)

    if not path.is_file():
        raise FileNotFoundError(f"FITS file does not exist: {path}")

    with fits.open(path, memmap=False) as hdul:
        names = {
            str(hdu.header.get("EXTNAME", hdu.name)).strip().upper(): i
            for i, hdu in enumerate(hdul)
        }

        if "IMAGE" not in names or "PSF" not in names:
            raise ValueError("FITS file must contain IMAGE and PSF extensions.")

        image_header = hdul[names["IMAGE"]].header.copy()
        psf_hdu = hdul[names["PSF"]]
        psf_header = psf_hdu.header.copy()

        models = np.array(psf_hdu.data, dtype=float, copy=True)

        if models.ndim != 3:
            raise ValueError(
                f"Expected PSF cube with shape (N, H, W); got {models.shape}."
            )

        if models.shape[0] == 0 or models.shape[1] != models.shape[2]:
            raise ValueError("PSF cube must contain non-empty square models.")

        if not np.all(np.isfinite(models)):
            raise ValueError("PSF cube contains non-finite values.")

        sums = np.sum(models, axis=(1, 2))

        if not np.allclose(sums, 1.0, rtol=1e-5, atol=1e-7):
            raise ValueError("PSF models are not normalized to unit sum.")

        oversampling = int(psf_header.get("OVERSAMP", 0))

        if oversampling < 1:
            raise ValueError("PSF header must provide positive OVERSAMP.")

        count = models.shape[0]
        centers_x = []
        centers_y = []
        widths_x = []
        widths_y = []

        for index in range(1, count + 1):
            keys = (
                f"XCTR_{index}",
                f"YCTR_{index}",
                f"XWID_{index}",
                f"YWID_{index}",
            )

            if not all(key in psf_header for key in keys):
                raise ValueError(
                    f"PSF header is missing spatial metadata for model {index}."
                )

            values = [float(psf_header[key]) for key in keys]

            if not np.all(np.isfinite(values)):
                raise ValueError(
                    f"PSF model {index} has non-finite spatial metadata."
                )

            if values[2] <= 0 or values[3] <= 0:
                raise ValueError(
                    f"PSF model {index} has invalid spatial width."
                )

            centers_x.append(values[0])
            centers_y.append(values[1])
            widths_x.append(values[2])
            widths_y.append(values[3])

        auxiliary_wcs = _auxiliary_wcs(image_header)

        return {
            "path": str(path),
            "models": models,
            "centers_x": np.asarray(centers_x),
            "centers_y": np.asarray(centers_y),
            "widths_x": np.asarray(widths_x),
            "widths_y": np.asarray(widths_y),
            "auxiliary_wcs": auxiliary_wcs,
            "oversampling": oversampling,
            "model_count": int(count),
            "model_shape": tuple(int(v) for v in models.shape[1:]),
            "normalization": "unit_sum",
            "detector": psf_header.get("DETECTOR"),
        }


def select_psf_model(grid, x, y):
    """Select the nearest PSF model using IMAGE pixel coordinates.

    Coordinates x and y are zero-based IMAGE pixel coordinates.
    The auxiliary WCS converts them to detector active-pixel coordinates.
    """
    x = float(x)
    y = float(y)

    if not np.isfinite(x) or not np.isfinite(y):
        raise ValueError("Image pixel coordinates must be finite.")

    if "auxiliary_wcs" not in grid:
        raise ValueError("PSF grid has no auxiliary WCS.")

    detector_x, detector_y = grid["auxiliary_wcs"].all_pix2world(
        [[x, y]], 0
    )[0]

    if not np.isfinite(detector_x) or not np.isfinite(detector_y):
        raise ValueError("Auxiliary WCS returned invalid coordinates.")

    centers_x = grid["centers_x"]
    centers_y = grid["centers_y"]

    distances = np.hypot(
        centers_x - detector_x,
        centers_y - detector_y,
    )

    index = int(np.argmin(distances))

    within_coverage = (
        abs(detector_x - centers_x[index]) <= grid["widths_x"][index] / 2
        and abs(detector_y - centers_y[index]) <= grid["widths_y"][index] / 2
    )

    return {
        "epsf": np.array(grid["models"][index], copy=True),
        "record_index": index,
        "binx": None,
        "biny": None,
        "xcenter": float(centers_x[index]),
        "ycenter": float(centers_y[index]),
        "xwidth": float(grid["widths_x"][index]),
        "ywidth": float(grid["widths_y"][index]),
        "aux_x": float(detector_x),
        "aux_y": float(detector_y),
        "distance_px": float(distances[index]),
        "within_grid_coverage": bool(within_coverage),
        "nstar": None,
        "neff_mean": None,
        "cwave_um": None,
        "cband_um": None,
        "oversampling_x": int(grid["oversampling"]),
        "oversampling_y": int(grid["oversampling"]),
        "detector": grid.get("detector"),
        "detector_coordinates": "0-based active pixel coordinates",
        "epsf_shape": grid["model_shape"],
        "epsf_normalization": "unit_sum",
        "warnings": (
            [] if within_coverage else
            ["Requested position is outside PSF model coverage."]
        ),
    }


def psf_diagnostics(selected_model):
    """Calculate moment-based diagnostics for a selected PSF model."""
    result = epsf_diagnostics(selected_model)
    result["model_type"] = "PSF cube"
    result["measurement_note"] = (
        "Positive-weight second-moment estimate; not a PSF fit."
    )
    return result
