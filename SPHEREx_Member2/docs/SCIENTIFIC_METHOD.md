# Scientific Method and Processing Decisions

## Processing order

The implementation follows the PRD sequence:

Preserve raw calibrated FITS -> inspect product structure -> quality masking -> WCS reprojection -> registration check -> photometric/background diagnostics -> blink/difference -> candidate review.

## FITS extension identification

The supplied files have an empty `PRIMARY` HDU. The science image is HDU 1 with `EXTNAME=IMAGE`. The auxiliary layers are `FLAGS`, `VARIANCE`, `ZODI`, `EPSF` and `WCS-WAVE`.

Code selects extensions by name and records the evidence.

Official IRSA documentation describes the Level 2 MEF product and the IMAGE, FLAGS, VARIANCE, ZODI and WCS-WAVE layers. The supplied QR3 files additionally contain an `EPSF` binary-table extension. The actual file structure takes precedence over any assumed HDU index.

## Quality masks

The science mask rejects:

- NaN and infinite science values;
- NaN, infinite or negative variance;
- uncovered reprojection pixels;
- named quality flags whose masks and descriptions are read from the `FLAGS` HDU header.

The Explanatory Supplement v1.3 Table 10 defines the core flags TRANSIENT, OVERFLOW, SUR_ERROR, NONFUNC, DICHROIC, MISSING_DATA, HOT, COLD, FULLSAMPLE, PHANMISS, NONLINEAR, PERSIST, OUTLIER and SOURCE.

Newer flags in the supplied QR3 headers, such as GHOST, GHOST_FPA, GHOST_EXT, STREAK, BLOOM, SNOWBALL and HALO, are used only when the actual FITS header provides their mask and description.

`SOURCE` is not automatically rejected. It identifies known-source pixels, which can be useful when estimating background, but those pixels still contain astrophysical signal. `FULLSAMPLE` is informational.

## Compatibility

Subtraction is blocked unless collection/release, band and units agree. Wavelength interval metadata is also compared when available.

The default workflow never silently mixes QR2 and QR3 or different detector bands.

## Reprojection and variance

Science images are reprojected with bilinear interpolation.

Variance is propagated with squared bilinear interpolation weights:

`Var(out) = sum_i (w_i^2 * Var(input_i))`

This assumes independent input-pixel noise. It does not model covariance between neighboring output pixels created by resampling. This limitation is included in processing metadata.

Flags are reprojected with nearest-neighbor interpolation so bit values are not blended.

Before science reprojection, invalid science pixels, invalid variance pixels and excluded quality-flag pixels are masked. A bilinear mask-coverage map is also reprojected; an output pixel is accepted only when all non-zero bilinear contributors are valid.

## Alignment

After WCS reprojection, local positive peaks in the background are detected and matched.

The current gate requires:

- At least three matches.
- Median residual <= 0.5 pixel.
- RMS residual <= 1.0 pixel.

These are configurable engineering thresholds, not official SPHEREx performance claims.

When requested target RA and Dec coordinates are available in the manifest, the pipeline converts the target position into reference-grid pixel coordinates and excludes detected peaks within a 3-pixel radius from alignment-source matching.

If target coordinates are unavailable or invalid, this exclusion cannot be applied.

The small 29 x 29 supplied cutouts may not contain enough background sources. If the alignment gate fails, the pipeline withholds difference-based candidate extraction.

## Difference and significance

The subtraction convention is exactly:

`difference = comparison_epoch - reference_epoch`

Positive residuals mean the comparison image is brighter at that pixel; negative residuals mean it is fainter.

Significance is:

`(comparison - reference) / sqrt(reference_variance + comparison_variance)`

It is produced only when valid variance maps are available on the same output grid. Zero denominator, invalid variance and invalid science pixels yield NaN.

## Background and calibration

The code estimates a robust median background offset on common valid pixels but does not automatically apply it.

A background correction can erase real variability if source contamination or sky differences are not controlled. Any later correction must use source-masked regions and be recorded.

No PSF matching is currently applied. PSF mismatch must be assessed before precision photometry or quantitative variability claims.

## Source detection and photometry

The code provides Photutils `DAOStarFinder` source detection and circular-aperture photometry.

Aperture flux errors are computed from the variance map when available. Source matching compares centroid shifts and flux changes between epochs.

A possible variability label requires a fixed centroid and a flux-change significance threshold. A possible motion label requires a centroid shift threshold.

Centroid uncertainties are not yet propagated into the motion threshold, and PSF matching is not implemented, so these labels remain preliminary candidates only.

## Candidate labels

Connected residuals are reported as `ambiguous/uncertain` by default.

The current implementation does not claim a confirmed moving object or variable source. Motion/variability classification requires robust source matching and photometry across epochs, with uncertainties and artifact checks.

## Proper motion

Astropy time parsing and `SkyCoord.apply_space_motion` are provided only when catalogue astrometry, provenance and reference epoch are supplied.

No catalogue values are guessed or embedded.


