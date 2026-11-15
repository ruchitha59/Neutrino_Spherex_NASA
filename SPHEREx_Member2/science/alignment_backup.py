"""WCS reprojection, variance propagation and background-star registration checks."""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import maximum_filter


def _science_hdu(hdul):
    matches = [h for h in hdul if str(h.header.get("EXTNAME", h.name)).strip().upper() == "IMAGE"]
    if len(matches) != 1 or matches[0].data is None:
        raise ValueError(f"Expected exactly one IMAGE HDU; found {len(matches)}.")
    return matches[0]


def reproject_to_reference(input_fits, ref_wcs, shape_out):
    """Reproject IMAGE onto a supplied WCS grid (PRD signature preserved).

    Returns the reprojected image and its footprint. Invalid/out-of-coverage
    pixels are NaN. The input FITS file is opened read-only.
    """
    from astropy.io import fits
    from astropy.wcs import WCS
    from reproject import reproject_interp

    with fits.open(input_fits, memmap=False) as hdul:
        science_hdu = _science_hdu(hdul)
        data = np.asarray(science_hdu.data, dtype=float)
        input_wcs = WCS(science_hdu.header).celestial
        if not input_wcs.has_celestial:
            raise ValueError(f"No valid celestial WCS in {input_fits}.")
        projected, footprint = reproject_interp(
            (data, input_wcs), ref_wcs, shape_out=shape_out, order="bilinear"
        )
    projected = np.asarray(projected, dtype=float)
    footprint = np.asarray(footprint, dtype=float)
    projected[~np.isfinite(footprint) | (footprint <= 0)] = np.nan
    return projected, footprint


def _bilinear_variance_to_reference(variance, input_wcs, ref_wcs, shape_out,
                                    input_valid_mask=None):
    """Propagate variance using squared bilinear weights (independent input pixels).

    This is a per-output-pixel variance estimate. It does not model covariance
    between neighboring reprojected output pixels.
    """
    ny, nx = shape_out
    yy, xx = np.indices((ny, nx), dtype=float)
    ra, dec = ref_wcs.pixel_to_world_values(xx, yy)
    xin, yin = input_wcs.world_to_pixel_values(ra, dec)

    x0, y0 = np.floor(xin).astype(int), np.floor(yin).astype(int)
    dx, dy = xin - x0, yin - y0
    out = np.full((ny, nx), np.nan, dtype=float)
    accum = np.zeros((ny, nx), dtype=float)
    good = np.isfinite(xin) & np.isfinite(yin)
    complete = good.copy()
    var = np.asarray(variance, dtype=float)
    h, w = var.shape
    input_valid = (
        np.isfinite(var) & (var >= 0)
        if input_valid_mask is None
        else np.asarray(input_valid_mask, dtype=bool) & np.isfinite(var) & (var >= 0)
    )
    if input_valid.shape != var.shape:
        raise ValueError("Input variance mask and variance shapes must match.")

    for ox, oy, weight in [
        (0, 0, (1 - dx) * (1 - dy)),
        (1, 0, dx * (1 - dy)),
        (0, 1, (1 - dx) * dy),
        (1, 1, dx * dy),
    ]:
        active = good & (weight > 1e-12)
        ix, iy = x0 + ox, y0 + oy
        inside = active & (ix >= 0) & (ix < w) & (iy >= 0) & (iy < h)
        values = np.full((ny, nx), np.nan, dtype=float)
        values[inside] = var[iy[inside], ix[inside]]
        valid_value = inside & input_valid[np.clip(iy, 0, h - 1), np.clip(ix, 0, w - 1)] & np.isfinite(values) & (values >= 0)
        complete &= (~active) | valid_value
        accum[valid_value] += (weight[valid_value] ** 2) * values[valid_value]

    out[complete & good] = accum[complete & good]
    return out


