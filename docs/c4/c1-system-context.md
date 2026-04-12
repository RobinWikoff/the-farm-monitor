# C1 - System Context

## Purpose

Show The Farm Monitor as a system and its relationships with users and external systems.

```mermaid
C4Context
    title The Farm Monitor - System Context

    Person(user, "Farm Operator", "Views weather risk dashboards")
    Person(dev, "Developer/Maintainer", "Runs dev-safe/dev-live profiles and integration tests")

    System_Boundary(farm_boundary, "The Farm Monitor") {
        System(farm_monitor, "The Farm Monitor", "Streamlit weather monitoring dashboard")
    }

    System_Ext(vc_api, "Visual Crossing API", "Forecast/current weather and historical weather data")
    System_Ext(om_api, "Open-Meteo API", "Wind speed/gust/direction enrichment")
    System_Ext(local_fs, "Local File System", "Guardrail state and historical cache")
    System_Ext(ci_runner, "GitHub Actions", "CI profiles for non-live and manual live test workflows")

    Rel(user, farm_monitor, "Uses weather dashboard", "Browser")
    Rel(dev, farm_monitor, "Runs app and tests", "Python/Streamlit")
    Rel(farm_monitor, vc_api, "Fetches forecast/current + historical bands", "HTTPS JSON")
    Rel(farm_monitor, om_api, "Fetches wind forecast/current", "HTTPS JSON")
    Rel(farm_monitor, local_fs, "Reads/writes guardrail + historical cache", "JSON/CSV")
    Rel(dev, ci_runner, "Push/PR/manual dispatch", "GitHub")
    Rel(ci_runner, farm_monitor, "Executes test suites with runtime flags", "pytest")
```

## Context Narrative

- Primary actor is the farm operator who consumes operational weather insights.
- The application integrates two weather providers:
  - Visual Crossing for primary weather and historical band.
  - Open-Meteo for wind override.
- Local filesystem is architecturally significant because fallback reliability depends on persisted state.
- CI is part of the system context due to enforced runtime profile behavior and live/non-live test separation.

## Key Constraints

- API usage is constrained by development guardrails (budget + cooldown).
- Non-live test workflows must not hit external network APIs.
- Production profile must remain live-data capable.
