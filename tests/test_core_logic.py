import sys
from datetime import datetime, timedelta
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


def test_resolve_runtime_config_dev_safe_forces_sample_when_live_not_explicitly_allowed():
    cfg = app.resolve_runtime_config(
        secrets={},
        environ={"ENV": "dev", "DEV_USE_SAMPLE_DATA": "false"},
    )

    assert cfg["profile"] == "dev-safe"
    assert cfg["effective_data_mode"] == "sample"
    assert cfg["live_api_enabled"] is False


def test_resolve_runtime_config_dev_live_allows_live_when_explicitly_opted_in():
    cfg = app.resolve_runtime_config(
        secrets={},
        environ={
            "ENV": "dev",
            "DEV_ALLOW_LIVE_API": "true",
            "DEV_USE_SAMPLE_DATA": "false",
        },
    )

    assert cfg["profile"] == "dev-live"
    assert cfg["effective_data_mode"] == "live"
    assert cfg["live_api_enabled"] is True


def test_resolve_runtime_config_prod_uses_live_mode():
    cfg = app.resolve_runtime_config(
        secrets={},
        environ={"ENV": "prod", "DEV_USE_SAMPLE_DATA": "true"},
    )

    assert cfg["profile"] == "prod"
    assert cfg["effective_data_mode"] == "live"
    assert cfg["live_api_enabled"] is True