def reproject_observation(input_fits, ref_wcs, shape_out):
    """Reproject science, quality masks, flags, footprint and variance."""
    from astropy.io import fits
    from astropy.wcs import WCS
    from reproject import reproject_interp
    from science.quality import build_valid_mask, flag_definitions_from_header

    with fits.open(input_fits, memmap=False) as hdul:
        science_hdu = _science_hdu(hdul)
        input_wcs = WCS(science_hdu.header).celestial
        image = np.asarray(science_hdu.data, dtype=float)
        names = {str(h.header.get("EXTNAME", h.name)).strip().upper(): h for h in hdul}
        variance = np.asarray(names["VARIANCE"].data, dtype=float) if "VARIANCE" in names and names["VARIANCE"].data is not None else None
        flags = np.asarray(names["FLAGS"].data) if "FLAGS" in names and names["FLAGS"].data is not None else None
        definitions = flag_definitions_from_header(names["FLAGS"].header) if "FLAGS" in names else {}

        input_valid_mask, input_mask_counts = build_valid_mask(
            image, flags, variance, flag_definitions=definitions
        )
        masked_image = image.copy()
        masked_image[~input_valid_mask] = np.nan

        projected, footprint = reproject_interp(
            (masked_image, input_wcs), ref_wcs, shape_out=shape_out, order="bilinear"
        )
        projected_mask, mask_footprint = reproject_interp(
            (input_valid_mask.astype(float), input_wcs), ref_wcs,
            shape_out=shape_out, order="bilinear"
        )
        # Require all non-zero bilinear contributors to be valid. This avoids
        # allowing a flagged input pixel to contaminate a valid output pixel.
        projected_valid_mask = (
            np.isfinite(projected_mask) & (projected_mask >= 0.999) &
            np.isfinite(footprint) & (footprint > 0) &
            np.isfinite(mask_footprint) & (mask_footprint > 0)
        )

        projected_variance = None
        if variance is not None:
            projected_variance = _bilinear_variance_to_reference(
                variance, input_wcs, ref_wcs, shape_out,
                input_valid_mask=input_valid_mask,
            )
            projected_valid_mask &= np.isfinite(projected_variance) & (projected_variance >= 0)

        projected_flags = None
        if flags is not None:
            projected_flags, _ = reproject_interp(
                (flags.astype(float), input_wcs), ref_wcs,
                shape_out=shape_out, order="nearest-neighbor"
            )
            projected_flags = np.where(np.isfinite(projected_flags), projected_flags, 0).astype(np.int64)

        projected = np.asarray(projected, dtype=float)
        footprint = np.asarray(footprint, dtype=float)
        projected[~projected_valid_mask] = np.nan
        if projected_variance is not None:
            projected_variance[~projected_valid_mask] = np.nan
        metadata = {
            "bunit": science_hdu.header.get("BUNIT"),
            "observation_id": science_hdu.header.get("OBSID"),
            "date_obs": science_hdu.header.get("DATE-OBS"),
            "detector": science_hdu.header.get("DETECTOR"),
            "finast": science_hdu.header.get("FINAST"),
            "variance_propagation": "squared bilinear interpolation weights; assumes independent input pixels",
            "covariance_modelled": False,
            "mask_propagation": "bilinear mask coverage; all non-zero input contributors must be valid",
            "input_mask_counts": input_mask_counts,
        }
    return {
        "image": projected,
        "variance": projected_variance,
        "flags": projected_flags,
        "footprint": footprint,
        "valid_pixel_mask": projected_valid_mask,
        "metadata": metadata,
    }


def _local_peaks(data, valid_mask, threshold_sigma):
    values = np.asarray(data, dtype=float)
    sample = values[valid_mask & np.isfinite(values)]
    if sample.size < 20:
        return np.empty((0, 2), dtype=float)
    med = np.median(sample)
    sigma = 1.4826 * np.median(np.abs(sample - med))
    if not np.isfinite(sigma) or sigma <= 0:
        sigma = np.std(sample)
    if not np.isfinite(sigma) or sigma <= 0:
        return np.empty((0, 2), dtype=float)
    peaks = valid_mask & (values == maximum_filter(values, size=3)) & (values > med + threshold_sigma * sigma)
    y, x = np.where(peaks)
    return np.column_stack([x, y]).astype(float)


def measure_alignment_residuals(reference, comparison, reference_mask=None,
                                 comparison_mask=None, threshold_sigma=5.0,
                                 max_match_distance_px=3.0, min_matches=3,
                                 exclude_position_px=None, exclude_radius_px=3.0):
    """Compare stable positive background-source centroids after WCS reprojection.

    This simple centroid matcher is a quality gate, not a replacement for a
    dedicated astrometric solver. It reports failure when too few matches exist.
    """
    ref = np.asarray(reference, dtype=float)
    cmp = np.asarray(comparison, dtype=float)
    if ref.shape != cmp.shape:
        raise ValueError("Aligned arrays must have identical shapes.")
    rm = np.isfinite(ref) if reference_mask is None else np.asarray(reference_mask, bool) & np.isfinite(ref)
    cm = np.isfinite(cmp) if comparison_mask is None else np.asarray(comparison_mask, bool) & np.isfinite(cmp)
    rp = _local_peaks(ref, rm, threshold_sigma)
    cp = _local_peaks(cmp, cm, threshold_sigma)
    if exclude_position_px is not None:
        ex, ey = map(float, exclude_position_px)
        rp = rp[np.hypot(rp[:, 0] - ex, rp[:, 1] - ey) > float(exclude_radius_px)]
        cp = cp[np.hypot(cp[:, 0] - ex, cp[:, 1] - ey) > float(exclude_radius_px)]
    if len(rp) < min_matches or len(cp) < min_matches:
        return {
            "passed": False, "matches": 0, "median_offset_px": None,
            "rms_offset_px": None,
            "reason": f"Insufficient background sources (reference={len(rp)}, comparison={len(cp)}; need {min_matches}).",
        }
    distances, indices = cKDTree(cp).query(rp, k=1)
    keep = distances <= max_match_distance_px
    if keep.sum() < min_matches:
        return {
            "passed": False, "matches": int(keep.sum()), "median_offset_px": None,
            "rms_offset_px": None, "reason": "Too few nearest-neighbor background-source matches.",
        }
    offsets = cp[indices[keep]] - rp[keep]
    norms = np.hypot(offsets[:, 0], offsets[:, 1])
    median = float(np.median(norms))
    rms = float(np.sqrt(np.mean(norms ** 2)))
    return {
        "passed": bool(median <= 0.5 and rms <= 1.0),
        "matches": int(keep.sum()),
        "median_offset_px": median,
        "rms_offset_px": rms,
        "tolerance_median_px": 0.5,
        "tolerance_rms_px": 1.0,
        "reason": None if median <= 0.5 and rms <= 1.0 else "Residual exceeds configured alignment tolerance.",
    }
