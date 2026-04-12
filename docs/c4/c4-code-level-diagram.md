# C4 - Code-Level Diagram

## Purpose

Provide code-level views for implementation-critical components.

## C4A - Runtime + Guardrail + Weather Fetch Flow

```mermaid
classDiagram
    class run_app {
      +run_app()
    }

    class resolve_runtime_config {
      +resolve_runtime_config(secrets, environ) dict
      +validate_runtime_config(runtime) list
      +get_runtime_config_warnings(runtime) list
    }

    class Guardrails {
      +check_and_record_dev_api_request(key, runtime, now, ...)
      +record_dev_api_cooldown(key, runtime, now, ...)
      +get_dev_guardrail_snapshot(...)
      +_load_dev_guardrail_state(date)
      +_save_dev_guardrail_state(state)
    }

    class WeatherIngestion {
      +guarded_requests_get(url, params, timeout, guardrail_key)
      +fetch_forecast_and_current(vc_api_key)
      +fetch_historical_band(today_str, vc_api_key)
      +fetch_wind_openmeteo()
      +_build_dev_sample_payload(now_mtn)
    }

    class Analytics {
      +get_temp_trend(df, live_temp, current_hour)
      +get_wind_trend(df, live_wind_speed, current_hour)
      +kitty_comfort_status(...)
      +aqi_interpretation(aqi)
      +render_status_banner(...)
      +render_kitty_comfort_banner(...)
    }

    class Visualization {
      +build_chart(...)
      +build_wind_chart(...)
      +build_precip_chart(...)
      +build_aqi_chart(...)
    }

    run_app --> resolve_runtime_config : resolve + validate profile
    run_app --> WeatherIngestion : acquire live/sample data
    WeatherIngestion --> Guardrails : enforce dev limits
    run_app --> Analytics : derive metrics + status
    run_app --> Visualization : render charts
```

### Code-Level Notes (Weather)

- `guarded_requests_get` centralizes guardrail enforcement for all live HTTP calls.
- `fetch_historical_band` includes leap-day handling and 429 early-stop behavior.
- `run_app` coordinates fallback order, then passes normalized datasets to analytics + chart builders.

## C4B - Memo Data-to-PDF Flow

```mermaid
classDiagram
    class MemoData {
      +date: str
      +memo_title: str
      +organization_name: str
      +logo_path: str
      +from_mapping(data) MemoData
    }

    class load_memo_data {
      +load_memo_data(input_path) MemoData
    }

    class build_memo_story {
      +build_memo_story(memo)
    }

    class NumberedCanvas {
      +showPage()
      +save()
      +_draw_header()
      +_draw_footer(page_number, page_count)
    }

    class generate_memo_pdf {
      +generate_memo_pdf(memo, output_path)
    }

    class memo_ui {
      +build_memo_data_from_form(raw) MemoData
      +_generate_pdf_bytes(memo) bytes
      +main()
    }

    class memo_cli {
      +parse_args()
      +main()
    }

    load_memo_data --> MemoData : construct validated model
    memo_ui --> MemoData : construct from form mapping
    memo_ui --> generate_memo_pdf : generate bytes
    memo_cli --> load_memo_data : load input file
    memo_cli --> generate_memo_pdf : generate output PDF
    generate_memo_pdf --> build_memo_story : build content flowables
    generate_memo_pdf --> NumberedCanvas : page header/footer + numbering
```

### Code-Level Notes (Memo)

- `MemoData.from_mapping` is the contract gate for required fields and date format.
- `NumberedCanvas` performs post-page buffering so footer can render `Page X of Y` accurately.
- UI and CLI share the same schema + generator path, reducing behavior drift.

## Traceability To Requirements

Primary requirement trace file: [../feature-requirements.md](../feature-requirements.md)

Mapping guidance:
- Runtime profile and guardrail requirements map to C4A classes `resolve_runtime_config` and `Guardrails`.
- Weather fallback and chart behavior map to `run_app`, `WeatherIngestion`, `Analytics`, and `Visualization`.
- Memo requirements map to C4B classes `MemoData`, `generate_memo_pdf`, `memo_ui`, and `memo_cli`.
