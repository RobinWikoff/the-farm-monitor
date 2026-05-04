# C4 Architecture Documentation

This section documents The Farm Monitor architecture using the C4 model.

## Diagram Set

1. [C1 - System Context](c1-system-context.md)
2. [C2 - Container Diagram](c2-container-diagram.md)
3. [C3 - Component Diagram](c3-component-diagram.md)
4. [C4 - Code-Level Diagram](c4-code-level-diagram.md)

## Scope Covered

- Weather monitoring application runtime in `app.py`
- Memo generation subsystem in `memo/`
- External weather providers and local persistence boundaries
- Runtime profile, guardrail, and fallback behavior

## Modeling Notes

- Diagrams use Mermaid C4 syntax for repository-native rendering in Markdown viewers that support Mermaid.
- Relationships represent runtime call flow and data dependencies, not import-only dependencies.
- C4 Level 4 is provided for key implementation hotspots rather than every function in the codebase.

## How To Keep This Updated

1. Run the single C4 maintenance workflow script:
	- `./scripts/c4_docs_workflow.sh --range HEAD~1..HEAD`
2. If architecture-relevant files changed, update the corresponding C4 page(s) in `docs/c4/`.
3. Generate wiki-ready embed snippets from rendered diagrams:
	- `./scripts/c4_wiki_sync.sh --skip-copy`
4. If wiki repo is checked out locally, sync rendered diagrams into wiki assets:
	- `./scripts/c4_wiki_sync.sh --wiki-repo /path/to/the-farm-monitor.wiki`
5. Keep `docs/feature-requirements.md` and C4 docs aligned in the same PR when behavior/architecture changed.
6. If architecture changed, include a short note in `Changelog.MD`.
7. If no architecture changed, add `No C4 changes required` in the PR description.

## Wiki Diagram Format Policy

- Preferred wiki display format: PNG (consistent rendering in wiki pages).
- Include an adjacent SVG link for zoom/high-fidelity viewing.
- Generated wiki snippets live at `docs/c4/.maintenance/wiki-c4-embed-snippets.md`.

## Current Process Boundary

- Active process: `scripts/c4_docs_workflow.sh`
- Wiki sync helper: `scripts/c4_wiki_sync.sh` (asset copy + markdown snippet generation)
- Legacy diagram rendering scripts are archived under `scripts/archive/legacy-c4-rendering/` and are not part of the current maintenance process.
