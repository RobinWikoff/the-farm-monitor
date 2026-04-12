# C2 - Container Diagram

## Purpose

Show deployable/runtime containers and data flow between them.

```mermaid
C4Container
    title The Farm Monitor - Container Diagram

    Person(user, "Farm Operator")
    Person(dev, "Developer")

    System_Boundary(farm, "The Farm Monitor") {
        Container(web_ui, "Weather Dashboard UI", "Streamlit (Python)", "Interactive weather monitoring app")
        Container(memo_ui, "Memo UI", "Streamlit (Python)", "Form-driven memo PDF generation")
        Container(memo_cli, "Memo CLI", "Python CLI", "Batch/offline memo PDF generation")
        ContainerDb(local_state, "Local State Store", "JSON + CSV files", "Guardrail state + historical band cache")
    }

    System_Ext(vc_api, "Visual Crossing API", "Weather API")
    System_Ext(om_api, "Open-Meteo API", "Weather API")

    Rel(user, web_ui, "Views charts, metrics, and status banners", "Browser")
    Rel(user, memo_ui, "Fills memo form and downloads PDF", "Browser")

    Rel(dev, web_ui, "Runs and validates runtime profiles", "streamlit run")
    Rel(dev, memo_ui, "Runs memo UI locally", "streamlit run")
    Rel(dev, memo_cli, "Generates PDF from YAML/JSON", "python -m memo.cli")

    Rel(web_ui, vc_api, "Reads forecast/current and historical data", "HTTPS JSON")
    Rel(web_ui, om_api, "Reads wind data", "HTTPS JSON")
    Rel(web_ui, local_state, "Persists guardrail + cache data", "File I/O")

    Rel(memo_ui, memo_cli, "Uses shared schema/generator modules", "In-process Python modules")
    Rel(memo_cli, local_state, "Reads input files and writes output PDF", "File I/O")
```

## Container Narrative

- `Weather Dashboard UI` is the core operational container and includes guardrails, fallback logic, and visual analytics.
- `Memo UI` and `Memo CLI` are separate entry points sharing the same domain and PDF generation internals.
- `Local State Store` is not a service but is modeled as a container DB because it stores stateful artifacts:
  - `.streamlit/guardrails/dev_api_state.json`
  - `.streamlit/hist_cache/hist_YYYY-MM-DD.csv`

## Reliability and Operation Notes

- Weather container degrades to cached/session/sample data on provider failures.
- Memo containers are deterministic and do not require external APIs.
- Runtime profile configuration determines whether external API calls are allowed.
