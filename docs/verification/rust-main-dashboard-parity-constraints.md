# Rust vs Main Dashboard Comprehensive Constraints and Requirements

Date: 2026-05-27
Parent issue: #102
Purpose: define a canonical, traceable constraints and requirements baseline for Rust parity work, using docs, wiki, chat-history signals, issues, and PR evidence.

## 1) Source Plan

### 1.1 Authoritative functional sources
- `app.py` (user-visible behavior source of truth)
- `docs/feature-requirements.md` (feature contract)
- `docs/verification/rust-main-dashboard-parity-constraints.md` (this canonical parity baseline)

### 1.2 Supporting markdown sources in docs
- `docs/Model_documentation_process.md`
- `docs/ProcessPreferencesNotes.md`
- `docs/feature-requirements.md`
- `docs/ops.md`
- `docs/rust-phase-c-ui-parity-checklist.md`
- `docs/scientific-paper-draft.md`
- `docs/uor/adr-0001-uor-backend-integration-mode.md`
- `docs/uor/issue-9-followup-issues.md`
- `docs/uor/issue-9-uor-evaluation.md`
- `docs/c4/README.md`
- `docs/c4/c1-system-context.md`
- `docs/c4/c2-container-diagram.md`
- `docs/c4/c3-component-diagram.md`
- `docs/c4/c4-code-level-diagram.md`
- `docs/c4/c4-ui-feature-map.md`
- `docs/c4/wiki-page-2-c4-descriptions-draft.md`
- `docs/c4/.maintenance/latest-c4-update-report.md`
- `docs/c4/.maintenance/wiki-c4-embed-snippets.md`
- `docs/verification/rust-102a-layout-parity-notes.md`
- `docs/verification/rust-parity-pass-fail-matrix-template.md`

### 1.3 Chat history sources (supplemental signals)
- `docs/chat_history/chat01.json`
- `docs/chat_history/chat02.json`
- `docs/chat_history/chat03.json`
- `docs/chat_history/chat04.json`
- `docs/chat_history/chat05.json`

Use rule: chat history can inform recurring pain points and acceptance expectations, but does not override explicit contracts in `docs/feature-requirements.md` or `app.py`.

### 1.4 Wiki sources
- `the-farm-monitor.wiki/Home.md`
- `the-farm-monitor.wiki/Model-Purpose-and-Problem.md`
- `the-farm-monitor.wiki/Model-Architecture-and-Behavior.md`
- `the-farm-monitor.wiki/Model-Validation-and-Evidence.md`
- `the-farm-monitor.wiki/Model-Limitations-and-Risks.md`
- `the-farm-monitor.wiki/Model-Change-Log-and-Traceability.md`
- `the-farm-monitor.wiki/Model-Documentation-Process.md`

### 1.5 Traceability sources from GitHub

Issues (primary parity chain):
- #94, #102, #103, #104, #105, #106, #107

PRs (primary parity chain):
- #99, #100, #101, #108

Related historical behavior evidence:
- Issues #1, #2, #3, #4, #7, #17, #22, #25, #30, #32, #34, #41, #43, #44, #45, #47, #50, #52, #55, #57, #58, #67, #69, #70, #83, #87, #88
- PRs #31, #35, #42, #46, #48, #49, #51, #53, #54, #56, #59, #60, #61, #65, #71, #72, #84, #85, #87, #88

