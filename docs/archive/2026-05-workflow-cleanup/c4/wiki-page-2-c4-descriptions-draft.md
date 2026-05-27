# C4 Architecture Descriptions

This page mirrors the canonical C4 sources under `docs/c4/` and embeds rendered diagrams for wiki readability.

## C1 - System Context

Shows The Farm Monitor in relation to users, external weather APIs, local state, CI workflows, and planned integrations.

![C1 - System Context](images/c4/c1-system-context.png)

[SVG version](images/c4/c1-system-context.svg)

## C2 - Container Diagram

Shows deployable/runtime boundaries: the Streamlit weather app container and local state store, plus provider dependencies.

![C2 - Container Diagram](images/c4/c2-container-diagram.png)

[SVG version](images/c4/c2-container-diagram.svg)

## C3 - Component Diagram

Shows major internal components inside `app.py`: runtime config, guardrails, ingestion, fallback orchestrator, analytics, charts, and UI composition.

![C3 - Component Diagram](images/c4/c3-component-diagram.png)

[SVG version](images/c4/c3-component-diagram.svg)

## C4 - Code-Level Diagram

Shows detailed code-level function groupings and relationships among runtime config, guardrails, weather ingestion, historical cache, analytics, banners, and visualization.

![C4 - Code-Level Diagram](images/c4/c4-code-level-diagram.png)

[SVG version](images/c4/c4-code-level-diagram.svg)

## Maintenance Notes

- Canonical source lives in repository C4 markdown files under `docs/c4/`.
- Preferred wiki display format is PNG; include SVG links for detailed zoom.
- Regenerate snippets after C4 updates with:

```bash
./scripts/c4_wiki_sync.sh --skip-copy
```

- If wiki repo is local, sync assets with:

```bash
./scripts/c4_wiki_sync.sh --wiki-repo /path/to/the-farm-monitor.wiki
```
