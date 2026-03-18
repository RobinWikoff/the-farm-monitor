import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


class _MockResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _sample_temp_df():
    return pd.DataFrame(
        {
            "Hour": [0, 1, 2, 3],
            "Temperature": [60.0, 61.2, 63.8, 62.5],
        }
    )


def test_get_temp_trend_happy_path_delta_and_label():
    df = _sample_temp_df()

    delta, since_label = app.get_temp_trend(df=df, live_temp=65.1, current_hour=2)

    assert delta == 3.9
    assert since_label == "since 01:00"


def test_get_temp_trend_midnight_returns_none_tuple():
    df = _sample_temp_df()

    result = app.get_temp_trend(df=df, live_temp=60.0, current_hour=0)

    assert result == (None, None)


def test_get_temp_trend_missing_prior_hour_returns_none_tuple():
    df = pd.DataFrame({"Hour": [0, 2, 3], "Temperature": [60.0, 63.8, 62.5]})

    result = app.get_temp_trend(df=df, live_temp=65.1, current_hour=2)

    assert result == (None, None)


def test_fetch_forecast_and_current_keeps_hours_when_wdir_missing(monkeypatch):
    payload = {
        "days": [
            {
                "hours": [
                    {
                        "datetime": "00:00:00",
                        "temp": 30.0,
                        "feelslike": 28.0,
                        "windspeed": 5.0,
                    },
                    {
                        "datetime": "01:00:00",
                        "temp": 31.0,
                        "feelslike": 29.0,
                        "windspeed": 6.0,
                    },
                ]
            }
        ],
        "currentConditions": {
            "temp": 32.0,
            "feelslike": 30.0,
            "windspeed": 7.0,
        },
    }

    def fake_get(url, params, timeout):
        return _MockResponse(payload)

    monkeypatch.setattr(app.requests, "get", fake_get)

    forecast_df, live_temp = app.fetch_forecast_and_current.__wrapped__("fake-key")

    assert len(forecast_df) == 2
    assert forecast_df["Hour"].tolist() == [0, 1]
    assert forecast_df["WindDir"].tolist() == ["Unknown", "Unknown"]
    assert live_temp["Actual"] == 32.0
    assert live_temp["WindDir"] == "Unknown"


def test_fetch_historical_band_leap_year_fallback_and_aggregation(monkeypatch):
    called_urls = []

    def fake_get(url, params, timeout):
        called_urls.append(url)
        payload = {
            "days": [
                {
                    "hours": [
                        {
                            "datetime": "00:00:00",
                            "temp": 30.0,
                            "feelslike": 28.0,
                            "windspeed": 5.0,
                        },
                        {
                            "datetime": "01:00:00",
                            "temp": 31.0,
                            "feelslike": 29.0,
                            "windspeed": 6.0,
                        },
                    ]
                }
            ]
        }
        return _MockResponse(payload)

    monkeypatch.setattr(app, "HISTORY_YEARS", 2)
    monkeypatch.setattr(app.requests, "get", fake_get)

    band = app.fetch_historical_band.__wrapped__("2024-02-29", "fake-key")

    # 2024-02-29 falls back to 2023-02-28 and 2022-02-28 (both non-leap years)
    assert any("/2023-02-28/2023-02-28" in url for url in called_urls)
    assert any("/2022-02-28/2022-02-28" in url for url in called_urls)

    assert sorted(band["Hour"].tolist()) == [0, 1]
    assert list(band.columns) == [
        "Hour",
        "ActualHigh",
        "ActualLow",
        "ActualMean",
        "FeelsLikeHigh",
        "FeelsLikeLow",
        "FeelsLikeMean",
        "WindSpeedHigh",
        "WindSpeedLow",
        "WindSpeedMean",
    ]


