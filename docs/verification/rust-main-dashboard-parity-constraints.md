# Rust Main Dashboard Parity Constraints

Last refreshed: 2026-06-01
Baseline commit: `9be79e0` (after PR #125 merge)
Scope chain: #122 -> #106 -> #107 -> #102

## Verification intent

This document captures the current parity constraints used to compare Rust `/dashboard` output against the Python main dashboard behavior.

## Must-match constraints

1. Section coverage parity
- Temperature, Wind, Air Quality, Precipitation, Brightness, Data Sources are present.

2. Observed/forecast semantics parity
- Temperature, Wind, and AQI charts split observed vs forecast by current-hour boundary.

3. Chart-layer semantic parity
- Temperature includes target threshold plus historical context (band + mean).
- Wind includes gust overlay plus historical context (band + mean).
- AQI includes explicit observed->forecast split marker and explanatory labels.
- Brightness dual-axis intent is explicit (UV left axis, cloud-cover right axis).

4. Control-strip parity
- Runtime mode selector, temperature basis selector, and wind cutoff input are visible and active.

5. Single-column layout parity guardrail
- Cards render in one-column flow for desktop and mobile to avoid layout drift.

## Allowed/approved deviation

1. Interaction model
- Approved deviation: static SVG semantics are accepted for Phase C parity.
- Not required for closure: Altair-style hover/inspection interactivity parity.

## Evidence anchors

1. Code anchors
- `rust/crates/farm-monitor-api/src/main.rs` chart builders and template/CSS markers.

2. Validation commands
- `cargo fmt --manifest-path rust/Cargo.toml --all`
- `cargo clippy --manifest-path rust/Cargo.toml --workspace --all-targets --all-features -- -D warnings`
- `cargo test --manifest-path rust/Cargo.toml -p farm-monitor-api`

3. Issue/PR traceability
- #122 closed via PR #125.
- Static vs interactive decision recorded in #122 comment on 2026-06-01.
