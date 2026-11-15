import numpy as np
from science.quality import build_valid_mask, flag_definitions_from_header


def test_mask_excludes_nonfinite_and_documented_flags():
    science = np.array([[1.0, np.nan], [3.0, 4.0]])
    flags = np.array([[0, 0], [1, 64]], dtype=np.int32)
    defs = {
        "TRANSIENT": {"mask": 1, "description": "transient"},
        "NONFUNC": {"mask": 64, "description": "dead"},
    }
    mask, counts = build_valid_mask(science, flags, flag_definitions=defs)
    assert mask.tolist() == [[True, False], [False, False]]
    assert counts["non_finite_science"] == 1
    assert counts["flag_TRANSIENT"] == 1
    assert counts["flag_NONFUNC"] == 1


def test_variance_and_coverage_are_checked():
    science = np.ones((2, 2))
    variance = np.array([[1.0, -1.0], [np.nan, 2.0]])
    footprint = np.array([[1.0, 1.0], [0.0, 1.0]])
    mask, counts = build_valid_mask(science, variance=variance, footprint=footprint)
    assert mask.tolist() == [[True, False], [False, True]]
    assert counts["invalid_variance"] == 2
    assert counts["uncovered"] == 1


def test_flags_header_parser_uses_header_masks_not_guessed_positions():
    header = {
        "MSKN0000": "TRANSIENT", "MSKM0000": 1, "MSKD0000": "transient hit",
        "MSKN0025": "STREAK", "MSKM0025": 33554432, "MSKD0025": "streak artifact",
    }
    result = flag_definitions_from_header(header)
    assert result["TRANSIENT"]["mask"] == 1
    assert result["STREAK"]["mask"] == 33554432


def test_mp_flag_header_uses_bit_positions():
    header = {
        "MP_TRANSIENT": 0,
        "MP_SUR_ERROR": 2,
        "MP_OUTLIER": 19,
        "MP_SOURCE": 21,
    }

    definitions = flag_definitions_from_header(header)

    assert definitions["TRANSIENT"]["mask"] == 1
    assert definitions["SUR_ERROR"]["mask"] == 4
    assert definitions["OUTLIER"]["mask"] == 524288
    assert definitions["SOURCE"]["mask"] == 2097152

    science = np.ones((1, 4))
    flags = np.array(
        [[0, 1, 524288, 2097152]],
        dtype=np.int32,
    )

    mask, counts = build_valid_mask(
        science,
        flags,
        flag_definitions=definitions,
    )

    assert mask.tolist() == [[True, False, False, True]]
    assert counts["flag_TRANSIENT"] == 1
    assert counts["flag_OUTLIER"] == 1
