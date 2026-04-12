# The Farm Monitor: Feature Requirements and Logic

This document defines product features, implementation requirements, and behavior rules.

## Scope

- Weather dashboard in Streamlit.

## Weather Dashboard

### 1) Runtime profile resolution

Requirements:
- Environment values available from env/secrets: `ENV`, `CI`, `RUN_LIVE_INTEGRATION_TESTS`, `DEV_ALLOW_LIVE_API`, `DEV_USE_SAMPLE_DATA`.
- `ENV` should be `dev` or `prod`.

Logic:
- Resolves profile into one of: `prod`, `dev-safe`, `dev-live`, `ci-non-live`, `ci-live-manual`.
- `prod` always uses live APIs.
- `dev-safe` forces sample mode unless live is explicitly enabled.
- `ci-non-live` forces sample mode.
- `ci-live-manual` requires explicit opt-in and explicit live allowance.
- Invalid combinations produce runtime validation errors.

### 2) Dev API guardrails

Requirements:
- Dev profile with live API enabled.
- Optional budget and cooldown variables:
  - `DEV_BUDGET_VC_FORECAST`
  - `DEV_BUDGET_VC_HISTORICAL`
  - `DEV_BUDGET_OPEN_METEO_WIND`
  - `DEV_API_COOLDOWN_MINUTES`

Logic:
- Tracks per-provider usage, blocked attempts, and cooldown windows.
- Blocks calls once budget is exhausted for a provider.
- Applies provider cooldown after 429 responses.
- Persists day-scoped state to `.streamlit/guardrails/dev_api_state.json`.
- Sidebar controls can reset usage/blocked counters and clear cooldowns.

### 3) Forecast + current conditions ingestion

Requirements:
- Visual Crossing API key in env or Streamlit secrets for live mode.

Logic:
- Fetches hourly forecast + current conditions in one request.
- Parses temperature, wind, precipitation, humidity, snow, AQI, and pollutants.
- Keeps rows when wind direction is missing (`WindDir = Unknown`).
- If current fields are missing, fills from most recent forecast row.

### 4) Historical comparison band

Requirements:
- Current date string and Visual Crossing API key in live mode.

Logic:
- Fetches the same calendar day over prior years.
- Handles leap-year rollover (Feb 29 to Feb 28 in non-leap years).
- Aggregates hourly high/low/mean for Actual, Feels Like, and Wind Speed.
- Stops yearly loop at first 429 response.
- Uses cache/session fallback when live fetch is unavailable.

### 5) Wind source override

Requirements:
- Open-Meteo availability in live mode.

Logic:
- Fetches hourly/current wind speed, gust, and direction.
- Replaces wind fields from forecast dataset when available.
- Uses session fallback on failures.

### 6) Outage fallback behavior

Requirements:
- Session state available.

Logic:
- Forecast failure fallback order: session cache, then emergency local sample data.
- Historical fallback order: disk cache, live fetch, session cache, then unavailable caption.
- Wind fallback order: live fetch, then session wind cache.
- User messaging differentiates general outage, budget exhaustion, and cooldown block.

### 7) Temperature operand toggle

Requirements:
- User selects `Feels Like` or `Actual`.

Logic:
- Uses selected temperature column for metrics and charting.
- Overrides current hour with live value.
- Shows Now, High, Low, and one-hour trend delta.

### 8) Seasonal status banner

Requirements:
- Monitoring mode and threshold selected.

Logic:
- Winter mode (`Warming Focus`):
  - Success when current temp >= threshold.
  - Info when threshold is reached later today.
  - Warning when not reached today.
- Summer mode (`Cooling Focus`):
  - Success when current temp <= threshold.
  - Info when threshold is reached later today.
  - Warning when not reached today.
- Info text uses first qualifying forecast hour.

### 9) Kitty comfort status

Requirements:
- Current temperature, optional wind speed/gust, and rain/snow flag.

Logic:
- Temperature comfortable if `32 < temp <= 85`.
- Wind comfortable if `max(speed, gust) <= 5` when wind data exists.
- Precip comfortable only when no active rain/snow.
- Overall banner is success only when all active checks pass.

### 10) Wind analytics section

Requirements:
- Wind columns present or defaultable.

Logic:
- Displays current wind speed/direction, fastest wind, strongest gust.
- Computes one-hour delta where prior data exists.
- Renders actual vs forecast wind chart, gust overlay, and optional historical wind band.

### 11) Precipitation section

Requirements:
- Precipitation/humidity/snow fields present or defaultable.

Logic:
- Displays recent rain/snow status, total accumulation today, current precip probability, humidity.
- Renders hourly actual precipitation chart.

### 12) Air quality section

Requirements:
- AQI and pollutant fields present when reported by source.

Logic:
- Interprets AQI categories from Good to Hazardous.
- Displays current/high/low AQI and relevant hours.
- Renders observed vs forecast AQI chart.
- Shows pollutant table and marks missing values as not reported by source.

### 13) Data source transparency panel

Requirements:
- None.

Logic:
- Explains provider/source roles and blended-model caveats.

## Maintenance Plan (Keep This Updated)

This file should be updated whenever behavior changes in any of these files:
- `app.py`
- `tests/test_core_logic.py`
- `tests/test_guardrail_config_sanity.py`
- `tests/test_integration_live_api.py`

Update checklist for each feature change:
1. Update the relevant section in this document (Requirements and Logic).
2. Add or update tests that enforce the new behavior.
3. Add one changelog entry summarizing behavior change.
4. Verify README links still point to this file.

Definition of done for feature PRs:
- If feature behavior changed, this file is updated in the same PR.
- If no behavior changed, PR description should explicitly say "No feature-doc changes required".
