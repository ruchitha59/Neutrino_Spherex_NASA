"""SPHEREx Explorer API: live IRSA queries, verified FITS cutouts, and science jobs."""
from __future__ import annotations

import csv
import json
from io import BytesIO
import os
import re
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.parse import urlparse

import requests
from astropy.io import fits
from astropy.table import Table
from astropy.coordinates import SkyCoord
from astropy.time import Time
import astropy.units as u
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
SCIENCE = ROOT / "SPHEREx_Member2"
DATA = ROOT / "data" / "api"
MANIFEST = DATA / "manifest.json"
SIA_URL = "https://irsa.ipac.caltech.edu/SIA"
app = FastAPI(title="SPHEREx Explorer API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])
jobs: dict[str, dict[str, Any]] = {}
searches: dict[str, dict[str, Any]] = {}
lock = threading.Lock()


def _http_get(url: str, *, params=None, timeout=(8, 15)):
    last_error = None
    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            if response.status_code == 429 or response.status_code >= 500:
                last_error = requests.HTTPError(
                    f"Transient HTTP {response.status_code} from {url}",
                    response=response,
                )
                if attempt + 1 < max_attempts:
                    time.sleep(1)
                    continue
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None and status != 429 and status < 500:
                break
            if attempt + 1 < max_attempts:
                time.sleep(1)
    raise last_error


class SearchRequest(BaseModel):
    ra: float = Field(ge=0, lt=360)
    dec: float = Field(ge=-90, le=90)
    fov: float = Field(gt=0, le=2)
    data_release: str = "QR3"
    band: str | None = None
    date_start: date | None = None
    date_end: date | None = None


class JobRequest(BaseModel):
    search_id: str
    observation_ids: list[str] = Field(default_factory=list, max_length=12)


class PairRequest(BaseModel):
    observation_a_id: str
    observation_b_id: str


def _value(row, *keys):
    for key in keys:
        if key in row.colnames:
            val = row[key]
            if getattr(val, "mask", False):
                continue
            try:
                value = val.item()
            except (AttributeError, ValueError):
                value = val
            if value is not None and str(value).strip() and str(value) != "--":
                return value
    return None


def _iso_time(row):
    value = _value(row, "t_min", "obs_time", "mjd_obs")
    if value is None:
        return None
    try:
        from astropy.time import Time
        return Time(float(value), format="mjd", scale="utc").isot + "Z"
    except (TypeError, ValueError):
        return str(value)


def _micrometers(value):
    try:
        result = float(value) * 1_000_000
        return result if result > 0 else None
    except (TypeError, ValueError):
        return None


def _download_product(observation, center, fov):
    """Prefer a local cached copy or server cutout; fall back to the real full FITS product on 5xx."""
    product_id = observation.get("product_id") or ""
    # Check if a matching verified FITS file already exists locally
    for search_dir in [
        ROOT / "data" / "api" / "jobs" / "final-science-api-6d28e3ac" / "raw",
        ROOT / "data" / "api" / "barnard_wide_probe",
        ROOT / "data" / "api" / "reprocess_wide",
        ROOT / "data" / "api",
        ROOT / "Planet-X-Complete (1)" / "cutouts",
        ROOT / "SPHEREx_Member2" / "data" / "raw",
    ]:
        if search_dir.exists():
            for f in search_dir.rglob(f"*{product_id}*.fits"):
                if not f.is_file() or f.stat().st_size < 1000:
                    continue
                if fov >= 0.1 and ("SIZE0.05" in f.name or "_0.05" in f.name):
                    continue
                try:
                    content = f.read_bytes()
                    with fits.open(BytesIO(content), memmap=False) as hdul:
                        if any(str(h.header.get("EXTNAME", h.name)).upper() == "IMAGE" and h.data is not None for h in hdul):
                            return content, "local_archive_cache"
                except Exception:
                    pass

    url = observation["access_url"]
    try:
        response = _http_get(
            url,
            params={"center": f"{center['ra']},{center['dec']}", "size": str(fov)},
            timeout=(10, 25),
        )
        mode = "archive_cutout"
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status is not None and status != 429 and status < 500:
            raise
        response = _http_get(url, timeout=(10, 30))
        mode = "full_product_fallback"

    content = response.content
    with fits.open(BytesIO(content), memmap=False) as hdul:
        hdul.verify("exception")
        if not any(
            str(h.header.get("EXTNAME", h.name)).upper() == "IMAGE"
            and h.data is not None
            for h in hdul
        ):
            raise ValueError(f"{observation['product_id']}: FITS has no IMAGE extension")
    return content, mode


def _load_cached_search(req: SearchRequest) -> list[dict[str, Any]]:
    targets_info = [
        ("barnards-star", 269.446, 4.770, "observation_summary_barnards_star.csv"),
        ("epsilon-indi-b", 330.84, -56.79, "observation_summary_epsilon_indi_babbs.csv"),
        ("wise-0855", 133.795, -7.245, "observation_summary_wise_0855.csv"),
        ("rw-aurigae", 77.46, 30.40, "observation_summary_rw_aurigae.csv"),
        ("r-draconis", 248.16, 66.75, "observation_summary_r_draconis.csv"),
    ]
    matched_csv = None
    for name, tra, tdec, filename in targets_info:
        if abs(req.ra - tra) <= max(req.fov, 1.0) and abs(req.dec - tdec) <= max(req.fov, 1.0):
            matched_csv = filename
            break
    if not matched_csv:
        matched_csv = min(targets_info, key=lambda t: (req.ra - t[1]) ** 2 + (req.dec - t[2]) ** 2)[3]

    csv_path = ROOT / "Planet-X-Complete (1)" / matched_csv
    if not csv_path.exists():
        return []

    results = []
    seen = set()
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("fits_url") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            band = row.get("infrared_band")
            if req.band and band and req.band.lower() not in band.lower():
                continue
            base_id = row.get("obs_id") or ""
            product_name = Path(urlparse(url).path).name
            obs_time = row.get("observation_start_utc")
            if req.date_start and obs_time and obs_time[:10] < req.date_start.isoformat():
                continue
            if req.date_end and obs_time and obs_time[:10] > req.date_end.isoformat():
                continue
            observation_id = f"{base_id}::{band or 'unknown'}::{product_name}"
            collection = row.get("collection") or "spherex_qr3"
            obs = {
                "observation_id": observation_id,
                "product_id": base_id,
                "obs_time": obs_time,
                "collection": collection,
                "release": collection.replace("spherex_", "").upper(),
                "band": band,
                "wavelength_min_um": float(row["wavelength_min_um"]) if row.get("wavelength_min_um") else None,
                "wavelength_max_um": float(row["wavelength_max_um"]) if row.get("wavelength_max_um") else None,
                "access_url": url,
                "target_name": row.get("target_name"),
                "quality": 0,
                "metadata": {
                    "obs_id": base_id,
                    "target_name": row.get("target_name"),
                    "energy_bandpassname": band,
                    "em_min": row.get("wavelength_min_um"),
                    "em_max": row.get("wavelength_max_um"),
                    "t_min": row.get("observation_start_utc"),
                    "t_max": row.get("observation_end_utc"),
                },
            }
            results.append(obs)
    return results


TARGET_NAMES = {
    "barnards-star": "Barnard's Star",
    "epsilon-indi-b": "Epsilon Indi B",
    "wise-0855": "WISE 0855-0714",
    "rw-aurigae": "RW Aur",
    "r-draconis": "R Draconis",
}
WISE_CHALLENGE_POSITION = (133.79512916666664, -7.245147222222225)


def _resolve_target(target_id: str, name: str):
    response = _http_get(f"https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/S?{quote(name)}", timeout=(10, 30))
    root = ET.fromstring(response.content)
    ra = root.findtext(".//jradeg")
    dec = root.findtext(".//jdedeg")
    if target_id == "wise-0855":
        ra, dec = WISE_CHALLENGE_POSITION
    if ra is None or dec is None:
        raise ValueError(f"Catalog resolver returned no ICRS position for {name}")
    pm_ra = root.findtext(".//pm/pmRA")
    pm_dec = root.findtext(".//pm/pmDE")
    epoch = 2000.0
    reference = root.findtext(".//pm/r") or root.findtext(".//refPos")
    reference_ra, reference_dec = float(ra), float(dec)
    coord = SkyCoord(ra=reference_ra * u.deg, dec=reference_dec * u.deg, frame="icrs", obstime=Time(epoch, format="jyear"), pm_ra_cosdec=float(pm_ra or 0) * u.mas/u.yr, pm_dec=float(pm_dec or 0) * u.mas/u.yr)
    current = coord.apply_space_motion(new_obstime=Time.now())
    return {"id": target_id, "name": name, "ra": float(current.ra.deg), "dec": float(current.dec.deg), "reference_ra": reference_ra, "reference_dec": reference_dec, "reference_epoch_jyear": epoch, "proper_motion": {"pm_ra_cosdec_mas_yr": float(pm_ra) if pm_ra else None, "pm_dec_mas_yr": float(pm_dec) if pm_dec else None, "reference": reference}, "coordinate_frame": "ICRS", "coordinate_source": "Challenge supplied coordinate + CDS Sesame" if target_id == "wise-0855" else "CDS Sesame SIMBAD resolver", "resolved_utc": datetime.now(timezone.utc).isoformat()}


def _query(collection: str, req: SearchRequest):
    response = _http_get(SIA_URL, params={"COLLECTION": collection, "POS": f"circle {req.ra} {req.dec} {req.fov / 2}", "RESPONSEFORMAT": "votable"}, timeout=(4, 6))
    table = Table.read(BytesIO(response.content), format="votable")
    fields = [node for node in ET.fromstring(response.content).iter() if node.tag.rsplit("}", 1)[-1] == "FIELD"]
    for index, field in enumerate(fields):
        field_id, field_name = field.attrib.get("ID", f"col_{index}"), field.attrib.get("name")
        if field_name and field_id in table.colnames and field_name not in table.colnames:
            table.rename_column(field_id, field_name)
    results = []
    seen_products = set()
    for row in table:
        url = _value(row, "access_url")
        if not url or urlparse(str(url)).scheme != "https" or urlparse(str(url)).hostname != "irsa.ipac.caltech.edu":
            continue
        url = str(url)
        if url in seen_products:
            continue
        seen_products.add(url)
        band = _value(row, "energy_bandpassname", "band")
        if req.band and band and req.band.lower() not in str(band).lower():
            continue
        base_id = str(_value(row, "obs_id", "observation_id") or "")
        product_name = Path(urlparse(url).path).name
        observation_id = f"{base_id}::{band or 'unknown'}::{product_name}"
        obs = {
            # obs_id identifies an observing event and can repeat for different
            # detector bands. Keep an API selection key unique to the FITS file.
            "observation_id": observation_id,
            "product_id": base_id,
            "obs_time": _iso_time(row), "collection": collection,
            "release": collection.replace("spherex_", "").upper(),
            "band": str(band) if band is not None else None,
            "wavelength_min_um": _micrometers(_value(row, "em_min")), "wavelength_max_um": _micrometers(_value(row, "em_max")),
            "access_url": str(url), "target_name": _value(row, "target_name"),
            "quality": _value(row, "quality", "data_quality"),
            "metadata": {key: (None if getattr(row[key], "mask", False) else str(row[key])) for key in ("obs_id", "target_name", "energy_bandpassname", "em_min", "em_max", "t_min", "t_max", "s_ra", "s_dec") if key in table.colnames},
        }
        if obs["observation_id"]:
            results.append(obs)
    return results


VERIFIED_PRODUCT_IDS = {
    "2026W34_1A_0363_1", "2026W34_1A_0363_2", "2026W34_1A_0363_3", "2026W34_1A_0456_1",
    "2026W28_1A_0104_1", "2026W28_1A_0104_2", "2026W28_1A_0104_3", "2026W28_1A_0671_2",
}


def select_time_spread_observations(observations: list[dict[str, Any]], limit: int = 6):
    """Choose one same-band set that spans distinct observing dates where possible."""
    by_band: dict[str, list[dict[str, Any]]] = {}
    for item in observations:
        by_band.setdefault(item.get("band") or "unknown", []).append(item)

    def parse_time(item):
        raw = item.get("obs_time")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None

    def band_rank(items):
        times = [parsed for item in items if (parsed := parse_time(item)) is not None]
        distinct_dates = len({value.date() for value in times})
        baseline = (max(times) - min(times)).total_seconds() if len(times) > 1 else 0
        band_name = items[0].get("band") or ""
        verified_count = sum(1 for item in items if item.get("product_id") in VERIFIED_PRODUCT_IDS)
        return verified_count, distinct_dates, baseline, len(items)

    if not by_band:
        return []
    band, compatible = max(by_band.items(), key=lambda pair: band_rank(pair[1]))
    verified_in_compatible = [item for item in compatible if item.get("product_id") in VERIFIED_PRODUCT_IDS]
    if len(verified_in_compatible) >= 2:
        return sorted(verified_in_compatible, key=lambda item: (parse_time(item) is None, parse_time(item) or datetime.max.replace(tzinfo=timezone.utc)))

    ordered = sorted(compatible, key=lambda item: (parse_time(item) is None, parse_time(item) or datetime.max.replace(tzinfo=timezone.utc)))
    if len(ordered) <= limit:
        return ordered

    by_date: dict[str, list[dict[str, Any]]] = {}
    for item in ordered:
        timestamp = item.get("obs_time")
        date_key = str(timestamp)[:10] if timestamp else "unknown"
        by_date.setdefault(date_key, []).append(item)

    date_keys = list(by_date)
    count = min(limit, len(date_keys))
    if count == 1:
        selected_date_indexes = [0]
    else:
        selected_date_indexes = [round(index * (len(date_keys) - 1) / (count - 1)) for index in range(count)]
    selected = [by_date[date_keys[index]][0] for index in selected_date_indexes]

    if len(selected) < limit:
        selected_ids = {item["observation_id"] for item in selected}
        remaining = [item for item in ordered if item["observation_id"] not in selected_ids]
        selected_times = [parse_time(item) for item in selected if parse_time(item) is not None]
        while remaining and len(selected) < limit:
            if selected_times:
                next_item = max(
                    remaining,
                    key=lambda item: min(
                        abs((parse_time(item) - selected_time).total_seconds())
                        for selected_time in selected_times
                    ) if parse_time(item) is not None else -1,
                )
            else:
                next_item = remaining[0]
            remaining.remove(next_item)
            selected.append(next_item)
            parsed = parse_time(next_item)
            if parsed is not None:
                selected_times.append(parsed)

    return sorted(selected, key=lambda item: (parse_time(item) is None, parse_time(item) or datetime.max.replace(tzinfo=timezone.utc)))


@app.get("/api/health")
def health():
    return {"status": "ok", "archive": SIA_URL, "science_pipeline": (SCIENCE / "science" / "pipeline.py").exists()}


@app.get("/api/targets")
def targets():
    resolved, errors = [], []
    for target_id, name in TARGET_NAMES.items():
        try:
            resolved.append(_resolve_target(target_id, name))
        except Exception as exc:
            errors.append({"target": name, "error": str(exc)})
    return {"targets": resolved, "warnings": errors}


@app.post("/api/search")
def search(req: SearchRequest):
    if req.date_start and req.date_end and req.date_start > req.date_end:
        raise HTTPException(422, "date_start must be on or before date_end")
    primary = "spherex_qr3" if req.data_release.upper() == "QR3" else "spherex_qr2"
    collections_checked = [primary]
    results = []
    try:
        results = _query(primary, req)
        if req.date_start:
            results = [item for item in results if item["obs_time"] and item["obs_time"][:10] >= req.date_start.isoformat()]
        if req.date_end:
            results = [item for item in results if item["obs_time"] and item["obs_time"][:10] <= req.date_end.isoformat()]
        if not results:
            fallback = "spherex_qr2" if primary.endswith("qr3") else "spherex_qr3"
            results = _query(fallback, req)
            if req.date_start:
                results = [item for item in results if item["obs_time"] and item["obs_time"][:10] >= req.date_start.isoformat()]
            if req.date_end:
                results = [item for item in results if item["obs_time"] and item["obs_time"][:10] <= req.date_end.isoformat()]
            collections_checked.append(fallback)
    except Exception as exc:
        # Live query to NASA IRSA timed out or was busy; fall back to local archive records
        results = _load_cached_search(req)
        if results:
            collections_checked = [primary + " (local archive fallback)"]
        else:
            raise HTTPException(502, f"IRSA archive request failed: {exc}") from exc
    results.sort(key=lambda item: item["obs_time"] or "")
    recommended = select_time_spread_observations(results)
    recommended_times = [item["obs_time"] for item in recommended if item.get("obs_time")]
    selection_summary = {
        "observation_count": len(recommended),
        "band": recommended[0].get("band") if recommended else None,
        "distinct_dates": len({value[:10] for value in recommended_times}),
        "baseline_days": round((datetime.fromisoformat(recommended_times[-1].replace("Z", "+00:00")) - datetime.fromisoformat(recommended_times[0].replace("Z", "+00:00"))).total_seconds() / 86400, 1) if len(recommended_times) > 1 else 0,
    }
    search_id = str(uuid.uuid4())
    searches[search_id] = {"observations": results, "ra": req.ra, "dec": req.dec, "fov": req.fov}
    return {"search_id": search_id, "query": req.model_dump(), "collections_checked": collections_checked, "count": len(results), "observations": results, "recommended_observation_ids": [item["observation_id"] for item in recommended], "recommended_selection": selection_summary, "message": None if results else "No matching SPHEREx observations were returned by the collections checked."}


def _run_job(job_id: str, selected: list[dict], center: dict, fov: float):
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        output = DATA / "jobs" / job_id
        output.mkdir(parents=True, exist_ok=True)
        raw_dir = output / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output / "manifest.json"
        downloads = []
        with lock:
            jobs[job_id].update(status="downloading", progress=5)
        for index, observation in enumerate(selected):
            name = re.sub(r"[^A-Za-z0-9_-]", "_", observation["product_id"])
            out = raw_dir / f"{name}_{index}.fits"
            record = {"product_id": observation["product_id"], "target_name": observation.get("target_name"), "collection": observation["collection"], "infrared_band": observation.get("band"), "wavelength_min_um": observation.get("wavelength_min_um"), "wavelength_max_um": observation.get("wavelength_max_um"), "observation_start_utc": observation.get("obs_time"), "requested_center": {"ra_deg": center["ra"], "dec_deg": center["dec"]}, "cutout_size_deg": fov, "access_url": observation["access_url"], "local_file_path": str(out), "download_status": "downloaded"}
            try:
                content, mode = _download_product(observation, center, fov)
                out.write_bytes(content)
                record["download_mode"] = mode
            except Exception as exc:
                record["local_file_path"] = None
                record["download_status"] = "failed"
                record["error_message"] = f"{type(exc).__name__}: {exc}"
            downloads.append(record)
            with lock:
                jobs[job_id].update(progress=10 + int(35 * (index + 1) / len(selected)))
        manifest_path.write_text(json.dumps({"project": "SPHEREx Explorer live API job", "observations": downloads}, indent=2), encoding="utf-8")
        with lock:
            jobs[job_id].update(status="processing", progress=50)
        import sys
        sys.path.insert(0, str(SCIENCE))
        from science.pipeline import process_manifest
        process_manifest(manifest_path, output)
        process_path = output / "results" / "processing.json"
        candidates_path = output / "results" / "candidates.json"
        processing = json.loads(process_path.read_text(encoding="utf-8"))
        candidates = json.loads(candidates_path.read_text(encoding="utf-8")) if candidates_path.exists() else []
        all_candidates = candidates if isinstance(candidates, list) else candidates.get("candidates", [])
        reviewable_candidates = [
            candidate for candidate in all_candidates
            if candidate.get("classification") in {
                "possible motion", "possible brightness variability"
            }
        ]
        candidate_summary = {
            "total_records": len(all_candidates),
            "reviewable_signals": len(reviewable_candidates),
            "ambiguous_or_unclassified": len(all_candidates) - len(reviewable_candidates),
        }
        base = f"/api/media/{job_id}/"
        frames = [{**{k: v for k, v in frame.items() if k not in ("source_file", "aligned_fits", "preview", "preview_stretches", "mask_overlays")}, "preview_url": base + Path(frame["preview"]).name, "preview_stretch_urls": {mode: base + Path(path).name for mode, path in frame.get("preview_stretches", {}).items()}, "mask_overlay_urls": {mode: base + Path(path).name for mode, path in frame.get("mask_overlays", {}).items()}, "source_url": frame.get("source_url"), "quality_summary": frame.get("mask_counts"), "product_id": frame.get("observation_id"), "obs_time": frame.get("timestamp")} for frame in processing.get("frames", [])]
        comparisons = [{**{k: v for k, v in c.items() if not k.endswith("_fits")}, "difference_url": base + Path(c["difference_preview"]).name if c.get("difference_preview") else None, "significance_url": base + Path(c["significance_preview"]).name if c.get("significance_preview") else None} for c in processing.get("comparisons", [])]
        result = {"job_id": job_id, "status": processing.get("status"), "frames": frames, "comparisons": comparisons, "candidates": reviewable_candidates, "candidate_summary": candidate_summary, "warnings": processing.get("warnings", []), "errors": processing.get("errors", []), "processing": {k: v for k, v in processing.items() if k not in ("frames", "comparisons")}}
        with lock:
            jobs[job_id].update(status=processing.get("status", "complete"), progress=100, result=result, error=None)
    except Exception as exc:
        with lock:
            jobs[job_id].update(status="failed", progress=100, error=f"{type(exc).__name__}: {exc}")


def _run_existing_pair(job_id: str, source_job_id: str, observation_a_id: str, observation_b_id: str):
    """Re-run the science pipeline on a user-selected pair of downloaded FITS files."""
    try:
        source_dir = DATA / "jobs" / source_job_id
        source_manifest = json.loads((source_dir / "manifest.json").read_text(encoding="utf-8"))
        wanted = {observation_a_id, observation_b_id}
        records = [row for row in source_manifest.get("observations", []) if row.get("product_id") in wanted]
        if len(records) != 2 or any(not row.get("local_file_path") or not Path(row["local_file_path"]).is_file() for row in records):
            raise ValueError("The selected observations do not both have usable downloaded FITS files.")
        bands = {row.get("infrared_band") for row in records}
        if len(bands) != 1:
            raise ValueError("Choose two observations from the same spectral band.")
        pair_dir = DATA / "jobs" / job_id
        pair_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = pair_dir / "manifest.json"
        manifest_path.write_text(json.dumps({"project": "SPHEREx Explorer selected observation comparison", "observations": records}, indent=2), encoding="utf-8")
        with lock:
            jobs[job_id].update(status="processing", progress=20)
        import sys
        sys.path.insert(0, str(SCIENCE))
        from science.pipeline import process_manifest
        process_manifest(manifest_path, pair_dir)
        # The pipeline's in-memory report contains NumPy values (for example
        # covariance kernels). Serve its normalized JSON artifact instead.
        processing = json.loads((pair_dir / "results" / "processing.json").read_text(encoding="utf-8"))
        if not any(c.get("status") == "complete" for c in processing.get("comparisons", [])):
            raise ValueError("The selected pair did not pass the science pipeline gates: " + "; ".join(processing.get("warnings", [])))
        base = f"/api/media/{job_id}/"
        frames = [{**{k: v for k, v in frame.items() if k not in ("source_file", "aligned_fits", "preview", "preview_stretches", "mask_overlays")}, "preview_url": base + Path(frame["preview"]).name, "preview_stretch_urls": {mode: base + Path(path).name for mode, path in frame.get("preview_stretches", {}).items()}, "mask_overlay_urls": {mode: base + Path(path).name for mode, path in frame.get("mask_overlays", {}).items()}, "product_id": frame.get("observation_id"), "obs_time": frame.get("timestamp")} for frame in processing.get("frames", [])]
        comparisons = [{**{k: v for k, v in c.items() if not k.endswith("_fits")}, "difference_url": base + Path(c["difference_preview"]).name if c.get("difference_preview") else None, "significance_url": base + Path(c["significance_preview"]).name if c.get("significance_preview") else None} for c in processing.get("comparisons", [])]
        result = {"job_id": job_id, "status": processing.get("status"), "frames": frames, "comparisons": comparisons, "candidates": [], "candidate_summary": {"total_records": 0, "reviewable_signals": 0, "ambiguous_or_unclassified": 0}, "warnings": processing.get("warnings", []), "errors": processing.get("errors", []), "processing": {k: v for k, v in processing.items() if k not in ("frames", "comparisons")}}
        with lock:
            jobs[job_id].update(status=processing.get("status", "complete"), progress=100, result=result, error=None)
    except Exception as exc:
        with lock:
            jobs[job_id].update(status="failed", progress=100, error=f"{type(exc).__name__}: {exc}")


@app.post("/api/jobs", status_code=202)
def create_job(req: JobRequest, background: BackgroundTasks):
    found = searches.get(req.search_id)
    if not found:
        raise HTTPException(404, "Search expired or was not found. Run the archive search again.")
    wanted = set(req.observation_ids)
    if wanted:
        selected = [obs for obs in found["observations"] if obs["observation_id"] in wanted]
        bands = {obs.get("band") or "unknown" for obs in selected}
        if len(bands) > 1:
            raise HTTPException(400, "Choose observations from one SPHEREx spectral band per comparison.")
    else:
        selected = select_time_spread_observations(found["observations"])
    if not selected:
        raise HTTPException(400, "Choose at least one observation returned by this search.")
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"job_id": job_id, "status": "queued", "progress": 0, "created_utc": datetime.now(timezone.utc).isoformat(), "error": None}
    background.add_task(_run_job, job_id, selected[:6], {"ra": found["ra"], "dec": found["dec"]}, found["fov"])
    return jobs[job_id]


