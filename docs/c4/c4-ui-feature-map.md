# C4 Supplementary: UI Feature → Backend Map

## Purpose

Show how each user-visible UI section connects to backend data sources, analytics, and fallback paths.

## High-Level Overview

```mermaid
---
title: UI Feature Map – High-Level Overview | Generated %%RENDER_DATE%%
---
flowchart TD
    subgraph EXT["External Systems"]
        direction LR
        VC["Visual Crossing API"]
        OM["Open-Meteo API"]
        FS[("Local File State")]
    end

    subgraph BE["Backend"]
        direction LR
        CFG["Runtime Config\n& Guardrails"]
        ING["Weather\nIngestion"]
        CACHE["Historical\nCache"]
        ANA["Analytics &\nInterpretation"]
        VIZ["Visualization\n& Banners"]
    end

    subgraph UI["Dashboard UI"]
        direction LR
        TEMP["Temperature\nMetrics · Banner · Chart"]
        COMFORT["Kitty Comfort\nBanner"]
        WIND["Wind\nSection · Chart"]
        PRECIP["Precipitation\nSection · Chart"]
        AQI["Air Quality\nSection · Chart · Table"]
        SYS["System\nSidebar · Sources · Dev"]
    end

    VC -->|HTTPS| ING
    OM -->|HTTPS| ING
    FS <-->|read/write| CFG
    FS <-->|read/write| CACHE

    SYS --> CFG
    CFG -->|allow/block| ING
    CACHE --> ING
    ING --> ANA
    ING --> VIZ
    ANA --> VIZ

    VIZ --> TEMP
    VIZ --> COMFORT
    VIZ --> WIND
    VIZ --> PRECIP
    VIZ --> AQI

    classDef external fill:#e8f4fd,stroke:#2196F3,stroke-width:2px
    classDef backend fill:#fff3e0,stroke:#FF9800,stroke-width:2px
    classDef ui fill:#e8f5e9,stroke:#4CAF50,stroke-width:2px

    class VC,OM,FS external
    class CFG,ING,CACHE,ANA,VIZ backend
    class TEMP,COMFORT,WIND,PRECIP,AQI,SYS ui
```

## Domain Detail: Temperature

```mermaid
---
title: UI Feature Map – Temperature Domain | Generated %%RENDER_DATE%%
---
flowchart LR
    subgraph EXT["External"]
        vc_api(["Visual Crossing"])
    end

    subgraph BE["Backend"]
        vc_fetch["fetch_forecast\n_and_current()"]
        hist_fetch["fetch_historical\n_band()"]
        analytics["get_temp_trend()"]
        banners["render_status\n_banner()"]
        viz["build_chart()"]
    end

    subgraph UI["Temperature UI"]
        temp_metrics["Temperature Metrics\nNow / High / Low / Trend"]
        status_banner["Seasonal Status Banner\nWarming / Cooling Focus"]
        temp_chart["Temperature Chart\nForecast + Observed\n+ Historical Band"]
        sidebar["Sidebar Settings\nmode + threshold"]
    end

    vc_api --> vc_fetch
    vc_api --> hist_fetch

    vc_fetch --> temp_metrics
    analytics --> temp_metrics
    sidebar -->|"Feels Like / Actual"| temp_metrics

    vc_fetch --> status_banner
    banners --> status_banner
    sidebar -->|"mode + threshold"| status_banner

    vc_fetch --> temp_chart
    hist_fetch --> temp_chart
    viz --> temp_chart

    classDef external fill:#e8f4fd,stroke:#2196F3,stroke-width:2px
    classDef backend fill:#fff3e0,stroke:#FF9800,stroke-width:2px
    classDef ui fill:#e8f5e9,stroke:#4CAF50,stroke-width:2px

    class vc_api external
    class vc_fetch,hist_fetch,analytics,banners,viz backend
    class temp_metrics,status_banner,temp_chart,sidebar ui
```

## Domain Detail: Wind & Comfort

