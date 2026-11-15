# SPHEREx Explorer integration status

## Current data path

The React search form calls the API through the Vite `/api` proxy. The API resolves the five named challenge targets through CDS Sesame/SIMBAD, queries IRSA SIA2, downloads FITS cutouts using the archive-returned `access_url`, validates FITS structure, and hands real files to the Member 2 WCS/masking/difference pipeline. The browser receives generated PNG previews, observation metadata, quality summaries, comparison gate results, and preliminary candidate records through API result/media endpoints.

The search response reports archive product rows, including multiple spectral bands from the same epoch. Processing selects one band at a time; the backend rejects cross-band comparisons. Shareable query parameters include RA, Dec, FOV, release, and target ID.

## Live archive checks

Checked on 2026-11-14 through the connected API service using resolved target coordinates and QR3-first search with QR2 fallback when QR3 returned no products:

| Target | IRSA rows returned | Collections checked | Result |
|---|---:|---|---|
| Barnard's Star | 129 | QR3 | Coverage returned |
| Epsilon Indi B | 120 | QR3 | Coverage returned |
| WISE 0855-0714 | 0 | QR3, QR2 | No matching archive product returned |
| RW Aur | 114 | QR3 | Coverage returned |
| R Draconis | 127 | QR3 | Coverage returned |

These are archive rows, not independent epochs; SIA2 can return different bands for one observation. The UI displays the real products and processes only a same-band group.

## Real end-to-end processing check

R Draconis field, QR3, SPHEREx-D6:

- IRSA search returned 127 rows.
- Four real FITS frames were successfully downloaded, inspected, and reprojected onto a shared ICRS grid; two failed cutouts were recorded as missing inputs.
- Three comparisons were attempted. All were blocked by the Member 2 alignment gate because there were too few reliable background-source matches.
- The result was `partial`, with zero candidates. No difference image or detection was shown as scientifically valid.
- The API result and generated PNG preview URLs returned HTTP 200.
- Follow-up root-cause check: the 0.1° cutouts were about 59×58 pixels. A real 0.5° cutout returned about 293×292 pixels; the frontend now defaults to 0.5° and keeps smaller fields available.
- Reprocessing at 3σ and experimentally at 2σ still did not produce the required three reliable one-to-one background matches. IRSA returned HTTP 503 for most wider cutout requests, preventing a complete wider-field comparison. The alignment gate remains intact; treating these frames as aligned would be scientifically unsafe.

## Root fixes and successful real-data run

- The search result `obs_id` repeats across detector bands. The API now deduplicates repeated access URLs and assigns each FITS product a band- and filename-specific selection ID. Explicit jobs reject mixed bands, preventing the former cross-band duplicate selection.
- The frontend now defaults to a tested 0.5° field, which supplied enough background stars without weakening the 5σ alignment gate.
- A full API run on real Barnard's Star QR3 data completed: four unique D2 FITS products downloaded, four frames processed, all three comparisons passed alignment (1,055, 1,212, and 1,066 matches), and a generated preview returned HTTP 200.
- IRSA returned a real 61,021,440-byte FITS file from the direct product URL while its cutout endpoint returned `503 Server busy, retry later.` The API now falls back to the full real FITS product after transient cutout errors. Reprocessing a full product alongside three cutouts completed with four frames and all three comparisons passing.
- The pipeline emitted 3,119 raw source/residual records for this field, of which 136 were classified as possible motion or brightness variability; 2,983 remained ambiguous. The API review queue now exposes only the 136 classified signals, retains the full set in the processing files, and reports the counts so a large field does not flood the UI.
- The real-frame viewer controls now work: linear/log/square-root/asinh previews and valid-pixel mask overlays are generated from processed FITS frames; contrast and brightness adjust the displayed frame. Candidate review status filtering is active.

The R Draconis run above is the initial blocked-field result. The later Barnard's Star run below verifies the corrected path end to end. Difference products and review signals remain preliminary and candidates require human review.

## Current science integration update

- Before difference imaging and aperture photometry, each comparison pair is PSF-homogenized using measured local EPSF/PSF second moments and normalized Gaussian convolution. Deconvolution is refused; pairs without a valid covered PSF model are blocked instead of producing an uncorrected difference.
- Short-range noise autocorrelation is estimated empirically from masked blank sky. Covariance-aware aperture and connected-component significance corrections are approximate; they do not reconstruct the full spatial covariance matrix.
- PSF moments are evaluated at the requested field center, so this is a local approximation and does not model PSF variation over the whole cutout. Photometric calibration and source-level PSF validation are still not claimed.
- WISE 0855-0714 has no usable SPHEREx products returned in the supported field sizes for QR2 or QR3. The interface reports no archive coverage instead of showing fabricated/demo frames. This target cannot produce an end-to-end real-data result until the archive has usable observations.
- The Three.js/Drei visualization remains dynamically loaded. Vite's current build emits a large optional 3D chunk warning; the core application bundle is much smaller. This is a performance advisory, not a functional build failure.

