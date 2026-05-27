# Local Workflow: Documentation Process

Canonical model documentation governance is maintained in wiki:
- Model-Documentation-Process (the-farm-monitor.wiki)
- https://github.com/RobinWikoff/the-farm-monitor/wiki/Model-Documentation-Process

This local file is intentionally limited to repository-local workflow glue.

## Local C4 Workflow Hooks
- Run C4 doc impact check:
  - ./scripts/c4_docs_workflow.sh --range HEAD~1..HEAD
- If architecture-relevant files changed, update docs/c4/* source files and sync wiki architecture narrative.

## Local Policy
- Treat wiki pages as canonical narrative and process references.
- Keep local docs to pointers and repository-only execution hooks.
