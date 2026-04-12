# C2 - Container Diagram

## Purpose

Show deployable/runtime containers and data flow between them.

```mermaid
C4Container
    title The Farm Monitor – Container Diagram | Generated %%RENDER_DATE%%

    Person(user, "Farm Operator")
    Person(dev, "Developer")

    System_Boundary(farm, "The Farm Monitor") {
        Container(web_ui, "Weather Dashboard UI", "Streamlit (Python)", "Interactive weather monitoring app")
        ContainerDb(local_state, "Local State Store", "JSON + CSV files", "Guardrail state + historical band cache")
    }

    System_Ext(vc_api, "Visual Crossing API", "Weather API")
    System_Ext(om_api, "Open-Meteo API", "Weather API")

    Rel(user, web_ui, "Views charts, metrics, and status banners", "Browser")

    Rel(dev, web_ui, "Runs and validates runtime profiles", "streamlit run")

    Rel(web_ui, vc_api, "Reads forecast/current and historical data", "HTTPS JSON")
    Rel(web_ui, om_api, "Reads wind data", "HTTPS JSON")
    Rel(web_ui, local_state, "Persists guardrail + cache data", "File I/O")
```

## Container Narrative

- `Weather Dashboard UI` is the core operational container and includes guardrails, fallback logic, and visual analytics.
- `Local State Store` is not a service but is modeled as a container DB because it stores stateful artifacts:
  - `.streamlit/guardrails/dev_api_state.json`
  - `.streamlit/hist_cache/hist_YYYY-MM-DD.csv`

## Reliability and Operation Notes

- Weather container degrades to cached/session/sample data on provider failures.
- Runtime profile configuration determines whether external API calls are allowed.
