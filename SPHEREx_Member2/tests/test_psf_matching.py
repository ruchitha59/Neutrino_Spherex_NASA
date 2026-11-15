import numpy as np

from science.psf_matching import (
    convolve_to_common_psf,
    gaussian_matching_kernel,
    match_pair_psf,
)


def test_gaussian_matching_kernel_is_normalized_and_symmetric():
    kernel = gaussian_matching_kernel(np.array([[0.3, 0.05], [0.05, 0.2]]))
    assert kernel.shape[0] % 2 == 1
    assert kernel.shape[1] % 2 == 1
    assert np.isclose(kernel.sum(), 1.0)
    assert np.allclose(kernel, kernel[::-1, ::-1])


def test_psf_matching_broadens_image_and_propagates_variance_and_mask():
    yy, xx = np.mgrid[:41, :41]
    image = np.exp(-((xx - 20) ** 2 + (yy - 20) ** 2) / (2 * 1.1 ** 2))
    variance = np.ones_like(image)
    valid = np.ones_like(image, dtype=bool)
    flags = np.zeros_like(image, dtype=np.int32)
    flags[20, 22] = 4
    kernel = gaussian_matching_kernel(np.eye(2) * 0.36)

    result = convolve_to_common_psf(image, variance, flags, valid, kernel)

    assert result["image"].shape == image.shape
    assert result["variance"].shape == image.shape
    assert result["valid_mask"][20, 20]
    assert not result["valid_mask"][0, 0]
    assert result["variance"][20, 20] < variance[20, 20]
    assert result["flags"][20, 20] & 4
    assert np.nanmax(result["image"]) < np.max(image)


def test_pair_matching_uses_no_deconvolution_and_one_common_target():
    image = np.zeros((25, 25), dtype=float)
    image[12, 12] = 1.0
    variance = np.ones_like(image)
    flags = np.zeros_like(image, dtype=np.int32)
    valid = np.ones_like(image, dtype=bool)
    result = match_pair_psf(
        image, image, variance, variance, flags, flags, valid, valid,
        np.eye(2) * 0.2, np.eye(2) * 0.4,
    )
    assert np.allclose(result["target_covariance_px2"],
                       np.eye(2) * (0.4 * 1.05 + 0.01))
    assert result["reference"]["kernel_shape"] != [1, 1]
    assert result["comparison"]["kernel_shape"] != [1, 1]
    assert np.prod(result["reference"]["kernel_shape"]) > np.prod(
        result["comparison"]["kernel_shape"]
    )


def test_gaussian_matching_refuses_deconvolution():
    try:
        gaussian_matching_kernel(np.diag([-0.1, 0.2]))
    except ValueError as exc:
        assert "deconvolution is refused" in str(exc)
    else:
        raise AssertionError("A sharper target PSF must not be deconvolved.")