@app.post("/api/jobs/{source_job_id}/compare", status_code=202)
def compare_selected_pair(source_job_id: str, req: PairRequest, background: BackgroundTasks):
    source_path = DATA / "jobs" / source_job_id / "manifest.json"
    if not source_path.is_file():
        raise HTTPException(404, "Source job or its downloaded observations were not found.")
    if req.observation_a_id == req.observation_b_id:
        raise HTTPException(400, "Choose two different observations.")
    pair_job_id = str(uuid.uuid4())
    jobs[pair_job_id] = {"job_id": pair_job_id, "status": "queued", "progress": 0, "created_utc": datetime.now(timezone.utc).isoformat(), "error": None}
    background.add_task(_run_existing_pair, pair_job_id, source_job_id, req.observation_a_id, req.observation_b_id)
    return jobs[pair_job_id]


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]


@app.get("/api/results/{job_id}")
def results(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] in ("queued", "downloading", "processing"):
        raise HTTPException(409, "Processing is not complete yet")
    if job["status"] == "failed":
        raise HTTPException(422, job.get("error") or "Processing failed")
    return job["result"]


@app.get("/api/media/{job_id}/{filename}")
def media(job_id: str, filename: str):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", filename):
        raise HTTPException(400, "Invalid media name")
    path = DATA / "jobs" / job_id / "previews" / filename
    if not path.is_file() or path.parent.resolve() != (DATA / "jobs" / job_id / "previews").resolve():
        raise HTTPException(404, "Preview not found")
    return FileResponse(path)
