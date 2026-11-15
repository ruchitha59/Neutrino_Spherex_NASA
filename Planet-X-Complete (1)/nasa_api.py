
import requests
import xml.etree.ElementTree as ET
import os
import json
import re
import numpy as np

from astropy.table import Table
from astropy.time import Time
from astropy.io import fits

from io import BytesIO
from time import sleep
from datetime import datetime, timezone

from coordinate_validator import validate_coordinates


SIA_URL = "https://irsa.ipac.caltech.edu/SIA"
MANIFEST_FILE = "manifest.json"


# STEP 1: Query a SPHEREx collection
def query_collection(ra_deg, dec_deg, radius_deg, collection):

    params = {
        "COLLECTION": collection,
        "POS": f"circle {ra_deg} {dec_deg} {radius_deg}",
        "RESPONSEFORMAT": "votable"
    }

    print(f"\nSearching collection: {collection}")

    response = None

    for attempt in range(1, 4):

        try:
            response = requests.get(
                SIA_URL,
                params=params,
                timeout=(15, 120)
            )

            response.raise_for_status()
            print("NASA responded successfully!")
            break

        except requests.exceptions.RequestException as error:

            print(f"Attempt {attempt} failed: {error}")

            if attempt == 3:
                print(f"Could not access {collection}.")
                return None

            print("Retrying in 3 seconds...")
            sleep(3)

    try:

        root = ET.fromstring(response.content)

        fields = [
            element for element in root.iter()
            if element.tag.split("}")[-1] == "FIELD"
        ]

        results = Table.read(
            BytesIO(response.content),
            format="votable"
        )

        for index, field in enumerate(fields):

            old_name = field.attrib.get("ID", f"col_{index}")
            new_name = field.attrib.get("name")

            if old_name in results.colnames and new_name:
                results.rename_column(old_name, new_name)

        return results

    except Exception as error:

        print("Could not parse NASA VOTable:", error)
        return None


# STEP 2: Check whether usable results exist
def has_usable_results(results):

    if results is None or len(results) == 0:
        return False

    if "access_url" not in results.colnames:
        return False

    for url in results["access_url"]:

        if not np.ma.is_masked(url) and str(url).strip():
            return True

    return False


# STEP 3: Search QR3 first, then QR2
def search_spherex(ra_deg, dec_deg, radius_deg=0.05):

    if not validate_coordinates(ra_deg, dec_deg):
        raise ValueError("Invalid RA or Dec coordinates.")

    if (
        isinstance(radius_deg, bool)
        or not isinstance(radius_deg, (int, float))
        or not np.isfinite(radius_deg)
        or radius_deg <= 0
    ):
        raise ValueError("Search radius must be a positive number.")

    print("\nConnecting to NASA IRSA...")

    results = query_collection(
        ra_deg, dec_deg, radius_deg, "spherex_qr3"
    )

    if not has_usable_results(results):

        print("\nNo usable QR3 results found.")
        print("Trying QR2 Wide as fallback...")

        results = query_collection(
            ra_deg, dec_deg, radius_deg, "spherex_qr2"
        )

    if not has_usable_results(results):

        print("\nNo usable SPHEREx observations found.")
        return None

    print("\nSPHEREx search completed!")
    print("Number of records:", len(results))
    print("Number of metadata fields:", len(results.colnames))

    return results


# STEP 4: Convert MJD into readable UTC date and time
def convert_mjd_to_utc(value):

    if np.ma.is_masked(value) or value is None:
        return "Unavailable"

    try:
        return Time(
            float(value),
            format="mjd",
            scale="utc"
        ).isot

    except (ValueError, TypeError):
        return "Unavailable"


# STEP 5: Convert wavelength from metres to micrometres
def convert_to_micrometres(value):

    if np.ma.is_masked(value) or value is None:
        return "Unavailable"

    try:
        return f"{float(value) * 1_000_000:.4f}"

    except (ValueError, TypeError):
        return "Unavailable"


# STEP 6: Create observation summary
def create_observation_summary(results):

    required_columns = [
        "obs_id",
        "target_name",
        "energy_bandpassname",
        "em_min",
        "em_max",
        "t_min",
        "t_max",
        "obs_collection",
        "access_url"
    ]

    for column in required_columns:

        if column not in results.colnames:
            raise ValueError(
                f"Required metadata column is missing: {column}"
            )

    summary_rows = []

    for row in results:

        summary_rows.append([
            str(row["obs_id"]),
            str(row["target_name"]),
            str(row["energy_bandpassname"]),
            convert_to_micrometres(row["em_min"]),
            convert_to_micrometres(row["em_max"]),
            convert_mjd_to_utc(row["t_min"]),
            convert_mjd_to_utc(row["t_max"]),
            str(row["obs_collection"]),
            str(row["access_url"])
        ])

    summary = Table(
        rows=summary_rows,
        names=[
            "obs_id",
            "target_name",
            "infrared_band",
            "wavelength_min_um",
            "wavelength_max_um",
            "observation_start_utc",
            "observation_end_utc",
            "collection",
            "fits_url"
        ]
    )

    return summary


