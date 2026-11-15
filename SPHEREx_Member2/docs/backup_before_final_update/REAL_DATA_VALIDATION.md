# Real-Data Validation and Input Findings

## What was supplied

The ZIP handoff contains 30 FITS cutouts and a 46-record manifest. All 30 local FITS files match QR3 records. The remaining 16 manifest records are QR2 entries whose local FITS cutouts are absent from the ZIP, despite `download_status="downloaded"`.

The 30 cutouts split evenly by requested sky field:
- 15 cutouts around the Barnard's Star field (RA 269.45208°, Dec +4.69336°).
- 15 cutouts around the Epsilon Indi B field (RA 331.04415°, Dec −56.78284°).

The handoff includes CSV search summaries with 123 rows for Barnard's Star and 120 rows for Epsilon Indi B. These are archive summary rows, not 243 locally supplied FITS cutouts.

No supplied FITS files or target-specific manifest records were found for WISE 0855, RW Aurigae or R Draconis.

## FITS structure observed

All 30 files have seven HDUs:
0. Empty PRIMARY.
1. IMAGE — calibrated image.
2. FLAGS — bit flags.
3. VARIANCE — variance.
4. ZODI — zodiacal model.
5. EPSF — binary table.
6. WCS-WAVE — binary table.

29 science images are 29×29 pixels and one is 26×29 pixels. All image headers contain celestial WCS keywords and report `RADESYS=ICRS`; all have `FINAST=0`. The official supplement describes FINAST=0 as a good astrometric solution. Astropy WCS validation was not executable here, so these are header-level observations only.

Across the 30 files, the raw science arrays contain six non-finite pixels; variance arrays contain six non-finite pixels and no negative variance values. The supplied `FLAGS` headers include symbolic names, bit masks and descriptions. Flag incidences are recorded in `data/reports/fits_inspection.json`; incidences can overlap on the same pixel.

## Possible same-band comparison groups

The supplied data includes repeated observations within some bands:
- Barnard's Star field: D1 (3), D2 (3), D3 (2), D4 (3), D5 (2), D6 (2).
- Epsilon Indi B field: D2 (3), D3 (3), D5 (2), D6 (7).

These counts establish candidate input groups only. They do not prove that the observations pass WCS alignment, calibration, masking or PSF checks.

## Scientific compatibility

- QR2 and QR3 are kept separate.
- Different D1–D6 bands are kept separate.
- The selected comparison must have the same band, release and units.
- The FITS headers contain a WCS and `FINAST=0`, but WCS validity and residual registration have not been computed with Astropy.
- No difference/significance product was generated from the supplied real data in this environment.
- Photutils source detection and aperture photometry code is present but was not executed on the real cutouts.

## Verification labels

| Item | Status |
|---|---|
| Handoff ZIP opened and inventoried | VERIFIED |
| Manifest structure inspected | VERIFIED |
| 30 FITS files present | VERIFIED |
| FITS HDU layout from raw headers | PRELIMINARILY VERIFIED |
| FITS arrays' finite/variance sanity counts | PRELIMINARILY VERIFIED |
| Astropy FITS semantic inspection | NOT VERIFIED |
| Astropy WCS validity | NOT VERIFIED |
| Two real observations reprojected | NOT VERIFIED |
| Background-star residual alignment | NOT VERIFIED |
| Real difference/significance products | NOT VERIFIED |
| Real candidate detections | NOT VERIFIED |
| All five PRD target tests | NOT VERIFIED; only two target fields supplied |

No synthetic or placeholder image is presented as a real SPHEREx observation.
