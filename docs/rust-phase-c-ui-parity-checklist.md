# Rust Phase C UI Parity Checklist

Issue reference: #94
Scope: Rust migration Phase C, dashboard section migration and parity review.

## Section Parity
- [x] Temperature Trend section rendered with hourly values.
- [x] Current Conditions section rendered with live-like current metrics.
- [x] Wind Outlook section rendered with observed/forecast split and trend metrics.
- [x] Precipitation section rendered with accumulation, probability, humidity, and hourly rows.
- [x] Air Quality section rendered with current/high/low AQI, interpretation, and pollutant breakdown.
- [x] Sunrise / Sunset / Brightness section rendered with timing metrics and UV/cloud dual-axis semantics.
- [x] Data Sources section rendered with source metadata and generated timestamp.

## Behavior Parity Notes
- [x] Observed vs forecast semantics are present for wind and AQI rows.
- [x] Legend and axis intent is represented for brightness (UV left-axis semantics, cloud right-axis semantics).
- [x] Hour-level trend/summary metrics are present for wind and AQI.

## Intentional Deviations (Documented)
- Rust dashboard currently uses server-rendered HTML tables and bar indicators rather than embedded Altair charts.
- Provider data for Phase C remains normalized/mock-backed for migration progress; live provider parity will be completed in later milestones.
- Visual parity is behavior-first in this phase; exact chart styling and interactions are tracked as follow-up polish.

## Validation
- Rust quality gates:
  - `cargo fmt --all`
  - `cargo clippy --workspace --all-targets --all-features -- -D warnings`
  - `cargo test --workspace --all-features`
- Checklist reviewed against issue #94 acceptance criteria.
