# The Farm Monitor: Design and Implementation of a Personalized Agro-Environmental Dashboard Using Publicly Available Weather and Air Quality APIs

**Robin Wikoff**  
Independent Researcher, Loveland, Colorado  
[Draft — April 2026]

---

## Abstract

Small and hobby-scale agricultural operations lack access to tailored, real-time environmental monitoring tools that reflect their specific physical location and operational priorities. Commercial weather applications present generalized data without accommodation for farm-specific thresholds, livestock comfort indices, or historically contextualized forecasts. This paper describes the design, implementation, and iterative development of *The Farm Monitor*, a web-based environmental monitoring dashboard built with Python and Streamlit, targeting a single farm location in Loveland, Colorado (40.3720°N, 105.0579°W). The system integrates real-time forecast and current conditions data, five-year historical comparison bands, air quality index (AQI) monitoring with pollutant breakdowns, and farm-relevant status indicators including a seasonal temperature goal tracker and an animal comfort index. A three-tier fallback architecture ensures dashboard availability during provider outages or rate-limit events. The application is deployed via Streamlit Cloud and uses a developer API cost governance layer to bound quota consumption during iterative development. Thirteen discrete feature areas were implemented across multiple development iterations, with the development process itself conducted using AI-assisted (GitHub Copilot) pair programming within a structured CI/CD pipeline. Results demonstrate that publicly available weather APIs, when queried against precise coordinates and enriched with farm-specific logic, can serve as a viable foundation for personalized agricultural monitoring at near-zero marginal cost. Future work includes integrating the UOR Framework PRISM backend as a formal resolver layer to introduce certifiable, traceable environmental assessments.

---

## 1. Introduction

Agricultural operations of all scales are acutely sensitive to environmental conditions. Temperature extremes affect crops, livestock, and infrastructure. Precipitation drives planting and harvest decisions. Wind, humidity, and air quality affect animal health, equipment operation, and outdoor labor safety. For large commercial farms, dedicated agrometeorological services and on-site sensor networks are economically justified. For small farms, hobby farms, and homesteads, such resources are typically cost-prohibitive, leaving operators to rely on general-purpose weather applications that present conditions at airport weather stations often tens of kilometers from the farm itself.

The gap motivating this work is the absence of a low-cost, highly personalized, farm-centric environmental monitoring tool. A suitable tool should: (1) pull from data sources with sufficient precision for a specific latitude/longitude; (2) contextualize current conditions against multi-year historical baselines relevant to day-of-year; (3) present farm-relevant composite indicators such as seasonal temperature goals and outdoor comfort indices for both people and animals; (4) incorporate air quality data given the increasing prevalence of wildfire smoke events in the Western United States; and (5) degrade gracefully when upstream data providers are unavailable, rather than presenting a blank or error-state interface.

This paper presents *The Farm Monitor*, a purpose-built environmental dashboard addressing these requirements. The system was developed in an iterative, feature-by-feature manner beginning in early 2026. The development methodology itself is of scientific interest: the system was built using GitHub Copilot, a large-language-model (LLM) based AI pair programming agent, through a structured conversational development process in which the human operator specified features in natural language and the AI agent produced, tested, and validated code implementations. This methodology allowed a single developer with a non-traditional software background to produce a production-deployed, fully tested, CI/CD-compliant application.

The remainder of this paper is organized as follows: Section 2 describes the materials (data sources, tooling, infrastructure) and methods (system architecture, development process, feature design); Section 3 presents the results (implemented feature set and system behavior); Section 4 discusses limitations, design decisions, and future directions including planned integration with the UOR Framework.

---

## 2. Materials and Methods

### 2.1 Target Site

The Farm Monitor is designed for a specific property in Loveland, Colorado, United States. The fixed geographic coordinates used for all API queries are latitude 40.3720°N, longitude 105.0579°W, elevation approximately 1,500 m above sea level. The climate is semi-arid with cold winters, hot summers, strong seasonal wind patterns, and susceptibility to wildfire smoke intrusion from regional fires. These site characteristics directly motivated the selection and prioritization of monitoring features.

### 2.2 Data Sources

