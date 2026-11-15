
"""
WCS reprojection, variance propagation and background-star registration checks.

Member 2 - SPHEREx Astronomical Image Processing and Detection.

Scientific notes:
- Original FITS files are opened read-only.
- Science images use bilinear interpolation.
- Quality flags use nearest-neighbour interpolation.
- Variance uses squared bilinear interpolation weights.
- Inter-pixel covariance introduced by resampling is not modelled.
- Alignment is a conservative quality gate, not a full astrometric solver.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import maximum_filter
from scipy.optimize import linear_sum_assignment


def _science_hdu(hdul):
    """Find the unique science IMAGE extension."""
    matches = [
        h for h in hdul
        if str(h.header.get("EXTNAME", h.name)).strip().upper() == "IMAGE"
    ]

    if len(matches) != 1 or matches[0].data is None:
        raise ValueError(
            f"Expected exactly one IMAGE HDU; found {len(matches)}."
        )

    return matches[0]


def reproject_to_reference(input_fits, ref_wcs, shape_out):
    """Reproject IMAGE onto a supplied WCS grid.

    PRD-required signature preserved.

    Returns:
        projected: Reprojected science image.
        footprint: Reprojection coverage footprint.

    Invalid and out-of-coverage pixels are NaN.
    The input FITS file is opened read-only.
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
            (data, input_wcs),
            ref_wcs,
            shape_out=shape_out,
            order="bilinear",
        )

    projected = np.asarray(projected, dtype=float)
    footprint = np.asarray(footprint, dtype=float)

    projected[
        ~np.isfinite(footprint) | (footprint <= 0)
    ] = np.nan

    return projected, footprint


def _bilinear_variance_to_reference(
    variance,
    input_wcs,
    ref_wcs,
    shape_out,
    input_valid_mask=None,
):
    """Propagate variance using squared bilinear interpolation weights.

    Assumes independent input pixels.

    This calculates per-output-pixel variance. It does not model covariance
    between neighbouring reprojected output pixels.
    """
    ny, nx = shape_out

    yy, xx = np.indices((ny, nx), dtype=float)

    ra, dec = ref_wcs.pixel_to_world_values(xx, yy)
    xin, yin = input_wcs.world_to_pixel_values(ra, dec)

    x0 = np.floor(xin).astype(int)
    y0 = np.floor(yin).astype(int)

    dx = xin - x0
    dy = yin - y0

    out = np.full((ny, nx), np.nan, dtype=float)
    accum = np.zeros((ny, nx), dtype=float)

    good = np.isfinite(xin) & np.isfinite(yin)
    complete = good.copy()

    var = np.asarray(variance, dtype=float)
    h, w = var.shape

    input_valid = (
        np.isfinite(var) & (var >= 0)
        if input_valid_mask is None
        else (
            np.asarray(input_valid_mask, dtype=bool)
            & np.isfinite(var)
            & (var >= 0)
        )
    )

    if input_valid.shape != var.shape:
        raise ValueError(
            "Input variance mask and variance shapes must match."
        )

    contributors = [
        (0, 0, (1 - dx) * (1 - dy)),
        (1, 0, dx * (1 - dy)),
        (0, 1, (1 - dx) * dy),
        (1, 1, dx * dy),
    ]

    for ox, oy, weight in contributors:
        active = good & (weight > 1e-12)

        ix = x0 + ox
        iy = y0 + oy

        inside = (
            active
            & (ix >= 0)
            & (ix < w)
            & (iy >= 0)
            & (iy < h)
        )

        values = np.full((ny, nx), np.nan, dtype=float)
        values[inside] = var[iy[inside], ix[inside]]

        clipped_y = np.clip(iy, 0, h - 1)
        clipped_x = np.clip(ix, 0, w - 1)

        valid_value = (
            inside
            & input_valid[clipped_y, clipped_x]
            & np.isfinite(values)
            & (values >= 0)
        )

        complete &= (~active) | valid_value

        accum[valid_value] += (
            weight[valid_value] ** 2
        ) * values[valid_value]

    out[complete & good] = accum[complete & good]

    return out


