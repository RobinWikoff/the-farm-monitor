# The Farm: Comfort Temperature Monitor — Changelog

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
- Added "📡 About the Data Sources" expandable section explaining Open-Meteo (forecast) and OpenWeatherMap (live temp), including live resolved OWM station name and ID
- Updated temperature caption to include sun warmth alongside wind chill and humidity
- Expanded "Features Coming Soon" roadmap with: Humidity, Wind (with Corgi Spin 🐕 local unit), Sunrise/Sunset, Brightness, AQI, Kitty Comfort Thresholds 🐱, Real vs. Feels Like Toggle
- Removed `st.write("---")` divider between Data Sources and Features Coming Soon sections
- Expanded Kitty Comfort Thresholds with alert states: Winter/Summer "Now Kitties are NOT comfortable" conditions (threshold was met but conditions have since worsened)
