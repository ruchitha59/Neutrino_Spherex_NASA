"""PSF homogenization for aligned SPHEREx image cutouts."""
from __future__ import annotations

import numpy as np
from scipy.signal import convolve2d

from science.psf import epsf_diagnostics, select_epsf_model, select_psf_model


def _model_for_position(spatial_psf, x, y):
    if spatial_psf is None:
        raise ValueError("A spatial PSF model is required for matching.")
    grid = spatial_psf["grid"]
    selected = (
        select_epsf_model(grid, x, y)
        if spatial_psf["type"] == "EPSF"
        else select_psf_model(grid, x, y)
    )
    if not selected["within_grid_coverage"]:
        raise ValueError("The requested field center is outside PSF model coverage.")
    return selected


def _psf_pixel_covariance(psf_model):
    model = np.asarray(psf_model["epsf"], dtype=float)
    weights = np.clip(model, 0.0, None)
    total = float(weights.sum())
    if model.ndim != 2 or not np.isfinite(total) or total <= 0:
        raise ValueError("PSF model has no finite positive weight.")
    yy, xx = np.indices(model.shape, dtype=float)
    cx = float(np.sum(weights * xx) / total)
    cy = float(np.sum(weights * yy) / total)
    ox = float(psf_model["oversampling_x"])
    oy = float(psf_model["oversampling_y"])
    dx = (xx - cx) / ox
    dy = (yy - cy) / oy
    covariance = np.array([
        [np.sum(weights * dx * dx) / total,
         np.sum(weights * dx * dy) / total],
        [np.sum(weights * dx * dy) / total,
         np.sum(weights * dy * dy) / total],
    ], dtype=float)
    if not np.all(np.isfinite(covariance)):
        raise ValueError("PSF model covariance is not finite.")
    return covariance


def _pixel_jacobian_to_reference(input_wcs, reference_wcs, x, y):
    """Map small input-pixel displacements to reference-grid pixels."""
    columns = []
    step = 0.5
    for dx, dy in ((step, 0.0), (0.0, step)):
        ra_p, dec_p = input_wcs.pixel_to_world_values(x + dx, y + dy)
        ra_m, dec_m = input_wcs.pixel_to_world_values(x - dx, y - dy)
        xp, yp = reference_wcs.world_to_pixel_values(ra_p, dec_p)
        xm, ym = reference_wcs.world_to_pixel_values(ra_m, dec_m)
        columns.append(np.array([(xp - xm) / (2 * step),
                                 (yp - ym) / (2 * step)], dtype=float))
    jacobian = np.column_stack(columns)
    if not np.all(np.isfinite(jacobian)) or abs(np.linalg.det(jacobian)) < 1e-8:
        raise ValueError("Could not transform PSF covariance to the reference grid.")
    return jacobian


def measure_psf_covariance(spatial_psf, input_wcs, reference_wcs,
                           center_ra_deg, center_dec_deg):
    """Measure the local PSF covariance in reference-grid pixel units."""
    x, y = input_wcs.world_to_pixel_values(float(center_ra_deg),
                                           float(center_dec_deg))
    if not np.isfinite(x) or not np.isfinite(y):
        raise ValueError("Requested center does not map to a valid input pixel.")
    selected = _model_for_position(spatial_psf, x, y)
    covariance_input = _psf_pixel_covariance(selected)
    jacobian = _pixel_jacobian_to_reference(input_wcs, reference_wcs, x, y)
    covariance_reference = jacobian @ covariance_input @ jacobian.T
    eigenvalues = np.linalg.eigvalsh(covariance_reference)
    if np.min(eigenvalues) <= 0 or not np.all(np.isfinite(eigenvalues)):
        raise ValueError("Measured PSF covariance is not positive definite.")
    diagnostics = epsf_diagnostics(selected)
    fwhm_factor = 2.0 * np.sqrt(2.0 * np.log(2.0))
    return {
        "covariance_px2": covariance_reference,
        "fwhm_reference_px": (
            fwhm_factor * np.sqrt(eigenvalues[::-1])
        ).tolist(),
        "selected_model": selected,
        "diagnostics": diagnostics,
        "input_pixel": [float(x), float(y)],
    }


def gaussian_matching_kernel(covariance_difference, truncate=4.0):
    """Create a normalized sampled Gaussian kernel from a covariance matrix."""
    covariance = np.asarray(covariance_difference, dtype=float)
    if covariance.shape != (2, 2) or not np.all(np.isfinite(covariance)):
        raise ValueError("Kernel covariance must be a finite 2x2 matrix.")
    covariance = (covariance + covariance.T) / 2
    eigenvalues = np.linalg.eigvalsh(covariance)
    if float(np.min(eigenvalues)) < -1e-8:
        raise ValueError("Target PSF is sharper than an input PSF; deconvolution is refused.")
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    eigenvalues = np.maximum(eigenvalues, 0.0)
    if float(np.max(eigenvalues)) < 1e-8:
        return np.ones((1, 1), dtype=float)
    covariance = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
    radius = max(1, int(np.ceil(float(truncate) * np.sqrt(float(np.max(eigenvalues))))))
    yy, xx = np.mgrid[-radius:radius + 1, -radius:radius + 1]
    coords = np.stack([xx, yy], axis=-1)
    inverse = np.linalg.pinv(covariance, rcond=1e-12)
    exponent = np.einsum("...i,ij,...j->...", coords, inverse, coords)
    kernel = np.exp(-0.5 * exponent)
    kernel[exponent > float(truncate) ** 2] = 0.0
    total = float(kernel.sum())
    if not np.isfinite(total) or total <= 0:
        raise ValueError("PSF matching kernel has no positive support.")
    return kernel / total


