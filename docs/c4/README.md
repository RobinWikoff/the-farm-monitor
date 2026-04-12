# C4 Architecture Documentation

This section documents The Farm Monitor architecture using the C4 model.

## Diagram Set

1. [C1 - System Context](c1-system-context.md)
2. [C2 - Container Diagram](c2-container-diagram.md)
3. [C3 - Component Diagram](c3-component-diagram.md)
4. [C4 - Code-Level Diagram](c4-code-level-diagram.md)
5. [UI Feature → Backend Map](c4-ui-feature-map.md) *(supplementary)*

## Scope Covered

- Weather monitoring application runtime in `app.py`
- External weather providers and local persistence boundaries
- Runtime profile, guardrail, and fallback behavior

## Modeling Notes

- Diagrams use Mermaid C4 syntax for repository-native rendering in Markdown viewers that support Mermaid.
- Relationships represent runtime call flow and data dependencies, not import-only dependencies.
- C4 Level 4 is provided for key implementation hotspots rather than every function in the codebase.

## How To Keep This Updated

1. Update the corresponding C4 page whenever a feature changes behavior or dependencies.
2. Keep `docs/feature-requirements.md` and C4 docs aligned in the same PR.
3. If architecture changed, include a short note in `Changelog.MD`.
4. If no architecture changed, add `No C4 changes required` in the PR description.
