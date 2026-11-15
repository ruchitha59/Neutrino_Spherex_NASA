from science.calibration import evaluate_compatibility


def meta(collection="spherex_qr3", band="SPHEREx-D3", bunit="MJy / sr"):
    return {
        "collection": collection, "band": band, "bunit": bunit,
        "wavelength_min_um": "1.6301", "wavelength_max_um": "2.4346",
        "finast": 0,
    }


def test_same_release_band_and_units_are_compatible():
    assert evaluate_compatibility(meta(), meta())["compatible"] is True


def test_different_band_is_blocked():
    result = evaluate_compatibility(meta(), meta(band="SPHEREx-D6"))
    assert result["compatible"] is False
    assert any("band" in reason.lower() for reason in result["reasons"])


def test_different_release_is_blocked():
    assert evaluate_compatibility(meta(), meta(collection="spherex_qr2"))["compatible"] is False
