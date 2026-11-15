
"""Conservative connected-component candidate extraction."""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def extract_difference_candidates(significance, difference, valid_mask, wcs,
                                  observation_pair, threshold_sigma=5.0,
                                  min_pixels=2, observation_times=None,
                                  variance=None, correlation_kernel=None):
    """Extract possible residual groups; never labels them confirmed discoveries."""
    sig = np.asarray(significance, dtype=float)
    diff = np.asarray(difference, dtype=float)
    valid = np.asarray(valid_mask, dtype=bool)
    if sig.shape != diff.shape or sig.shape != valid.shape:
        raise ValueError("Significance, difference and valid mask shapes must match.")
    var = None if variance is None else np.asarray(variance, dtype=float)
    if var is not None and var.shape != sig.shape:
        raise ValueError("Variance and significance arrays must have matching shapes.")
    rho = None if correlation_kernel is None else np.asarray(correlation_kernel, dtype=float)
    if rho is not None and (rho.ndim != 2 or rho.shape[0] != rho.shape[1] or rho.shape[0] % 2 != 1):
        raise ValueError("Correlation kernel must be square with odd dimensions.")
    candidates = []
    for sign in (1.0, -1.0):
        detected = valid & np.isfinite(sig) & (sign * sig >= threshold_sigma)
        labels, count = ndimage.label(detected)
        for label_id in range(1, count + 1):
            component = labels == label_id
            yy, xx = np.where(component)
            if len(xx) < min_pixels:
                continue
            weights = np.abs(sig[yy, xx])
            xcen = float(np.average(xx, weights=weights))
            ycen = float(np.average(yy, weights=weights))
            ra, dec = wcs.pixel_to_world_values(xcen, ycen)
            signed = float(np.nanmedian(diff[yy, xx]))
            covariance_factor = 1.0
            covariance_significance = None
            if rho is not None:
                from science.noise_covariance import component_correlation_factor
                covariance_factor = component_correlation_factor(component, rho)
            if var is not None:
                local_variance = var[component]
                if np.all(np.isfinite(local_variance) & (local_variance >= 0)):
                    total_variance = float(np.sum(local_variance) * covariance_factor)
                    flux_sum = float(np.sum(np.abs(diff[component])))
                    if total_variance > 0:
                        covariance_significance = flux_sum / np.sqrt(total_variance)
            if covariance_significance is not None and covariance_significance < threshold_sigma:
                continue
            candidate_id = f"cand_{len(candidates)+1:04d}"
            candidates.append({
            "candidate_id": candidate_id,
            "classification": "ambiguous/uncertain",
            "ra_deg": float(ra),
            "dec_deg": float(dec),
            "pixel_x": xcen,
            "pixel_y": ycen,
            "observation_pair": observation_pair,
            "observation_times": observation_times,
            "epoch_pair": observation_pair,
            "reference_flux": None,
            "comparison_flux": None,
            "flux_change": None,
            "measurement_uncertainty": None,
            "pixel_count": int(len(xx)),
            "median_difference": signed,
            "max_abs_significance": float(np.nanmax(np.abs(sig[yy, xx]))),
            "covariance_adjusted_component_significance": (
                float(covariance_significance)
                if covariance_significance is not None else None
            ),
            "noise_correlation_factor": float(covariance_factor),
            "quality_flags": [],
            "review_required": True,
            "artifact_warnings": [
                "Connected residual requires human review and source-level photometry."
            ],
            "classification_rationale": (
                "Thresholded residual component only; motion versus variability "
                "is not established."
            ),
            "scientific_caveat": (
                "This is an unverified candidate, not a confirmed discovery."
            ),
            })
    return candidates


def detect_sources(data, valid_mask, fwhm=2.5, threshold_sigma=5.0):
    """Detect point-like sources with Photutils DAOStarFinder.

    Returns a list of JSON-friendly centroid/shape records. This function
    requires Photutils and Astropy at runtime.
    """
    from astropy.stats import sigma_clipped_stats
    from photutils.detection import DAOStarFinder

    image = np.asarray(data, dtype=float)
    mask = ~np.asarray(valid_mask, dtype=bool) | ~np.isfinite(image)
    if mask.shape != image.shape:
        raise ValueError("Source mask and image shapes must match.")
    mean, median, std = sigma_clipped_stats(image, mask=mask, sigma=3.0)
    if not np.isfinite(std) or std <= 0:
        return []
    finder = DAOStarFinder(
        fwhm=float(fwhm),
        threshold=float(threshold_sigma) * float(std)
    )
    table = finder(image - median, mask=mask)
    if table is None:
        return []
    result = []
    for row in table:
        result.append({
            "x": float(row["xcentroid"]),
            "y": float(row["ycentroid"]),
            "flux": float(row["flux"]),
            "peak": float(row["peak"]),
            "sharpness": float(row["sharpness"]),
            "roundness1": float(row["roundness1"]),
            "roundness2": float(row["roundness2"]),
        })
    return result