## 2) Constraint Levels
- P0 (must match before #102 close): controls, section ordering, metric semantics, banner decision logic, chart intent and legend semantics.
- P1 (strongly expected in #102B/#102C): formatting/typography/table conventions, transparency panel quality, fallback messaging nuance.
- P2 (allowed deferred with explicit approval): visual polish and non-critical interactions.

## 3) Comprehensive Constraints and Requirements

### 3.1 Runtime, controls, and profile context (P0)
REQ-001: include controls equivalent to monitoring mode, temperature type (Feels Like vs Actual), and kitty wind cutoff.
REQ-002: show runtime/profile context (profile, data mode, live API on/off) or documented equivalent.
REQ-003: invalid runtime combinations must fail loud, not silently degrade.

### 3.2 Core section order and hierarchy (P0)
REQ-010: section order must match main behavior flow:
1. Kitty comfort banner
2. Temperature metrics + trend + seasonal status + temperature chart
3. Wind banner + wind metrics + wind chart
4. Precipitation metrics + chart
5. Air Quality metrics + chart + pollutant table
6. Sunrise/Sunset/Brightness metrics + chart + legend
7. Data-source transparency panel

### 3.3 Temperature and seasonal behavior (P0)
REQ-020: Feels Like vs Actual switch drives now/high/low and chart series.
REQ-021: 1-hour delta uses "since HH:00" semantics.
REQ-022: winter/summer seasonal status logic must preserve success/info/warning branches.
REQ-023: historical-band intent preserved when data is available.

### 3.4 Kitty comfort behavior (P0)
REQ-030: comfort combines temperature range, wind threshold, and active rain/snow status.
REQ-031: temperature comfort semantics: $32 < temp \le 85$.
REQ-032: wind comfort uses max(speed, gust) only when wind data exists.
REQ-033: banner must present overall outcome plus per-condition explanation.

### 3.5 Wind behavior and visuals (P0)
REQ-040: wind banner includes fastest wind and cutoff warning behavior.
REQ-041: wind metrics include speed now (with delta), direction, fastest wind, strongest gust.
REQ-042: wind chart semantics preserve observed vs forecast split, gust overlay, and historical-band intent.

### 3.6 Precipitation behavior and visuals (P0)
REQ-050: rain/snow recently is based on observed actual hours, not current hour only.
REQ-051: include total accumulation so far, precip probability now, and humidity now.
REQ-052: hourly precipitation chart intent and caption semantics preserved.

### 3.7 Air quality behavior and visuals (P0)
REQ-060: include current/high/low AQI and AQI interpretation category.
REQ-061: AQI chart preserves observed vs forecast semantics.
REQ-062: pollutant breakdown representation must support missing values using "Not reported by source" equivalent semantics.

### 3.8 Brightness behavior and visuals (P0)
REQ-070: include sunrise/sunset/daylight metrics and yesterday deltas.
REQ-071: include peak UV metric with interpretation.
REQ-072: preserve dual-axis intent (UV left axis, cloud cover right axis) and explicit legend semantics.

### 3.9 Data transparency and fallback messaging (P1)
REQ-080: data-source panel should explain provider roles and blended-model caveats.
REQ-081: include refresh cadence expectations where practical.
REQ-082: fallback messaging should distinguish outage vs guardrail budget block vs cooldown.
REQ-083: if simplified in Rust, differences must be documented as approved deviations.

### 3.10 Quality and governance gates
REQ-090: Rust quality gates required for parity PRs:
- `cargo fmt --all`
- `cargo clippy --workspace --all-targets --all-features -- -D warnings`
- `cargo test --workspace --all-features`

REQ-091: behavior changes must update documentation and traceability artifacts in the same PR or explicitly declare no doc impact.

## 4) Overlap and Conflict Notes

### 4.1 Overlap highlights
- Strong overlap: `docs/feature-requirements.md` + `app.py` + parity issues/PRs (#94/#102-#108) for dashboard behavior.
- Strong overlap: C4 docs and wiki architecture pages for system boundaries and responsibility split.
- Strong overlap: ops/process docs and guardrail-related issues/PRs for runtime safety constraints.

### 4.2 Current ambiguities to resolve
- Brightness/UV behavior is strongly present in `app.py` and issue/PR history (#2, #88), but is under-specified in `docs/feature-requirements.md`.
- P0 vs P1 boundary for data-source transparency wording quality requires explicit acceptance wording in #102 closure.
- "Recently" for rain/snow should be kept as observed-hours based; if a strict time window is introduced later, it must be versioned in requirements.

## 5) Issue and PR Traceability Map

### 5.1 Parity decomposition map
| Scope | Issue | PR Evidence | Status |
|---|---|---|---|
| Phase C umbrella | #94 | #99, #100, #101 | Closed |
| Follow-up parity umbrella | #102 | #108 (active chain start) | Open |
| Shell/layout parity | #103 | #108 | In progress |
| Section formatting parity | #104 | TBD | Open |
| Chart-like treatment parity | #105 | TBD | Open |
| Artifact refresh | #106 | TBD | Open |
| Final signoff and closure | #107 | TBD | Open |

### 5.2 Historical feature lineage (selected)
| Feature area | Foundational issue(s) | Implementing PR(s) |
|---|---|---|
| Real vs Feels Like | #1 | legacy chain prior to current parity cycle |
| Sunrise/Sunset/Brightness | #2 | #88 |
| Kitty comfort thresholds | #3, #67 | #61, #87 |
| Precipitation/humidity section | #4, #41, #83 | #42, #84, #85 |
| Wind section and semantics | #25, #32 | #46 and related chain |
| AQI and pollutant table | #7 | #65 |
| Guardrails and fallback resilience | #22, #30, #34, #44, #45, #50, #52, #55, #57, #58, #66, #70 | #31, #35, #49, #51, #53, #54, #56, #59, #60, #71, #72, #78 |

## 6) Acceptance Gate for #102 Closeout
Before closing #102, every requirement block in Section 3 must be marked in `docs/verification/rust-parity-pass-fail-matrix-template.md` as one of:
- PASS
- PASS with approved deviation
- FAIL

Merge-blocking rule: any P0 item marked FAIL blocks parity closeout until remediated or explicitly approved as deviation with linked issue and rationale.

## 7) Current Gap Snapshot (as of PR #108)
- Completed: shell/layout pass and parity framing artifacts.
- Missing/partial: control parity, kitty + seasonal banners, chart semantic parity, deeper transparency panel parity, and fallback messaging nuance parity.