```mermaid
---
title: UI Feature Map – Wind & Comfort Domain | Generated %%RENDER_DATE%%
---
flowchart LR
    subgraph EXT["External"]
        vc_api(["Visual Crossing"])
        om_api(["Open-Meteo"])
    end

    subgraph BE["Backend"]
        vc_fetch["fetch_forecast\n_and_current()"]
        wind_fetch["fetch_wind\n_openmeteo()"]
        analytics["get_wind_trend()"]
        comfort["kitty_comfort\n_status()"]
        viz["build_wind_chart()"]
    end

    subgraph UI["Wind & Comfort UI"]
        wind_section["Wind Section\nSpeed / Direction\nGust / Fastest"]
        wind_chart["Wind Chart\nActual vs Forecast\n+ Gust + Historical"]
        kitty_banner["Kitty Comfort Banner\nTemp + Wind + Precip"]
    end

    vc_api --> vc_fetch
    om_api --> wind_fetch

    wind_fetch --> wind_section
    analytics --> wind_section

    wind_fetch --> wind_chart
    vc_fetch --> wind_chart
    viz --> wind_chart

    vc_fetch --> kitty_banner
    wind_fetch --> kitty_banner
    comfort --> kitty_banner

    classDef external fill:#e8f4fd,stroke:#2196F3,stroke-width:2px
    classDef backend fill:#fff3e0,stroke:#FF9800,stroke-width:2px
    classDef ui fill:#e8f5e9,stroke:#4CAF50,stroke-width:2px

    class vc_api,om_api external
    class vc_fetch,wind_fetch,analytics,comfort,viz backend
    class wind_section,wind_chart,kitty_banner ui
```

## Domain Detail: Precipitation

```mermaid
---
title: UI Feature Map – Precipitation Domain | Generated %%RENDER_DATE%%
---
flowchart LR
    subgraph EXT["External"]
        vc_api(["Visual Crossing"])
    end

    subgraph BE["Backend"]
        vc_fetch["fetch_forecast\n_and_current()"]
        viz["build_chart()"]
    end

    subgraph UI["Precipitation UI"]
        precip_section["Precipitation Section\nRain/Snow\nAccumulation / Probability"]
        precip_chart["Precipitation Chart\nHourly Actual"]
    end

    vc_api --> vc_fetch
    vc_fetch --> precip_section
    vc_fetch --> precip_chart
    viz --> precip_chart

    classDef external fill:#e8f4fd,stroke:#2196F3,stroke-width:2px
    classDef backend fill:#fff3e0,stroke:#FF9800,stroke-width:2px
    classDef ui fill:#e8f5e9,stroke:#4CAF50,stroke-width:2px

    class vc_api external
    class vc_fetch,viz backend
    class precip_section,precip_chart ui
```

## Domain Detail: Air Quality

```mermaid
---
title: UI Feature Map – Air Quality Domain | Generated %%RENDER_DATE%%
---
flowchart LR
    subgraph EXT["External"]
        vc_api(["Visual Crossing"])
    end

    subgraph BE["Backend"]
        vc_fetch["fetch_forecast\n_and_current()"]
        aqi_interp["aqi_interpretation()"]
        viz["build_chart()"]
    end

    subgraph UI["Air Quality UI"]
        aqi_section["AQI Section\nCurrent / High / Low\n+ Category"]
        aqi_chart["AQI Chart\nObserved vs Forecast"]
        pollutant_table["Pollutant Table\nPM2.5 / PM10 / O3\nNO2 / SO2 / CO"]
    end

    vc_api --> vc_fetch
    vc_fetch --> aqi_section
    aqi_interp --> aqi_section
    vc_fetch --> aqi_chart
    viz --> aqi_chart
    vc_fetch --> pollutant_table

    classDef external fill:#e8f4fd,stroke:#2196F3,stroke-width:2px
    classDef backend fill:#fff3e0,stroke:#FF9800,stroke-width:2px
    classDef ui fill:#e8f5e9,stroke:#4CAF50,stroke-width:2px

    class vc_api external
    class vc_fetch,aqi_interp,viz backend
    class aqi_section,aqi_chart,pollutant_table ui
```

## Guardrail & Config Flow