def test_check_and_record_dev_api_request_increments_usage_and_blocks_at_cap(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runtime = app.resolve_runtime_config(
        secrets={},
        environ={
            "ENV": "dev",
            "DEV_ALLOW_LIVE_API": "true",
            "DEV_USE_SAMPLE_DATA": "false",
            "DEV_BUDGET_VC_FORECAST": "2",
        },
    )
    now = app.LOCAL_TZ.localize(datetime(2026, 3, 20, 9, 0, 0))
    environ = {
        "ENV": "dev",
        "DEV_ALLOW_LIVE_API": "true",
        "DEV_USE_SAMPLE_DATA": "false",
        "DEV_BUDGET_VC_FORECAST": "2",
    }

    assert app.check_and_record_dev_api_request(
        "visual_crossing_forecast", runtime=runtime, now=now, environ=environ
    ) == (True, None)
    assert app.check_and_record_dev_api_request(
        "visual_crossing_forecast", runtime=runtime, now=now, environ=environ
    ) == (True, None)

    allowed, reason = app.check_and_record_dev_api_request(
        "visual_crossing_forecast", runtime=runtime, now=now, environ=environ
    )
    assert allowed is False
    assert "budget exhausted" in reason

    snapshot = app.get_dev_guardrail_snapshot(runtime=runtime, now=now, environ=environ)
    vc_item = next(item for item in snapshot["items"] if item["key"] == "visual_crossing_forecast")
    assert vc_item["used"] == 2
    assert vc_item["blocked"] == 1


def test_record_dev_api_cooldown_blocks_until_expiry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runtime = app.resolve_runtime_config(
        secrets={},
        environ={
            "ENV": "dev",
            "DEV_ALLOW_LIVE_API": "true",
            "DEV_USE_SAMPLE_DATA": "false",
        },
    )
    now = app.LOCAL_TZ.localize(datetime(2026, 3, 20, 10, 0, 0))
    environ = {
        "ENV": "dev",
        "DEV_ALLOW_LIVE_API": "true",
        "DEV_USE_SAMPLE_DATA": "false",
        "DEV_API_COOLDOWN_MINUTES": "30",
    }

    until = app.record_dev_api_cooldown(
        "open_meteo_wind", runtime=runtime, now=now, environ=environ
    )
    assert until is not None

    allowed, reason = app.check_and_record_dev_api_request(
        "open_meteo_wind",
        runtime=runtime,
        now=now + timedelta(minutes=10),
        environ=environ,
    )
    assert allowed is False
    assert "cooling down" in reason

    allowed, reason = app.check_and_record_dev_api_request(
        "open_meteo_wind",
        runtime=runtime,
        now=now + timedelta(minutes=31),
        environ=environ,
    )
    assert allowed is True
    assert reason is None


def test_guardrail_state_persists_across_reloads(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runtime = app.resolve_runtime_config(
        secrets={},
        environ={
            "ENV": "dev",
            "DEV_ALLOW_LIVE_API": "true",
            "DEV_USE_SAMPLE_DATA": "false",
            "DEV_BUDGET_OPEN_METEO_WIND": "5",
        },
    )
    now = app.LOCAL_TZ.localize(datetime(2026, 3, 20, 11, 0, 0))
    environ = {
        "ENV": "dev",
        "DEV_ALLOW_LIVE_API": "true",
        "DEV_USE_SAMPLE_DATA": "false",
        "DEV_BUDGET_OPEN_METEO_WIND": "5",
    }

    app.check_and_record_dev_api_request(
        "open_meteo_wind", runtime=runtime, now=now, environ=environ
    )
    app.check_and_record_dev_api_request(
        "open_meteo_wind", runtime=runtime, now=now, environ=environ
    )

    date_str = now.strftime("%Y-%m-%d")
    state = app._load_dev_guardrail_state(date_str)
    assert state["usage"]["open_meteo_wind"] == 2


def test_get_dev_guardrail_snapshot_includes_remaining_and_cooldown_minutes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runtime = app.resolve_runtime_config(
        secrets={},
        environ={
            "ENV": "dev",
            "DEV_ALLOW_LIVE_API": "true",
            "DEV_USE_SAMPLE_DATA": "false",
            "DEV_BUDGET_VC_FORECAST": "4",
            "DEV_API_COOLDOWN_MINUTES": "45",
        },
    )
    now = app.LOCAL_TZ.localize(datetime(2026, 3, 20, 12, 0, 0))
    environ = {
        "ENV": "dev",
        "DEV_ALLOW_LIVE_API": "true",
        "DEV_USE_SAMPLE_DATA": "false",
        "DEV_BUDGET_VC_FORECAST": "4",
        "DEV_API_COOLDOWN_MINUTES": "45",
    }

    app.check_and_record_dev_api_request(
        "visual_crossing_forecast", runtime=runtime, now=now, environ=environ
    )

    snapshot = app.get_dev_guardrail_snapshot(runtime=runtime, now=now, environ=environ)

    assert snapshot["cooldown_minutes"] == 45
    vc_item = next(item for item in snapshot["items"] if item["key"] == "visual_crossing_forecast")
    assert vc_item["used"] == 1
    assert vc_item["remaining"] == 3


def test_format_dev_guardrail_sidebar_line_includes_remaining_and_cooldown():
    item = {
        "label": "VC forecast/current",
        "used": 2,
        "limit": 4,
        "remaining": 2,
        "blocked": 1,
        "cooldown_active": True,
        "cooldown_until": app.LOCAL_TZ.localize(datetime(2026, 3, 20, 13, 30, 0)),
    }

    line = app._format_dev_guardrail_sidebar_line(item)

    assert "2/4 used" in line
    assert "2 remaining" in line
    assert "1 blocked" in line
    assert "cooldown until 13:30" in line


def test_format_dev_guardrail_fallback_distinguishes_budget_and_cooldown():
    budget_msg = app._format_dev_guardrail_fallback(
        "forecast",
        app.DevAPIBlockedError("VC forecast/current dev budget exhausted (12/12)."),
    )
    cooldown_msg = app._format_dev_guardrail_fallback(
        "wind",
        app.DevAPIBlockedError("Open-Meteo wind cooling down until 14:15."),
    )

    assert "budget reached" in budget_msg
    assert "showing last known data" in budget_msg
    assert "cooldown active" in cooldown_msg
    assert "cached or forecast wind data" in cooldown_msg


def test_get_dev_budget_limits_invalid_values_fall_back_to_defaults():
    limits = app._get_dev_budget_limits(
        secrets={},
        environ={
            "DEV_BUDGET_VC_FORECAST": "abc",
            "DEV_BUDGET_VC_HISTORICAL": "",
            "DEV_BUDGET_OPEN_METEO_WIND": "-5",
        },
    )

    assert (
        limits["visual_crossing_forecast"]
        == app.DEV_API_BUDGET_DEFAULTS["visual_crossing_forecast"]
    )
    assert (
        limits["visual_crossing_historical"]
        == app.DEV_API_BUDGET_DEFAULTS["visual_crossing_historical"]
    )
    assert limits["open_meteo_wind"] == 0


def test_reset_dev_guardrail_usage_and_blocked_clears_counters_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    now = app.LOCAL_TZ.localize(datetime(2026, 3, 20, 8, 0, 0))
    date_str = now.strftime("%Y-%m-%d")
    app._save_dev_guardrail_state(
        {
            "date": date_str,
            "usage": {"visual_crossing_forecast": 3},
            "blocked": {"visual_crossing_forecast": 2},
            "cooldowns": {"visual_crossing_forecast": now.isoformat()},
        }
    )

    state = app.reset_dev_guardrail_usage_and_blocked(now=now)

    assert state["usage"] == {}
    assert state["blocked"] == {}
    assert "visual_crossing_forecast" in state["cooldowns"]


def test_clear_dev_guardrail_cooldowns_keeps_usage_and_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    now = app.LOCAL_TZ.localize(datetime(2026, 3, 20, 9, 0, 0))
    date_str = now.strftime("%Y-%m-%d")
    app._save_dev_guardrail_state(
        {
            "date": date_str,
            "usage": {"open_meteo_wind": 4},
            "blocked": {"open_meteo_wind": 1},
            "cooldowns": {"open_meteo_wind": now.isoformat()},
        }
    )

    state = app.clear_dev_guardrail_cooldowns(now=now)

    assert state["cooldowns"] == {}
    assert state["usage"] == {"open_meteo_wind": 4}
    assert state["blocked"] == {"open_meteo_wind": 1}


def test_get_dev_guardrail_raw_state_rolls_over_to_today(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    yesterday = app.LOCAL_TZ.localize(datetime(2026, 3, 19, 23, 0, 0))
    app._save_dev_guardrail_state(
        {
            "date": yesterday.strftime("%Y-%m-%d"),
            "usage": {"visual_crossing_forecast": 99},
            "blocked": {"visual_crossing_forecast": 10},
            "cooldowns": {"visual_crossing_forecast": yesterday.isoformat()},
        }
    )

    today = app.LOCAL_TZ.localize(datetime(2026, 3, 20, 7, 0, 0))
    state = app.get_dev_guardrail_raw_state(now=today)

    assert state["date"] == "2026-03-20"
    assert state["usage"] == {}
    assert state["blocked"] == {}
    assert state["cooldowns"] == {}


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


def test_fetch_forecast_and_current_maps_precip_probability_and_humidity(monkeypatch):
    payload = {
        "days": [
            {
                "hours": [
                    {
                        "datetime": "00:00:00",
                        "temp": 35.0,
                        "feelslike": 33.0,
                        "windspeed": 5.0,
                        "wdir": 180,
                        "precip": 0.12,
                        "precipprob": 65,
                        "humidity": 77,
                        "snow": 0.0,
                    }
                ]
            }
        ],
        "currentConditions": {
            "temp": 36.0,
            "feelslike": 34.0,
            "windspeed": 6.0,
            "wdir": 200,
            "precip": 0.2,
            "precipprob": 70,
            "humidity": 80,
            "snow": 0.0,
        },
    }

    def fake_get(url, params, timeout):
        return _MockResponse(payload)

    monkeypatch.setattr(app.requests, "get", fake_get)

    forecast_df, live_temp = app.fetch_forecast_and_current.__wrapped__("fake-key")

    assert forecast_df["PrecipIn"].tolist() == [0.12]
    assert forecast_df["PrecipProb"].tolist() == [65.0]
    assert forecast_df["Humidity"].tolist() == [77.0]
    assert forecast_df["SnowIn"].tolist() == [0.0]
    assert live_temp["PrecipIn"] == 0.2
    assert live_temp["PrecipProb"] == 70.0
    assert live_temp["Humidity"] == 80.0
    assert live_temp["SnowIn"] == 0.0


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


def test_build_precip_chart_layers():
    df = pd.DataFrame(
        {
            "Hour": list(range(24)),
            "PrecipIn": [0.0] * 8 + [0.1, 0.15, 0.12] + [0.0] * 13,
            "PrecipProb": [20.0] * 24,
            "Humidity": [55.0] * 24,
            "SnowIn": [0.0] * 24,
        }
    )

    chart = app.build_precip_chart(df=df, current_hour=10)
    spec = chart.to_dict()

    assert "layer" in spec
    assert len(spec["layer"]) == 3


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
