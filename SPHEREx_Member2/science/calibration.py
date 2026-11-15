"""Observation compatibility and background diagnostics."""
from __future__ import annotations

import numpy as np


def evaluate_compatibility(reference, comparison):
    """Decide whether two observations are eligible for pixel subtraction."""
    reasons, warnings = [], []
    for field, label in [
        ("collection", "data release/collection"),
        ("band", "spectral band"),
        ("bunit", "science units"),
    ]:
        left, right = reference.get(field), comparison.get(field)
        if left is None or right is None:
            warnings.append(f"{label} metadata missing; compatibility cannot be fully verified.")
        elif str(left).strip().lower() != str(right).strip().lower():
            reasons.append(f"Incompatible {label}: {left!r} versus {right!r}.")

    left_wave = (reference.get("wavelength_min_um"), reference.get("wavelength_max_um"))
    right_wave = (comparison.get("wavelength_min_um"), comparison.get("wavelength_max_um"))
    if all(v is not None for v in left_wave + right_wave):
        try:
            if not np.allclose(np.asarray(left_wave, float), np.asarray(right_wave, float), rtol=0, atol=1e-4):
                reasons.append(f"Incompatible wavelength intervals: {left_wave} versus {right_wave}.")
        except (TypeError, ValueError):
            warnings.append("Wavelength metadata is not numeric.")
    else:
        warnings.append("Wavelength interval metadata incomplete.")

    for item in (reference, comparison):
        finast = item.get("finast")
        if finast is None:
            warnings.append("FINAST astrometric-quality flag unavailable.")
        elif str(finast).strip() not in ("0", "0.0"):
            reasons.append(f"FINAST indicates non-good astrometry: {finast}.")

    if reference.get("psf_extension_available") and comparison.get("psf_extension_available"):
        warnings.append("PSF extensions are present, but PSF matching has not been performed.")
    else:
        warnings.append("PSF information incomplete; PSF matching has not been performed.")

    return {
        "compatible": not reasons,
        "reasons": reasons,
        "warnings": sorted(set(warnings)),
        "comparison_policy": "same collection, same band, same units and matching wavelength interval",
    }


def estimate_background_offset(reference, comparison, valid_mask):
    """Estimate a robust median offset; does not apply normalization."""
    ref = np.asarray(reference, dtype=float)
    cmp = np.asarray(comparison, dtype=float)
    mask = np.asarray(valid_mask, dtype=bool)
    if ref.shape != cmp.shape or ref.shape != mask.shape:
        raise ValueError("Reference, comparison and mask shapes must match.")
    sample = mask & np.isfinite(ref) & np.isfinite(cmp)
    if sample.sum() < 20:
        return {"available": False, "offset": None, "reason": "Fewer than 20 valid pixels."}
    delta = cmp[sample] - ref[sample]
    median = float(np.median(delta))
    mad = float(1.4826 * np.median(np.abs(delta - median)))
    return {
        "available": True,
        "offset": median,
        "robust_scatter": mad,
        "sample_pixels": int(sample.sum()),
        "applied": False,
        "note": "Diagnostic only. No automatic background subtraction was applied.",
    }


def estimate_background_level(image, background_mask):
    """Estimate a per-pixel background from valid source-masked pixels."""
    data = np.asarray(image, dtype=float)
    mask = np.asarray(background_mask, dtype=bool)
    if data.shape != mask.shape:
        raise ValueError("Image and background mask shapes must match.")
    sample = data[mask & np.isfinite(data)]
    if sample.size < 20:
        return {"available": False, "median": None, "scatter": None,
                "sample_pixels": int(sample.size)}
    median = float(np.median(sample))
    scatter = float(1.4826 * np.median(np.abs(sample - median)))
    return {"available": True, "median": median, "scatter": scatter,
            "sample_pixels": int(sample.size)}
