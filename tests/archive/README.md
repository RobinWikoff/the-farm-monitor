# Archived Python Tests

These tests were written for the Python/Streamlit implementation of the Farm Monitor dashboard (`app.py`).

The Python app was formally decommissioned on **2026-06-25** (Phase D, issue [#95](https://github.com/RobinWikoff/the-farm-monitor/issues/95)) when the Rust/Axum service went live on the Pi.

## Why archived (not deleted)

- Historical reference: the test logic documents expected Python app behavior that served as the parity baseline for the Rust migration.
- `test_guardrail_config_sanity.py` documents the runtime profile system and CI env var contract that was designed during Phase A.

## Active test suite

Rust tests live in `rust/crates/*/src/` (inline `#[cfg(test)]` modules), run via `cargo test --workspace`.

## Files

| File | What it tested |
|---|---|
| `conftest.py` | HTTP request blocking fixtures for non-live test runs |
| `test_core_logic.py` | Core Python app functions: temp trend, runtime config, forecast fetch, guardrails |
| `test_guardrail_config_sanity.py` | Runtime profile resolution and CI env var contract |
| `test_integration_live_api.py` | Live Visual Crossing API integration (opt-in, uses real API key) |
