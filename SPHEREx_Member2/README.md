# SPHEREx Explorer - Member 2 Science Pipeline

This repository contains the Member 2 astronomical image-processing and candidate-screening implementation for SPHEREx Explorer.

**Current status:** The supplied handoff includes 30 local SPHEREx-format FITS cutouts and a 46-record manifest. Member 2's science pipeline has been executed on the supplied real data. Job 009 processed six compatible observations, generated three difference images and three significance maps, and produced four preliminary candidate records. Three of five comparisons passed alignment; two were blocked due to insufficient background-source matches. The pipeline status is `partial`. All 34 automated tests pass. Candidate scientific validation, PSF matching, missing observations and full PRD target coverage remain outstanding. See `DELIVERY_STATUS.md` and `docs/REAL_DATA_VALIDATION.md`.

## 1. What Member 2 does

Member 2 takes Member 1's FITS cutouts and prepares scientifically comparable image frames:

1. Inspect every FITS HDU and identify the science image using `EXTNAME=IMAGE`.
2. Validate the manifest and local input files.
3. Build masks from non-finite values, variance validity, coverage and documented SPHEREx flags.
4. Compare only observations from the same collection/release, spectral band, units and wavelength interval.
5. Reproject images onto a common celestial WCS grid.
6. Propagate per-pixel variance using squared bilinear interpolation weights (assuming independent input pixels).
7. Check residual alignment using background-source centroids.
8. Create consistent-stretch previews and difference/significance products only after the quality gates pass.
9. Produce conservative candidate records with explicit caveats.

A pixel difference is not a confirmed discovery.

## 2. Project structure

```text
SPHEREx_Member2/
├── science/
│   ├── __init__.py
│   ├── inspect_fits.py
│   ├── validate_manifest.py
│   ├── quality.py
│   ├── calibration.py
│   ├── alignment.py
│   ├── difference.py
│   ├── visualization.py
│   ├── detection.py
│   ├── psf.py
│   ├── astrometry.py
│   └── pipeline.py
├── data/
│   ├── manifest.json
│   ├── raw/                 # 30 supplied FITS cutouts
│   ├── reports/             # input and inspection reports
│   ├── processed/
│   ├── previews/
│   └── results/
├── input_handoff/            # original Member 1 files, preserved
├── config/
│   └── default.json
├── tests/
├── docs/
├── requirements.txt
└── README.md
```

`input_handoff/` preserves the Member 1 files exactly as supplied. The processing pipeline does not edit original FITS files.

## 3. Installation on Windows 11

Install Python 3.12 (64-bit) and VS Code. In VS Code, open this project folder, then open **Terminal → New Terminal**.

### Create a virtual environment

```powershell
py -3.12 -m venv .venv
```

### Activate it in PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation for the current terminal, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Upgrade pip and install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Check the important packages:

```powershell
python -c "import numpy, astropy, reproject, scipy, photutils, matplotlib; print('Scientific environment ready')"
```

## 4. FITS basics in simple words

A FITS file is an astronomy data file. It can contain several HDUs (Header/Data Units). Each HDU has a header and may have data.

The supplied SPHEREx cutouts contain an empty `PRIMARY` HDU followed by:

| HDU extension | Purpose |
|---|---|
| `IMAGE` | Calibrated surface-brightness science image |
| `FLAGS` | Per-pixel quality and processing bit flags |
| `VARIANCE` | Per-pixel variance |
| `ZODI` | Modelled zodiacal-light background; not subtracted from IMAGE |
| `EPSF` | Effective PSF table present in the supplied QR3 cutouts |
| `WCS-WAVE` | Pixel-to-wavelength lookup table |

The code selects `IMAGE` by its extension name. It does not assume HDU 0 is the science image.

## 5. WCS basics

WCS means World Coordinate System. It maps image pixel coordinates (x, y) to sky coordinates (Right Ascension and Declination). The pipeline uses the celestial WCS to place observations on one common sky grid.

The background sky is aligned. The moving target is not forced to the same pixel location, because its apparent motion is the signal we want to preserve.

## 6. Inspect the supplied FITS files

From the project root:

```powershell
python -c "from science.inspect_fits import inspect_fits; import json; print(json.dumps(inspect_fits('data/raw/2026W33_2A_0594_4_SPHEREx-D3_RA269.45208_DEC4.69336_SIZE0.05000_cutout.fits'), indent=2))"
```

This command requires Astropy.

The preliminary handoff inventory is in:

- `data/reports/fits_inspection.json`
- `data/reports/input_inventory.json`
- `data/reports/manifest_validation.json`

The initial handoff inventory records the original binary-level inspection. Subsequent Astropy FITS inspection and WCS processing were executed as part of the Member 2 pipeline. A reference-versus-aligned WCS coordinate spot-check matched at three image positions. See `docs/REAL_DATA_VALIDATION.md`.

## 7. Run the pipeline

```powershell
python -m science.pipeline --manifest data/manifest.json --output-dir data/results/job_001 --config config/default.json
```

The pipeline selects the largest group of at least two locally available observations sharing:

- The same collection/release.
- The same band.
- The same requested sky field.
- The same science units.

It will not subtract different bands or silently mix QR2 and QR3.

## 8. Run tests

```powershell
python -m compileall -q science
python -m pytest -v
```

Latest recorded automated test result:

- 34 passed
- 0 skipped
- 0 failed

## 9. Output files

A completed or partial job writes:

```text
<output-dir>/
├── processed/
│   ├── frame_000_aligned.fits
│   ├── frame_001_aligned.fits
│   ├── difference_000_001.fits
│   └── significance_000_001.fits
├── previews/
│   ├── frame_000.png
│   ├── frame_001.png
│   ├── difference_000_001.png
│   └── significance_000_001.png
└── results/
    ├── processing.json
    └── candidates.json
```

Difference and significance files are created only when their scientific checks pass. A blocked comparison is recorded in `processing.json`, not silently forced through.

## 10. Supplied input findings

- The Member 1 manifest contains 46 observation records.
- 30 local FITS files are present; all 30 correspond to QR3 records.
- 16 QR2 records are listed in the manifest, but their FITS files are absent from the supplied handoff.
- The 30 supplied FITS files cover the Barnard's Star and Epsilon Indi B sky fields, with 15 observations each.
- The handoff does not include supplied FITS cutouts for WISE 0855, RW Aurigae or R Draconis.
- The supplied FITS files contain an empty `PRIMARY` HDU followed by `IMAGE`, `FLAGS`, `VARIANCE`, `ZODI`, `EPSF` and `WCS-WAVE` extensions.
- 29 science arrays are 29 x 29 pixels; one is 26 x 29 pixels.
- Astropy-based FITS and celestial WCS inspection has been executed.
- A reference-versus-aligned WCS coordinate spot-check matched at the top-left, centre and bottom-right image positions