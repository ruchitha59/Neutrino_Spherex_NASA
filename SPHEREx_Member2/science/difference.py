"""Pixel differences and significance with strict shape/validity checks."""
from __future__ import annotations

import numpy as np


def _same_shape(*arrays):
    shapes = [np.shape(a) for a in arrays]
    if any(shape != shapes[0] for shape in shapes[1:]):
        raise ValueError(f"All input arrays must have the same shape; got {shapes}.")


def make_difference(reference, comparison):
    """Return comparison_epoch - reference_epoch, preserving invalid pixels as NaN."""
    reference = np.asarray(reference, dtype=float)
    comparison = np.asarray(comparison, dtype=float)
    _same_shape(reference, comparison)
    valid = np.isfinite(reference) & np.isfinite(comparison)
    diff = np.full(reference.shape, np.nan, dtype=float)
    diff[valid] = comparison[valid] - reference[valid]
    return diff


def significance_difference(ref, cmp, ref_var, cmp_var):
    """Return (comparison-reference)/sqrt(ref_var+cmp_var) where valid.

    Variances must already be expressed on the same output grid and in
    squared units matching the science images. Zero denominator is invalid.
    """
    ref = np.asarray(ref, dtype=float)
    cmp = np.asarray(cmp, dtype=float)
    ref_var = np.asarray(ref_var, dtype=float)
    cmp_var = np.asarray(cmp_var, dtype=float)
    _same_shape(ref, cmp, ref_var, cmp_var)

    valid = (
        np.isfinite(ref) & np.isfinite(cmp) &
        np.isfinite(ref_var) & np.isfinite(cmp_var) &
        (ref_var >= 0) & (cmp_var >= 0)
    )
    out = np.full(ref.shape, np.nan, dtype=float)
    denom = np.sqrt(ref_var[valid] + cmp_var[valid])
    good = np.isfinite(denom) & (denom > 0)
    values = np.full(denom.shape, np.nan, dtype=float)
    values[good] = (cmp[valid][good] - ref[valid][good]) / denom[good]
    out[valid] = values
    return out