def test_fetch_historical_band_empty_response_returns_expected_empty_schema(
    monkeypatch,
):
    def fake_get(url, params, timeout):
        return _MockResponse({"days": []})

    monkeypatch.setattr(app, "HISTORY_YEARS", 2)
    monkeypatch.setattr(app.requests, "get", fake_get)

    band = app.fetch_historical_band.__wrapped__("2024-03-10", "fake-key")

    assert band.empty
    assert list(band.columns) == [
        "Hour",
        "ActualHigh",
        "ActualLow",
        "ActualMean",
        "FeelsLikeHigh",
        "FeelsLikeLow",
        "FeelsLikeMean",
    ]


def test_fetch_historical_band_partial_failure_still_aggregates(monkeypatch):
    def fake_get(url, params, timeout):
        if "/2022-03-10/2022-03-10" in url:
            raise app.requests.RequestException("rate limited")
        return _MockResponse(
            {
                "days": [
                    {
                        "hours": [
                            {
                                "datetime": "00:00:00",
                                "temp": 30.0,
                                "feelslike": 28.0,
                                "windspeed": 5.0,
                            },
                            {
                                "datetime": "01:00:00",
                                "temp": 32.0,
                                "feelslike": 30.0,
                                "windspeed": 7.0,
                            },
                        ]
                    }
                ]
            }
        )

    monkeypatch.setattr(app, "HISTORY_YEARS", 3)
    monkeypatch.setattr(app.requests, "get", fake_get)

    band = app.fetch_historical_band.__wrapped__("2025-03-10", "fake-key")

    assert not band.empty
    assert sorted(band["Hour"].tolist()) == [0, 1]
    row_h0 = band[band["Hour"] == 0].iloc[0]
    assert row_h0["ActualMean"] == 30.0
    assert row_h0["FeelsLikeMean"] == 28.0
    assert row_h0["WindSpeedMean"] == 5.0


def test_fetch_historical_band_stops_after_first_429(monkeypatch):
    call_count = 0

    def fake_get(url, params, timeout):
        nonlocal call_count
        call_count += 1
        error = app.requests.HTTPError("429 Client Error")
        error.response = type("Response", (), {"status_code": 429})()
        raise error

    monkeypatch.setattr(app, "HISTORY_YEARS", 5)
    monkeypatch.setattr(app.requests, "get", fake_get)

    band = app.fetch_historical_band.__wrapped__("2025-03-16", "fake-key")

    assert band.empty
    assert call_count == 1


def test_build_chart_layers_without_hist_band():
    df = pd.DataFrame(
        {
            "Hour": list(range(24)),
            "Temperature": [50 + (h * 0.5) for h in range(24)],
        }
    )

    chart = app.build_chart(
        df=df, live_temp=64.2, threshold=65.0, current_hour=12, hist_band=pd.DataFrame()
    )
    spec = chart.to_dict()

    assert "layer" in spec
    assert len(spec["layer"]) == 4


def test_build_chart_layers_with_hist_band():
    df = pd.DataFrame(
        {
            "Hour": list(range(24)),
            "Temperature": [50 + (h * 0.5) for h in range(24)],
        }
    )
    hist_band = pd.DataFrame(
        {
            "Hour": list(range(24)),
            "HistHigh": [60 + (h * 0.3) for h in range(24)],
            "HistLow": [45 + (h * 0.2) for h in range(24)],
            "HistMean": [52 + (h * 0.25) for h in range(24)],
        }
    )

    chart = app.build_chart(
        df=df, live_temp=64.2, threshold=65.0, current_hour=12, hist_band=hist_band
    )
    spec = chart.to_dict()

    assert "layer" in spec
    assert len(spec["layer"]) == 6