**Primary weather and air quality data** are sourced from the Visual Crossing Timeline API (Visual Crossing Corporation, Malvern, PA). The API returns a single JSON payload containing current conditions and hourly forecasts for up to a 15-day window, including temperature, feels-like temperature, wind speed, wind gust, wind direction, precipitation probability, precipitation accumulation, snow, humidity, and air quality index (AQI) alongside individual pollutant concentration estimates (PM2.5, PM10, ground-level ozone [O₃], nitrogen dioxide [NO₂], sulfur dioxide [SO₂], and carbon monoxide [CO]) when reported. AQI values are model-gridded estimates for the query coordinates and do not correspond to readings from a single physical sensor station.

**Historical comparison data** are also sourced from the Visual Crossing Timeline API, retrieving the same calendar day across the five preceding years (five-year lookback). Hourly temperature (actual and feels-like) and wind speed data from these five historical years are aggregated into hourly statistical bands (daily high, mean, and low) providing empirical context for the current-day forecast.

**Supplemental wind data** from Open-Meteo (Open-Meteo AG, Switzerland) were integrated in early development versions to provide higher-resolution wind speed, gust, and direction estimates. This source is retained in the data pipeline as an optional override layer. Open-Meteo makes no API key requirement for the resolution level used.

**Local sample data** consisting of a representative weather dataset is stored directly in the repository and used for development and testing without consuming live API quota.

### 2.3 Application Stack

The application is implemented in Python 3.11. Core dependencies include:

- **Streamlit** (>= 1.32): web interface rendering, session state management, secrets management, and cloud deployment.
- **Pandas**: tabular data handling, time series aggregation, and historical band computation.
- **Altair**: declarative chart rendering for all time-series visualizations.
- **Requests**: HTTP client for all external API calls.
- **PyTZ**: timezone normalization for Mountain Time (US/Mountain).
- **ReportLab**: PDF generation for the complementary memo template feature.

Code quality enforcement uses **Ruff** for both formatting and linting (pycodestyle, Pyflakes, PEP 8 compliance). All checks run in CI on each push and pull request via GitHub Actions. **Pytest** provides the automated test suite (unit and integration tests). A live integration test tier requiring explicit opt-in tokens is segregated from the default non-live CI run.

### 2.4 Runtime Profile and API Governance

The application resolves a runtime profile from environment variables and secrets, yielding one of five operating modes: `prod`, `dev-safe`, `dev-live`, `ci-non-live`, and `ci-live-manual`. This profile governs whether live API calls are permitted and whether developer guardrails apply.

In development modes with live API access enabled, a **developer API cost governance layer** tracks per-provider call counts, blocked attempts, and cooldown windows. Daily call budgets are configurable per provider (defaults: 12 Visual Crossing forecast/current calls, 3 Visual Crossing historical calls, 24 Open-Meteo wind calls). After a provider returns HTTP 429 (rate limit exceeded), a configurable cooldown window (default 30 minutes) is imposed before further calls. State persists to a local JSON file (`.streamlit/guardrails/dev_api_state.json`) scoped to the calendar day. This mechanism prevents unintentional quota exhaustion, particularly during rapid iterative development sessions where the dashboard may be repeatedly refreshed.

### 2.5 Resilience and Fallback Architecture

The data pipeline implements a three-tier fallback pattern for each data category:

1. **Live API call**: attempted when guardrails permit.
2. **Session state cache**: the most recent successful API payload is preserved in Streamlit session state; displayed with a user-visible warning banner identifying the age of cached data on subsequent cache hits.
3. **Emergency local sample data**: a hard-coded local data file is loaded as a last resort, ensuring the dashboard never presents a blank screen.

For the historical comparison band specifically, an additional disk-based cache layer with a seven-day TTL reduces API calls against the five-year query window, which is expensive in terms of Visual Crossing record consumption.

User-facing messaging distinguishes between a general API outage, a developer budget exhaustion event, and a developer cooldown block, providing operational transparency in all states.

### 2.6 Development Methodology

Development was conducted in GitHub Codespaces, a cloud-hosted IDE environment. Feature implementation proceeded through structured conversational sessions with GitHub Copilot, a code generation and agentic AI system. The developer specified desired features and behaviors in natural language; the AI agent executed file reads, code modifications, shell commands, test runs, and git operations within the Codespace environment.

This methodology constitutes a form of **AI-assisted iterative software development** in which the human operator functions as product owner and domain expert while the AI agent acts as the primary implementation developer. Development conversations were logged as structured JSON transcripts and are retained in the repository under `docs/chat_history/`. These logs constitute a primary record of design decisions, implementation rationale, and the evolution of system requirements.