def reproject_observation(input_fits, ref_wcs, shape_out):
    """Reproject science, quality masks, flags, footprint and variance."""
    from astropy.io import fits
    from astropy.wcs import WCS
    from reproject import reproject_interp

    from science.quality import (
        build_valid_mask,
        flag_definitions_from_header,
    )

    with fits.open(input_fits, memmap=False) as hdul:
        science_hdu = _science_hdu(hdul)

        input_wcs = WCS(science_hdu.header).celestial
        image = np.asarray(science_hdu.data, dtype=float)

        names = {
            str(h.header.get("EXTNAME", h.name)).strip().upper(): h
            for h in hdul
        }

        variance = (
            np.asarray(names["VARIANCE"].data, dtype=float)
            if (
                "VARIANCE" in names
                and names["VARIANCE"].data is not None
            )
            else None
        )

        flags = (
            np.asarray(names["FLAGS"].data)
            if (
                "FLAGS" in names
                and names["FLAGS"].data is not None
            )
            else None
        )

        definitions = (
            flag_definitions_from_header(names["FLAGS"].header)
            if "FLAGS" in names
            else {}
        )

        input_valid_mask, input_mask_counts = build_valid_mask(
            image,
            flags,
            variance,
            flag_definitions=definitions,
        )

        masked_image = image.copy()
        masked_image[~input_valid_mask] = np.nan

        projected, footprint = reproject_interp(
            (masked_image, input_wcs),
            ref_wcs,
            shape_out=shape_out,
            order="bilinear",
        )

        projected_mask, mask_footprint = reproject_interp(
            (input_valid_mask.astype(float), input_wcs),
            ref_wcs,
            shape_out=shape_out,
            order="bilinear",
        )

        # Require all non-zero bilinear contributors to be valid.
        projected_valid_mask = (
            np.isfinite(projected_mask)
            & (projected_mask >= 0.999)
            & np.isfinite(footprint)
            & (footprint > 0)
            & np.isfinite(mask_footprint)
            & (mask_footprint > 0)
        )

        projected_variance = None

        if variance is not None:
            projected_variance = _bilinear_variance_to_reference(
                variance,
                input_wcs,
                ref_wcs,
                shape_out,
                input_valid_mask=input_valid_mask,
            )

            projected_valid_mask &= (
                np.isfinite(projected_variance)
                & (projected_variance >= 0)
            )

        projected_flags = None

        if flags is not None:
            projected_flags, _ = reproject_interp(
                (flags.astype(float), input_wcs),
                ref_wcs,
                shape_out=shape_out,
                order="nearest-neighbor",
            )

            projected_flags = np.where(
                np.isfinite(projected_flags),
                projected_flags,
                0,
            ).astype(np.int64)

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
            "variance_propagation": (
                "squared bilinear interpolation weights; "
                "assumes independent input pixels"
            ),
            "covariance_modelled": False,
            "mask_propagation": (
                "bilinear mask coverage; all non-zero "
                "input contributors must be valid"
            ),
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
    """Detect positive local peaks and refine positions to subpixels.

    Uses a local 3x3 intensity-weighted centroid. Detections touching
    image boundaries or invalid pixels are rejected.
    """
    values = np.asarray(data, dtype=float)
    valid = (
        np.asarray(valid_mask, dtype=bool)
        & np.isfinite(values)
    )

    if valid.shape != values.shape:
        raise ValueError(
            "Peak-detection mask and image shapes must match."
        )

    sample = values[valid]

    if sample.size < 20:
        return np.empty((0, 2), dtype=float)

    med = float(np.median(sample))

    sigma = float(
        1.4826 * np.median(np.abs(sample - med))
    )

    if not np.isfinite(sigma) or sigma <= 0:
        sigma = float(np.std(sample))

    if not np.isfinite(sigma) or sigma <= 0:
        return np.empty((0, 2), dtype=float)

    safe_values = np.where(valid, values, -np.inf)

    local_maximum = maximum_filter(
        safe_values,
        size=3,
        mode="constant",
        cval=-np.inf,
    )

    peaks = (
        valid
        & (safe_values == local_maximum)
        & (values > med + float(threshold_sigma) * sigma)
    )

    y_peaks, x_peaks = np.where(peaks)

    height, width = values.shape
    refined = []

    for x, y in zip(x_peaks, y_peaks):

        # Reject peaks too close to image boundaries.
        if (
            x < 1
            or y < 1
            or x >= width - 1
            or y >= height - 1
        ):
            continue

        # Require all pixels in the centroid patch to be valid.
        local_valid = valid[y - 1:y + 2, x - 1:x + 2]

        if local_valid.shape != (3, 3) or not np.all(local_valid):
            continue

        patch = values[y - 1:y + 2, x - 1:x + 2] - med
        weights = np.clip(patch, 0.0, None)

        total_weight = float(np.sum(weights))

        if not np.isfinite(total_weight) or total_weight <= 0:
            continue

        yy, xx = np.indices((3, 3), dtype=float)

        centroid_x = float(
            x - 1 + np.sum(xx * weights) / total_weight
        )

        centroid_y = float(
            y - 1 + np.sum(yy * weights) / total_weight
        )

        refined.append((centroid_x, centroid_y))

    if not refined:
        return np.empty((0, 2), dtype=float)

    return np.asarray(refined, dtype=float)


