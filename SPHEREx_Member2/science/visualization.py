"""Consistent-stretch scientific previews."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def shared_limits(arrays, lower_percentile=1.0, upper_percentile=99.5):
    samples = []
    for array in arrays:
        data = np.asarray(array, dtype=float)
        finite = data[np.isfinite(data)]
        if finite.size:
            samples.append(finite)
    if not samples:
        return 0.0, 1.0
    combined = np.concatenate(samples)
    lo, hi = np.percentile(combined, [lower_percentile, upper_percentile])
    if not np.isfinite(lo) or not np.isfinite(hi) or lo == hi:
        lo, hi = float(np.nanmin(combined)), float(np.nanmax(combined) + 1e-12)
    return float(lo), float(hi)


def save_preview(data, output_path, title, unit=None, vmin=None, vmax=None,
                 cmap="gray", mask=None, stretch="linear",
                 overlay_invalid=False):
    data = np.asarray(data, dtype=float)
    shown = data.copy()
    if mask is not None:
        shown[~np.asarray(mask, dtype=bool)] = np.nan
    if vmin is None or vmax is None:
        vmin, vmax = shared_limits([shown])
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 5), constrained_layout=True)
    if stretch not in {"linear", "log", "sqrt", "asinh"}:
        raise ValueError(f"Unsupported image stretch: {stretch}")
    from astropy.visualization import (
        AsinhStretch, ImageNormalize, LinearStretch, LogStretch, SqrtStretch,
    )
    stretches = {
        "linear": LinearStretch,
        "log": LogStretch,
        "sqrt": SqrtStretch,
        "asinh": AsinhStretch,
    }
    norm = ImageNormalize(
        vmin=vmin, vmax=vmax, stretch=stretches[stretch](), clip=True
    )
    image = ax.imshow(shown, origin="lower", cmap=cmap, norm=norm)
    if overlay_invalid and mask is not None:
        from matplotlib.colors import ListedColormap
        invalid = np.ma.masked_where(
            np.asarray(mask, dtype=bool), np.ones(data.shape, dtype=float)
        )
        overlay_cmap = ListedColormap([(1.0, 0.12, 0.16, 0.58)])
        overlay_cmap.set_bad((0.0, 0.0, 0.0, 0.0))
        ax.imshow(invalid, origin="lower", cmap=overlay_cmap, vmin=0, vmax=1,
                  interpolation="nearest")
    fig.colorbar(image, ax=ax, label=unit or "science value")
    ax.set_title(title)
    ax.set_xlabel("Pixel X")
    ax.set_ylabel("Pixel Y")
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return str(output_path)
