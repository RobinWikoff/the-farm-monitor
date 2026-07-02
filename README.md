# The Farm Monitor

A location-specific weather dashboard for a working farm in Loveland, CO — built to answer practical questions like "is it nice enough for the cats to be outside today?"

**Live:** [farm.robinwikoff.com/dashboard](https://farm.robinwikoff.com/dashboard)

---

## What It Does

The Farm Monitor pulls live data from the Visual Crossing Timeline API and renders an hourly dashboard covering temperature, wind, precipitation, air quality, UV index, and sunrise/sunset for a specific set of coordinates in Colorado. It applies threshold logic (configurable wind cutoff, seasonal temperature bands, kitty comfort score) to surface actionable summaries rather than raw numbers.

The service runs continuously on a Raspberry Pi 4 on the home network and is publicly reachable through a Cloudflare Zero Trust named tunnel — no inbound router ports opened.

---

## Tech Stack

| Layer | Technology |
|---|---|
| HTTP server | Rust · [Axum](https://github.com/tokio-rs/axum) 0.7 · Tokio async runtime |
| Weather data | Visual Crossing Timeline API (hourly forecast + current conditions) |
| Deployment | Raspberry Pi 4 · aarch64 · Raspberry Pi OS 64-bit |
| Public access | Cloudflare Zero Trust named tunnel |
| Charts | Server-side SVG rendered inline (no client-side JavaScript charting library) |
| CI | GitHub Actions — Rust CI (fmt + clippy + test), Ruff (Python linting) |
| Historical tooling | Python prototype (archived as `app.py`) |

---

## Architecture

The Rust service is organized as a [Cargo workspace](rust/) with three crates:

```
rust/crates/
  farm-monitor-domain/   # shared domain types (LocationRequest, health status)
  farm-monitor-data/     # provider trait, VC client, normalization pipeline, file cache
  farm-monitor-api/      # Axum HTTP server, dashboard HTML + SVG rendering
```

Data flow on each request:

```
VisualCrossingProvider::fetch_forecast()
  → ProviderForecastResponse  (raw API fields)
  → normalize_provider_response()
  → ForecastBundle  (clamped, rounded, normalized)
  → dashboard_html()
  → inline HTML + SVG served directly
```

The `WeatherProvider` trait makes mock and live providers interchangeable, which is how the rollback test path works: clear the API key, get mock data; restore it, get live data — no code changes required.

---

## Key Design Decisions

**Native async traits (AFIT) instead of `async_trait` macro**  
On the aarch64 release build, `async_trait` triggered dead-code elimination via `--gc-sections` in the linker, silently dropping trait impls at runtime. Switching to Rust 1.75+ native async fn in traits resolved this and removed the proc-macro dependency.

**Server-side SVG charts**  
The dashboard renders all charts as inline SVG strings on the server. This means the Pi serves a single self-contained HTML response with no CDN dependencies, no JavaScript framework, and no extra round-trips — important for reliability on home network hardware.

**Mountain Time as the canonical clock**  
Visual Crossing returns data keyed to `America/Denver`. The service uses `chrono-tz` to convert `Utc::now()` to Mountain Time before matching "current hour" against forecast data, avoiding the 6–7 hour offset that caused wrong "now" values when using UTC directly.

**File-based forecast cache**  
The provider writes a daily JSON cache to disk. This means a Pi reboot or API outage within a day still serves data from the morning's fetch rather than showing N/A across the board.

---

## Migration History: Python → Rust

**Initial implementation** was a Streamlit/Python dashboard (`app.py`). It proved out the feature set quickly: Visual Crossing API integration, hourly charts, threshold logic, historical comparison bands, AQI and UV sections. Streamlit Cloud handled hosting and gave a public URL for free with minimal infrastructure work.

**Why migrate to Rust:** As the normalization pipeline and SVG rendering logic grew, two problems emerged. First, Streamlit's execution model re-runs the entire script on every interaction, which added latency and made it harder to reason about state. Second, the Pi deployment target is resource-constrained — a persistent compiled Rust binary with a small memory footprint fits better than a Python runtime with a Streamlit framework stack. The migration was also a deliberate exercise in building the same feature set twice: once to learn what the domain actually requires, and once to implement it correctly in a systems language.

**Parity approach:** Rather than a big-bang rewrite, the migration used explicit phases with defined acceptance criteria. Each phase had to pass before the next started. The Python dashboard remained in production until Phase D's formal rollback test passed.

| Phase | What was built |
|---|---|
| A | Cargo workspace, domain types, mock data, full HTML dashboard rendering end-to-end |
| B | File-based daily forecast cache, data normalization pipeline, rollback infrastructure |
| C | VisualCrossing live provider via `WeatherProvider` trait, full UI parity sign-off |
| D | Production cutover, rollback test, Streamlit decommission, Cloudflare tunnel for public URL |

`app.py` is retained in the repo with an archive notice. Full migration rationale and acceptance criteria are in the [wiki](https://github.com/RobinWikoff/the-farm-monitor/wiki/Rust-Parity-and-Acceptance-Criteria).

---

## Running Locally

**Requirements:** Rust stable toolchain, a [Visual Crossing API key](https://www.visualcrossing.com/) (free tier works).

```bash
# Clone and set up environment
git clone https://github.com/RobinWikoff/the-farm-monitor.git
cd the-farm-monitor

cat > rust/.env <<'EOF'
VISUAL_CROSSING_API_KEY=your_key_here
FM_BIND_ADDR=127.0.0.1:8080
EOF

# Build and run
cd rust
cargo build
VISUAL_CROSSING_API_KEY=your_key_here cargo run --bin farm-monitor-api

# Open http://127.0.0.1:8080/dashboard
```

Without an API key the service falls back to a deterministic mock dataset automatically.

**Cross-compiling for Raspberry Pi (aarch64):**

```bash
sudo apt-get install -y gcc-aarch64-linux-gnu
rustup target add aarch64-unknown-linux-gnu
CC_aarch64_unknown_linux_gnu=aarch64-linux-gnu-gcc \
  CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc \
  cargo build --release --target aarch64-unknown-linux-gnu
```

---

## Repository Structure

```
app.py                    # archived Python/Streamlit prototype
rust/                     # active Rust service (Cargo workspace)
  crates/
    farm-monitor-api/     # HTTP server + HTML/SVG rendering
    farm-monitor-data/    # provider, normalize, cache, models
    farm-monitor-domain/  # shared types
metrics/                  # language composition history (tracked weekly via CI)
scripts/                  # language stats tooling, C4 diagram helpers
docs/                     # feature requirements, ops reference, ADRs
the-farm-monitor.wiki/    # wiki mirror (separate git repo)
.github/workflows/        # Rust CI, formatting, language stats
```

---

## Documentation

The [project wiki](https://github.com/RobinWikoff/the-farm-monitor/wiki) contains the full documentation set:

- [Model Purpose and Problem](https://github.com/RobinWikoff/the-farm-monitor/wiki/Model-Purpose-and-Problem) — why this exists and what decisions it supports
- [Rust Parity and Acceptance Criteria](https://github.com/RobinWikoff/the-farm-monitor/wiki/Rust-Parity-and-Acceptance-Criteria) — the phase-by-phase migration baseline
- [Operations Reference](https://github.com/RobinWikoff/the-farm-monitor/wiki/Operations-Reference) — Pi deployment, service management, Cloudflare tunnel
- [Model Architecture and Behavior](https://github.com/RobinWikoff/the-farm-monitor/wiki/Model-Architecture-and-Behavior) — C4 diagrams and system design narrative

---

## Development Notes

- All behavior-changing PRs update the wiki feature page in the same change window.
- `cargo fmt` and `cargo clippy -- -D warnings` are enforced in CI.
- Python files use [Ruff](https://docs.astral.sh/ruff/) for formatting and linting.
- The `[skip ci]` tag is used on automated commits (e.g. weekly language stats snapshots) to avoid triggering the full CI pipeline unnecessarily.


