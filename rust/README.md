# Rust Migration Workspace

This directory hosts Phase A Rust migration scaffolding for The Farm Monitor.

## Scope (Phase A + Phase B in progress)

- Rust workspace and crate boundaries
- API crate with minimal `/healthz` endpoint
- Domain crate for shared data models
- Data crate for provider abstraction, normalization, file cache, and guardrails
- CI workflow for Rust lint/build/test checks

## Local Commands (when Rust toolchain is installed)

```bash
cd rust
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace
cargo run -p farm-monitor-api
```

## Health Check

When running, the API responds on `http://127.0.0.1:8080/healthz`.
