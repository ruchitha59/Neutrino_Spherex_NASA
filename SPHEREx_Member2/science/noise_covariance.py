"""Empirical short-range noise covariance for reprojected image cutouts."""
from __future__ import annotations

import numpy as np


def estimate_noise_correlation(image, valid_mask, max_lag_px=3,
                               min_pairs=128, clip_sigma=4.0):
    """Estimate a normalized autocorrelation kernel on masked blank sky.

    The returned kernel is symmetric and has a unit center. It captures local
    inter-pixel correlation in the supplied residual image, including the
    effects of resampling and subsequent convolution.
    """
    data = np.asarray(image, dtype=float)
    valid = np.asarray(valid_mask, dtype=bool) & np.isfinite(data)
    radius = int(max_lag_px)
    if data.ndim != 2 or valid.shape != data.shape or radius < 0:
        raise ValueError("Expected matching 2D image and mask arrays.")
    values = data[valid]
    kernel = np.zeros((2 * radius + 1, 2 * radius + 1), dtype=float)
    counts = np.zeros_like(kernel, dtype=np.int64)
    if values.size < int(min_pairs):
        return {"kernel": kernel, "sample_count": int(values.size),
                "available": False, "reason": "Too few blank-sky pixels."}
    median = float(np.median(values))
    sigma = float(1.4826 * np.median(np.abs(values - median)))
    if not np.isfinite(sigma) or sigma <= 0:
        sigma = float(np.std(values))
    if not np.isfinite(sigma) or sigma <= 0:
        return {"kernel": kernel, "sample_count": int(values.size),
                "available": False, "reason": "Blank-sky scatter is zero."}

    residual = np.clip(data - median, -float(clip_sigma) * sigma,
                       float(clip_sigma) * sigma)
    kernel[radius, radius] = 1.0
    counts[radius, radius] = int(values.size)
    height, width = data.shape
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dy < 0 or (dy == 0 and dx <= 0):
                continue
            y0, y1 = max(0, -dy), min(height, height - dy)
            x0, x1 = max(0, -dx), min(width, width - dx)
            first = (slice(y0, y1), slice(x0, x1))
            second = (slice(y0 + dy, y1 + dy), slice(x0 + dx, x1 + dx))
            pair_valid = valid[first] & valid[second]
            count = int(pair_valid.sum())
            counts[radius + dy, radius + dx] = count
            counts[radius - dy, radius - dx] = count
            if count < int(min_pairs):
                continue
            a = residual[first][pair_valid]
            b = residual[second][pair_valid]
            denom = float(np.sqrt(np.mean(a * a) * np.mean(b * b)))
            rho = float(np.mean(a * b) / denom) if denom > 0 else 0.0
            rho = float(np.clip(rho, -0.99, 0.99))
            kernel[radius + dy, radius + dx] = rho
            kernel[radius - dy, radius - dx] = rho
    return {
        "kernel": kernel,
        "sample_count": int(values.size),
        "pair_counts": counts,
        "sigma": sigma,
        "available": True,
        "method": "robust clipped blank-sky autocorrelation",
        "max_lag_px": radius,
    }


def covariance_factor_for_weights(weights, variance, correlation_kernel):
    """Return diagonal and covariance-aware variance for weighted flux sums."""
    weights = np.asarray(weights, dtype=float)
    variance = np.asarray(variance, dtype=float)
    rho = np.asarray(correlation_kernel, dtype=float)
    if weights.shape != variance.shape or weights.ndim != 2:
        raise ValueError("Weights and variance must be matching 2D arrays.")
    if rho.ndim != 2 or rho.shape[0] != rho.shape[1] or rho.shape[0] % 2 != 1:
        raise ValueError("Correlation kernel must be a square odd-sized array.")
    valid = np.isfinite(variance) & (variance >= 0) & np.isfinite(weights)
    w = np.where(valid, weights, 0.0)
    var = np.where(valid, variance, 0.0)
    diagonal = float(np.sum(w * w * var))
    total = diagonal
    center = rho.shape[0] // 2
    height, width = weights.shape
    for dy in range(0, center + 1):
        for dx in range(-center, center + 1):
            if dy == 0 and dx <= 0:
                continue
            corr = float(rho[center + dy, center + dx])
            if abs(corr) < 1e-12:
                continue
            y0, y1 = max(0, -dy), min(height, height - dy)
            x0, x1 = max(0, -dx), min(width, width - dx)
            first = (slice(y0, y1), slice(x0, x1))
            second = (slice(y0 + dy, y1 + dy), slice(x0 + dx, x1 + dx))
            pair_valid = valid[first] & valid[second]
            if not pair_valid.any():
                continue
            cross = (w[first] * w[second]
                     * np.sqrt(var[first] * var[second]))
            total += 2.0 * corr * float(np.sum(cross[pair_valid]))
    total = max(total, 0.0)
    factor = total / diagonal if diagonal > 0 else 1.0
    return {"diagonal_variance": diagonal,
            "covariance_variance": total,
            "correlation_factor": float(max(factor, 0.0))}


def component_correlation_factor(component_mask, correlation_kernel):
    """Approximate variance inflation of a connected component sum."""
    mask = np.asarray(component_mask, dtype=bool)
    rho = np.asarray(correlation_kernel, dtype=float)
    if mask.ndim != 2 or rho.ndim != 2 or rho.shape[0] != rho.shape[1] or rho.shape[0] % 2 != 1:
        raise ValueError("Expected a 2D component and odd square correlation kernel.")
    count = int(mask.sum())
    if count == 0:
        return 1.0
    center = rho.shape[0] // 2
    height, width = mask.shape
    factor = 1.0
    for dy in range(0, center + 1):
        for dx in range(-center, center + 1):
            if dy == 0 and dx <= 0:
                continue
            corr = float(rho[center + dy, center + dx])
            if abs(corr) < 1e-12:
                continue
            y0, y1 = max(0, -dy), min(height, height - dy)
            x0, x1 = max(0, -dx), min(width, width - dx)
            overlap = int(np.count_nonzero(
                mask[y0:y1, x0:x1] & mask[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
            ))
            factor += 2.0 * corr * overlap / count
    return float(max(factor, 1e-6))
