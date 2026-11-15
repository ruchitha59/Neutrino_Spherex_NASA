# Member 2 Delivery Status

## 1. Delivered components

- Modular Member 2 science package under `science/`.
- Exact PRD-required function names and signatures preserved and tested.
- FITS inspection and metadata extraction.
- Manifest validation and input resolution.
- Quality masking and preservation of invalid-pixel information.
- WCS reprojection to a common reference grid.
- Variance propagation using squared bilinear interpolation weights.
- Release, band, unit and wavelength compatibility checks.
- Background diagnostics and calibration checks.
- Difference and significance image generation.
- Consistent image previews and visualization.
- Source detection and aperture photometry.
- Candidate comparison and quality-flag annotation.
- EPSF grid loading, selection and diagnostic measurements.
- Pipeline orchestration and machine-readable processing results.
- Windows 11 / Python 3.12 setup instructions.
- Configuration files and synthetic test scenarios.
- Member 3 integration contract and supporting documentation.
- Original Member 1 handoff files preserved under `input_handoff/`.
- All 30 supplied local FITS files copied to `data/raw/`.
- Machine-readable manifest, FITS inventory, input inventory, target status and validation reports.

## 2. Environment and automated verification

Development environment:
- Operating system: Windows 11.
- Python: 3.12.6.
- Virtual environment: `.venv`.

Installed scientific packages include Astropy, NumPy, SciPy, reproject, Photutils, Matplotlib, scikit-image and pandas.

Latest verification:

- `py -3.12 -m compileall -q science`: PASSED.
- `py -3.12 -m pytest -q`: 51 passed, 0 failed.
- Required PRD function-name and signature compatibility test: PASSED.

The current automated test run completed in 3.24 seconds.

## 3. Real-data pipeline execution

Real-data processing was executed using Job 009:

`config/alignment_test_3sigma.json`

The selected group contained six real Epsilon Indi B observations from the same QR3 collection and SPHEREx-D6 band, with compatible units and wavelength metadata.

Pipeline results:

- Usable observations: 30.
- Frames written: 6.
- Comparison attempts: 5.
- Alignment comparisons passed: 3.
- Alignment comparisons blocked: 2.
- Difference FITS products generated: 3.
- Significance FITS products generated: 3.
- Frame previews generated: 6.
- Difference previews generated: 3.
- Significance previews generated: 3.
- Preliminary candidate records: 4.
- Missing or unavailable manifest inputs: 16.
- Pipeline errors: 0.
- Overall processing status: `partial`.

Six real observations were reprojected onto a common 29 x 29 ICRS reference grid.

A pixel-to-sky-coordinate spot-check at the top-left, center and bottom-right positions showed matching coordinates between the original reference FITS and its aligned output.

Three comparisons passed the configured alignment gate. Two were blocked because there were insufficient reliable background-source matches.

## 4. Scientific processing decisions and limitations

- QR2 and QR3 observations are not silently mixed.
- Different detector bands are not silently mixed.
- Invalid science and variance pixels and excluded quality flags are masked rather than zero-filled.
- Flags are reprojected using nearest-neighbor interpolation.
- Variance is propagated using squared bilinear interpolation weights.
- The variance propagation assumes independent input-pixel noise and does not model resampling-induced inter-pixel covariance.
- Background offsets are calculated diagnostically and are not automatically applied.
- Photometric scale normalization is not applied.
- Pairwise PSF homogenization uses local field-center EPSF/PSF second moments and normalized Gaussian kernels before differencing. It blocks pairs without reliable covered PSF models and refuses deconvolution.
- PSF matching is a local approximation; it does not model full spatial variation over each cutout and does not constitute calibrated source-level PSF photometry.
- Short-range inter-pixel noise covariance is estimated empirically from masked blank sky and used for approximate aperture/component significance corrections. Full covariance propagation remains outstanding.
- Target exclusion from alignment-source matching is applied when valid requested target coordinates are available in the manifest, using a 3-pixel radius.
- Candidate classifications remain preliminary and ambiguous/uncertain. They are not confirmed astronomical discoveries.

## 5. Outstanding items

- The 16 QR2 FITS files marked downloaded in the manifest are absent from the supplied handoff ZIP.
- The supplied data does not include target-specific FITS observations for WISE 0855, RW Aurigae or R Draconis.
- All five PRD target-specific tests cannot be considered verified from the supplied dataset.
- Two Job 009 comparisons did not pass the alignment gate.
- The four preliminary candidate records require human scientific review.
- Full spatially varying PSF matching and calibrated source-level PSF photometry remain outstanding.
- Centroid uncertainty propagation for robust motion classification remains outstanding.
- Full inter-pixel covariance propagation from reprojection is not modelled; the current short-range empirical covariance correction is approximate.
- Member 1's supplied `search_spherex` signature differs from the PRD starter signature, and `download_cutout()` is absent. Member 1 code was not changed.

## 6. Handover status

Member 2 has a tested processing implementation, preserved PRD interfaces, supporting documentation, and a successful partial real-data processing run.

The automated test suite passes completely. Real-data processing has been demonstrated on the supplied observations, but full scientific acceptance remains conditional on the outstanding data, alignment, PSF, photometric and candidate-validation requirements.

No missing data, blocked comparisons or preliminary candidates are represented as successful scientific detections.

## 7. Updated live integration result (2026-11-14)

The latest API end-to-end run processed four live IRSA QR3 SPHEREx-D2 FITS products for Barnard's Star. All four frames were written and all three comparisons passed alignment (1,044, 1,160 and 1,121 stable-source matches), PSF homogenization and empirical short-range covariance estimation. Difference and significance FITS/PNG products were emitted, with 3,090 raw candidate/residual records and 32 preliminary review signals. All preview, mask-overlay, difference and significance media URLs returned HTTP 200.

The earlier Job 009 result above remains a record of the supplied-handoff run; the live API job is the more recent end-to-end integration check. Candidate classifications are still preliminary and must be reviewed by a human.
