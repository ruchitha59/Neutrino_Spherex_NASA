import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as api  # noqa: E402


PRODUCTS = [
    {"observation_id": "d2-aug18", "band": "SPHEREx-D2", "obs_time": "2026-08-18T20:48:38Z"},
    {"observation_id": "d2-aug19", "band": "SPHEREx-D2", "obs_time": "2026-08-19T08:12:34Z"},
    {"observation_id": "d3-aug18", "band": "SPHEREx-D3", "obs_time": "2026-08-18T20:48:38Z"},
]


def test_search_filters_by_band_and_inclusive_date_range(monkeypatch):
    def fake_query(_collection, request):
        return [item for item in PRODUCTS if not request.band or item["band"] == request.band]

    monkeypatch.setattr(api, "_query", fake_query)
    request = api.SearchRequest(
        ra=10,
        dec=2,
        fov=0.5,
        band="SPHEREx-D2",
        date_start=date(2026, 8, 18),
        date_end=date(2026, 8, 18),
    )

    result = api.search(request)

    assert result["count"] == 1
    assert result["observations"][0]["observation_id"] == "d2-aug18"
    assert result["observations"][0]["band"] == "SPHEREx-D2"
    assert result["recommended_observation_ids"] == ["d2-aug18"]


def test_temporal_selection_prefers_more_distinct_dates_and_spreads_the_baseline():
    observations = [
        {"observation_id": f"d2-aug18-{index}", "band": "SPHEREx-D2", "obs_time": f"2026-08-18T20:{index:02}:00Z"}
        for index in range(10)
    ]
    dates = ["2026-08-01", "2026-08-08", "2026-08-15", "2026-08-22", "2026-08-29", "2026-09-05", "2026-09-12", "2026-09-19"]
    observations.extend(
        {"observation_id": f"d3-{day}", "band": "SPHEREx-D3", "obs_time": f"{day}T12:00:00Z"}
        for day in dates
    )

    selected = api.select_time_spread_observations(observations, limit=6)

    assert len(selected) == 6
    assert {item["band"] for item in selected} == {"SPHEREx-D3"}
    selected_dates = [item["obs_time"][:10] for item in selected]
    assert selected_dates == sorted(selected_dates)
    assert len(set(selected_dates)) == 6
    assert selected_dates[0] == dates[0]
    assert selected_dates[-1] == dates[-1]


def test_search_rejects_inverted_date_range_before_archive_request(monkeypatch):
    def unexpected_query(*_args):
        pytest.fail("Archive should not be queried for an inverted date range")

    monkeypatch.setattr(api, "_query", unexpected_query)
    request = api.SearchRequest(
        ra=10,
        dec=2,
        fov=0.5,
        date_start=date(2026, 8, 20),
        date_end=date(2026, 8, 18),
    )

    with pytest.raises(HTTPException) as error:
        api.search(request)

    assert error.value.status_code == 422