Feature development followed a consistent cycle: (1) human-specified feature description; (2) agent inspection of existing code; (3) implementation; (4) local validation by the human operator in a running Streamlit instance; (5) CI verification; (6) pull request with issue-closing commit message. Git branches were created per feature or issue, and Ruff formatting/linting was enforced before merge.

Architecture documentation follows the **C4 model** (Context, Container, Component, Code levels), stored in `docs/c4/` and rendered from Mermaid diagram source.

---

## 3. Results

### 3.1 Feature Set

Thirteen discrete feature areas were implemented and are currently operational:

**Feature 1 — Runtime Profile Resolution.** The application resolves its operating mode from environment variables and secrets at startup. Invalid combinations produce runtime validation errors rather than silent fallbacks, enforcing configuration discipline.

**Feature 2 — Developer API Guardrails.** Per-provider daily call budgets and post-429 cooldown windows are enforced in development modes. A sidebar panel displays current usage, blocked counts, and cooldown status, with controls to reset state for a new development session.

**Feature 3 — Forecast and Current Conditions Ingestion.** A single Visual Crossing Timeline API request retrieves the hourly forecast and current conditions. The parser extracts temperature, feels-like temperature, wind speed and direction, precipitation probability and accumulation, snow status, humidity, and AQI with pollutant fields. Rows with missing wind direction are retained with `WindDir = Unknown` rather than discarded, preventing data loss on rows with valid temperature data.

**Feature 4 — Historical Comparison Band.** The same calendar date over the preceding five years is queried and aggregated into hourly statistical envelopes (high/mean/low) for temperature, feels-like temperature, and wind speed. Leap-year edge cases (February 29 in non-leap query years) are handled by rollback to February 28. API calls stop on the first 429 response; available years are used for partial bands.

**Feature 5 — Wind Source Override.** Open-Meteo current and hourly wind fields replace Visual Crossing wind fields when available, allowing use of the higher-resolution wind model.

**Feature 6 — Outage Fallback.** The three-tier fallback architecture (live → session cache → local sample) is implemented for forecast, historical band, and wind data streams independently. Banner messaging distinguishes failure modes.

**Feature 7 — Temperature Operand Toggle.** The user may display *Actual* temperature or *Feels Like* temperature as the primary operand for all metrics and charts. The current-hour value is always overridden with the live `currentConditions` value from the API.

**Feature 8 — Seasonal Status Banner.** The operator selects a monitoring mode (*Winter: Warming Focus* or *Summer: Cooling Focus*) and a daily temperature threshold. In Warming Focus, the banner reports success when the current temperature meets or exceeds the threshold; in Cooling Focus, when it meets or falls below. If the threshold is not yet met but will be reached later today, the banner reports an informational state with the projected hour. Otherwise a warning state is shown.

**Feature 9 — Kitty Comfort Index.** A composite outdoor comfort assessment for a small animal (domestic cat) evaluates three components: temperature (comfortable in the range 32–85°F), wind (comfortable when maximum of speed and gust ≤ 5 mph), and precipitation (comfortable only when no active rain or snow is reported). The overall banner is in a success state only when all active component checks pass.

**Feature 10 — Wind Analytics Section.** Current wind speed, wind direction, fastest observed wind, and strongest gust are displayed with one-hour delta indicators. Charts render observed vs. forecast wind speed with an optional gust overlay and historical wind band.

**Feature 11 — Precipitation Section.** Recent rainfall and snowfall status, total daily accumulation, current precipitation probability, and current humidity are displayed. An hourly actual precipitation chart is rendered.

**Feature 12 — Air Quality Section.** AQI values from the Visual Crossing data stream are interpreted into the US EPA categorical scale (Good, Moderate, Unhealthy for Sensitive Groups, Unhealthy, Very Unhealthy, Hazardous). Current, daily high, and daily low AQI are displayed with their corresponding hours and interpretive labels. A time-series chart overlays observed and forecasted AQI values, and a pollutant breakdown table reports PM2.5, PM10, O₃, NO₂, SO₂, and CO concentrations; values absent from the API response are marked as *Not reported by source* with an explanatory note, distinguishing API non-reporting from true-zero conditions.

**Feature 13 — Data Source Transparency Panel.** A collapsible panel explains the role of each data provider, the blended nature of the AQI gridded model, and the source of the historical band, enabling the operator to reason about data provenance and limitations.