def convolve_to_common_psf(image, variance, flags, valid_mask, kernel):
    """Convolve an image and propagate its marginal variance and quality mask."""
    data = np.asarray(image, dtype=float)
    valid = np.asarray(valid_mask, dtype=bool) & np.isfinite(data)
    kernel = np.asarray(kernel, dtype=float)
    if data.ndim != 2 or valid.shape != data.shape:
        raise ValueError("Image and PSF validity mask must be matching 2D arrays.")
    if kernel.ndim != 2 or not np.all(np.isfinite(kernel)):
        raise ValueError("PSF matching kernel must be a finite 2D array.")
    denominator = convolve2d(valid.astype(float), kernel, mode="same", boundary="fill")
    numerator = convolve2d(np.where(valid, data, 0.0), kernel,
                           mode="same", boundary="fill")
    matched = np.full(data.shape, np.nan, dtype=float)
    good = denominator >= 1.0 - 1e-6
    matched[good] = numerator[good] / denominator[good]

    matched_variance = None
    if variance is not None:
        var = np.asarray(variance, dtype=float)
        if var.shape != data.shape:
            raise ValueError("Variance and image shapes must match.")
        var_valid = valid & np.isfinite(var) & (var >= 0)
        var_denominator = convolve2d(var_valid.astype(float), kernel,
                                     mode="same", boundary="fill")
        var_numerator = convolve2d(np.where(var_valid, var, 0.0), kernel ** 2,
                                   mode="same", boundary="fill")
        variance_good = good & (var_denominator >= 1.0 - 1e-6)
        matched_variance = np.full(data.shape, np.nan, dtype=float)
        matched_variance[variance_good] = (
            var_numerator[variance_good] / denominator[variance_good] ** 2
        )
        good &= variance_good
        matched[~good] = np.nan

    matched_flags = None
    if flags is not None:
        flag_array = np.asarray(flags)
        if flag_array.shape != data.shape:
            raise ValueError("FLAGS and image shapes must match.")
        matched_flags = np.zeros(flag_array.shape, dtype=flag_array.dtype)
        support = (kernel > max(float(kernel.max()) * 1e-6, 1e-12)).astype(float)
        integer_flags = flag_array.astype(np.int64, copy=False)
        for bit_position in range(63):
            bit = 1 << bit_position
            if not np.any(integer_flags & bit):
                continue
            touched = convolve2d(((integer_flags & bit) != 0).astype(float),
                                 support, mode="same", boundary="fill") > 0
            matched_flags[touched] |= bit

    return {
        "image": matched,
        "variance": matched_variance,
        "flags": matched_flags,
        "valid_mask": good,
        "kernel_shape": [int(v) for v in kernel.shape],
        "kernel_sum": float(kernel.sum()),
    }


def match_pair_psf(reference, comparison, reference_variance,
                   comparison_variance, reference_flags, comparison_flags,
                   reference_mask, comparison_mask,
                   reference_covariance, comparison_covariance,
                   safety_fraction=0.05, minimum_padding_px2=0.01):
    """Match a pair to a common circular Gaussian no sharper than either PSF."""
    covariances = [np.asarray(reference_covariance, dtype=float),
                   np.asarray(comparison_covariance, dtype=float)]
    broadest = max(float(np.max(np.linalg.eigvalsh(c))) for c in covariances)
    target_variance = broadest * (1.0 + float(safety_fraction)) + float(minimum_padding_px2)
    target = np.eye(2, dtype=float) * target_variance
    outputs = []
    for image, variance, flags, mask, covariance in zip(
        (reference, comparison),
        (reference_variance, comparison_variance),
        (reference_flags, comparison_flags),
        (reference_mask, comparison_mask),
        covariances,
    ):
        kernel_covariance = target - covariance
        kernel = gaussian_matching_kernel(kernel_covariance)
        outputs.append(convolve_to_common_psf(image, variance, flags, mask, kernel))
    return {
        "reference": outputs[0],
        "comparison": outputs[1],
        "target_covariance_px2": target,
        "reference_kernel_shape": outputs[0]["kernel_shape"],
        "comparison_kernel_shape": outputs[1]["kernel_shape"],
        "method": "local EPSF/PSF moment matching with normalized Gaussian convolution",
        "safety_fraction": float(safety_fraction),
        "minimum_padding_px2": float(minimum_padding_px2),
    }
