import csv
import json
import re
from pathlib import Path
from collections import Counter

DATA_DIR = Path(r"C:\Users\ruchitha\Downloads\Planet-x-remaining-targets")
CUTOUT_DIR = DATA_DIR / "cutouts"
PROJECT_DIR = Path.cwd()
OUTPUT_FILE = PROJECT_DIR / "data" / "member1_manifest.json"

CSV_FILES = [
    DATA_DIR / "observation_summary_rw_aurigae.csv",
    DATA_DIR / "observation_summary_r_draconis.csv",
    DATA_DIR / "observation_summary_wise_0855.csv",
]

filename_pattern = re.compile(
    r"^(?P<obs_id>.+?)_SPHEREx-(?P<band>D[1-6])"
    r"_RA(?P<ra>-?\d+(?:\.\d+)?)"
    r"_DEC(?P<dec>-?\d+(?:\.\d+)?)"
    r"_SIZE(?P<size>\d+(?:\.\d+)?)_cutout\.fits$"
)

# Read all CSV records and index them by observation ID + band.
records = {}

for csv_file in CSV_FILES:
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV not found: {csv_file}")

    with csv_file.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            key = (row["obs_id"].strip(), row["infrared_band"].strip())

            if key in records:
                raise ValueError(f"Duplicate CSV record: {key}")

            records[key] = row

fits_files = sorted(CUTOUT_DIR.glob("*.fits"))

if not fits_files:
    raise FileNotFoundError(f"No FITS files found in {CUTOUT_DIR}")

observations = []
matched_keys = set()
errors = []

for fits_path in fits_files:
    match = filename_pattern.match(fits_path.name)

    if not match:
        errors.append(f"Unrecognized filename: {fits_path.name}")
        continue

    info = match.groupdict()
    obs_id = info["obs_id"]
    band = "SPHEREx-" + info["band"]
    key = (obs_id, band)

    if key not in records:
        errors.append(
            f"No CSV match for {fits_path.name} "
            f"(observation={obs_id}, band={band})"
        )
        continue

    if key in matched_keys:
        errors.append(f"More than one FITS file matched CSV record: {key}")
        continue

    matched_keys.add(key)
    row = records[key]

    observations.append({
        "product_id": obs_id,
        "target_name": row["target_name"],
        "collection": row["collection"],
        "infrared_band": band,
        "wavelength_min_um": float(row["wavelength_min_um"]),
        "wavelength_max_um": float(row["wavelength_max_um"]),
        "observation_start_utc": row["observation_start_utc"],
        "observation_end_utc": row["observation_end_utc"],
        "requested_center": {
            "ra_deg": float(info["ra"]),
            "dec_deg": float(info["dec"]),
        },
        "cutout_size_deg": float(info["size"]),
        "access_url": row["fits_url"],
        "local_file_path": str(fits_path.resolve()),
        "download_status": "downloaded",
        "error_message": None,
    })

if errors:
    print("\nMANIFEST BUILD FAILED:")
    for error in errors:
        print(" -", error)
    raise SystemExit(1)

if len(observations) != len(fits_files):
    raise SystemExit(
        f"Count mismatch: {len(observations)} matched "
        f"out of {len(fits_files)} FITS files."
    )

manifest = {
    "project": "Planet X and SPHEREx - Member 1 Dataset",
    "observations": observations,
}

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT_FILE.open("w", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=4)

print("\nMANIFEST CREATED SUCCESSFULLY")
print("Output:", OUTPUT_FILE)
print("FITS files found:", len(fits_files))
print("CSV records available:", len(records))
print("Observations matched:", len(observations))
print("\nCollection distribution:")
for name, count in sorted(
    Counter(item["collection"] for item in observations).items()
):
    print(f"  {name}: {count}")

print("\nBand distribution:")
for name, count in sorted(
    Counter(item["infrared_band"] for item in observations).items()
):
    print(f"  {name}: {count}")

print("\nTarget distribution:")
for name, count in sorted(
    Counter(item["target_name"] for item in observations).items()
):
    print(f"  {name}: {count}")

print("\nExisting manifests were not modified.")