def test_build_chart_serialized_spec_has_live_override_for_current_hour():
    df = pd.DataFrame(
        {
            "Hour": list(range(24)),
            "Temperature": [50 + (h * 0.5) for h in range(24)],
        }
    )

    current_hour = 12
    live_temp = 64.2
    chart = app.build_chart(
        df=df,
        live_temp=live_temp,
        threshold=65.0,
        current_hour=current_hour,
        hist_band=pd.DataFrame(),
    )
    spec = chart.to_dict()

    datasets = spec.get("datasets", {})
    all_rows = []
    for rows in datasets.values():
        all_rows.extend(rows)

    assert any(
        row.get("Hour") == current_hour
        and row.get("Status") == "Actual"
        and row.get("Temperature") == live_temp
        for row in all_rows
    )


@pytest.mark.parametrize(
    "live_temp, threshold, forecast_future, mode, expected_call",
    [
        (
            66.0,
            65.0,
            pd.DataFrame({"Hour": [10], "Temperature": [66.0]}),
            "Winter (Warming Focus)",
            "success",
        ),
        (
            62.0,
            65.0,
            pd.DataFrame({"Hour": [12, 13], "Temperature": [64.0, 65.0]}),
            "Winter (Warming Focus)",
            "info",
        ),
        (
            62.0,
            65.0,
            pd.DataFrame({"Hour": [12, 13], "Temperature": [64.0, 64.5]}),
            "Winter (Warming Focus)",
            "warning",
        ),
        (
            68.0,
            70.0,
            pd.DataFrame({"Hour": [10], "Temperature": [68.0]}),
            "Summer (Cooling Focus)",
            "success",
        ),
        (
            73.0,
            70.0,
            pd.DataFrame({"Hour": [12, 13], "Temperature": [72.0, 70.0]}),
            "Summer (Cooling Focus)",
            "info",
        ),
        (
            73.0,
            70.0,
            pd.DataFrame({"Hour": [12, 13], "Temperature": [72.0, 71.0]}),
            "Summer (Cooling Focus)",
            "warning",
        ),
    ],
)
def test_render_status_banner_all_threshold_paths(
    monkeypatch, live_temp, threshold, forecast_future, mode, expected_call
):
    called = {"success": 0, "info": 0, "warning": 0}

    monkeypatch.setattr(
        app.st,
        "success",
        lambda msg: called.__setitem__("success", called["success"] + 1),
    )
    monkeypatch.setattr(app.st, "info", lambda msg: called.__setitem__("info", called["info"] + 1))
    monkeypatch.setattr(
        app.st,
        "warning",
        lambda msg: called.__setitem__("warning", called["warning"] + 1),
    )

    app.render_status_banner(
        live_temp=live_temp,
        threshold=threshold,
        forecast_future=forecast_future,
        mode=mode,
    )

    assert called[expected_call] == 1
    for name, count in called.items():
        if name != expected_call:
            assert count == 0


def test_render_status_banner_winter_info_uses_first_qualifying_forecast_hour_in_text(
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(app.st, "success", lambda msg: None)
    monkeypatch.setattr(app.st, "warning", lambda msg: None)
    monkeypatch.setattr(app.st, "info", lambda msg: captured.setdefault("msg", msg))

    forecast_future = pd.DataFrame(
        {
            "Hour": [11, 12, 13],
            "Temperature": [64.9, 65.0, 67.0],
        }
    )

    app.render_status_banner(
        live_temp=62.0,
        threshold=65.0,
        forecast_future=forecast_future,
        mode="Winter (Warming Focus)",
    )

    assert "by 12:00" in captured["msg"]


def test_render_status_banner_summer_info_uses_first_qualifying_forecast_hour_in_text(
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(app.st, "success", lambda msg: None)
    monkeypatch.setattr(app.st, "warning", lambda msg: None)
    monkeypatch.setattr(app.st, "info", lambda msg: captured.setdefault("msg", msg))

    forecast_future = pd.DataFrame(
        {
            "Hour": [14, 15, 16],
            "Temperature": [72.0, 70.0, 68.0],
        }
    )

    app.render_status_banner(
        live_temp=73.0,
        threshold=70.0,
        forecast_future=forecast_future,
        mode="Summer (Cooling Focus)",
    )

    assert "by 15:00" in captured["msg"]