# STEP 7: Safely read a metadata value
def get_metadata_value(row, column):

    if column not in row.colnames:
        return None

    value = row[column]

    if np.ma.is_masked(value):
        return None

    return str(value).strip()


# STEP 8: Update manifest.json
def update_manifest(record):

    if os.path.exists(MANIFEST_FILE):

        with open(MANIFEST_FILE, "r", encoding="utf-8") as file:
            manifest = json.load(file)

    else:

        manifest = {
            "project": "Planet X and SPHEREx",
            "observations": []
        }

    if "observations" not in manifest:
        manifest["observations"] = []

    record_key = (
        record["product_id"],
        record["infrared_band"],
        record["requested_center"]["ra_deg"],
        record["requested_center"]["dec_deg"],
        record["cutout_size_deg"]
    )

    existing_index = None

    for index, existing in enumerate(manifest["observations"]):

        existing_key = (
            existing["product_id"],
            existing["infrared_band"],
            existing["requested_center"]["ra_deg"],
            existing["requested_center"]["dec_deg"],
            existing["cutout_size_deg"]
        )

        if existing_key == record_key:
            existing_index = index
            break

    if existing_index is not None:
        manifest["observations"][existing_index] = record
    else:
        manifest["observations"].append(record)

    manifest["last_updated_utc"] = datetime.now(
        timezone.utc
    ).isoformat()

    with open(MANIFEST_FILE, "w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=4)

    print("\nManifest updated successfully!")
    print("File:", MANIFEST_FILE)


# STEP 9: Create a manifest record
def create_manifest_record(
    row,
    ra_deg,
    dec_deg,
    size_deg,
    file_path,
    status,
    error_message=None
):

    return {
        "product_id": get_metadata_value(row, "obs_id"),
        "target_name": get_metadata_value(row, "target_name"),
        "collection": get_metadata_value(row, "obs_collection"),
        "infrared_band": get_metadata_value(
            row, "energy_bandpassname"
        ),
        "wavelength_min_um": convert_to_micrometres(
            row["em_min"]
        ) if "em_min" in row.colnames else "Unavailable",
        "wavelength_max_um": convert_to_micrometres(
            row["em_max"]
        ) if "em_max" in row.colnames else "Unavailable",
        "observation_start_utc": convert_mjd_to_utc(
            row["t_min"]
        ) if "t_min" in row.colnames else "Unavailable",
        "observation_end_utc": convert_mjd_to_utc(
            row["t_max"]
        ) if "t_max" in row.colnames else "Unavailable",
        "requested_center": {
            "ra_deg": ra_deg,
            "dec_deg": dec_deg
        },
        "cutout_size_deg": size_deg,
        "access_url": get_metadata_value(row, "access_url"),
        "local_file_path": file_path,
        "download_status": status,
        "error_message": error_message,
        "recorded_at_utc": datetime.now(
            timezone.utc
        ).isoformat()
    }


# STEP 10: Select multiple observations and download FITS cutouts
def select_observations_for_download(results, limit=5):

    if results is None or len(results) == 0:
        return []

    candidates = []
    seen_urls = set()

    for row in results:

        access_url = get_metadata_value(row, "access_url")

        if not access_url:
            continue

        if access_url in seen_urls:
            continue

        seen_urls.add(access_url)

        band = (
            get_metadata_value(row, "energy_bandpassname")
            or "Unknown"
        )

        observation_time = (
            convert_mjd_to_utc(row["t_min"])
            if "t_min" in row.colnames
            else "Unavailable"
        )

        observation_date = (
            observation_time[:10]
            if observation_time != "Unavailable"
            else "Unavailable"
        )

        candidates.append({
            "row": row,
            "url": access_url,
            "band": band,
            "date": observation_date
        })

    if not candidates:
        print("No valid FITS access URLs were found.")
        return []

    # First, choose at most one product from each distinct date.
    # Prefer bands that have been selected fewer times.
    selected = []
    selected_urls = set()
    band_counts = {}

    dates = sorted({
        candidate["date"]
        for candidate in candidates
    })

    for observation_date in dates:

        if len(selected) >= limit:
            break

        date_candidates = [
            candidate
            for candidate in candidates
            if candidate["date"] == observation_date
        ]

        date_candidates.sort(
            key=lambda candidate: (
                band_counts.get(candidate["band"], 0),
                candidate["url"]
            )
        )

        chosen = date_candidates[0]

        selected.append(chosen)
        selected_urls.add(chosen["url"])

        band_counts[chosen["band"]] = (
            band_counts.get(chosen["band"], 0) + 1
        )

    # If fewer than the requested number of distinct dates exist,
    # fill the remaining places with other unique products.
    remaining = [
        candidate
        for candidate in candidates
        if candidate["url"] not in selected_urls
    ]

    remaining.sort(
        key=lambda candidate: (
            band_counts.get(candidate["band"], 0),
            candidate["date"],
            candidate["url"]
        )
    )

    for candidate in remaining:

        if len(selected) >= limit:
            break

        selected.append(candidate)

        band_counts[candidate["band"]] = (
            band_counts.get(candidate["band"], 0) + 1
        )

    return [candidate["row"] for candidate in selected]


# STEP 10A: Download and verify one selected FITS cutout
def download_one_fits_cutout(row, ra_deg, dec_deg, size_deg=0.05):

    access_url = get_metadata_value(row, "access_url")

    if not access_url:
        print("Skipping product because its access URL is unavailable.")
        return None

    obs_id = (
        get_metadata_value(row, "obs_id")
        or "unknown_product"
    )

    band = (
        get_metadata_value(row, "energy_bandpassname")
        or "unknown_band"
    )

    safe_obs_id = re.sub(r"[^A-Za-z0-9_-]", "_", obs_id)
    safe_band = re.sub(r"[^A-Za-z0-9_-]", "_", band)

    # Including coordinates and cutout size prevents different
    # requested cutouts from overwriting one another.
    filename = (
        f"{safe_obs_id}_{safe_band}_"
        f"RA{ra_deg:.5f}_DEC{dec_deg:.5f}_"
        f"SIZE{size_deg:.5f}_cutout.fits"
    )

    os.makedirs("cutouts", exist_ok=True)
    file_path = os.path.join("cutouts", filename)

    # Reuse an existing valid file from an earlier run.
    if os.path.exists(file_path):

        try:
            with fits.open(file_path, memmap=False) as hdul:
                hdul.verify("exception")

                if len(hdul) == 0:
                    raise ValueError("Existing FITS file is empty.")

            print("\nAlready downloaded and verified; skipping:")
            print(file_path)

            successful_record = create_manifest_record(
                row,
                ra_deg,
                dec_deg,
                size_deg,
                file_path,
                "downloaded"
            )

            update_manifest(successful_record)
            return file_path

        except Exception:
            print("\nExisting file is invalid. Downloading it again.")

    cutout_params = {
        "center": f"{ra_deg},{dec_deg}",
        "size": str(size_deg)
    }

    print("\nPreparing FITS cutout...")
    print("Observation ID:", obs_id)
    print("Infrared band:", band)

    retry_delays = [5, 10]
    fits_data = None
    failure_reason = None

    for attempt in range(1, 4):

        try:

            print(f"\nDownload attempt {attempt} of 3...")

            response = requests.get(
                access_url,
                params=cutout_params,
                timeout=(15, 180)
            )

            response.raise_for_status()

            temporary_data = response.content

            with fits.open(
                BytesIO(temporary_data),
                memmap=False
            ) as hdul:

                hdul.verify("exception")

                if len(hdul) == 0:
                    raise ValueError("Downloaded FITS file is empty.")

                print("\nFITS file verified successfully!")
                print("Number of HDUs:", len(hdul))

                for index, hdu in enumerate(hdul):

                    image_shape = (
                        hdu.data.shape
                        if hdu.data is not None
                        else "No image data"
                    )

                    print(
                        f"HDU {index}: "
                        f"{hdu.name}, Shape: {image_shape}"
                    )

            fits_data = temporary_data
            failure_reason = None

            print("\nDownload and verification successful!")
            break

        except requests.exceptions.HTTPError as error:

            status_code = error.response.status_code
            failure_reason = str(error)

            print(f"HTTP error: {status_code}")

            if status_code not in [502, 503, 504]:
                print("This HTTP error is not eligible for automatic retry.")
                break

        except requests.exceptions.RequestException as error:

            failure_reason = str(error)
            print("Network error:", error)

        except Exception as error:

            failure_reason = str(error)
            print("FITS validation failed:", error)

        if attempt < 3:

            delay = retry_delays[attempt - 1]
            print(f"Retrying in {delay} seconds...")
            sleep(delay)

    if fits_data is None:

        failed_record = create_manifest_record(
            row,
            ra_deg,
            dec_deg,
            size_deg,
            None,
            "failed",
            failure_reason
        )

        update_manifest(failed_record)

        print("\nFITS download could not be completed.")
        return None

    try:

        with open(file_path, "wb") as file:
            file.write(fits_data)

        print("\nFITS cutout downloaded successfully!")
        print("Downloaded size:", round(len(fits_data) / 1024, 2), "KB")
        print("File location:", file_path)

        successful_record = create_manifest_record(
            row,
            ra_deg,
            dec_deg,
            size_deg,
            file_path,
            "downloaded"
        )

        update_manifest(successful_record)

        return file_path

    except OSError as error:

        print("\nCould not save FITS file:", error)

        failed_record = create_manifest_record(
            row,
            ra_deg,
            dec_deg,
            size_deg,
            None,
            "failed",
            str(error)
        )

        update_manifest(failed_record)

        return None


# STEP 10B: Download a selected group of observations
def download_multiple_fits_cutouts(
    results,
    ra_deg,
    dec_deg,
    size_deg=0.05,
    limit=5
):

    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit <= 0
    ):
        raise ValueError("Download limit must be a positive integer.")

    selected_rows = select_observations_for_download(
        results,
        limit
    )

    if not selected_rows:
        print("No observations were selected for download.")
        return []

    print(f"\nSelected {len(selected_rows)} observations for download:")
    for index, row in enumerate(selected_rows, start=1):

        band = get_metadata_value(row, "energy_bandpassname")
        obs_id = get_metadata_value(row, "obs_id")

        observation_time = (
            convert_mjd_to_utc(row["t_min"])
            if "t_min" in row.colnames
            else "Unavailable"
        )

        print(
            f"{index}. {obs_id} | {band} | "
            f"{observation_time}"
        )

    downloaded_files = []

    for index, row in enumerate(selected_rows, start=1):

        print("\n" + "=" * 55)
        print(f"DOWNLOADING SELECTED OBSERVATION {index}/{len(selected_rows)}")
        print("=" * 55)

        file_path = download_one_fits_cutout(
            row,
            ra_deg,
            dec_deg,
            size_deg
        )

        if file_path:
            downloaded_files.append(file_path)

    print("\n====================================")
    print("MULTIPLE DOWNLOAD SUMMARY")
    print("====================================")
    print("Selected observations:", len(selected_rows))
    print("Successfully available FITS files:", len(downloaded_files))
    print("Failed downloads:", len(selected_rows) - len(downloaded_files))

    return downloaded_files