```mermaid
---
title: UI Feature Map – Guardrail & Config Flow | Generated %%RENDER_DATE%%
---
flowchart TD
    subgraph UI["Dev Controls"]
        sidebar["Sidebar Settings"]
        guardrail_controls["Guardrail Controls\nReset / Clear / Raw State"]
    end

    subgraph CFG["Configuration"]
        runtime["RuntimeConfig\nresolve_runtime_config()"]
        guardrails["Guardrails\ncheck_and_record\n_dev_api_request()"]
    end

    subgraph ING["Ingestion Gates"]
        vc_fetch["fetch_forecast_and_current()"]
        hist_fetch["fetch_historical_band()"]
        wind_fetch["fetch_wind_openmeteo()"]
        sample["_build_dev_sample_payload()"]
        hist_cache["HistoricalCache\n_load_hist_band_from_disk()"]
    end

    subgraph FS["Local File State"]
        guard_json[("guardrails.json")]
        hist_csv[("hist_cache/*.csv")]
    end

    sidebar -->|"profile display"| runtime
    guardrail_controls -->|"reset / clear"| guardrails

    runtime --> guardrails
    guardrails -->|"allow/block"| vc_fetch
    guardrails -->|"allow/block"| hist_fetch
    guardrails -->|"allow/block"| wind_fetch
    runtime -->|"force sample"| sample

    guardrails <-->|"read/write"| guard_json
    hist_cache <-->|"read/write"| hist_csv

    sample -.->|"emergency fallback"| vc_fetch
    hist_cache -.->|"disk fallback"| hist_fetch

    classDef ui fill:#e8f5e9,stroke:#4CAF50,stroke-width:2px
    classDef config fill:#fce4ec,stroke:#E91E63,stroke-width:2px
    classDef ingestion fill:#fff3e0,stroke:#FF9800,stroke-width:2px
    classDef storage fill:#e8f4fd,stroke:#2196F3,stroke-width:2px

    class sidebar,guardrail_controls ui
    class runtime,guardrails config
    class vc_fetch,hist_fetch,wind_fetch,sample,hist_cache ingestion
    class guard_json,hist_csv storage
```

## Feature → Data Source Matrix

| UI Feature | Visual Crossing | Open-Meteo | Historical Cache | Session State | Sample Data |
|---|---|---|---|---|---|
| Temperature Metrics | Primary | — | — | Fallback | Emergency |
| Seasonal Status Banner | Primary | — | — | Fallback | Emergency |
| Kitty Comfort | Primary | Wind data | — | Fallback | Emergency |
| Temperature Chart | Forecast lines | — | Historical band | Fallback | Emergency |
| Wind Section | Forecast wind | Live override | — | Fallback | Emergency |
| Wind Chart | Forecast wind | Live override | Historical band | Fallback | Emergency |
| Precipitation Section | Primary | — | — | Fallback | Emergency |
| Precipitation Chart | Primary | — | — | Fallback | Emergency |
| AQI Section | Primary | — | — | Fallback | Emergency |
| AQI Chart | Primary | — | — | Fallback | Emergency |
| Pollutant Table | Primary | — | — | Fallback | Emergency |
| Guardrail Controls | — | — | — | — | — |
| Data Sources Panel | Static | Static | — | — | — |

## Fallback Cascade

```mermaid
---
title: UI Feature Map – Fallback Cascade | Generated %%RENDER_DATE%%
---
flowchart LR
    subgraph FC["Forecast Path"]
        direction TB
        F1["Live API"] -->|fail| F2["Session Cache"]
        F2 -->|fail| F3["Sample Data"]
    end

    subgraph HC["Historical Path"]
        direction TB
        H1["Live API"] -->|fail| H2["Disk Cache"]
        H2 -->|fail| H3["Session Cache"]
        H3 -->|fail| H4["Unavailable caption"]
    end

    subgraph WC["Wind Path"]
        direction TB
        W1["Open-Meteo Live"] -->|fail| W2["Session Wind Cache"]
        W2 -->|fail| W3["Forecast wind only"]
    end

    classDef cascade fill:#fff3e0,stroke:#FF9800,stroke-width:2px
    class F1,F2,F3,H1,H2,H3,H4,W1,W2,W3 cascade
```
