# Data Dictionary

## Member 1 manifest fields observed

| Field | Meaning | Handling |
|---|---|---|
| `product_id` | IRSA observation/product identifier | Preserved |
| `target_name` | Survey-planning target identifier | Preserved; not assumed to be a common object name |
| `collection` | Data release collection, e.g. `spherex_qr2`, `spherex_qr3` | Required for compatibility |
| `infrared_band` | Detector band label, e.g. `SPHEREx-D3` | Required for compatibility |
| `wavelength_min_um`, `wavelength_max_um` | Available band interval | Compared when present |
| `observation_start_utc`, `observation_end_utc` | Exposure times from the handoff | Preserved |
| `requested_center.ra_deg`, `requested_center.dec_deg` | Requested sky position in degrees | Validated |
| `cutout_size_deg` | Requested cutout size | Preserved |
| `access_url` | IRSA source URL | Preserved |
| `local_file_path` | Relative local FITS path | Windows separators normalized at read time; original manifest untouched |
| `download_status` | Member 1 download state | Preserved; local existence independently checked |
| `error_message` | Download error if reported | Preserved |

## FITS HDUs observed in supplied files

| HDU index | EXTNAME | Shape | Meaning |
|---:|---|---|---|
| 0 | PRIMARY | no data | Empty primary header |
| 1 | IMAGE | 29 x 29 (one 26 x 29) | Calibrated science image; `MJy / sr` |
| 2 | FLAGS | same as IMAGE | Pixel flags |
| 3 | VARIANCE | same as IMAGE | Variance; `MJy2 / sr2` |
| 4 | ZODI | same as IMAGE | Zodiacal model; `MJy / sr` |
| 5 | EPSF | binary table | Effective PSF data in the supplied QR3 files |
| 6 | WCS-WAVE | binary table | Wavelength lookup table |

## Important image header fields

`OBSID`, `DETECTOR`, `DATE-OBS`, `MJD-OBS`, `FINAST`, `RADESYS`, `CTYPE1`, `CTYPE2`, `CRVAL1`, `CRVAL2`, `CRPIX1`, `CRPIX2`, `PC1_1`, `PC1_2`, `PC2_1`, `PC2_2`, SIP distortion coefficients, and `BUNIT`.

## Processing outputs

`processing.json` records job status, inputs, selected comparison group, frame paths, mask counts, alignment residuals, compatibility decisions, background diagnostics, uncertainty availability, warnings and errors.

`candidates.json` contains candidate IDs, sky/pixel coordinates, epoch pair, residual statistics, quality flags, artifact warnings, rationale and caveat. Missing or unavailable measurements are JSON `null`; no values are fabricated.

## Latest real-data processing reference - Job009

The latest real-data run used six compatible Epsilon Indi B observations.

| Processing field | Job009 result |
|---|---|
| Pipeline status | `partial` |
| Usable observations | 30 |
| Selected frames | 6 |
| Comparisons attempted | 5 |
| Alignment passed | 3 |
| Alignment blocked | 2 |
| Difference images generated | 3 |
| Significance maps generated | 3 |
| Preliminary candidate records | 4 |
| Missing manifest inputs | 16 |
| Pipeline errors | 0 |

Alignment residuals and candidate measurements are recorded in `processing.json` and `candidates.json` under the job output directory.

All four candidate records are preliminary and unverified. Their presence does not establish an astronomical discovery.
