# Scientific Risk Report

| Risk | Evidence / status | Handling |
|---|---|---|
| Missing FITS inputs | 16 of 46 manifest records are absent locally | Report partial input; never assume manifest download status means a file exists |
| Mixed releases | QR2 and QR3 appear in the manifest | Separate by collection; no cross-release subtraction |
| Mixed bands | D1-D6 appear in the supplied data | Require the same band and compatible wavelength interval |
| Small cutouts | 29 x 29 pixels, with one 26 x 29 image | Registration may not find enough stable background sources |
| Astrometric uncertainty | Astropy WCS inspection completed; reference-versus-aligned coordinates matched at three image positions. Job009 alignment passed for three comparisons and blocked two | Use empirical background-source registration; retain alignment thresholds and block comparisons with insufficient matches |
| Resampling covariance | Reprojection changes noise correlation | Per-pixel variance propagated with squared bilinear weights, assuming independent input pixels; inter-pixel covariance is not modeled |
| PSF variation | EPSF extensions are present and diagnostics were calculated; PSF matching was not performed | Do not claim precision photometry or confirmed variability until PSF compatibility and matching are validated |
| Flags/artifacts | FLAGS HDU contains documented and header-described bits | Use actual masks and descriptions; exclude flagged pixels conservatively |
| Source masking | SOURCE flags are present | Do not treat known-source pixels as invalid science pixels solely because they carry SOURCE flags |
| Moving target alignment | Target motion can affect apparent position | Align the background; when valid requested target coordinates are available, exclude the target region within a 3-pixel radius from alignment matching |
| False candidates | Job009 produced four preliminary candidate records, all requiring further validation | Keep candidates ambiguous/uncertain; require source-level photometry, astrometric review and human validation |
| Five-target validation | Supplied FITS data cover Barnard's Star and Epsilon Indi B only | WISE 0855, RW Aurigae and R Draconis remain NOT VERIFIED |

## Job009 real-data status

- Six compatible Epsilon Indi B observations were selected.
- Three of five comparisons passed the alignment gate.
- Two comparisons were blocked because there were too few background-source matches.
- Three difference images and three significance maps were generated.
- Four preliminary candidate records were produced.
- The pipeline completed with status `partial`.

## Important scientific limitations

- No PSF matching was performed.
- Background offset estimates are diagnostic only; no automatic background correction was applied.
- Candidate records are not confirmed discoveries.
- Variance propagation assumes independent input pixels and does not model inter-pixel covariance.
- The supplied observations do not provide complete validation for all five PRD targets.

See `docs/REAL_DATA_VALIDATION.md` for detailed processing results.