def measure_alignment_residuals(
    reference,
    comparison,
    reference_mask=None,
    comparison_mask=None,
    threshold_sigma=5.0,
    max_match_distance_px=3.0,
    min_matches=3,
    exclude_position_px=None,
    exclude_radius_px=3.0,
):
    """Measure one-to-one background-source alignment residuals.

    This is a conservative registration quality gate, not a full
    astrometric solution.

    PRD pipeline function name and arguments are preserved.
    """
    ref = np.asarray(reference, dtype=float)
    cmp = np.asarray(comparison, dtype=float)

    if ref.shape != cmp.shape:
        raise ValueError(
            "Aligned arrays must have identical shapes."
        )

    rm = (
        np.isfinite(ref)
        if reference_mask is None
        else (
            np.asarray(reference_mask, dtype=bool)
            & np.isfinite(ref)
        )
    )

    cm = (
        np.isfinite(cmp)
        if comparison_mask is None
        else (
            np.asarray(comparison_mask, dtype=bool)
            & np.isfinite(cmp)
        )
    )

    if rm.shape != ref.shape or cm.shape != cmp.shape:
        raise ValueError(
            "Alignment masks and image shapes must match."
        )

    rp = _local_peaks(ref, rm, threshold_sigma)
    cp = _local_peaks(cmp, cm, threshold_sigma)

    if exclude_position_px is not None:
        ex, ey = map(float, exclude_position_px)

        rp = rp[
            np.hypot(rp[:, 0] - ex, rp[:, 1] - ey)
            > float(exclude_radius_px)
        ]

        cp = cp[
            np.hypot(cp[:, 0] - ex, cp[:, 1] - ey)
            > float(exclude_radius_px)
        ]

    if len(rp) < min_matches or len(cp) < min_matches:
        return {
            "passed": False,
            "matches": 0,
            "median_offset_px": None,
            "rms_offset_px": None,
            "reason": (
                f"Insufficient background sources "
                f"(reference={len(rp)}, comparison={len(cp)}; "
                f"need {min_matches})."
            ),
        }

    # Calculate pairwise distances between detected sources.
    distances = np.linalg.norm(
        rp[:, None, :] - cp[None, :, :],
        axis=2,
    )

    # Enforce one-to-one matching. A source cannot be reused
    # to match multiple sources in the other observation.
    ref_indices, cmp_indices = linear_sum_assignment(distances)

    assigned_distances = distances[
        ref_indices,
        cmp_indices,
    ]

    keep = (
        assigned_distances <= float(max_match_distance_px)
    )

    matched_ref = rp[ref_indices[keep]]
    matched_cmp = cp[cmp_indices[keep]]

    match_count = int(np.count_nonzero(keep))

    if match_count < min_matches:
        return {
            "passed": False,
            "matches": match_count,
            "median_offset_px": None,
            "rms_offset_px": None,
            "reason": (
                "Too few one-to-one background-source matches."
            ),
        }

    offsets = matched_cmp - matched_ref

    norms = np.hypot(
        offsets[:, 0],
        offsets[:, 1],
    )

    median = float(np.median(norms))
    rms = float(np.sqrt(np.mean(norms ** 2)))

    passed = median <= 0.5 and rms <= 1.0

    return {
        "passed": bool(passed),
        "matches": match_count,
        "median_offset_px": median,
        "rms_offset_px": rms,
        "tolerance_median_px": 0.5,
        "tolerance_rms_px": 1.0,
        "reason": (
            None
            if passed
            else "Residual exceeds configured alignment tolerance."
        ),
    }
