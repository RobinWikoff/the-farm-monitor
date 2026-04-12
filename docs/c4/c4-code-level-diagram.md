# C4 - Code-Level Diagram

## Purpose

Provide a complete code-level view of all public and internal components in `app.py`.

## Runtime + Guardrail + Weather Fetch Flow

```mermaid
---
title: C4 Code-Level Diagram | Generated %%RENDER_DATE%%
---
classDiagram
    class run_app {
      +run_app()
    }

    class RuntimeConfig {
      +resolve_runtime_config(secrets, environ) dict
      +inspect_runtime_config(runtime) dict
      +validate_runtime_config(runtime) list
      +get_runtime_config_warnings(runtime) list
      -_as_bool(value, default) bool
      -_get_cfg_value(name, secrets, environ) Any
      -_get_streamlit_secrets() Mapping
    }

    class DevAPIBlockedError {
      <<exception>>
    }

    class Guardrails {
      +check_and_record_dev_api_request(key, runtime, now, ...)
      +record_dev_api_cooldown(key, runtime, now, ...)
      +get_dev_guardrail_snapshot(...)
      +reset_dev_guardrail_usage_and_blocked(...)
      +clear_dev_guardrail_cooldowns(...)
      +get_dev_guardrail_raw_state(now) dict
      -_load_dev_guardrail_state(date) dict
      -_save_dev_guardrail_state(state)
      -_fresh_dev_guardrail_state(date_str) dict
      -_dev_guardrail_state_path() str
      -_get_dev_budget_limits(secrets, environ) dict
      -_get_dev_cooldown_minutes(secrets, environ) int
      -_guardrail_now(now) datetime
      -_get_dev_near_limit_pct(secrets, environ) float
      -_format_dev_guardrail_sidebar_line(item) str
      -_format_dev_guardrail_fallback(kind, exc) str
    }

    class WeatherIngestion {
      +guarded_requests_get(url, params, timeout, guardrail_key) Response
      +fetch_forecast_and_current(vc_api_key) tuple
      +fetch_historical_band(today_str, vc_api_key) DataFrame
      +fetch_wind_openmeteo() tuple
      -_build_dev_sample_payload(now_mtn) dict
      -_get_vc_api_key() str
    }

    class HistoricalCache {
      -_hist_cache_path(date_str) str
      -_load_hist_band_from_disk(date_str) DataFrame
      -_save_hist_band_to_disk(date_str, hist_band)
    }

    class Analytics {
      +get_temp_trend(df, live_temp, current_hour) float
      +get_wind_trend(df, live_wind_speed, current_hour) float
      +kitty_comfort_status(live_temp_f, wind_speed, wind_gust, rain_or_snow) dict
      +aqi_interpretation(aqi) str
      +wind_degree_to_cardinal(degrees) str
    }

    class StatusBanners {
      +render_status_banner(live_temp, threshold, forecast_future, mode)
      +render_wind_banner(fastest_wind_speed, fastest_wind_hour)
      +render_kitty_comfort_banner(status)
    }

    class Visualization {
      +build_chart(...)
      +build_wind_chart(...)
      +build_precip_chart(df, current_hour) LayerChart
      +build_aqi_chart(df, current_hour) LayerChart
    }

    run_app --> RuntimeConfig : resolve + validate profile
    run_app --> WeatherIngestion : acquire live/sample data
    run_app --> HistoricalCache : disk fallback for historical band
    WeatherIngestion --> Guardrails : enforce dev limits
    Guardrails --> DevAPIBlockedError : raises on blocked call
    run_app --> Analytics : derive metrics + status
    run_app --> StatusBanners : render weather/wind/kitty banners
    run_app --> Visualization : render charts
    WeatherIngestion --> HistoricalCache : cache historical band to disk
```

### Code-Level Notes

- `DevAPIBlockedError` is a custom exception raised by guardrails when a live API call is blocked (budget exhausted, cooldown active).
- `guarded_requests_get` centralizes guardrail enforcement for all live HTTP calls and records 429 cooldowns.
- `fetch_historical_band` includes leap-day handling, 429 early-stop, and 7-day `@st.cache_data` TTL.
- `HistoricalCache` manages the disk-based CSV cache for historical band data, providing fallback when live fetch is unavailable.
- `_format_dev_guardrail_fallback` generates user-facing messages that distinguish budget exhaustion, cooldown, and general outage.
- `run_app` coordinates fallback order (live → session → disk cache → sample), then passes normalized datasets to analytics, banners, and chart builders.
- `RuntimeConfig` includes `inspect_runtime_config` which returns both errors and warnings in a single call, used internally by the convenience wrappers.

## Traceability To Requirements

Primary requirement trace file: [../feature-requirements.md](../feature-requirements.md)

Mapping guidance:
- Runtime profile and guardrail requirements map to `RuntimeConfig` and `Guardrails`.
- Weather fallback and cache behavior map to `run_app`, `WeatherIngestion`, and `HistoricalCache`.
- Analytics and threshold logic map to `Analytics` and `StatusBanners`.
- Chart rendering maps to `Visualization`.