def _aperture_coverage(valid_mask, x, y, radius):
    """Return image and valid-pixel coverage of a circular aperture.

    Coverage is weighted by the exact fractional pixel overlap returned by
    Photutils. The denominator is the full aperture area, including portions
    that may fall outside the image.
    """
    from photutils.aperture import CircularAperture

    valid = np.asarray(valid_mask, dtype=bool)
    if valid.ndim != 2:
        raise ValueError("Aperture validity mask must be two-dimensional.")

    aperture = CircularAperture((float(x), float(y)), r=float(radius))
    aperture_mask = aperture.to_mask(method="exact")
    total_weight = float(np.sum(aperture_mask.data))
    if not np.isfinite(total_weight) or total_weight <= 0:
        return {
            "image_coverage_fraction": 0.0,
            "valid_coverage_fraction": 0.0,
        }

    overlap_slices = aperture_mask.get_overlap_slices(valid.shape)
    large_slice, small_slice = overlap_slices
    if large_slice is None or small_slice is None:
        image_coverage = 0.0
        valid_coverage = 0.0
    else:
        weights = np.asarray(aperture_mask.data[small_slice], dtype=float)
        valid_overlap = valid[large_slice]
        image_coverage = float(np.sum(weights) / total_weight)
        valid_coverage = float(np.sum(weights * valid_overlap) / total_weight)

    return {
        "image_coverage_fraction": float(np.clip(image_coverage, 0.0, 1.0)),
        "valid_coverage_fraction": float(np.clip(valid_coverage, 0.0, 1.0)),
    }


def measure_aperture_photometry(data, sources, valid_mask, variance=None,
                                aperture_radius_px=2.5, background_per_pixel=0.0,
                                min_aperture_coverage=0.99,
                                correlation_kernel=None):
    """Measure circular-aperture flux and report incomplete aperture coverage.

    Flux/error values are withheld when less than ``min_aperture_coverage``
    of the full aperture has valid image support. The partial sum is retained
    separately for diagnostics and is never presented as a complete flux.
    """
    from photutils.aperture import CircularAperture, aperture_photometry

    image = np.asarray(data, dtype=float)
    valid = np.asarray(valid_mask, dtype=bool)
    if valid.shape != image.shape:
        raise ValueError("Aperture validity mask and image shapes must match.")
    mask = ~valid | ~np.isfinite(image)
    if not sources:
        return []
    if not 0.0 < float(min_aperture_coverage) <= 1.0:
        raise ValueError("min_aperture_coverage must be in (0, 1].")

    positions = [(float(s["x"]), float(s["y"])) for s in sources]
    apertures = CircularAperture(positions, r=float(aperture_radius_px))
    corrected = image - float(background_per_pixel)
    error = None
    if variance is not None:
        var = np.asarray(variance, dtype=float)
        if var.shape != image.shape:
            raise ValueError("Variance and image shapes must match.")
        error = np.sqrt(np.where(np.isfinite(var) & (var >= 0), var, np.nan))

    table = aperture_photometry(corrected, apertures, error=error, mask=mask)
    aperture_masks = apertures.to_mask(method="exact")
    if not isinstance(aperture_masks, list):
        aperture_masks = [aperture_masks]
    measurements = []
    for i, source in enumerate(sources):
        partial_flux = float(table["aperture_sum"][i])
        partial_error = (
            float(table["aperture_sum_err"][i])
            if error is not None and "aperture_sum_err" in table.colnames else None
        )
        correlation_correction = 1.0
        if (correlation_kernel is not None and variance is not None
                and aperture_masks[i] is not None):
            from science.noise_covariance import covariance_factor_for_weights
            aperture_mask = aperture_masks[i]
            large_slice, small_slice = aperture_mask.get_overlap_slices(image.shape)
            if large_slice is not None and small_slice is not None:
                local_weights = np.asarray(aperture_mask.data[small_slice], dtype=float)
                local_variance = np.asarray(var[large_slice], dtype=float)
                local_weights = np.where(valid[large_slice], local_weights, 0.0)
                cov = covariance_factor_for_weights(
                    local_weights, local_variance, correlation_kernel
                )
                if cov["covariance_variance"] >= 0:
                    partial_error = float(np.sqrt(cov["covariance_variance"]))
                    correlation_correction = float(np.sqrt(cov["correlation_factor"]))
        coverage = _aperture_coverage(
            valid & np.isfinite(image), source["x"], source["y"],
            aperture_radius_px,
        )
        image_fraction = coverage["image_coverage_fraction"]
        valid_fraction = coverage["valid_coverage_fraction"]
        truncated = image_fraction < 0.999
        incomplete = valid_fraction < float(min_aperture_coverage)

        # Never treat a truncated/masked aperture sum as a complete source flux.
        flux = None if incomplete else partial_flux
        flux_error = None if incomplete else partial_error
        warnings = []
        if truncated:
            warnings.append(
                "Circular aperture extends beyond the image boundary; "
                "full aperture coverage is unavailable."
            )
        if valid_fraction < float(min_aperture_coverage) and not truncated:
            warnings.append(
                "Circular aperture contains invalid or masked pixels; "
                "measured flux is incomplete."
            )

        measurements.append({
            **source,
            "aperture_flux": flux,
            "aperture_flux_error": flux_error,
            "aperture_flux_partial": partial_flux,
            "aperture_flux_error_partial": partial_error,
            "aperture_radius_px": float(aperture_radius_px),
            "background_per_pixel": float(background_per_pixel),
            "aperture_image_coverage_fraction": image_fraction,
            "aperture_valid_coverage_fraction": valid_fraction,
            "aperture_coverage_fraction": valid_fraction,
            "aperture_truncated_by_image_boundary": bool(truncated),
            "aperture_incomplete": bool(incomplete),
            "aperture_minimum_coverage_required": float(min_aperture_coverage),
            "noise_correlation_error_factor": correlation_correction,
            "aperture_warnings": warnings,
        })
    return measurements