### 3.2 System Availability and Resilience Behavior

The fallback architecture was validated through intentional budget exhaustion tests during development. When the Visual Crossing forecast budget was depleted, the dashboard continued to render the most recent session-cached conditions without presenting a blank state, with a yellow warning banner indicating data freshness. When no session cache existed and the budget was exhausted, the emergency local sample data was loaded with a prominent error banner. Distinct messaging for budget exhaustion vs. general outage vs. cooldown block was confirmed to render correctly in each condition.

The P1 production incident documented in the chat history (`chat04.json`) revealed that a timestamp formatting regression in the data parsing layer caused a silent row-exclusion failure, resulting in empty chart sections. This class of failure was resolved by adding explicit regression tests for the relevant field and by reviewing the fallback logging behavior to improve future detectability.

### 3.3 API Cost Profile

Under the default developer guardrail configuration, a single full development session refreshing the app at moderate frequency consumes fewer than 12 Visual Crossing forecast-equivalent records and fewer than 3 historical band record queries per day. The Streamlit forecast cache TTL (10 minutes) and seven-day historical band disk cache substantially reduce call volume relative to raw page refresh rates. This cost profile makes iterative development feasible within the free tier of the Visual Crossing API.

### 3.4 Architecture Documentation

The system is documented through C4-model architecture files at all four levels (system context, container diagram, component diagram, and code-level diagram) plus a UI feature map. These are stored as Mermaid-diagram source files in `docs/c4/` and rendered to SVG/PNG for distribution. Architecture documentation is maintained under a same-PR update policy: any PR that changes feature behavior is required to update the relevant C4 files and feature requirements document in the same merge.

---

## 4. Discussion

### 4.1 Viability of Publicly Available APIs for Farm-Scale Monitoring

The central finding of this work is that publicly available, coordinate-queried weather APIs—specifically the Visual Crossing Timeline API—provide sufficient data density and feature coverage for a meaningful farm-scale environmental monitoring application at negligible marginal cost. The single-endpoint design of the Visual Crossing API, which returns current conditions, hourly forecasts, and historical year-over-year data from the same base URL, proved particularly suitable for a single-location dashboard application: it minimizes request overhead while providing co-registered, internally consistent data across time windows.

A specific limitation emerged with respect to air quality data. AQI values returned by the Visual Crossing API are grid-cell model estimates rather than readings from a known physical sensor station. It is not possible, from the API response, to identify which monitoring station contributed to the AQI value, or to assess the vintage of the underlying measurement. For regulatory or precision agricultural purposes, this limitation would require augmentation with station-level EPA AirNow API data or direct sensor deployment. For the intended use case—awareness of general air quality conditions affecting outdoor work and animal welfare—the gridded estimate is operationally sufficient.

### 4.2 The Kitty Comfort Index as a Domain Adaptation Pattern

The Kitty Comfort composite indicator illustrates the core design principle of the application: translating generic meteorological data into farm-specific, semantically meaningful composites. Rather than displaying raw temperature and wind speed independently, the index synthesizes three conditions against thresholds calibrated to the specific thermal and wind tolerance profile of the monitored animal. This pattern—composite threshold evaluation over multiple environmental variables—is generalizable to livestock heat stress indices, irrigation scheduling thresholds, pest pressure models, and crop thermal accumulation units (growing degree days). The current implementation provides the architectural template; future development will extend this pattern to additional farm-relevant composites.

### 4.3 AI-Assisted Development Methodology

The development of The Farm Monitor using conversational AI-agent pair programming is noteworthy as a methodology. Across five documented chat sessions totaling over 70 discrete development interactions, the agent (GitHub Copilot) executed the full spectrum of software development tasks: reading and reasoning about existing code, implementing new features, running tests, resolving merge conflicts, debugging production regressions, writing CI-compliant code under Ruff formatting constraints, and producing documentation including architecture diagrams. The human developer's role was primarily that of product owner: specifying requirements in natural language, conducting validation in a running application, making strategic decisions (e.g., which branch to use, whether to merge or iterate), and exercising critical judgment when agent suggestions were incorrect (as documented in chat3, request 15, where the agent incorrectly described AQI data as station-specific; the human corrected this and the agent updated its understanding for the remainder of the session).

