# PRD Function Compatibility Report

The Member 2 PRD starter code defines the following exact callable interfaces. Their names and signatures are preserved in the implementation.

| PRD function | PRD signature | Implemented module | Implemented signature | Compatibility | Test |
|---|---|---|---|---|---|
| `inspect_fits` | `inspect_fits(path)` | `science/inspect_fits.py` | `inspect_fits(path)` | Preserved | Signature compatibility and Astropy FITS inspection test passed |
| `reproject_to_reference` | `reproject_to_reference(input_fits, ref_wcs, shape_out)` | `science/alignment.py` | `reproject_to_reference(input_fits, ref_wcs, shape_out)` | Preserved | Signature compatibility, synthetic identity-grid test and real-data reprojection executed |
| `make_difference` | `make_difference(reference, comparison)` | `science/difference.py` | `make_difference(reference, comparison)` | Preserved | Signature compatibility and executed unit tests passed |
| `significance_difference` | `significance_difference(ref, cmp, ref_var, cmp_var)` | `science/difference.py` | `significance_difference(ref, cmp, ref_var, cmp_var)` | Preserved | Signature compatibility and executed unit tests passed |

## Verification summary

- All four required PRD function names and signatures are preserved.
- The PRD compatibility test passed.
- FITS inspection was executed using Astropy.
- The reprojection implementation was tested on a synthetic identity grid and used in the real-data pipeline.
- Real-data processing generated aligned frames and difference/significance products for comparisons that passed the alignment gate.
- The latest automated test suite completed with 34 passed and 0 failed.

## Member 1 interface observations - no changes made

The supplied `input_handoff/nasa_api.py` defines:

- `search_spherex(ra_deg, dec_deg, radius_deg)` - function exists, but the supplied signature differs from the PRD starter signature, which includes a default radius and optional collection argument.
- `download_one_fits_cutout(row, ra_deg, dec_deg, size_deg)` - exists.
- `download_multiple_fits_cutouts(results, ra_deg, dec_deg, size_deg, limit)` - exists.
- `download_cutout()` - the exact PRD starter function name is not present.
- `inspect_fits()` - not present in the supplied Member 1 code.

These Member 1 discrepancies are documented only. Member 1 files were not modified.

## Compatibility rule

Do not rename or remove the required PRD functions. New behavior belongs in helper functions or wrappers while retaining the public PRD signatures.
