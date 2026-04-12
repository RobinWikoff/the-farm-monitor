# C3 - Component Diagram

## Purpose

Show major components inside the main weather container.

## Weather Dashboard Components

```mermaid
C4Component
    title Component Diagram | Generated %%RENDER_DATE%%

    Container_Boundary(weather_app, "Weather Dashboard (app.py)") {
        Component(runtime_cfg, "Runtime Config Resolver", "Functions", "Resolves profile/data mode and validates env constraints")
        Component(guardrails, "Dev Guardrail Manager", "Functions + local state", "Budget, cooldown, blocked counters, snapshots")
        Component(data_ingest, "Data Ingestion Layer", "Functions", "Fetches VC forecast/current, VC historical, Open-Meteo wind")
        Component(fallbacks, "Fallback Orchestrator", "run_app flow", "Session/disk/sample fallback and user messaging")
        Component(analytics, "Domain Analytics", "Functions", "Trend calculations, thresholds, kitty comfort, AQI interpretation")
        Component(charts, "Chart Builders", "Altair functions", "Temperature, wind, precipitation, AQI visualizations")
        Component(ui_comp, "UI Composition", "Streamlit", "Sidebar, metrics, banners, expanders, tables")
    }

    System_Ext(vc_api, "Visual Crossing API", "Forecast/current/historical")
    System_Ext(om_api, "Open-Meteo API", "Wind")
    System_Ext(local_state, "Local File State", "Guardrail + cache")

    Rel(runtime_cfg, guardrails, "Enables/disables enforcement by profile")
    Rel(guardrails, data_ingest, "Allows/blocks live API calls")
    Rel(data_ingest, vc_api, "Calls")
    Rel(data_ingest, om_api, "Calls")
    Rel(guardrails, local_state, "Reads/writes state")
    Rel(fallbacks, local_state, "Reads/writes historical cache")
    Rel(fallbacks, data_ingest, "Requests live data")
    Rel(fallbacks, analytics, "Provides normalized datasets")
    Rel(analytics, charts, "Supplies derived values")
    Rel(charts, ui_comp, "Returns chart specs")
    Rel(fallbacks, ui_comp, "Provides warning/status text")
```

### Weather Component Responsibilities

- Runtime Config Resolver:
  - Determines profile (`prod`, `dev-safe`, `dev-live`, `ci-non-live`, `ci-live-manual`).
  - Raises validation errors for invalid combinations.
- Dev Guardrail Manager:
  - Enforces per-provider budgets in dev-live.
  - Applies cooldown after 429 and records blocked attempts.
- Data Ingestion Layer:
  - Retrieves forecast/current weather and historical aggregation inputs.
  - Retrieves Open-Meteo wind for replacement merge.
- Fallback Orchestrator:
  - Implements cascading fallback strategy (live -> cache/session -> sample).
- Domain Analytics:
  - Threshold evaluations, trend deltas, comfort status, AQI labels.
- Chart Builders:
  - Encodes observed/forecast bridges and historical overlays.
- UI Composition:
  - Renders final user-visible dashboard state.
