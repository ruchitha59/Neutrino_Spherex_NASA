"""FITS inspection utilities for SPHEREx spectral-image MEFs.

The public inspect_fits(path) interface intentionally matches the PRD starter
function. The returned list contains one JSON-serializable record per HDU.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from astropy.io import fits
from astropy.wcs import WCS


SCIENCE_EXTENSIONS = {"IMAGE"}
AUXILIARY_EXTENSIONS = {"FLAGS", "VARIANCE", "ZODI", "PSF", "EPSF", "WCS-WAVE"}


def _plain(value: Any) -> Any:
    """Convert FITS/Astropy values into JSON-safe Python values."""
    if value is None:
        return None
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _header_subset(header, keys):
    return {key: _plain(header[key]) for key in keys if key in header}


def inspect_fits(path):
    """Inspect every HDU in a FITS file; preserve the PRD function name.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to an original SPHEREx FITS cutout.

    Returns
    -------
    list[dict]
        One report dictionary for each HDU. IMAGE is selected by EXTNAME,
        never by assuming that HDU 0 contains science data.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"FITS file does not exist: {path}")

    report = []
    with fits.open(path, memmap=False, checksum=True) as hdul:
        image_candidates = [
            i for i, hdu in enumerate(hdul)
            if str(hdu.header.get("EXTNAME", hdu.name)).strip().upper() in SCIENCE_EXTENSIONS
            and getattr(hdu, "data", None) is not None
        ]
        selected_science_index = image_candidates[0] if len(image_candidates) == 1 else None

        for index, hdu in enumerate(hdul):
            header = hdu.header
            data = getattr(hdu, "data", None)
            extname = str(header.get("EXTNAME", hdu.name)).strip()
            row = {
                "index": index,
                "name": str(hdu.name),
                "extname": extname,
                "hdu_type": type(hdu).__name__,
                "has_data": data is not None,
                "shape": list(data.shape) if data is not None and hasattr(data, "shape") else None,
                "dtype": str(data.dtype) if data is not None and hasattr(data, "dtype") else None,
                "bitpix": _plain(header.get("BITPIX")),
                "bunit": _plain(header.get("BUNIT")),
                "is_science_candidate": extname.upper() in SCIENCE_EXTENSIONS,
                "is_selected_science": index == selected_science_index,
                "is_auxiliary": extname.upper() in AUXILIARY_EXTENSIONS,
                "header": {
                    key: _plain(value) for key, value in header.items()
                    if key not in ("COMMENT", "HISTORY")
                },
                "wcs": None,
                "wcs_valid": False,
                "wcs_error": None,
            }
            if data is not None and getattr(data, "ndim", 0) >= 2:
                try:
                    wcs = WCS(header).celestial
                    valid = bool(wcs.has_celestial)
                    if valid:
                        ny, nx = data.shape[-2:]
                        world = wcs.pixel_to_world_values((nx - 1) / 2, (ny - 1) / 2)
                        valid = all(
                            value is not None and bool(__import__("numpy").isfinite(value))
                            for value in world
                        )
                    row["wcs_valid"] = valid
                    row["wcs"] = {
                        "ctype": list(wcs.wcs.ctype),
                        "cunit": [str(unit) for unit in wcs.wcs.cunit],
                        "radesys": _plain(header.get("RADESYS")),
                        "crval": list(wcs.wcs.crval),
                        "crpix": list(wcs.wcs.crpix),
                        "pixel_scale_matrix": wcs.pixel_scale_matrix.tolist(),
                    }
                except Exception as exc:
                    row["wcs_error"] = f"{type(exc).__name__}: {exc}"
            report.append(row)

        if len(image_candidates) != 1:
            for row in report:
                row["science_selection_warning"] = (
                    f"Expected exactly one IMAGE HDU; found {len(image_candidates)}."
                )
        return report


def inspect_fits_metadata(path):
    """Return a compact file-level summary plus the full HDU report."""
    hdus = inspect_fits(path)
    selected = [h for h in hdus if h["is_selected_science"]]
    science = selected[0] if selected else None
    header = science["header"] if science else {}
    return {
        "path": str(path),
        "hdu_count": len(hdus),
        "selected_science_hdu": science["index"] if science else None,
        "science_selection_evidence": "EXTNAME=IMAGE" if science else None,
        "science_shape": science["shape"] if science else None,
        "bunit": science["bunit"] if science else None,
        "wcs_valid": science["wcs_valid"] if science else False,
        "observation_id": header.get("OBSID"),
        "observation_time": header.get("DATE-OBS"),
        "detector": header.get("DETECTOR"),
        "finast": header.get("FINAST"),
        "hdus": hdus,
    }
