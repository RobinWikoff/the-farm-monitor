# The Farm: Comfort Temperature Monitor — Changelog

---

## v12 — App Shows Blank Screen When API Rate Limited
Added session state fallback for forecast and live temp data so the app degrades gracefully when Visual Crossing is rate limited.
- Forecast and live temp now saved to session state on every successful load
- If API returns 429, app shows last known good data with a yellow warning banner
- If API returns 429 AND no session state exists, shows a clear error message instead of blank screen
- Closes #20 (pending verification after quota reset)

---

## v11 — Today_Naive Was A Ghost
Fixed recurring historical band disappearance, extended caching, added session state fallback, and patched API key exposure in error messages.
- Fixed `today_naive` reference bug in `fetch_historical_band` — variable was removed in a previous patch but still referenced, causing silent crashes
- Extended historical band cache TTL from 24 hours to 7 days — 5-year historical data barely changes, cuts Visual Crossing record usage by 7x
- Added session state fallback for historical band — if VC is rate limited, app shows last known good band instead of crashing
- Extended forecast cache from 5 to 10 minutes to reduce API calls
- Sanitized error messages — API errors no longer display full request URL (which included the API key)
- Closes #15, Closes #19

---

## v10 — Dev Label
Added DEV indicator to browser tab and app heading when running in the dev environment.
- Browser tab shows "The Farm [DEV]" in dev, "The Farm" in prod
- App heading shows "The Farm: How's the Weather? — DEV" in dev
- Reads `ENV = "dev"` from Streamlit secrets — absent in prod, no code change needed to distinguish environments
- Closes #18

---

## v9 — Remove Features Coming Soon Section
Cleaned up the UI by removing the roadmap expander — all features are now tracked as GitHub Issues.
- Removed "🚀 Features Coming Soon" expander and all roadmap content from `app.py`
- Roadmap is now fully managed in GitHub Issues with P1–P4 priority labels
- Closes #14

---

## v8 — Goodbye Open Meteo
Moved forecast and live temperature entirely to Visual Crossing. Open-Meteo and OpenWeatherMap both removed.
- Replaced `fetch_forecast` (Open-Meteo) and `fetch_live_temp` (OWM) with single `fetch_forecast_and_current()` call to Visual Crossing Timeline API
- `WEATHER_API_KEY` (OWM) no longer needed in Streamlit secrets — only `VISUAL_CROSSING_API_KEY` required
- Live conditions and hourly forecast now refresh every 5 minutes from Visual Crossing `currentConditions` and `hours` data
- Updated "About the Data Sources" expander to reflect Visual Crossing as sole source for forecast and live temp
- Removed `OWM_BASE`, `METEO_URL` constants and `_get_api_key()` helper

---

## v7 — Historical Band Needs Visual Crossing API
Swapped Open-Meteo archive API for Visual Crossing Timeline API for the 5-year historical band.
- Replaced all Open-Meteo archive calls with Visual Crossing `feelslike` hourly data
- Added `_get_vc_api_key()` helper reading `VISUAL_CROSSING_API_KEY` from Streamlit secrets
- Removed retry/backoff/sleep logic no longer needed
- Cleaned up unused imports (`HTTPAdapter`, `Retry`, `time`)
- Updated "About the Data Sources" expander to credit Visual Crossing for historical band

---

## v6 — Sorry Will Try Again In 1 Second
Attempted to fix Open-Meteo 429 rate limiting with retry logic and polite delays.
- Added `_make_retry_session()` with exponential backoff (2, 4, 8, 16, 32s) on 429/5xx
- Added `time.sleep(1)` between per-year archive calls
- Added leap year guard (Feb 29 → Feb 28 fallback)
- Note: Still hit rate limits due to Streamlit Cloud shared IPs; superseded by v7

---

## v5 — Too Many Requests Revenge
Attempted to fix Open-Meteo 429 errors by collapsing 5 API calls into 1.
- Replaced 5 per-year archive requests with a single date-range request
- Filtered results in Python to matching month/day rows
- Note: Large range request also hit rate limits; superseded by v6 and v7

---

## v4 — Stop Being Mad
Fixed Streamlit deprecation warning for chart width parameter.
- Replaced `use_container_width=True` with `width="stretch"` on `st.altair_chart`

---

## v3 — Historical Band Is Invisible Patch
Fixed the 5-year historical band disappearing from the chart.
- Stripped timezone from `today` before date math in `fetch_historical_band` so cache key stays stable
- Added leap year guard: Feb 29 falls back to Feb 28 in non-leap years
- Removed empty `alt.layer()` that was silently breaking Altair layer composition
- Replaced ambiguous layer stacking with explicit `if/else` chart assembly

---

## v2 — The Pocket Corgi
Optimized for mobile viewing and cleaned up UI navigation.
- Moved chart legend from `bottom-left` (overlapping data) to `bottom` with `columns=2` grid layout
- Suppressed duplicate `strokeDash` legend entry
- Reduced Y-axis padding and data label font sizes for narrow screens
- X-axis labels every hour (all 24) with `-45°` angle
- Wrapped "Features Coming Soon" content in `st.expander` — heading stays full size outside
- "About the Data Sources" and "Features Coming Soon" both now collapse/expand consistently

---

## v1 — The Weathered Corgi
First named release. Added data sourcing transparency, live trend indicator, and expanded roadmap.
- Added `get_temp_trend()`: compares live temp to prior hour forecast, renders ↑↓ delta on "Feels Like Now" metric with "since HH:00" label
- `fetch_live_temp()` now returns `(feels_like, station_name, station_id)` tuple
- Expanded Kitty Comfort Thresholds with alert states: Winter/Summer "Now Kitties are NOT comfortable" conditions (threshold was met but conditions have since worsened)
- Added "📡 About the Data Sources" expandable section explaining Open-Meteo (forecast) and OpenWeatherMap (live temp), including live resolved OWM station name and ID
- Updated temperature caption to include sun warmth alongside wind chill and humidity
- Expanded "Features Coming Soon" roadmap with: Humidity, Wind (with Corgi Spin 🐕 local unit), Sunrise/Sunset, Brightness, AQI, Kitty Comfort Thresholds 🐱, Real vs. Feels Like Toggle
- Removed `st.write("---")` divider between Data Sources and Features Coming Soon sections
