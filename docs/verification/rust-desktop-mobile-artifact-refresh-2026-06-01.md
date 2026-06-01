# Rust Desktop/Mobile Artifact Refresh - 2026-06-01

Issue: #106
Related: #122, #107, #102

## What was refreshed

1. Post-#122 parity state was re-validated for:
- Desktop chart semantics and layer mapping.
- Mobile stacking/readability behavior.

2. Verification artifacts updated:
- `docs/verification/rust-main-dashboard-parity-constraints.md`
- `docs/verification/rust-parity-pass-fail-matrix-template.md`

## Desktop checks

1. Temperature chart now includes:
- target threshold line.
- historical context band + mean overlay.

2. Wind chart now includes:
- gust overlay.
- historical context band + mean overlay.

3. AQI chart now includes:
- explicit observed->forecast split marker and label.

4. Brightness chart now includes:
- explicit right-axis line and left/right axis communication.

## Mobile checks

1. One-column card flow is retained under responsive breakpoints.
2. Metrics/cards stack to a single column to preserve readability.
3. Chart blocks preserve axis labels and legend chips without requiring horizontal section reflow.

## Acceptance statement

#106 acceptance criteria are satisfied with these refreshed artifacts and matrix outcomes.
Remaining closure steps proceed in #107 and #102.
