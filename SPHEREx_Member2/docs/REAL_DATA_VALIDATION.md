# Real-Data Validation and Input Findings

## What was supplied

The ZIP handoff contains 30 FITS cutouts and a 46-record manifest. All 30 local FITS files match QR3 records. The remaining 16 manifest records are QR2 entries whose local FITS cutouts are absent from the ZIP, despite `download_status="downloaded"`.

The 30 cutouts split evenly by requested sky field:
- 15 cutouts around the Barnard's Star field (RA 269.45208Â°, Dec +4.69336Â°).
- 15 cutouts around the Epsilon Indi B field (RA 331.04415Â°, Dec âˆ’56.78284Â°).

The handoff includes CSV search summaries with 123 rows for Barnard's Star and 120 rows for Epsilon Indi B. These are archive summary rows, not 243 locally supplied FITS cutouts.

No supplied FITS files or target-specific manifest records were found for WISE 0855, RW Aurigae or R Draconis.

## FITS structure observed

All 30 files have seven HDUs:
0. Empty PRIMARY.
1. IMAGE â€” calibrated image.
2. FLAGS â€” bit flags.
3. VARIANCE â€” variance.
4. ZODI â€” zodiacal model.
5. EPSF â€” binary table.
6. WCS-WAVE â€” binary table.

29 science images are 29Ã—29 pixels and one is 26Ã—29 pixels. The image headers contain celestial WCS keywords and report `RADESYS=ICRS`; all have `FINAST=0`.

Astropy FITS inspection and WCS processing were executed. A pixel-to-sky-coordinate comparison between the original reference FITS and its aligned output produced matching coordinates at the top-left, center and bottom-right pixel positions.

Across the 30 files, the raw science arrays contain six non-finite pixels; variance arrays contain six non-finite pixels and no negative variance values. The supplied `FLAGS` headers include symbolic names, bit masks and descriptions. Flag incidences are recorded in `data/reports/fits_inspection.json`; incidences can overlap on the same pixel.

## Real-data pipeline execution â€” Job 009

The pipeline was executed using:

`config/alignment_test_3sigma.json`

The alignment source-detection threshold was configured to 3 sigma. The candidate-detection threshold remained at 5 sigma.

The selected processing group contains six Epsilon Indi B observations from the same QR3 collection, SPHEREx-D6 band and compatible units and wavelength interval.

Six real observations were reprojected onto a common 29Ã—29 ICRS reference grid. One observation was used as the reference, producing five comparison attempts.

Results:
- Six aligned frame FITS files were generated.
- Six frame previews were generated.
- Five comparison attempts were evaluated.
- Three comparisons passed the alignment gate.
- Two comparisons were blocked because there were insufficient reliable background-source matches.
- Three difference FITS products were generated.
- Three significance FITS products were generated.
- Three difference previews and three significance previews were generated.
- Four preliminary candidate records were produced.

The pipeline reported:
- Status: `partial`
- Usable observations: 30
- Frames written: 6
- Comparisons: 5
- Candidates: 4
- Manifest inputs missing or unavailable: 16
- Pipeline errors: 0

## Alignment validation

The alignment gate requires:
- At least three one-to-one background-source matches.
- Median residual no greater than 0.5 pixel.
- RMS residual no greater than 1.0 pixel.

Three comparisons passed:

| Comparison | Matches | Median residual (px) | RMS residual (px) | Result |
|---|---:|---:|---:|---|
| 0276_1 â†’ 0276_2 | 3 | 0.2978 | 0.3075 | PASSED |
| 0276_1 â†’ 0276_3 | 3 | 0.1334 | 0.2428 | PASSED |
| 0276_1 â†’ 0276_4 | 3 | 0.2489 | 0.4057 | PASSED |

Two comparisons were blocked:
- 0276_1 â†’ 0434_3: too few one-to-one background-source matches.
- 0276_1 â†’ 0578_1: insufficient background sources.

The pipeline uses the requested target coordinates to exclude detected peaks within a 3-pixel radius from alignment-source matching when valid target coordinates are available.

These alignment results are engineering checks on the supplied cutouts, not official SPHEREx astrometric performance claims.

## Scientific compatibility and processing decisions

- QR2 and QR3 are kept separate.
- Different D1â€“D6 bands are kept separate.
- The selected comparison group uses compatible collection, band, units and wavelength metadata.
- Science images are reprojected using bilinear interpolation.
- Variance is propagated using squared bilinear interpolation weights, assuming independent input-pixel noise.
- Quality flags are reprojected using nearest-neighbor interpolation.
- Invalid and excluded pixels are masked rather than zero-filled.
- Background offsets are measured diagnostically and are not automatically applied.
- Photometric scale normalization is not applied.
- PSF matching is not performed.

The EPSF extensions were available and selected for the processed observations. PSF diagnostics were calculated, but these are not a substitute for PSF matching or full PSF-aware photometric validation.

## Candidate detection findings

Four preliminary candidate records were generated.

All records are labelled `ambiguous/uncertain`. They are not confirmed moving objects, transients or variable sources.

The candidate records include sky coordinates, epoch information, measurements and quality flags where available. Some residual candidates have high pixel-level significance, but this alone does not establish an astrophysical detection.

Further review is required, including:
- Inspecting reference, comparison, difference and significance images at the same sky position.
- Checking quality flags and possible instrumental artifacts.
- Reviewing EPSF information and PSF differences.
- Performing source-level photometric validation.
- Assessing astrometric and centroid uncertainties.

No discovery claim is made from these preliminary candidates.

## Verification labels

| Item | Status |
|---|---|
| Handoff ZIP opened and inventoried | VERIFIED |
| Manifest structure inspected | VERIFIED |
| 30 FITS files present | VERIFIED |
| FITS HDU layout inspected with Astropy | VERIFIED |
| FITS arrays' finite/variance sanity checks | VERIFIED |
| Required PRD function names preserved | VERIFIED |
| Six real observations reprojected | VERIFIED |
| Reference/aligned WCS coordinate spot-check | VERIFIED at three pixel positions |
| Three comparison alignment gates passed | VERIFIED |
| Two comparisons correctly blocked | VERIFIED |
| Three real difference products generated | VERIFIED |
| Three real significance products generated | VERIFIED |
| Four preliminary candidate records generated | VERIFIED |
| Candidate scientific classification | PENDING HUMAN REVIEW |
| PSF matching and precision photometric validation | NOT IMPLEMENTED |
| All five PRD target tests | NOT VERIFIED; required target-specific data were not supplied |

## Limitations

The available dataset supports a partial real-data processing demonstration. It does not provide all required target-specific observations.

The pipeline does not currently perform PSF matching or full uncertainty propagation for centroid motion. Variance propagation does not model inter-pixel covariance introduced by resampling.

No synthetic or placeholder image is presented as a real SPHEREx observation. Preliminary candidates must not be interpreted as confirmed astronomical discoveries.
