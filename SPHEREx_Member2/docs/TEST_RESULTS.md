# Test Results

## Execution environment

- Operating system: Windows 11.
- Python: 3.12.6.
- Virtual environment: `.venv`.
- pytest: 9.2.0.

Scientific dependencies installed and used include:

- NumPy
- Astropy
- SciPy
- reproject
- Photutils
- Matplotlib
- scikit-image
- pandas

## Executed verification

### Python compilation

Command:

```powershell
python -m compileall -q science
```

Result: PASSED.

### Automated tests

Command:

```powershell
python -m pytest -v
```

Latest actual result:

- **34 passed**
- **0 skipped**
- **0 failed**

Execution time: 3.48 seconds.

## Test coverage

The passing tests cover:

- PRD function-name and signature compatibility.
- FITS science-extension selection instead of assuming PRIMARY contains science data.
- Reprojection on a synthetic identity WCS grid.
- Manifest path resolution and missing-file reporting.
- Release, band and unit compatibility.
- Difference sign convention and invalid-pixel handling.
- Significance calculation using variance.
- Invalid variance and zero-denominator masking.
- EPSF grid loading, model selection and diagnostic calculations.
- Quality masks and FITS-header-derived flag definitions.
- Identical and stationary synthetic observations.
- Registration rejection for a known one-pixel shift.
- Successful synthetic background-source registration.
- Brightness increase and decrease behavior.
- Synthetic noise and significance behavior.
- NaN, bad-pixel and incomplete-coverage masking.
- Background-offset diagnostic behavior.
- Conservative ambiguous candidate classification.
- Source-catalogue variability and possible-motion scenarios.
- Candidate quality-flag annotation.
- Variance reprojection using squared bilinear interpolation weights.

## Real-data pipeline verification

Job 009 was executed using:

`config/alignment_test_3sigma.json`

Results:

- 30 locally available FITS observations identified.
- Six real observations selected and reprojected to a common ICRS grid.
- Five comparison attempts evaluated.
- Three comparisons passed alignment.
- Two comparisons were blocked due to insufficient background-source matches.
- Three real difference FITS products generated.
- Three real significance FITS products generated.
- Four preliminary candidate records generated.
- No pipeline errors reported.
- Overall pipeline status: `partial`.

The original reference and aligned FITS WCS coordinate mappings were also compared at three image positions and matched.

## Remaining scientific validation

The following are not established by the automated tests or Job 009:

- Full PSF matching and PSF-aware photometric validation.
- Complete centroid uncertainty propagation for motion classification.
- Inter-pixel covariance modelling after reprojection.
- Human validation of all four preliminary candidate records.
- Processing and verification of all five PRD target-specific datasets.
- End-to-end Member 3 integration.

A passing test suite does not independently establish scientific discovery or complete PRD acceptance.

## Verification conclusion

The implementation compiles successfully and all 34 automated tests pass in the Windows 11 / Python 3.12.6 environment.

A partial real-data processing run has also been completed successfully. Blocked comparisons, missing observations and scientific limitations are explicitly reported rather than treated as successful results.
