# Member 2 Presentation Script (2–3 minutes)

“My responsibility is the astronomical image-processing and detection part of SPHEREx Explorer. Member 1 supplies the archive manifest and FITS cutouts. My job is to make sure two images are scientifically comparable before we subtract them.

First, I inspect every FITS extension. In our supplied cutouts, the science image is the HDU named IMAGE, not the empty primary HDU. The other layers include FLAGS, VARIANCE, ZODI, EPSF and WCS-WAVE.

Next, I build a quality mask. This removes invalid pixels and pixels flagged by the instrument pipeline. I keep the reasons for exclusion instead of replacing bad pixels with zero.

Then I check compatibility. We cannot subtract different spectral bands or silently mix releases. The images must use the same band, release and units. I reproject compatible observations to a common ICRS sky grid and check stable background sources. Importantly, I align the background sky, not the moving target.

Only if the quality and alignment checks pass do I create a difference image. Positive residuals mean the comparison image is brighter; negative residuals mean it is fainter. A significance map is generated only when valid variance information is available.

Finally, the pipeline produces candidate records with coordinates, epoch information, measurements, quality flags and scientific caveats. These are possible changes, not confirmed discoveries.

For our current handoff, 30 QR3 FITS cutouts are present, covering the Barnard’s Star and Epsilon Indi B fields. Sixteen QR2 manifest entries have no local FITS file, and the other three PRD targets are not represented in this handoff. Real-data alignment and difference products still need to be run in the fully installed Python environment.”