This collaboration suggests that LLM-based development agents, when operating within a well-structured project (CI enforcement, clear conventions, documented feature requirements), can sustain production-quality iterative development across multi-session, multi-feature work. Limitations observed include: occasional hallucination of correct execution in terminal operations that had not actually succeeded (requiring human verification in the running app), and a tendency to conflate stale process state with merged code behavior during the production outage incident.

### 4.4 Future Direction: UOR Framework PRISM Integration

The planned next architectural phase documented in `docs/uor/` introduces a three-layer system model: the existing Streamlit application as UI/App layer, a new PRISM integration module in this repository as an adapter/orchestrator, and the UOR Framework as an external resolver backend. The UOR Framework (under development by external collaborators) provides formally specified resolver semantics, including the production of cryptographically bound certificates and execution traces alongside computation results.

For The Farm Monitor, the target proof-of-integration use case is the AQI resolver pathway: user-provided query parameters would be mapped into a typed PRISM request payload, dispatched to the UOR backend, and the returned certificate and trace rendered in the UI alongside the resolved AQI assessment. This would represent a significant advance in data provenance: rather than displaying an opaque API-sourced number, the dashboard would display a formally certified environmental assessment with a traceable computation history.

Architecture Decision Record ADR-0001 formally documents the decision to adopt a **service boundary** integration mode (external service call over HTTP with typed contracts) as the first implementation step, deferring higher-complexity options (embedded CLI execution, native Python-Rust bindings) until the contract surface stabilizes.

### 4.5 Limitations

Several limitations constrain the current system. First, the geographic specificity of the application—it is hardcoded to lat/lon coordinates of a single farm—means it is not directly generalizable without modification. Parameterization of the target location is a straightforward engineering task but has not been prioritized. Second, the system depends entirely on third-party API availability and accuracy; no on-site physical sensors are included, meaning the displayed conditions are model-derived estimates. Third, the historical comparison band relies on the same forecast provider's archive, creating a single-source band that does not capture inter-provider uncertainty. Fourth, the Kitty Comfort Index uses fixed thresholds that are not calibrated against any empirical study of feline thermal comfort; they represent the operator's practical judgment and should not be generalized to other species or contexts without revision.

---

## 5. Conclusion

The Farm Monitor demonstrates that a small agricultural operation can implement a highly personalized, real-time, multi-variable environmental monitoring dashboard using freely available APIs, open-source tooling, and AI-assisted development, at near-zero recurring infrastructure cost. The thirteen implemented feature areas provide operational coverage of temperature, wind, precipitation, air quality, seasonal goal tracking, and animal comfort relevant to a high-altitude semi-arid farm in Colorado. The three-tier fallback architecture ensures dashboard availability during API disruptions. The AI-assisted development methodology employed here compressed a development timeline that would conventionally require substantial software engineering effort into a series of focused conversational sessions, while maintaining CI/CD discipline, automated test coverage, and formal documentation. Future integration of the UOR Framework PRISM backend will introduce formally resolved, certificate-bearing environmental assessments as the system matures toward a rigorous agro-environmental intelligence platform.

---

## References

1. Visual Crossing Corporation. *Visual Crossing Weather Timeline API Documentation*. Retrieved April 2026 from https://www.visualcrossing.com/resources/documentation/weather-api/timeline-weather-api/

2. Open-Meteo AG. *Open-Meteo Free Weather API Documentation*. Retrieved April 2026 from https://open-meteo.com/en/docs

3. United States Environmental Protection Agency. *Air Quality Index (AQI) — A Guide to Air Quality and Your Health*. EPA-456/F-14-002. Office of Air Quality Planning and Standards, 2014.

4. Brown, T., et al. *Language Models are Few-Shot Learners*. Advances in Neural Information Processing Systems, 2020. (foundational reference for LLM code generation capability)

5. Simon, P. *The C4 Model for Visualising Software Architecture*. leanpub.com/visualising-software-architecture, 2018.

6. Kotsis, S.V. and Chung, K.C. A Guide for Writing in the Scientific Forum. *Plastic and Reconstructive Surgery* 126(5):1763–71, 2010.

7. Wikoff, R. *The Farm Monitor — Repository and Development Logs*. GitHub: RobinWikoff/the-farm-monitor. Accessed April 2026.

---

*Correspondence: This paper was drafted using GitHub Copilot (Claude Sonnet 4.6) based on project source code, architecture documentation, feature requirement specifications, and AI-developer chat session transcripts archived at `docs/chat_history/`.*