def compare_source_catalogues(reference_sources, comparison_sources, wcs,
                              reference_metadata, comparison_metadata,
                              match_radius_px=3.0, variability_sigma=3.0,
                              motion_threshold_px=1.0):
    """Cross-match sources and report possible motion/variability candidates."""
    from scipy.spatial.distance import cdist
    from scipy.optimize import linear_sum_assignment

    if not reference_sources or not comparison_sources:
        return []
    ref_xy = np.array([[s["x"], s["y"]] for s in reference_sources], dtype=float)
    cmp_xy = np.array([[s["x"], s["y"]] for s in comparison_sources], dtype=float)
    distance_matrix = cdist(ref_xy, cmp_xy)
    ref_indices, cmp_indices = linear_sum_assignment(distance_matrix)
    candidates = []
    for i, j in zip(ref_indices, cmp_indices):
        distance = distance_matrix[i, j]
        if not np.isfinite(distance) or distance > float(match_radius_px):
            continue
        ref_source, cmp_source = reference_sources[i], comparison_sources[int(j)]
        dx = float(cmp_source["x"] - ref_source["x"])
        dy = float(cmp_source["y"] - ref_source["y"])
        position_change = float(np.hypot(dx, dy))
        ref_flux = ref_source.get("aperture_flux")
        cmp_flux = cmp_source.get("aperture_flux")
        ref_err = ref_source.get("aperture_flux_error")
        cmp_err = cmp_source.get("aperture_flux_error")
        flux_change = (
            None if ref_flux is None or cmp_flux is None
            else float(cmp_flux - ref_flux)
        )
        flux_significance = None
        if ref_err is not None and cmp_err is not None:
            denom = float(np.hypot(ref_err, cmp_err))
            if denom > 0 and flux_change is not None:
                flux_significance = float(flux_change / denom)

        ref_incomplete = bool(ref_source.get("aperture_incomplete", False))
        cmp_incomplete = bool(cmp_source.get("aperture_incomplete", False))
        aperture_incomplete = ref_incomplete or cmp_incomplete

        if aperture_incomplete:
            classification = "ambiguous/uncertain"
            rationale = (
                "Aperture photometry is incomplete in at least one observation; "
                "brightness variability cannot be assessed reliably."
            )
        elif (
            flux_significance is not None
            and abs(flux_significance) >= variability_sigma
            and position_change <= 0.5
        ):
            classification = "possible brightness variability"
            rationale = (
                "Aperture-flux change exceeds the configured uncertainty threshold "
                "while the centroid remains nearly fixed."
            )
        elif position_change >= motion_threshold_px:
            classification = "possible motion"
            rationale = (
                "Matched source centroid shifts by more than the configured pixel "
                "threshold after background alignment."
            )
        else:
            classification = "ambiguous/uncertain"
            rationale = (
                "Matched source does not meet the conservative motion or "
                "variability threshold."
            )

        ra, dec = wcs.pixel_to_world_values(ref_source["x"], ref_source["y"])
        candidates.append({
            "candidate_id": f"src_{len(candidates)+1:04d}",
            "classification": classification,
            "ra_deg": float(ra),
            "dec_deg": float(dec),
            "pixel_x": float(ref_source["x"]),
            "pixel_y": float(ref_source["y"]),
            "observation_pair": [
                reference_metadata.get("observation_id"),
                comparison_metadata.get("observation_id"),
            ],
            "observation_times": [
                reference_metadata.get("timestamp"),
                comparison_metadata.get("timestamp"),
            ],
            "epoch_pair": [
                reference_metadata.get("observation_id"),
                comparison_metadata.get("observation_id"),
            ],
            "reference_flux": ref_flux,
            "comparison_flux": cmp_flux,
            "flux_change": flux_change,
            "flux_change_significance": flux_significance,
            "reference_aperture_coverage_fraction": ref_source.get(
                "aperture_coverage_fraction"
            ),
            "comparison_aperture_coverage_fraction": cmp_source.get(
                "aperture_coverage_fraction"
            ),
            "reference_aperture_image_coverage_fraction": ref_source.get(
                "aperture_image_coverage_fraction"
            ),
            "comparison_aperture_image_coverage_fraction": cmp_source.get(
                "aperture_image_coverage_fraction"
            ),
            "reference_aperture_truncated_by_image_boundary": bool(
                ref_source.get("aperture_truncated_by_image_boundary", False)
            ),
            "comparison_aperture_truncated_by_image_boundary": bool(
                cmp_source.get("aperture_truncated_by_image_boundary", False)
            ),
            "aperture_incomplete": bool(aperture_incomplete),
            "near_image_boundary": bool(
                ref_source.get("aperture_truncated_by_image_boundary", False)
                or cmp_source.get("aperture_truncated_by_image_boundary", False)
            ),
            "review_required": True,
            "position_change_px": position_change,
            "position_dx_px": dx,
            "position_dy_px": dy,
            "quality_flags": [],
            "artifact_warnings": [
                "PSF matching is not currently performed.",
                "Centroid uncertainties are not yet propagated into the motion threshold.",
            ] + (
                [
                    "At least one circular aperture is incomplete; "
                    "flux variability significance is withheld."
                ] if aperture_incomplete else []
            ) + (
                ["At least one circular aperture extends beyond the image boundary."]
                if (
                    ref_source.get("aperture_truncated_by_image_boundary", False)
                    or cmp_source.get("aperture_truncated_by_image_boundary", False)
                ) else []
            ),
            "classification_rationale": rationale,
            "scientific_caveat": (
                "Possible candidate only; requires PSF-aware photometry, "
                "astrometric uncertainty review and human validation."
            ),
        })
    return candidates


