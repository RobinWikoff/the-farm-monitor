# Issue 9: UOR PRISM Backend Integration Evaluation

## Clarified Goal
Use this project as the application and UI layer, build a PRISM integration layer in this repository, and use the UOR Framework as the backend core.

This issue is a discovery and architecture decision issue to answer:
1. How this app can call into a UOR/PRISM backend.
2. What contract shape should sit between this app and UOR.
3. What minimum implementation proves the integration works.

## Desired End State (v1)
1. UI/App Layer (this repo): Streamlit user experience and app orchestration.
2. PRISM Layer (this repo): integration adapter/orchestrator that prepares requests and processes backend outputs.
3. UOR Backend (external source of truth): resolver/certification core invoked via service contract.
4. At least one real app path uses the full three-layer flow end-to-end.

## Target Architecture (v1)
1. UI/App Layer
- Handles user interaction, visualization, and app state.
- Does not implement UOR resolver internals.

2. PRISM Layer
- Lives in this project as an integration boundary.
- Converts app inputs into backend query payloads.
- Receives resolver output, certificate, and trace.
- Applies fallback behavior when backend is unavailable.

3. UOR Framework Backend
- Provides core resolver and formal backend semantics.
- Returns normalized result/certificate/trace payloads.

## What We Know So Far
- UOR framework is Rust-first with PRISM-oriented resolver patterns and strict conformance tooling.
- This app is Python-first and currently computes domain outputs directly.
- We need a bridge boundary, not an immediate full rewrite.

## Integration Options to Evaluate
## Option A: Service Boundary (Recommended First)
Run UOR backend as a separate service and call it from the PRISM layer in this app.

Pros:
- Clear language/runtime boundary.
- Lowest disruption to existing app.
- Easier incremental rollout.

Cons:
- Requires API contract and deployment model.

## Option B: Embedded Local Process
Call UOR CLI binaries from the PRISM layer and parse emitted artifacts.

Pros:
- Fastest path for local proof-of-concept.

Cons:
- Operationally brittle.
- Harder error handling and scaling.

## Option C: Native Binding Layer
Build a direct Python binding into Rust components.

Pros:
- Tight integration.

Cons:
- Highest implementation complexity.
- Not a good first step for discovery.

## Recommended Sequence
1. Start with Option A for production-shaped architecture.
2. Use Option B only as a temporary feasibility spike.
3. Revisit Option C only after contracts and workflows stabilize.

## Proposed PRISM <-> UOR Contract Surface (Draft)
Frontend request should contain:
- query_type
- input_payload
- policy_flags

Backend response should contain:
- resolver_result
- certificate
- trace
- diagnostics

## Current Gap Analysis
### Present
- Frontend UI and workflows exist.
- CI/test/lint basics are in place.

### Missing
- No explicit PRISM integration layer in this repo.
- No UOR contract schemas.
- No service client in app.
- No certificate/trace rendering path in UI.

## Phase Plan
## Phase 0: Discovery Spike (This Issue)
Deliverables:
1. Decide integration option for first implementation.
2. Define minimal backend contract (request/response).
3. Define one app use case for proof (recommended: AQI resolver path).
4. Produce implementation issue breakdown.

Exit criteria:
- Written architecture decision captured.
- Follow-up build issues created and prioritized.

## Phase 1: Adapter and Contract
Deliverables:
1. PRISM integration module for UOR backend calls.
2. Typed request/response models.
3. Error-handling and timeout strategy.

## Phase 2: First End-to-End Hookup
Deliverables:
1. One app workflow routed through backend.
2. UI surface for result/certificate/trace.
3. Test coverage for happy path and fallback path.

## Risks to Manage
1. Treating this as a full rewrite too early.
2. Locking to unstable contract fields.
3. Coupling UI directly to backend internals.

## Next Actions
1. Add an ADR for "UOR backend integration mode".
2. Draft JSON schema for request/response payloads.
3. Define proof-of-integration workflow and acceptance tests.
