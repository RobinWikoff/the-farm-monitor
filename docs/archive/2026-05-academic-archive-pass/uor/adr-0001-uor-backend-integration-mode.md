# ADR-0001: UOR Backend Integration Mode

## Status
Proposed

## Context
The Farm Monitor is a Python/Streamlit application. The target architecture is:
1. UI/App layer in this repository.
2. PRISM integration layer in this repository.
3. UOR Framework backend as external core resolver system.

We need a first integration mode that is practical, testable, and can evolve toward deeper conformance.

## Decision
Adopt a service-boundary integration as the first implementation mode:
1. Frontend remains Python/Streamlit.
2. PRISM integration code in this repo invokes backend services via typed contracts.
3. UOR backend remains the source of backend resolver logic.

## Alternatives Considered
## A) Embedded CLI execution
- Pros: Fast local spike.
- Cons: Brittle process handling, weak operational model.

## B) Native Python-Rust bindings
- Pros: Tight coupling and lower RPC overhead.
- Cons: Highest complexity; poor first-step fit.

## Consequences
### Positive
- Clear architecture boundary and ownership.
- Incremental rollout without frontend rewrite.
- Contract-first testing and CI enforcement is straightforward.

### Layer Ownership
- UI/App layer: user flows, rendering, local state.
- PRISM layer: request mapping, transport, response normalization, fallback policy.
- UOR backend: resolver execution, backend semantics, certificate/trace production.

### Negative
- Requires service lifecycle and availability handling.
- Additional operational complexity (timeouts/retries/errors).

## Initial Contract Scope
- Request: query_type, input_payload, policy_flags
- Response: resolver_result, certificate, trace, diagnostics

## Acceptance Criteria
1. One app workflow calls backend service end-to-end.
2. Response contract validated in tests.
3. UI exposes resolver result and minimal certificate/trace fields.

## Follow-up
- Add JSON schemas for request/response.
- Add client adapter module in Python.
- Add CI compatibility check for contract validation.
