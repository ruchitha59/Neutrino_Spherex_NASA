# Implementation Plan and Stage Gates

## Stage gate status

1. **Input gate - COMPLETE:** Preserved the Member 1 handoff, validated manifest paths, inventoried FITS files and inspected FITS HDU structure using Astropy.

2. **Core science gate - COMPLETE:** Installed Astropy, reproject and Photutils. Executed FITS inspection, WCS processing, quality masking, variance propagation and synthetic tests.

3. **Two-epoch gate - PARTIALLY COMPLETE:** Selected a compatible same-release, same-band observation group, reprojected six real observations onto a common ICRS grid and evaluated five background-source alignment comparisons. Three passed; two were blocked due to insufficient matches.

4. **Difference gate - PARTIALLY COMPLETE:** Generated three real difference images and three significance maps after alignment gates passed. Other comparisons were withheld.

5. **Candidate gate - PRELIMINARY:** Generated four candidate records. All remain ambiguous/uncertain and require human scientific review. PSF matching and complete uncertainty validation remain outstanding.

6. **Integration gate - IMPLEMENTED, INTEGRATION NOT CONFIRMED:** Preserved the `process_manifest(...)` entry point and documented the processing outputs and Member 3 interface contract. End-to-end integration with Member 3 has not been verified.

7. **Target gate - PARTIALLY COMPLETE:** Processed the supplied Barnard's Star and Epsilon Indi B fields. The supplied handoff does not contain all five PRD target-specific datasets. Missing observations must not be invented.

## Latest real-data run

Job: `job_009`

Configuration: `config/alignment_test_3sigma.json`

- Usable observations: 30
- Frames written: 6
- Comparison attempts: 5
- Alignment passes: 3
- Alignment blocks: 2
- Difference products: 3
- Significance products: 3
- Preliminary candidate records: 4
- Missing manifest inputs: 16
- Pipeline errors: 0
- Overall status: `partial`

## Automated verification

- Python compilation: passed.
- Automated tests: 34 passed, 0 failed.
- PRD function-name and signature compatibility: passed.

## Acceptance principle

A stage is not considered scientifically complete merely because code executes or an output file is generated. Blocked comparisons, missing observations, unvalidated candidates and unverified integrations must remain explicitly documented.
