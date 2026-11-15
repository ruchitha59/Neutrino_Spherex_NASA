# Scientific Risk Report

| Risk | Evidence / status | Handling |
|---|---|---|
| Missing FITS inputs | 16 of 46 manifest records absent locally | Report partial input; never assume downloaded status means file exists |
| Mixed releases | QR2 and QR3 appear in manifest | Separate by collection; no cross-release subtraction |
| Mixed bands | D1–D6 appear | Require same band and wavelength interval |
| Small cutouts | 29×29 pixels, one 26×29 | Registration may not find enough stable background sources |
| Astrometric uncertainty | Header WCS fields present; FINAST=0 | Run Astropy WCS checks and empirical registration before accepting |
| Resampling covariance | Reprojection changes noise correlation | Per-pixel variance propagated with squared weights; inter-pixel covariance not modeled |
| PSF variation | EPSF present, no PSF matching yet | Block precision photometry until PSF compatibility is assessed |
| Flags/artifacts | FLAGS HDU contains documented and header-described bits | Use actual masks/descriptions; exclude flagged pixels conservatively |
| Source masking | SOURCE flags are abundant | Do not treat known-source pixels as invalid science pixels |
| Moving target alignment | target may move relative to background | Align background; exclude target region from registration in next iteration |
| False candidates | difference residuals can be artifacts | Candidate records remain ambiguous; require human review |
| Five-target validation | only two target fields supplied | Other three targets remain NOT VERIFIED |
