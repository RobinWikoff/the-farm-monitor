# Issue 9: UOR Compatibility Evaluation

## Decision (Initial)
- Track selected: Compatibility-first.
- Scope of issue 9: Evaluation and roadmap only (no full rewrite).
- Product surface remains Python/Streamlit in near term.

## Source Framework
- UOR reference repository: https://github.com/UOR-Foundation/UOR-Framework
- Key conformance model observed:
  - Workspace-level conformance gate (`uor-conformance`).
  - Multi-artifact expectations (source quality, ontology artifacts, SHACL fixtures, docs, website).
  - PRISM-oriented resolver pattern and shape-based declarations.

## Current Project Snapshot
- Runtime: Python 3.11
- App: Streamlit dashboard
- Tooling: Ruff + pytest
- Main entrypoint: app.py
- Current architecture: app-centric weather/memo workflows

## Compatibility Target Profile (v0)
This repository will define "UOR-compatible" as:
1. UOR-aligned domain contracts for query, resolver input/output, certificate, and trace.
2. Deterministic serialization for those contracts (machine-checkable payloads).
3. CI validation of contract schemas and compatibility checks.
4. One implemented PRISM-like flow path (Define -> Resolve -> Certify) in this codebase.

## Gap Analysis (High-Level)
### Present Today
- Basic CI quality gates exist (format/lint/tests).
- Domain app logic and charted observables already exist.

### Missing for UOR Compatibility
- No UOR contract schema package.
- No certificate or trace model for resolver outcomes.
- No explicit PRISM pipeline stages in app architecture.
- No UOR compatibility checks in CI.
- No adapter layer to map app domain objects to UOR concepts.

## Phased Migration Plan
## Phase A: Target and Contract Design
Deliverables:
- Compatibility ADR (track choice, boundaries, assumptions).
- Contract definitions for Query/ResolverResult/Certificate/Trace.
- Validation strategy and CI gate design.

Exit criteria:
- Contracts reviewed and accepted.
- Follow-up implementation issues created.

## Phase B: Python Adapter Layer
Deliverables:
- `uor_adapter` package for mapping app data -> UOR-aligned contracts.
- Typed models and serialization helpers.
- Unit tests for mapping and serialization.

Exit criteria:
- Adapter emits stable, validated artifacts for sample and live data modes.

## Phase C: Certification + Trace
Deliverables:
- Certificate payload for selected resolver outputs.
- Trace payload recording staged execution metadata.
- Persisted outputs for local inspection.

Exit criteria:
- One end-to-end flow emits query/result/certificate/trace.

## Phase D: PRISM Flow Alignment
Deliverables:
- Explicit staged orchestration in app/service layer:
  - Define
  - Resolve
  - Certify
- UI/CLI visibility for stage status.

Exit criteria:
- At least one feature path runs through explicit stages.

## Phase E: Advanced Alignment (Optional)
Deliverables:
- Evaluate extraction of core resolver logic into Rust components.
- Evaluate deeper interoperability with UOR workspace-style conformance.

Exit criteria:
- Feasibility decision with cost and migration recommendation.

## Risks
- Scope creep toward full framework rewrite.
- Overfitting to UOR internals before adapter boundary stabilizes.
- CI complexity growth without clear compatibility target.

## Immediate Next Actions
1. Author compatibility ADR with architecture boundary diagram.
2. Draft schema for query/result/certificate/trace payloads.
3. Add a non-blocking CI check job for schema validation.
4. Implement first adapter model slice for current weather + AQI flow.