# STEP 11: Get coordinates from the user
def get_user_coordinates():

    print("\n====================================")
    print("       SPHEREx OBSERVATION SEARCH")
    print("====================================")

    try:

        ra = float(input("\nEnter Right Ascension (RA) in degrees: "))
        dec = float(input("Enter Declination (Dec) in degrees: "))
        radius = float(input("Enter search radius in degrees: "))

        if not validate_coordinates(ra, dec):
            raise ValueError("Invalid RA or Dec values.")

        if not np.isfinite(radius) or radius <= 0:
            raise ValueError("Search radius must be positive.")

        return ra, dec, radius

    except ValueError as error:

        print("\nInvalid input:", error)
        return None


# STEP 12: Run the complete workflow
if __name__ == "__main__":

    user_input = get_user_coordinates()

    if user_input is not None:

        ra, dec, radius = user_input

        results = search_spherex(ra, dec, radius)

        if results is not None and len(results) > 0:

            summary = create_observation_summary(results)

            print("\nTotal observations:", len(summary))

            display_summary = summary[
                [
                    "obs_id",
                    "target_name",
                    "infrared_band",
                    "wavelength_min_um",
                    "wavelength_max_um",
                    "observation_start_utc",
                    "observation_end_utc",
                    "collection"
                ]
            ]

            print("\nFirst 10 observations:")
            display_summary[:10].pprint(max_width=180)

            available_bands = sorted(
                set(summary["infrared_band"])
            )

            print("\nAvailable infrared bands:")
            print(available_bands)

            summary.write(
                "observation_summary.csv",
                format="csv",
                overwrite=True
            )

            print("\nObservation summary saved!")
            print("File: observation_summary.csv")

            download_multiple_fits_cutouts(
                results,
                ra,
                dec,
                size_deg=0.05,
                limit=15
            )

        else:

            print("\nNo observations were returned.")

    else:

        print("\nSearch cancelled due to invalid input.")
