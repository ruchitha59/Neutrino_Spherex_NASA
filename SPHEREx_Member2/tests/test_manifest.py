import json
from pathlib import Path

from science.validate_manifest import validate_manifest


def test_manifest_resolves_windows_paths_and_reports_missing(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "present.fits").write_bytes(b"placeholder")
    manifest = {
        "project": "test",
        "observations": [
            {
                "product_id": "obs1", "collection": "spherex_qr3",
                "infrared_band": "SPHEREx-D3",
                "observation_start_utc": "2026-01-01T00:00:00",
                "access_url": "https://example.org/real.fits",
                "local_file_path": "cutouts\\present.fits",
                "requested_center": {"ra_deg": 12.0, "dec_deg": -3.0},
            },
            {
                "product_id": "obs2", "collection": "spherex_qr3",
                "infrared_band": "SPHEREx-D3",
                "observation_start_utc": "2026-01-02T00:00:00",
                "access_url": "https://example.org/missing.fits",
                "local_file_path": "cutouts\\missing.fits",
                "requested_center": {"ra_deg": 12.0, "dec_deg": -3.0},
            },
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = validate_manifest(path)
    assert result["observation_count"] == 2
    assert result["valid_record_count"] == 1
    assert result["records"][0]["file_exists"] is True
    assert result["records"][1]["file_exists"] is False
