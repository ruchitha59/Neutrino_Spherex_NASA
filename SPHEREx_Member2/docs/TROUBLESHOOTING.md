# Troubleshooting

## `ModuleNotFoundError: astropy`

Activate `.venv` and run:

```powershell
python -m pip install -r requirements.txt
```

## PowerShell refuses to activate `.venv`

Run this in the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Manifest says downloaded but the file is missing

The supplied handoff has 16 QR2 manifest records with no local FITS cutout. The validator reports these records as missing. Re-download through Member 1's archive workflow or provide the files; do not create placeholder FITS files.

## No comparison is produced

Check `processing.json`:
- `blocked_incompatible`: release, band, wavelength or units do not match.
- `blocked_alignment`: too few background sources or residual offsets exceed the configured tolerance.
- `failed`: no compatible local observation group exists.

The supplied cutouts are only about 29 x 29 pixels, so the background-source alignment check may not find the required three sources.

## Astropy/reproject tests are skipped

Install the complete requirements in Python 3.12, then rerun:

```powershell
python -m pytest -q -rs
```

Do not treat skipped tests as successful tests.

## Difference looks like bright/dark pairs around every star

This is often caused by small registration offsets. Do not classify the residuals as moving objects. Inspect the alignment residuals and withhold candidate extraction until registration passes.

