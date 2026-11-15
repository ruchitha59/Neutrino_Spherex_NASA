"""Reproducible Member 2 pipeline entry point.

The pipeline is deliberately conservative: incompatible observations are never
subtracted, and candidate extraction is gated by background-source alignment.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales

from science.inspect_fits import inspect_fits_metadata
from science.validate_manifest import validate_manifest, resolve_manifest_path
from science.quality import build_valid_mask, flag_definitions_from_header
from science.calibration import (
    evaluate_compatibility, estimate_background_offset, estimate_background_level
)
from science.alignment import reproject_observation, measure_alignment_residuals
from science.difference import make_difference, significance_difference
from science.visualization import shared_limits, save_preview
from science.detection import (
    extract_difference_candidates, detect_sources,
    measure_aperture_photometry, compare_source_catalogues,
    annotate_candidate_flags,
)
from science.psf_matching import measure_psf_covariance, match_pair_psf
from science.noise_covariance import estimate_noise_correlation
from science.psf import (
    load_epsf_grid,
    select_epsf_model,
    epsf_diagnostics,
    load_psf_cube,
    select_psf_model,
    psf_diagnostics,
)


LOGGER = logging.getLogger("spherex_member2")


def _frame_covers_center(frame, ra_deg, dec_deg):
    """Return whether an image footprint includes the requested sky center."""
    try:
        x, y = frame["wcs"].world_to_pixel_values(float(ra_deg), float(dec_deg))
        height, width = frame["image"].shape
        return bool(
            np.isfinite(x) and np.isfinite(y)
            and 0 <= x < width and 0 <= y < height
        )
    except Exception:
        return False


def _make_requested_center_grid(reference, cutout_size_deg):
    """Build a square grid centered on the search coordinate at input scale."""
    ref_wcs = reference["wcs"].deepcopy()
    center = reference["metadata"].get("requested_center") or {}
    if cutout_size_deg is None:
        return ref_wcs, reference["image"].shape

    pixel_scales_deg = np.asarray(proj_plane_pixel_scales(ref_wcs), dtype=float)
    pixel_scale_deg = float(np.nanmedian(np.abs(pixel_scales_deg)))
    if not np.isfinite(pixel_scale_deg) or pixel_scale_deg <= 0:
        raise ValueError("Reference image has an invalid celestial pixel scale.")
    size = max(2, int(round(float(cutout_size_deg) / pixel_scale_deg)))
    ref_wcs.wcs.crval = [float(center["ra_deg"]), float(center["dec_deg"])]
    ref_wcs.wcs.crpix = [(size + 1) / 2.0, (size + 1) / 2.0]
    return ref_wcs, (size, size)


def _read_observation(path, manifest_record):
    with fits.open(path, memmap=False) as hdul:
        science = [h for h in hdul if str(h.header.get("EXTNAME", h.name)).strip().upper() == "IMAGE"]
        if len(science) != 1:
            raise ValueError(f"{path}: expected exactly one IMAGE HDU, found {len(science)}.")
        sci = science[0]
        extensions = {str(h.header.get("EXTNAME", h.name)).strip().upper(): h for h in hdul}
        image = np.asarray(sci.data, dtype=float)
        wcs = WCS(sci.header).celestial
        if not wcs.has_celestial:
            raise ValueError(f"{path}: IMAGE HDU has no celestial WCS.")
        flags_hdu = extensions.get("FLAGS")
        variance_hdu = extensions.get("VARIANCE")
        flags = np.asarray(flags_hdu.data) if flags_hdu is not None and flags_hdu.data is not None else None
        variance = np.asarray(variance_hdu.data, dtype=float) if variance_hdu is not None and variance_hdu.data is not None else None
        definitions = flag_definitions_from_header(flags_hdu.header) if flags_hdu is not None else {}
        valid, counts = build_valid_mask(image, flags, variance, flag_definitions=definitions)
        metadata = {
            "product_id": manifest_record.get("product_id"),
            "observation_id": manifest_record.get("product_id"),
            "collection": manifest_record.get("collection"),
            "band": manifest_record.get("infrared_band"),
            "wavelength_min_um": manifest_record.get("wavelength_min_um"),
            "wavelength_max_um": manifest_record.get("wavelength_max_um"),
            "timestamp": manifest_record.get("observation_start_utc"),
            "access_url": manifest_record.get("access_url"),
            "bunit": sci.header.get("BUNIT"),
            "finast": sci.header.get("FINAST"),
            "detector": sci.header.get("DETECTOR"),
            "exposure_time_s": sci.header.get("TELAPSE") or sci.header.get("EXPTIME"),
            "psf_extension_available": ("EPSF" in extensions or "PSF" in extensions),
            "target_name": manifest_record.get("target_name"),
            "requested_center": manifest_record.get("requested_center"),
        }
    return {
        "path": str(path), "image": image, "wcs": wcs, "flags": flags,
        "variance": variance, "valid_mask": valid, "mask_counts": counts,
        "flag_definitions": definitions, "metadata": metadata,
    }


def _json_default(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return str(value)


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")

def _load_spatial_psf(fits_path):
    """Load whichever spatial PSF format is available."""
    from astropy.io import fits

    with fits.open(fits_path, memmap=False) as hdul:
        extensions = {
            str(hdu.header.get("EXTNAME", hdu.name)).strip().upper()
            for hdu in hdul
        }

    if "EPSF" in extensions:
        return {
            "type": "EPSF",
            "grid": load_epsf_grid(fits_path),
        }

    if "PSF" in extensions:
        return {
            "type": "PSF",
            "grid": load_psf_cube(fits_path),
        }

    raise ValueError("No supported EPSF or PSF extension found.")


def _candidate_epsf_report(candidate, original_frame, spatial_psf):
    """Select and report a spatial EPSF or PSF at a candidate position."""
    observation_id = original_frame["metadata"].get("observation_id")

    report = {
        "observation_id": observation_id,
        "status": "unavailable",
        "warnings": [],
    }

    if spatial_psf is None:
        report["warnings"].append(
            "Spatial PSF model could not be loaded for this observation."
        )
        return report

    try:
        ra = float(candidate["ra_deg"])
        dec = float(candidate["dec_deg"])

        x, y = original_frame["wcs"].world_to_pixel_values(ra, dec)
        x, y = float(x), float(y)

        if not np.isfinite(x) or not np.isfinite(y):
            raise ValueError("Original-image pixel coordinates are not finite.")

        image_shape = original_frame["image"].shape

        if not (0 <= x < image_shape[1] and 0 <= y < image_shape[0]):
            report["status"] = "outside_original_image"
            report["original_image_pixel"] = [x, y]
            report["warnings"].append(
                "Candidate position falls outside the original observation image."
            )
            return report

        psf_type = spatial_psf["type"]
        grid = spatial_psf["grid"]

        if psf_type == "EPSF":
            selected = select_epsf_model(grid, x, y)
            diagnostics = epsf_diagnostics(selected)
        elif psf_type == "PSF":
            selected = select_psf_model(grid, x, y)
            diagnostics = psf_diagnostics(selected)
        else:
            raise ValueError(f"Unsupported spatial PSF type: {psf_type}")

        report.update({
            "status": (
                "selected"
                if selected["within_grid_coverage"]
                else "outside_spatial_psf_grid"
            ),
            "psf_format": psf_type,
            "original_image_pixel": [x, y],
            "selected_model": {
                "record_index": selected["record_index"],
                "binx": selected["binx"],
                "biny": selected["biny"],
                "model_center_detector_coordinates": [
                    selected["xcenter"],
                    selected["ycenter"],
                ],
                "candidate_detector_coordinates": [
                    selected["aux_x"],
                    selected["aux_y"],
                ],
                "distance_from_model_center_detector_pixels": (
                    selected["distance_px"]
                ),
                "within_grid_coverage": selected["within_grid_coverage"],
                "wavelength_center_um": selected["cwave_um"],
                "wavelength_bandwidth_um": selected["cband_um"],
                "nstar": selected["nstar"],
                "neff_mean": selected["neff_mean"],
                "oversampling": [
                    selected["oversampling_x"],
                    selected["oversampling_y"],
                ],
                "epsf_shape": list(selected["epsf_shape"]),
                "normalization": selected["epsf_normalization"],
            },
            "diagnostics": diagnostics,
            "warnings": list(selected["warnings"]),
        })

    except Exception as exc:
        report["status"] = "error"
        report["warnings"].append(
            f"{type(exc).__name__}: {exc}"
        )

    return report


def process_manifest(manifest_path, output_dir, config_path=None):
    """Process the largest compatible same-release/same-band observation group.

    Parameters match the proposed PRD interface. The original Member 1
    manifest and FITS files are read-only.
    """
    manifest_path = Path(manifest_path)
    output_dir = Path(output_dir)
    config = {
        "max_epochs": 6,
        "alignment_threshold_sigma": 5.0,
        "alignment_min_matches": 3,
        "alignment_max_match_distance_px": 3.0,
        "candidate_threshold_sigma": 5.0,
        "background_source_mask_radius_px": 3.0,
    }
    if config_path:
        config.update(json.loads(Path(config_path).read_text(encoding="utf-8")))

    report = validate_manifest(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Preserve the complete original manifest metadata. The validation
    # report contains only a reduced record used for file validation.
    # The validator preserves each manifest row's original index. Use that
    # index to recover the exact source record. product_id alone is NOT unique:
    # the supplied manifest legitimately contains 2026W39_1A_0276_1 in both
    # SPHEREx-D3 and SPHEREx-D6.
    manifest_observations = manifest.get("observations", [])

    records = report["records"]
    usable = [r for r in records if r["file_exists"] and not r["errors"]]
    failures = [r for r in records if not r["file_exists"] or r["errors"]]

    loaded = []
    inspection_reports = []
    loaded_file_keys = set()

    for record in usable:
        try:
            path = Path(record["local_file_path"])
            manifest_index = record.get("index")

            if (
                not isinstance(manifest_index, int)
                or manifest_index < 0
                or manifest_index >= len(manifest_observations)
            ):
                raise ValueError(
                    "Validator record has no valid original manifest index; "
                    "refusing ambiguous metadata matching."
                )

            original_record = manifest_observations[manifest_index]
            original_id = (
                original_record.get("product_id")
                or original_record.get("observation_id")
                or original_record.get("obs_id")
            )
            original_band = (
                original_record.get("infrared_band")
                or original_record.get("band")
            )
            original_collection = original_record.get("collection")
            original_local = (
                original_record.get("local_file_path")
                or original_record.get("local_fits")
            )

            # Defensive cross-checks ensure validator rows and manifest rows
            # still refer to the same observation and exact local FITS file.
            if str(original_id) != str(record.get("product_id")):
                raise ValueError(
                    "Manifest index/product ID mismatch; refusing to load "
                    "the observation with uncertain metadata."
                )
            if original_band and str(original_band) != str(record.get("band")):
                raise ValueError(
                    "Manifest index/band mismatch; refusing to assign "
                    "metadata from a different spectral band."
                )
            if original_collection and str(original_collection) != str(record.get("collection")):
                raise ValueError(
                    "Manifest index/collection mismatch; refusing ambiguous metadata."
                )
            if original_local and Path(str(original_local).replace("\\\\", "/")).name != path.name:
                raise ValueError(
                    "Manifest index/local filename mismatch; refusing to load "
                    "the observation with uncertain metadata."
                )

            # Avoid processing an identical local FITS file twice, while
            # preserving legitimate same-product observations in different bands.
            file_key = str(path.resolve()).casefold()
            if file_key in loaded_file_keys:
                failures.append({
                    "product_id": record.get("product_id"),
                    "band": record.get("band"),
                    "error": "Duplicate local FITS path skipped to prevent self-comparison.",
                })
                continue
            loaded_file_keys.add(file_key)

            inspection_reports.append(inspect_fits_metadata(path))
            loaded.append(_read_observation(path, original_record))
        except Exception as exc:
            failures.append({
                "product_id": record.get("product_id"),
                "band": record.get("band"),
                "error": f"{type(exc).__name__}: {exc}",
            })
            LOGGER.exception("Could not load %s", record.get("product_id"))

    # Group only observations with verified release, band, units and field.
    # Never group records when essential scientific metadata is missing.
    groups = defaultdict(list)
    coverage_failures = []
    for item in loaded:
        m = item["metadata"]
        center = m.get("requested_center") or {}

        band = m.get("band")
        collection = m.get("collection")
        bunit = m.get("bunit")
        ra = center.get("ra_deg")
        dec = center.get("dec_deg")

        if (
            not collection
            or not band
            or not bunit
            or ra is None
            or dec is None
        ):
            LOGGER.warning(
                "Skipping observation %s from comparison grouping: "
                "required metadata is missing.",
                m.get("product_id"),
            )
            continue

        # SIA circle searches return any product intersecting the requested
        # field, including edge strips that do not contain the target. Such a
        # strip must never define the reference grid or enter a time series.
        center_covered = _frame_covers_center(item, ra, dec)
        if not center_covered:
            coverage_failures.append({
                "product_id": m.get("product_id"),
                "band": band,
                "error": "Requested target coordinate is outside this product footprint; excluded from time-series processing.",
            })
            continue

        field_key = (round(float(ra), 4), round(float(dec), 4))
        group_key = (collection, band, field_key, bunit)

        # A product identifier can occur in more than one band. Within one
        # group, however, the same product/band/source URL is one observation
        # and must never be compared with itself.
        observation_key = (
            str(m.get("product_id") or m.get("observation_id") or ""),
            str(collection),
            str(band),
            str(m.get("access_url") or ""),
            str(item.get("path") or ""),
        )
        existing_keys = {
            (
                str(existing["metadata"].get("product_id") or existing["metadata"].get("observation_id") or ""),
                str(existing["metadata"].get("collection") or ""),
                str(existing["metadata"].get("band") or ""),
                str(existing["metadata"].get("access_url") or ""),
                str(existing.get("path") or ""),
            )
            for existing in groups[group_key]
        }
        if observation_key in existing_keys:
            LOGGER.warning(
                "Skipping duplicate observation %s (%s) in comparison group.",
                m.get("product_id"), band,
            )
            continue
        groups[group_key].append(item)

    eligible_groups = [(key, sorted(items, key=lambda x: str(x["metadata"].get("timestamp") or "")))
                       for key, items in groups.items() if len(items) >= 2]
    eligible_groups.sort(key=lambda pair: len(pair[1]), reverse=True)

    processing = {
        "schema_version": "1.0",
        "job_id": output_dir.name,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "software_version": "0.1.0",
        "input_manifest": str(manifest_path),
        "input_observation_count": len(manifest.get("observations", [])),
        "usable_local_observation_count": len(loaded),
        "missing_or_failed_input_count": len(failures) + len(coverage_failures),
        "excluded_noncovering_input_count": len(coverage_failures),
        "input_failures": failures + coverage_failures,
        "input_observation_ids": [item["metadata"].get("observation_id") for item in loaded],
        "input_source_urls": [item["metadata"].get("access_url") for item in loaded],
        "fits_inspection": [
            {
                "path": item.get("path"),
                "hdu_count": item.get("hdu_count"),
                "selected_science_hdu": item.get("selected_science_hdu"),
                "science_selection_evidence": item.get("science_selection_evidence"),
                "science_shape": item.get("science_shape"),
                "bunit": item.get("bunit"),
                "wcs_valid": item.get("wcs_valid"),
                "observation_id": item.get("observation_id"),
                "observation_time": item.get("observation_time"),
                "detector": item.get("detector"),
                "finast": item.get("finast"),
                "hdus": [
                    {key: hdu.get(key) for key in ["index", "extname", "shape", "bunit", "wcs_valid"]}
                    for hdu in item.get("hdus", [])
                ],
            }
            for item in inspection_reports
        ],
        "groups_found": len(groups),
        "selected_group": None,
        "frames": [],
        "comparisons": [],
        "warnings": [],
        "errors": [],
        "status": "failed",
    }
    candidates = {"schema_version": "1.0", "job_id": output_dir.name, "candidates": []}

    if not eligible_groups:
        processing["warnings"].append("No two locally available observations share the same release, band, units and field.")
        processing["status"] = "failed"
        _write_json(output_dir / "results" / "processing.json", processing)
        _write_json(output_dir / "results" / "candidates.json", candidates)
        return processing

    group_key, frames = eligible_groups[0]
    frames = frames[:int(config["max_epochs"])]
    processing["selected_group"] = {
        "collection": group_key[0], "band": group_key[1],
        "field_center_rounded_deg": list(group_key[2]), "bunit": group_key[3],
        "epoch_count": len(frames),
    }

    # Prefer the observation with the largest usable footprint. SIA products
    # may be partial strips, so using the first chronological product can
    # collapse the common grid to a one-pixel-wide image.
    reference = max(
        frames,
        key=lambda frame: int(np.count_nonzero(frame["valid_mask"])),
    )
    frames = [reference] + [frame for frame in frames if frame is not reference]
    requested_center = reference["metadata"].get("requested_center") or {}
    cutout_size_deg = next((
        row.get("cutout_size_deg") for row in manifest_observations
        if row.get("requested_center") == requested_center
        and row.get("cutout_size_deg") is not None
    ), None)
    # Keep the archive-selected pixel scale/orientation while anchoring the
    # requested square field to the ICRS search coordinate.
    ref_wcs, shape_out = _make_requested_center_grid(reference, cutout_size_deg)
    processing["reference_grid"] = {
        "shape_out": list(shape_out),
        "radesys": reference["metadata"].get("radesys", "ICRS"),
        "ctype": list(ref_wcs.wcs.ctype),
        "crval": list(ref_wcs.wcs.crval),
        "crpix": list(ref_wcs.wcs.crpix),
        "pixel_scale_matrix": ref_wcs.pixel_scale_matrix.tolist(),
        "reference_observation_id": reference["metadata"].get("observation_id"),
        "grid_centered_on_requested_coordinate": cutout_size_deg is not None,
        "requested_cutout_size_deg": cutout_size_deg,
    }
    processing["reprojection"] = {
        "science_interpolation": "bilinear",
        "flags_interpolation": "nearest-neighbor",
        "variance_method": "squared bilinear weights; assumes independent input pixels",
        "covariance_modelled": "empirical short-range autocorrelation measured on masked blank sky",
    }
    processing["masking"] = {
        "nonfinite_science": True,
        "invalid_variance": True,
        "coverage_footprint": True,
        "flag_definitions_source": "FITS FLAGS HDU header (MSKN/MSKM/MSKD or MP_* bit positions)",
    }
    processing["calibration_and_normalization"] = {
        "release_band_unit_compatibility_required": True,
        "background_offset": "source-masked diagnostic only; not applied",
        "photometric_scale_normalization": "not applied",
        "psf_matching": "local spatial PSFs homogenized to a conservative common Gaussian before differencing",
    }
    processing["alignment_tolerances"] = {
        "min_background_matches": int(config["alignment_min_matches"]),
        "median_offset_px_max": 0.5,
        "rms_offset_px_max": 1.0,
        "target_exclusion_radius_px": 3.0,
    }
    projected = []
    for index, frame in enumerate(frames):
        try:
            aligned = reproject_observation(frame["path"], ref_wcs, shape_out)
            valid, counts = build_valid_mask(
                aligned["image"], aligned["flags"], aligned["variance"],
                aligned["footprint"], frame["flag_definitions"]
            )
            aligned["valid_mask"] = valid
            aligned["mask_counts"] = counts
            aligned["metadata"] = frame["metadata"]
            aligned["flag_definitions"] = frame["flag_definitions"]
            aligned["source_path"] = frame["path"]
            aligned["source_frame_index"] = index
            projected.append(aligned)

            processed_path = output_dir / "processed" / f"frame_{index:03d}_aligned.fits"
            processed_path.parent.mkdir(parents=True, exist_ok=True)
            out_header = ref_wcs.to_header(relax=True)
            out_header["BUNIT"] = str(frame["metadata"].get("bunit") or "")
            out_header["OBSID"] = str(frame["metadata"].get("observation_id") or "")
            out_header["DATE-OBS"] = str(frame["metadata"].get("timestamp") or "")
            fits.PrimaryHDU(data=aligned["image"], header=out_header).writeto(processed_path, overwrite=True)

            processing["frames"].append({
                "index": index,
                "observation_id": frame["metadata"].get("observation_id"),
                "timestamp": frame["metadata"].get("timestamp"),
                "collection": frame["metadata"].get("collection"),
                "band": frame["metadata"].get("band"),
                "wavelength_min_um": frame["metadata"].get("wavelength_min_um"),
                "wavelength_max_um": frame["metadata"].get("wavelength_max_um"),
                "bunit": frame["metadata"].get("bunit"),
                "exposure_time_s": frame["metadata"].get("exposure_time_s"),
                "psf_extension_available": frame["metadata"].get("psf_extension_available"),
                "source_url": frame["metadata"].get("access_url"),
                "source_file": frame["path"],
                "aligned_fits": str(processed_path.relative_to(output_dir)),
                "mask_counts": counts,
                "variance_available": aligned["variance"] is not None,
                "finast": frame["metadata"].get("finast"),
            })
        except Exception as exc:
            processing["errors"].append({
                "observation_id": frame["metadata"].get("observation_id"),
                "error": f"{type(exc).__name__}: {exc}",
            })

    if not projected:
        processing["status"] = "failed"
        _write_json(output_dir / "results" / "processing.json", processing)
        _write_json(output_dir / "results" / "candidates.json", candidates)
        return processing

    limits = shared_limits([p["image"] for p in projected])
    for index, item in enumerate(projected):
        frame_meta = item["metadata"]
        title = " | ".join(str(x) for x in [
            frame_meta.get("observation_id"), frame_meta.get("timestamp"),
            frame_meta.get("collection"), frame_meta.get("band")
        ] if x)
        frame_index = item["source_frame_index"]
        preview = output_dir / "previews" / f"frame_{frame_index:03d}.png"
        save_preview(item["image"], preview, title, frame_meta.get("bunit"),
                     limits[0], limits[1], mask=item["valid_mask"])
        preview_stretches = {"linear": str(preview.relative_to(output_dir))}
        mask_overlays = {}
        for stretch in ("log", "sqrt", "asinh"):
            stretched = output_dir / "previews" / f"frame_{frame_index:03d}_{stretch}.png"
            save_preview(item["image"], stretched, title, frame_meta.get("bunit"),
                         limits[0], limits[1], mask=item["valid_mask"],
                         stretch=stretch)
            preview_stretches[stretch] = str(stretched.relative_to(output_dir))
        for stretch in ("linear", "log", "sqrt", "asinh"):
            overlay = output_dir / "previews" / f"frame_{frame_index:03d}_mask_{stretch}.png"
            save_preview(item["image"], overlay, title, frame_meta.get("bunit"),
                         limits[0], limits[1], mask=item["valid_mask"],
                         stretch=stretch, overlay_invalid=True)
            mask_overlays[stretch] = str(overlay.relative_to(output_dir))
        frame_record = next(row for row in processing["frames"] if row["index"] == frame_index)
        frame_record["preview"] = str(preview.relative_to(output_dir))
        frame_record["preview_stretches"] = preview_stretches
        frame_record["mask_overlays"] = mask_overlays
    # Load each original observation's spatial PSF once.
    # Supports the legacy EPSF table and the newer PSF image cube.
    # The cache is keyed by the original frame index.
    spatial_psf_grids = {}

    for item in projected:
        frame_index = item["source_frame_index"]
        if frame_index in spatial_psf_grids:
            continue

        original_frame = frames[frame_index]

        try:
            spatial_psf_grids[frame_index] = _load_spatial_psf(
                original_frame["path"]
            )
        except Exception as exc:
            spatial_psf_grids[frame_index] = None
            processing["warnings"].append(
                "Spatial PSF unavailable for observation "
                f"{original_frame['metadata'].get('observation_id')}: "
                f"{type(exc).__name__}: {exc}"
            )
            
    for index in range(1, len(projected)):
        ref, cmp = projected[0], projected[index]
        ref_meta, cmp_meta = ref["metadata"], cmp["metadata"]
        compatibility = evaluate_compatibility(ref_meta, cmp_meta)
        comparison_result = {
            "reference_observation_id": ref_meta.get("observation_id"),
            "comparison_observation_id": cmp_meta.get("observation_id"),
            "compatibility": compatibility,
        }
        if not compatibility["compatible"]:
            comparison_result["status"] = "blocked_incompatible"
            processing["comparisons"].append(comparison_result)
            continue

        requested_center = ref_meta.get("requested_center") or {}
        exclude_position = None
        if requested_center.get("ra_deg") is not None and requested_center.get("dec_deg") is not None:
            try:
                exclude_position = ref_wcs.world_to_pixel_values(
                    float(requested_center["ra_deg"]), float(requested_center["dec_deg"])
                )
            except Exception:
                exclude_position = None
        alignment = measure_alignment_residuals(
            ref["image"], cmp["image"], ref["valid_mask"], cmp["valid_mask"],
            threshold_sigma=float(config["alignment_threshold_sigma"]),
            max_match_distance_px=float(config["alignment_max_match_distance_px"]),
            min_matches=int(config["alignment_min_matches"]),
            exclude_position_px=exclude_position,
            exclude_radius_px=3.0,
        )
        comparison_result["alignment"] = alignment
        if not alignment["passed"]:
            comparison_result["status"] = "blocked_alignment"
            comparison_result["reason"] = "Difference and candidate extraction withheld because background-source alignment did not pass."
            processing["comparisons"].append(comparison_result)
            continue

        raw_ref, raw_cmp = ref, cmp
        ref_original = frames[raw_ref["source_frame_index"]]
        cmp_original = frames[raw_cmp["source_frame_index"]]
        center = ref_meta.get("requested_center") or {}
        center_ra = center.get("ra_deg")
        center_dec = center.get("dec_deg")
        if center_ra is None or center_dec is None:
            center_ra, center_dec = ref_wcs.pixel_to_world_values(
                (shape_out[1] - 1) / 2.0, (shape_out[0] - 1) / 2.0
            )
        try:
            ref_psf = measure_psf_covariance(
                spatial_psf_grids.get(raw_ref["source_frame_index"]),
                ref_original["wcs"], ref_wcs, center_ra, center_dec,
            )
            cmp_psf = measure_psf_covariance(
                spatial_psf_grids.get(raw_cmp["source_frame_index"]),
                cmp_original["wcs"], ref_wcs, center_ra, center_dec,
            )
            matched_pair = match_pair_psf(
                raw_ref["image"], raw_cmp["image"],
                raw_ref["variance"], raw_cmp["variance"],
                raw_ref["flags"], raw_cmp["flags"],
                raw_ref["valid_mask"], raw_cmp["valid_mask"],
                ref_psf["covariance_px2"], cmp_psf["covariance_px2"],
            )
        except Exception as exc:
            comparison_result["status"] = "blocked_psf_matching"
            comparison_result["reason"] = (
                "Difference and candidate extraction withheld because reliable "
                f"PSF matching was unavailable: {type(exc).__name__}: {exc}"
            )
            processing["comparisons"].append(comparison_result)
            continue

        ref = {**raw_ref, **matched_pair["reference"]}
        cmp = {**raw_cmp, **matched_pair["comparison"]}
        comparison_result["psf_matching"] = {
            "status": "complete",
            "method": matched_pair["method"],
            "reference_psf_fwhm_px": ref_psf["fwhm_reference_px"],
            "comparison_psf_fwhm_px": cmp_psf["fwhm_reference_px"],
            "reference_covariance_px2": ref_psf["covariance_px2"],
            "comparison_covariance_px2": cmp_psf["covariance_px2"],
            "target_covariance_px2": matched_pair["target_covariance_px2"],
            "reference_kernel_shape": matched_pair["reference_kernel_shape"],
            "comparison_kernel_shape": matched_pair["comparison_kernel_shape"],
            "safety_fraction": matched_pair["safety_fraction"],
            "minimum_padding_px2": matched_pair["minimum_padding_px2"],
        }

        common_mask = ref["valid_mask"] & cmp["valid_mask"]

        # Detect sources once in each aligned observation. DAOStarFinder
        # returns subpixel centroids that are also reused for photometry.
        ref_sources = detect_sources(ref["image"], ref["valid_mask"])
        cmp_sources = detect_sources(cmp["image"], cmp["valid_mask"])

        # SOURCE is informational in these FITS products. Do not reject it
        # as a quality bit: all pixels in the inspected cutouts carry it.
        # Instead, mask regions around detected sources when estimating sky.
        background_mask = common_mask.copy()
        source_mask_radius_px = float(
            config.get("background_source_mask_radius_px", 3.0)
        )
        yy, xx = np.ogrid[:background_mask.shape[0],
                          :background_mask.shape[1]]

        for source in ref_sources + cmp_sources:
            source_x = float(source["x"])
            source_y = float(source["y"])
            distance_squared = (
                (xx - source_x) ** 2 + (yy - source_y) ** 2
            )
            background_mask &= (
                distance_squared > source_mask_radius_px ** 2
            )

        # Exclude the requested target location from the sky estimate too.
        if exclude_position is not None:
            target_x, target_y = map(float, exclude_position)
            target_distance_squared = (
                (xx - target_x) ** 2 + (yy - target_y) ** 2
            )
            background_mask &= (
                target_distance_squared > source_mask_radius_px ** 2
            )

        background = estimate_background_offset(
            ref["image"], cmp["image"], background_mask
        )
        reference_noise = estimate_noise_correlation(
            ref["image"], background_mask
        )
        comparison_noise = estimate_noise_correlation(
            cmp["image"], background_mask
        )
        ref_background = estimate_background_level(
            ref["image"], background_mask
        )
        cmp_background = estimate_background_level(
            cmp["image"], background_mask
        )
        difference = make_difference(ref["image"], cmp["image"])
        difference[~common_mask] = np.nan
        difference_noise = estimate_noise_correlation(
            difference, background_mask
        )
        diff_path = output_dir / "processed" / f"difference_000_{index:03d}.fits"
        fits.PrimaryHDU(data=difference, header=ref_wcs.to_header(relax=True)).writeto(diff_path, overwrite=True)
        diff_png = output_dir / "previews" / f"difference_000_{index:03d}.png"
        save_preview(difference, diff_png, "Comparison - reference", ref_meta.get("bunit"), cmap="coolwarm")

        significance_path = None
        significance_png = None
        candidate_rows = []
        if ref["variance"] is not None and cmp["variance"] is not None:
            significance = significance_difference(
                ref["image"], cmp["image"], ref["variance"], cmp["variance"]
            )
            significance[~common_mask] = np.nan
            sig_path = output_dir / "processed" / f"significance_000_{index:03d}.fits"
            fits.PrimaryHDU(data=significance, header=ref_wcs.to_header(relax=True)).writeto(sig_path, overwrite=True)
            significance_path = str(sig_path.relative_to(output_dir))
            sig_png = output_dir / "previews" / f"significance_000_{index:03d}.png"
            save_preview(significance, sig_png, "Difference significance", "sigma", cmap="coolwarm")
            significance_png = str(sig_png.relative_to(output_dir))
            candidate_rows = extract_difference_candidates(
                significance, difference, common_mask, ref_wcs,
                [ref_meta.get("observation_id"), cmp_meta.get("observation_id")],
                threshold_sigma=float(config["candidate_threshold_sigma"]),
                observation_times=[ref_meta.get("timestamp"), cmp_meta.get("timestamp")],
                variance=ref["variance"] + cmp["variance"],
                correlation_kernel=(
                    difference_noise["kernel"]
                    if difference_noise["available"] else None
                ),
            )
            for candidate_index, candidate in enumerate(candidate_rows, start=1):
                candidate["candidate_id"] = f"diff_{index:03d}_{candidate_index:04d}"
            annotate_candidate_flags(
    candidate_rows, ref, cmp, common_mask=common_mask
)

            # Recover the corresponding original observations.
            ref_original = frames[ref["source_frame_index"]]
            cmp_original = frames[cmp["source_frame_index"]]

            ref_spatial_psf = spatial_psf_grids.get(
                ref["source_frame_index"]
            )
            cmp_spatial_psf = spatial_psf_grids.get(
                cmp["source_frame_index"]
            )

            for candidate in candidate_rows:
                candidate["epsf_analysis"] = {
                    "reference": _candidate_epsf_report(
                        candidate, ref_original, ref_spatial_psf
                    ),
                    "comparison": _candidate_epsf_report(
                        candidate, cmp_original, cmp_spatial_psf
                    ),
                    "psf_matching_performed": True,
                    "interpretation": (
                        "The pair was convolved to a conservative common local "
                        "PSF before differencing; native spatial PSF diagnostics "
                        "are retained for human review."
                    ),
                }

            candidates["candidates"].extend(candidate_rows)

        source_catalogue_summary = {
            "reference_source_count": None,
            "comparison_source_count": None,
            "matched_candidate_count": 0,
            "photometry_available": False,
        }
        try:
            if not ref_background["available"] or not cmp_background["available"]:
                raise RuntimeError("Insufficient source-masked background pixels for reliable aperture photometry.")
            ref_photometry = measure_aperture_photometry(
                ref["image"], ref_sources, ref["valid_mask"], ref["variance"],
                background_per_pixel=ref_background["median"],
                correlation_kernel=(
                    reference_noise["kernel"]
                    if reference_noise["available"] else None
                ),
            )
            cmp_photometry = measure_aperture_photometry(
                cmp["image"], cmp_sources, cmp["valid_mask"], cmp["variance"],
                background_per_pixel=cmp_background["median"],
                correlation_kernel=(
                    comparison_noise["kernel"]
                    if comparison_noise["available"] else None
                ),
            )
            source_candidates = compare_source_catalogues(
                ref_photometry, cmp_photometry, ref_wcs, ref_meta, cmp_meta
            )
            for candidate_index, candidate in enumerate(source_candidates, start=1):
                candidate["candidate_id"] = f"source_{index:03d}_{candidate_index:04d}"
            annotate_candidate_flags(
    source_candidates, ref, cmp, common_mask=common_mask
)
            candidates["candidates"].extend(source_candidates)
            source_catalogue_summary = {
                "reference_source_count": len(ref_sources),
                "comparison_source_count": len(cmp_sources),
                "matched_candidate_count": len(source_candidates),
                "photometry_available": True,
                "reference_covariance_available": reference_noise["available"],
                "comparison_covariance_available": comparison_noise["available"],
            }
        except ImportError as exc:
            processing["warnings"].append(
                f"Photutils source photometry unavailable; difference-only candidate extraction used: {exc}"
            )
        except Exception as exc:
            processing["warnings"].append(
                f"Source photometry failed for {cmp_meta.get('observation_id')}: {type(exc).__name__}: {exc}"
            )

        comparison_result.update({
            "status": "complete",
            "difference_fits": str(diff_path.relative_to(output_dir)),
            "difference_preview": str(diff_png.relative_to(output_dir)),
            "significance_fits": significance_path,
            "significance_preview": significance_png,
            "background_diagnostic": background,
            "reference_background": ref_background,
            "comparison_background": cmp_background,
            "source_catalogue": source_catalogue_summary,
            "candidate_count": len(candidate_rows) + source_catalogue_summary["matched_candidate_count"],
            "noise_covariance": {
                "status": "empirically_estimated" if difference_noise["available"] else "unavailable",
                "method": difference_noise.get("method"),
                "max_lag_px": difference_noise.get("max_lag_px"),
                "blank_sky_samples": difference_noise.get("sample_count"),
                "correlation_kernel": difference_noise["kernel"],
                "reference_blank_sky_samples": reference_noise.get("sample_count"),
                "comparison_blank_sky_samples": comparison_noise.get("sample_count"),
            },
            "variance_covariance_note": "Marginal variances are propagated through reprojection and PSF matching; empirical short-range covariance is estimated from masked blank sky and used for candidate/aperture significance.",
            "psf_matching_status": "performed_before_difference_and_photometry",
            "photometric_claims": "not_supported_without_source_level_photometry_and_psf_validation",
        })
        processing["comparisons"].append(comparison_result)

    if failures or coverage_failures:
        excluded_count = len(failures) + len(coverage_failures)
        processing["warnings"].append(
            f"{excluded_count} manifest inputs were unavailable or did not cover the requested target; the usable subset was processed."
        )
    if any(c.get("status") == "complete" for c in processing["comparisons"]):
        processing["status"] = "complete" if not failures and not coverage_failures else "partial"
    elif processing["frames"]:
        processing["status"] = "partial"
        processing["warnings"].append("Frames were inspected/reprojected, but no comparison passed all scientific gates.")
    else:
        processing["status"] = "failed"

    processing["candidate_count"] = len(candidates["candidates"])
    _write_json(output_dir / "results" / "processing.json", processing)
    _write_json(output_dir / "results" / "candidates.json", candidates)
    return processing


def main():
    parser = argparse.ArgumentParser(description="Run SPHEREx Member 2 processing.")
    parser.add_argument("--manifest", required=True, help="Path to Member 1 manifest.json")
    parser.add_argument("--output-dir", required=True, help="Directory for processing products")
    parser.add_argument("--config", default=None, help="Optional JSON configuration file")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = process_manifest(args.manifest, args.output_dir, args.config)
    print(json.dumps({
        "status": result["status"],
        "usable_observations": result["usable_local_observation_count"],
        "frames_written": len(result["frames"]),
        "comparisons": len(result["comparisons"]),
        "candidates": result.get("candidate_count", 0),
    }, indent=2))
    raise SystemExit(0 if result["status"] in ("complete", "partial") else 1)


if __name__ == "__main__":
    main()

