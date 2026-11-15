# Test Results

## Execution environment

- Runtime Python: 3.13 in the isolated execution environment. Deployment instructions target Python 3.12 on Windows 11.
- Available: NumPy, SciPy, Matplotlib, pandas, scikit-image, pytest.
- Missing: Astropy, reproject and Photutils.
- Dependency installation was attempted, but package-index DNS/network access was unavailable.

## Executed results

Command:

```powershell
python -m pytest -q -rs
```

Actual result:

- **25 passed**
- **2 skipped**
- **0 failed**

The two skipped tests are:
- `tests/test_alignment.py` — skipped because Astropy is not installed (and reproject is also required).
- `tests/test_fits_inspection.py` — skipped because Astropy FITS is not installed.

The 25 passing tests cover:
- PRD function-name/signature compatibility (AST-level);
- subtraction sign convention and invalid-pixel behavior;
- significance formula, invalid variance and zero denominator;
- quality masks and header-derived flag masks;
- Windows-style manifest path resolution and missing-file reporting;
- release/band/unit compatibility;
- synthetic identical and stationary images;
- synthetic one-pixel source shift (registration gate rejection);
- synthetic stable-background registration;
- synthetic brightness increase/decrease;
- synthetic noise/significance;
- NaN/bad-pixel/incomplete-coverage masking;
- background-offset diagnostic (not applied);
- ambiguous-only candidate labeling.

Additional syntax check:

```powershell
python -m compileall -q science tests
```

Actual result: completed successfully (exit code 0).

## Not verified

- Astropy FITS semantic inspection.
- Astropy WCS parsing/validity.
- `reproject` image reprojection on actual FITS data.
- End-to-end real-data pipeline.
- Real alignment residuals and difference/significance images.
- Photutils source-level photometry.
- Full test run in Python 3.12 with all dependencies installed.

A skipped test is not counted as passed. Real-data acceptance remains NOT VERIFIED.