def _local_valid_fraction(mask, x, y, radius):
    """Calculate valid-pixel fraction in a clipped local square."""
    array = np.asarray(mask, dtype=bool)

    if array.ndim != 2:
        raise ValueError("Local validity mask must be two-dimensional.")

    height, width = array.shape
    x = int(round(float(x)))
    y = int(round(float(y)))

    if x < 0 or y < 0 or x >= width or y >= height:
        return None

    x0 = max(0, x - radius)
    x1 = min(width, x + radius + 1)
    y0 = max(0, y - radius)
    y1 = min(height, y + radius + 1)

    patch = array[y0:y1, x0:x1]

    if patch.size == 0:
        return None

    return float(np.count_nonzero(patch) / patch.size)


def annotate_candidate_flags(
    candidates,
    reference_frame,
    comparison_frame,
    common_mask=None,
):
    """Attach central and nearby quality flags and local mask diagnostics.

    Existing three-argument calls remain supported.
    """
    informational_flags = {"SOURCE", "FULLSAMPLE"}

    documented_bad_flags = {
        "TRANSIENT", "OVERFLOW", "SUR_ERROR", "NONFUNC",
        "DICHROIC", "MISSING_DATA", "HOT", "COLD",
        "PHANMISS", "NONLINEAR", "PERSIST", "OUTLIER",
    }

    artifact_keywords = (
        "ghost", "streak", "bloom",
        "snowball", "halo", "crosstalk",
    )

    frames = (
        ("reference", reference_frame),
        ("comparison", comparison_frame),
    )

    for candidate in candidates:
        x = int(round(float(candidate.get("pixel_x", 0.0))))
        y = int(round(float(candidate.get("pixel_y", 0.0))))

        central_flags = []
        nearby_flags = []
        local_support = {}

        for label, frame in frames:
            flags = frame.get("flags")
            definitions = frame.get("flag_definitions", {})
            valid_mask = frame.get("valid_mask")

            if valid_mask is None:
                valid_mask = frame.get("valid_pixel_mask")

            if valid_mask is not None:
                local_support[label] = {
                    "valid_fraction_3x3": _local_valid_fraction(
                        valid_mask, x, y, 1
                    ),
                    "valid_fraction_5x5": _local_valid_fraction(
                        valid_mask, x, y, 2
                    ),
                }

            if flags is None:
                continue

            array = np.asarray(flags)

            if y < 0 or x < 0 or y >= array.shape[0] or x >= array.shape[1]:
                continue

            central_value = int(array[y, x])

            for name, info in definitions.items():
                bitmask = int(info["mask"])

                if central_value & bitmask:
                    central_flags.append(f"{label}:{name}")

            # Inspect nearby detector flags in a 5x5 region.
            y0 = max(0, y - 2)
            y1 = min(array.shape[0], y + 3)
            x0 = max(0, x - 2)
            x1 = min(array.shape[1], x + 3)

            patch = array[y0:y1, x0:x1].astype(np.int64)

            for name, info in definitions.items():
                if name in informational_flags:
                    continue

                description = (info.get("description") or "").lower()

                is_bad_flag = (
                    name in documented_bad_flags
                    or any(word in name.lower() for word in artifact_keywords)
                    or any(word in description for word in artifact_keywords)
                )

                if not is_bad_flag:
                    continue

                bitmask = int(info["mask"])

                if np.any((patch & bitmask) != 0):
                    nearby_flags.append(f"{label}:{name}")

        candidate["quality_flags"] = sorted(set(central_flags))
        candidate["nearby_quality_flags"] = sorted(set(nearby_flags))
        candidate["local_support"] = local_support

        # Use the common reference/comparison validity mask when supplied.
        if common_mask is not None:
            candidate["valid_fraction_3x3"] = _local_valid_fraction(
                common_mask, x, y, 1
            )
            candidate["valid_fraction_5x5"] = _local_valid_fraction(
                common_mask, x, y, 2
            )
        else:
            candidate["valid_fraction_3x3"] = None
            candidate["valid_fraction_5x5"] = None

        fraction_3x3 = candidate["valid_fraction_3x3"]
        fraction_5x5 = candidate["valid_fraction_5x5"]

        near_boundary = (
            fraction_3x3 is not None and fraction_3x3 < 1.0
        ) or (
            fraction_5x5 is not None and fraction_5x5 < 1.0
        )

        candidate["near_invalid_boundary"] = bool(near_boundary)
        candidate["detector_quality_warning"] = bool(nearby_flags)
        candidate["near_image_boundary"] = bool(
            candidate.get("near_image_boundary", False)
        )
        candidate["local_quality_review_required"] = bool(
            near_boundary
            or nearby_flags
            or candidate["near_image_boundary"]
        )

        # Preserve any existing review requirement. Every unverified source
        # candidate and every difference residual requires human review.
        candidate["review_required"] = bool(
            candidate.get("review_required", False)
            or candidate["local_quality_review_required"]
        )

        if near_boundary:
            candidate.setdefault("artifact_warnings", []).append(
                "Candidate lies near invalid pixels; local image support is incomplete."
            )

        if nearby_flags:
            candidate.setdefault("artifact_warnings", []).append(
                "Nearby detector-quality flags require inspection: "
                + ", ".join(sorted(set(nearby_flags)))
            )

        if candidate["near_image_boundary"]:
            candidate.setdefault("artifact_warnings", []).append(
                "Candidate aperture extends beyond the image boundary."
            )

        if candidate["review_required"]:
            candidate["artifact_warnings"] = sorted(
                set(candidate.get("artifact_warnings", []))
            )

    return candidates
