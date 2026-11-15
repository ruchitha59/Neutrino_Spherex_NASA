# SPHEREx Explorer — Member 2 Science Pipeline

This repository contains the Member 2 astronomical image-processing and candidate-screening implementation for SPHEREx Explorer.

**Important status:** the supplied handoff includes 30 local SPHEREx-format FITS cutouts and a 46-record manifest. The code and synthetic tests are prepared, but the full Astropy/reproject processing run could not be executed in this environment because those packages are unavailable and package installation was blocked by network restrictions. Real-data alignment, difference images and candidate results are therefore **NOT VERIFIED**. The pipeline is designed to state this honestly rather than invent results.

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
│   ├── inspect_fits.py
│   ├── validate_manifest.py
│   ├── quality.py
│   ├── calibration.py
│   ├── alignment.py
│   ├── difference.py
│   ├── visualization.py
│   ├── detection.py
│   ├── astrometry.py
│   └── pipeline.py
├── data/
│   ├── manifest.json
│   ├── raw/                 # 30 supplied FITS cutouts
│   ├── reports/             # input and inspection reports
│   ├── processed/
│   ├── previews/
│   └── results/
├── input_handoff/           # original Member 1 files, preserved
├── config/default.json
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

The inventory JSON explicitly records that the initial binary-level inspection was not an Astropy semantic WCS validation.

## 7. Run the pipeline

```powershell
python -m science.pipeline --manifest data/manifest.json --output-dir data/results/job_001 --config config/default.json
```

The pipeline selects the largest group of at least two locally available observations sharing:

- the same collection/release,
- the same band,
- the same requested sky field,
- the same science units.

It will not subtract different bands or silently mix QR2 and QR3.

## 8. Run tests

```powershell
python -m pytest -q
```

Some FITS/WCS tests are automatically skipped if Astropy or reproject is not installed. A complete run must be performed after installing `requirements.txt`.

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

- The Member 1 manifest contains 46 records.
- 30 local FITS files are present; all 30 correspond to QR3 records.
- 16 QR2 records are marked `downloaded` in the manifest but their FITS files are absent from the handoff ZIP.
- The 30 FITS files cover the Barnard's Star and Epsilon Indi B sky fields (15 each).
- The handoff does not include supplied FITS cutouts for WISE 0855, RW Aurigae or R Draconis.
- The 30 supplied FITS files have an empty primary HDU and the six named extensions listed above.
- 29 science arrays are 29×29 pixels; one is 26×29 pixels.
- The IMAGE headers contain celestial WCS keywords and `FINAST=0`; Astropy-based WCS validation still needs to be run.
- The handoff contains several repeated epochs within the same band, so same-band comparisons may be possible. They have not yet been processed or scientifically accepted.

See `docs/REAL_DATA_VALIDATION.md` for the full qualification.

## 11. Scientific limitations

- Same-band, same-release compatibility is required for subtraction.
- The pipeline does not automatically normalize away source flux changes.
- Background offset estimates are diagnostics only; no automatic correction is applied.
- Variance reprojection uses squared bilinear weights and assumes independent input pixels. Inter-pixel covariance after resampling is not modeled.
- A candidate extracted from a difference/significance map is unverified and requires source-level photometry and human review.
- The supplied cutouts are small (about 0.05 degrees); they may contain too few stable background sources to pass the registration gate.
- `WCS-WAVE` is retained as metadata; its lookup table is intended for visualization. Precision spectral analysis should use the official CWAVE/CBAND calibration product.
- Proper-motion propagation is performed only when catalogue astrometry is explicitly supplied. The pipeline does not invent catalogue values.

## 12. Official references

- [SPHEREx Archive at IRSA — Data Products](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/)
- [SPHEREx Explanatory Supplement](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp_QR.pdf)
- [IRSA SPHEREx Mission Page](https://irsa.ipac.caltech.edu/Missions/spherex.html)
- [Astropy FITS documentation](https://docs.astropy.org/en/stable/io/fits/)
- [Astropy WCS documentation](https://docs.astropy.org/en/stable/wcs/)
- [reproject documentation](https://reproject.readthedocs.io/)

SPHEREx acknowledgement text and DOI should be taken from the current IRSA release documentation before public presentation.
