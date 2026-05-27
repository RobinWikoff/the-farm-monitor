# C1 - System Context

## Purpose

Show The Farm Monitor as a system and its relationships with users and external systems.

```mermaid
C4Context
    title System Context | Generated %%RENDER_DATE%%

  Person(user, "Farm Residents/Stewards", "Use weather insights for daily farm decisions")
    Person(dev, "Developer/Maintainer", "Runs dev-safe/dev-live profiles and integration tests")

    System_Boundary(farm_boundary, "The Farm Monitor") {
        System(farm_monitor, "The Farm Monitor", "Streamlit weather monitoring dashboard")
    }

    System_Ext(vc_api, "Visual Crossing API", "Forecast/current weather and historical weather data")
    System_Ext(om_api, "Open-Meteo API", "Wind speed/gust/direction enrichment")
    System_Ext(local_sample, "Local Sample Payload", "Internal local fallback weather dataset")
    System_Ext(local_station, "Local Weather Station (Planned)", "Microclimate live weather feed")
    System_Ext(indoor_sensors, "Indoor Temperature Sensors via Bridge (Planned)", "Indoor climate feed for indoor/outdoor comparisons")
    System_Ext(inat_api, "iNaturalist API (Planned)", "Flora and fauna observations and trend context")
    System_Ext(kitty_cam, "Kitty Cam Bridge/API (Planned)", "Pen presence and behavior event stream")
    System_Ext(land_sat, "Land Satellite Data API (Planned)", "Soil moisture and land condition data")
    System_Ext(local_fs, "Local File System", "Guardrail state and historical cache")
    System_Ext(ci_runner, "GitHub Actions", "CI profiles for non-live and manual live test workflows")

    Rel(user, farm_monitor, "Uses weather dashboard", "Browser")
    Rel(dev, farm_monitor, "Runs app and tests", "Python/Streamlit")
    Rel(farm_monitor, vc_api, "Fetches forecast/current + historical bands", "HTTPS JSON")
    Rel(farm_monitor, om_api, "Fetches wind forecast/current", "HTTPS JSON")
    Rel(farm_monitor, local_sample, "Uses local sample data during fallback/sample modes", "Local JSON")
    Rel(farm_monitor, local_station, "Planned integration for microclimate live conditions", "HTTPS JSON/API (planned)")
    Rel(farm_monitor, indoor_sensors, "Planned integration for indoor/outdoor decision support", "Bridge/API (planned)")
    Rel(farm_monitor, inat_api, "Planned integration for biodiversity and trend context", "HTTPS API (planned)")
    Rel(farm_monitor, kitty_cam, "Planned integration for cat pen state and return-inference support", "Bridge/API events (planned)")
    Rel(farm_monitor, land_sat, "Planned integration for soil and land-condition context", "HTTPS API (planned)")
    Rel(farm_monitor, local_fs, "Reads/writes guardrail + historical cache", "JSON/CSV")
    Rel(dev, ci_runner, "Push/PR/manual dispatch", "GitHub")
    Rel(ci_runner, farm_monitor, "Executes test suites with runtime flags", "pytest")
```

## Context Narrative

- Primary actors are farm residents and stewards using the dashboard for human-reviewed daily decisions.
- Current live providers are Visual Crossing (primary weather + historical band) and Open-Meteo (wind enrichment/override).
- Local sample payloads and local filesystem state are significant context dependencies for fallback reliability.
- Planned context integrations include local weather station feeds, indoor sensors via bridge, iNaturalist, kitty camera events, and land satellite data.
- CI is part of the system context due to enforced runtime profile behavior and live/non-live test separation.

## Key Constraints

- API usage is constrained by development guardrails (budget + cooldown).
- Non-live test workflows must not hit external network APIs.
- Production profile must remain live-data capable.
