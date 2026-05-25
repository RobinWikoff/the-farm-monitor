# Rust vs Main Dashboard Parity Constraints

Date: 2026-05-25
Parent issue: #102
Purpose: tighten parity definition against the Streamlit main dashboard behavior in app.py.

## Baseline Definition
The source of truth for parity is the user-visible behavior and information architecture in app.py.
Parity is not satisfied by section name matching alone; it requires control flow, metric semantics, and chart/legend meaning parity.

## Constraint Levels
- P0 (must match before #102 close): user-facing controls, section ordering, key metric semantics, status banners, and chart intent (observed vs forecast + legends).
- P1 (strongly expected in #102B/#102C): formatting/typography/table structure and data-source transparency wording quality.
- P2 (acceptable deferred only with explicit approval): interaction polish and non-critical visual tuning.

## Explicit Constraints (from main app)

### 1) Top-level controls and runtime context (P0)
- Include controls equivalent to:
  - Monitoring mode selector (winter/summer threshold mode).
  - Temperature type toggle (Feels Like vs Actual).
  - Kitty wind cutoff control.
- Show runtime/profile context line (profile, data mode, live API on/off).
- DEV-only guardrail information can be simplified in Rust, but omission must be documented as intentional deviation.

### 2) Core section order and hierarchy (P0)
Required section progression:
1. Kitty comfort banner (above temperature area)
2. Temperature metrics + trend + seasonal status + temperature chart
3. Wind banner + wind metrics + wind chart
4. Precipitation metrics + precipitation chart
5. Air Quality metrics + AQI chart + pollutant breakdown table
6. Sunrise/Sunset/Brightness metrics + brightness chart + UV/cloud legend
7. Data sources transparency panel

### 3) Temperature behavior parity (P0)
- Respect Feels Like vs Actual operand switch for displayed Now/High/Low and chart series.
- Preserve 1-hour delta behavior and "since HH:00" semantics.
- Preserve seasonal status banner decision logic (warming/cooling focus outcomes).
- Preserve historical-band intent for temperature chart where available.

### 4) Kitty comfort behavior parity (P0)
- Maintain combined pass/fail logic across:
  - temperature comfort range,
  - wind threshold,
  - active rain/snow detection.
- Banner must clearly show overall result and per-condition explanation.

### 5) Wind behavior parity (P0)
- Keep explicit wind banner for fastest forecasted wind and cutoff warning behavior.
- Keep metrics: speed now (with delta), direction, fastest wind, strongest gust.
- Preserve chart semantics:
  - observed vs forecast split,
  - gust overlay treatment,
  - historical band/mean intent where available.

### 6) Precipitation behavior parity (P0)
- Keep rain/snow recently boolean based on actual observed hours, not only current hour.
- Keep total accumulation so far and now-probability/humidity metrics.
- Keep hourly precipitation chart intent and explanatory caption.

### 7) Air quality behavior parity (P0)
- Keep current/high/low AQI and category interpretation.
- Keep AQI chart observed/forecast semantics and explanatory caption.
- Pollutant breakdown should be table-like and represent missing values as "Not reported by source" equivalent semantics.

### 8) Brightness behavior parity (P0)
- Keep sunrise/sunset/daylight metrics with yesterday deltas.
- Keep peak UV metric and interpretation.
- Keep dual-axis chart intent: UV (left) + cloud cover (right), with explicit legend semantics.

### 9) Data source transparency parity (P1)
- Keep an expandable/discrete panel explaining provider roles and caveats.
- Preserve refresh cadence transparency and blended-model caveat messaging.

### 10) Fallback messaging parity (P1)
- Differentiate generic outage vs guardrail block vs cooldown states in user messaging.
- If simplified in Rust, document exact difference and rationale.

## Current Rust Gap Summary (as of #103 PR #108)
- Achieved: section shell/layout flow improvements and lighter visual shell.
- Missing/partial:
  - top-level interactive controls parity,
  - kitty comfort banner + seasonal status banner,
  - chart-level parity (temperature/wind/precip/AQI/brightness),
  - data-source transparency depth,
  - fallback/guardrail UX messaging parity.

## Mapping To Existing Child Issues
- #103: shell/layout parity (in progress via PR #108).
- #104: section formatting parity should explicitly include heading/metric/table conventions and section-level captions.
- #105: chart-like visual treatment parity should explicitly include observed/forecast semantics, legends/axes, and callouts.
- #106: verification artifacts should be upgraded to include pass/fail per constraint above.
- #107: final closeout should include approved-deviation list with rationale for any unmet P0/P1 items.

## Suggested Acceptance Gate Update
Before closing #102, require a pass/fail matrix for each numbered constraint above, with one of:
- PASS
- PASS with approved deviation
- FAIL (must be remediated)