## Verification performed

- Frontend production build: passed.
- Frontend ESLint: passed.
- Backend Python syntax compilation: passed.
- Member 2 suite: 51 passed in the latest run.
- Browser check: target preset loaded live resolver coordinates, archive search returned real product cards, processing progress was displayed, and a runtime render error found during the check was fixed.
- Current workspace API proxy: `/api/health`, `/api/targets` (all five targets), and a live Barnard's Star archive search through Vite returned HTTP 200; all 147 rows had unique product IDs and access URLs.
- Real-data result-shape verification after the viewer changes: all four frames returned the four stretch URLs and four mask-overlay URLs; API media files existed, three comparisons passed, and the review API returned 136 signals with a 3,119-record summary.
- Current frontend code after the wider-field and review-queue changes: ESLint and Vite production build passed. The bundle-size advisory (>500 kB) remains a build warning, not an error.

## Final integration verification (2026-11-14)

- PRD review covered the coordinate/FOV query, optional release/band/date filters, real-data handling, timeline playback, difference/significance views, metadata/provenance, candidate review/export, URL sharing and honest no-coverage behavior.
- Live local health and target endpoints returned HTTP 200; all five target records resolved without resolver warnings. A live Barnard's Star QR3 search returned 144 real products, all selected products had unique IDs/access URLs.
- A new end-to-end Barnard's Star job used four actual QR3 SPHEREx-D2 FITS products from IRSA. The job completed with four frames and three completed comparisons; alignment had 1,044, 1,160 and 1,121 matches. PSF matching completed for all comparisons, empirical noise covariance was estimated, and difference/significance products were generated.
- All 38 unique frame-stretch, mask-overlay, difference and significance image URLs for that job returned HTTP 200. The processing result contained 3,090 candidate/residual records, 32 reviewable signals and 3,058 ambiguous/unclassified records.
- The new band/date filters were checked against live archive data: SPHEREx-D2 and 2026-08-18 returned three products; an inverted date range returned HTTP 422.
- Member 2 suite: 51 passed; API filter tests: 2 passed; frontend interaction tests: 8 passed. Frontend ESLint, Python syntax compilation and production build passed. `npm audit` reports zero vulnerabilities. Vite still warns that the optional, lazy-loaded 3D chunk is 922 kB (244 kB gzip); the main entry is 269 kB (80 kB gzip).
- Browser rendering was inspected. The computer-use tool exposed the page but rejected its accessibility click action, so a physical-browser click pass is not claimed. React interaction tests exercise search/filter/share URLs, timeline controls, image display/comparison, candidate filters/exports, metadata, no-coverage, processing-failure and one-frame states.

## Remaining limitations

- WISE 0855 has no usable QR2/QR3 products within the supported search area; its no-coverage state is the correct PRD behavior. It cannot show a real blink comparison until suitable archive observations exist.
- The PSF homogenization uses a field-center local second-moment approximation, and the short-range covariance adjustment is empirical/approximate. It is not a complete spatially varying PSF or full covariance model.
- Candidate labels are preliminary and require human science review. The app makes no confirmed-discovery claim.
- The 3D vendor chunk warning remains a performance concern, not a build or API error.

## Follow-up fix: partial archive footprints (2026-11-14)

- A later six-product real R Draconis D1 selection exposed an IRSA SIA edge case: a circle search can return products that intersect the requested field while their image footprint misses the requested target. Three products were 1, 7, and 24 pixels wide at the target's row; choosing the first as the reference had collapsed the common grid to 293×1 and blocked every comparison.
- The science pipeline now excludes frames whose WCS footprint does not contain the requested ICRS coordinate, picks the usable frame with the largest valid footprint, and centers a square common grid on the actual requested coordinates at the selected data's native pixel scale. Excluded products are recorded as input failures with a clear coverage reason, and successful processing with excluded inputs reports `partial`.
- Reprocessing those same archived FITS files (no synthetic data) produced a 292×292 requested-center grid, three target-covering frames, and two completed comparisons. Both passed astrometric alignment (317 and 114 matched background sources) and PSF matching; 788 preliminary candidate/residual records were generated. The three non-covering products were visibly recorded as skipped.
- The corrected live FastAPI path was rerun against IRSA for R Draconis: it selected six real D1 epochs across 50.4 days, returned a transparent `partial` result with three valid frames and two completed comparisons, and all 31 generated preview/stretch/mask/difference/significance media URLs returned HTTP 200.
- Regression tests cover target-footprint rejection and requested-center grid construction. Member 2 suite: 53 passed; API tests: 3 passed; frontend interaction tests: 8 passed.

## Run locally

See [backend/README.md](backend/README.md) for Python setup and API start command. Run the frontend with `cd spherex-frontend` then `npm run dev`.
