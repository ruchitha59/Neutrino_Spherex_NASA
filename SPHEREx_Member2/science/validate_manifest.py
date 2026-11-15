"""Validation for the Member 1 manifest without imposing a new schema."""
from __future__ import annotations

import json
import os
from pathlib import Path
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse


def resolve_manifest_path(manifest_dir, local_path):
    """Resolve POSIX or Windows-style relative paths from a manifest."""
    if not local_path:
        return None
    text = str(local_path).replace("\\", os.sep).replace("/", os.sep)
    candidate = Path(text)
    if candidate.is_absolute():
        return candidate
    base = Path(manifest_dir)
    direct = base / candidate
    if direct.is_file():
        return direct
    basename = Path(text).name
    for fallback in (base / "raw" / basename, base.parent / "raw" / basename):
        if fallback.is_file():
            return fallback
    return direct


def validate_manifest(manifest_path):
    """Validate manifest structure, metadata, duplicates and local file presence."""
    manifest_path = Path(manifest_path)
    with manifest_path.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)

    errors, warnings, records = [], [], []
    if not isinstance(manifest, dict):
        raise ValueError("Manifest root must be a JSON object.")
    observations = manifest.get("observations")
    if not isinstance(observations, list):
        raise ValueError("Manifest must contain an observations array.")

    seen = Counter()
    for index, item in enumerate(observations):
        if not isinstance(item, dict):
            errors.append({"index": index, "error": "Observation record is not an object."})
            continue
        product_id = item.get("product_id") or item.get("observation_id") or item.get("obs_id")
        collection = item.get("collection")
        band = item.get("infrared_band") or item.get("band")
        url = item.get("access_url") or item.get("source_url")
        timestamp = item.get("observation_start_utc") or item.get("obs_time")
        center = item.get("requested_center") or {}
        ra = center.get("ra_deg", item.get("ra_deg"))
        dec = center.get("dec_deg", item.get("dec_deg"))
        local = item.get("local_file_path") or item.get("local_fits")
        key = (product_id, collection, band, url)
        seen[key] += 1

        row_errors = []
        if not product_id:
            row_errors.append("Missing product/observation identifier.")
        if not collection:
            row_errors.append("Missing collection/release.")
        if not url:
            row_errors.append("Missing archive source URL.")
        if not timestamp:
            row_errors.append("Missing observation timestamp.")
        else:
            try:
                datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            except ValueError:
                row_errors.append("Observation timestamp is not valid ISO-8601.")
        if ra is None or dec is None:
            row_errors.append("Missing requested coordinate metadata.")
        else:
            try:
                if not (0 <= float(ra) < 360 and -90 <= float(dec) <= 90):
                    row_errors.append("RA/Dec outside valid ICRS degree ranges.")
            except (TypeError, ValueError):
                row_errors.append("RA/Dec are not numeric.")
        if not band:
            warnings.append({"index": index, "warning": "Band metadata unavailable."})
        if url:
            parsed_url = urlparse(str(url))
            if parsed_url.scheme not in ("https", "http") or not parsed_url.netloc:
                row_errors.append("Archive source URL is not a valid HTTP(S) URL.")
        wave_min = item.get("wavelength_min_um")
        wave_max = item.get("wavelength_max_um")
        if wave_min is not None and wave_max is not None:
            try:
                if float(wave_min) <= 0 or float(wave_max) <= float(wave_min):
                    row_errors.append("Wavelength interval is invalid.")
            except (TypeError, ValueError):
                row_errors.append("Wavelength interval is not numeric.")
        if item.get("download_status") not in (None, "downloaded"):
            warnings.append({"index": index, "warning": f"Member 1 download status is {item.get('download_status')!r}."})

        resolved = resolve_manifest_path(manifest_path.parent, local)
        exists = bool(resolved and resolved.is_file())
        if local and not exists:
            row_errors.append(f"Local FITS file missing: {local}")
        if not local:
            row_errors.append("Missing local FITS path.")

        records.append({
            "index": index,
            "product_id": product_id,
            "collection": collection,
            "band": band,
            "timestamp": timestamp,
            "access_url": url,
            "local_file_path": str(resolved) if resolved else None,
            "file_exists": exists,
            "errors": row_errors,
        })
        for message in row_errors:
            errors.append({"index": index, "error": message})

    duplicate_keys = [
        {"key": list(key), "count": count}
        for key, count in seen.items() if count > 1
    ]
    if duplicate_keys:
        warnings.append({
            "warning": "Exact duplicate manifest product/collection/band/URL records found.",
            "records": duplicate_keys,
        })

    return {
        "schema_version": "1.0",
        "manifest_path": str(manifest_path),
        "observation_count": len(observations),
        "valid_record_count": sum(not row["errors"] for row in records),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "records": records,
    }
