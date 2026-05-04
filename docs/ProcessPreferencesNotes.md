# Process Preferences & Notes

## Gitignore Structure & Transfer Process

### What is currently gitignored

| Path / Pattern | Purpose |
|---|---|
| `__pycache__/` | Python bytecode cache |
| `.pytest_cache/` | Pytest run cache |
| `.env` | Local env vars (API keys etc.) |
| `.env.*` (except `.env.example`) | Any env variant files |
| `.streamlit/secrets.toml` | Streamlit secrets — API keys |
| `.streamlit/hist_cache/` | Cached weather history CSVs |
| `.streamlit/guardrails/` | Runtime guardrail state (e.g. `dev_api_state.json`) |

### Files/folders that exist locally but are NOT in git

```
.env
.streamlit/secrets.toml
.streamlit/hist_cache/
    hist_2026-04-08.csv       ← example cached fetch
.streamlit/guardrails/
    dev_api_state.json        ← runtime API throttle/state
.venv/                        ← Python virtual environment
```

### What IS tracked in git (`.streamlit/` subset)

```
.streamlit/config.toml        ← Streamlit theme/server config, safe to commit
```

---

## Transfer Process: Moving Ignored Files Between Environments

When moving from one environment (e.g. GitHub Codespace) to a new local dev container:

1. **On the source machine**, pack all ignored runtime files into a tar.gz:
   ```bash
   tar -czf ignored-files-transfer.tar.gz \
     .env \
     .streamlit/secrets.toml \
     .streamlit/hist_cache/ \
     .streamlit/guardrails/
   ```

2. **Transfer** the archive to the new machine (drag-drop into VS Code, `scp`, or download/upload).

3. **On the destination**, list contents before extracting to verify:
   ```bash
   tar -tzf ignored-files-transfer.tar.gz | grep -v '^\.venv/' | grep -v '__pycache__'
   ```

4. **Extract** only the needed files:
   ```bash
   tar -xzf ignored-files-transfer.tar.gz \
     .env \
     .streamlit/secrets.toml \
     .streamlit/hist_cache/ \
     .streamlit/guardrails/
   ```

5. **Delete** the archive from the workspace when done — it contains secrets:
   ```bash
   rm ignored-files-transfer.tar.gz
   ```

6. **Set up the Python venv** (if not already present):
   - VS Code will auto-create it via `configure_python_environment`, or run:
   ```bash
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```

7. **Verify** with a pytest smoke check:
   ```bash
   .venv/bin/pytest --tb=short -q
   ```

---

## Notes & Reminders

- `.env.example` is the **only** `.env` variant committed to git — keep it up to date when new env var keys are added.
- `VISUAL_CROSSING_API_KEY` is the only API secret currently required by the app. It can live in either `.env` or `.streamlit/secrets.toml`; the app checks env vars first, then Streamlit secrets.
- The `.venv/` directory is now explicitly gitignored.
- `hist_cache/` CSVs are safe to transfer but are non-critical — the app will re-fetch missing dates from the Visual Crossing API.
- `hist_cache/` now has retention cleanup support via `DEV_HIST_CACHE_RETENTION_DAYS` (default: 14 days), pruning old `hist_YYYY-MM-DD.csv` files when new cache writes occur.
- `guardrails/dev_api_state.json` tracks API call throttle state. Transferring it preserves call counts; leaving it out resets the counter (usually fine in a fresh container).
- C4 wiki embedding process now uses `scripts/c4_wiki_sync.sh` to generate paste-ready markdown snippets and (optionally) copy rendered PNG/SVG files into a local wiki repo checkout.
- C4 wiki preferred display format is PNG, with an SVG link under each diagram for zoom fidelity.

---

## Issue Template & SOP

Extracted from real issues opened in this repo (chat03, chat04 session history, issues #7, #9, #71, and sidebar/wind/fire issues).

---

### Issue Types & Templates

There are four recurring issue types. Use the matching template below.

---

#### Type 1: P1 Production Bug (severity label + "P1" in title)

Used when a live user-visible failure or data outage is detected.

```markdown
Title: P1 <Short Description of Outage>

## Summary
[One paragraph: what's broken, user impact, urgency.]

## Impact
- [Bullet: visible symptom to user]
- [Bullet: failure mode — crash vs graceful degradation]
- [Bullet: scope — all users / specific conditions]

## What Happened
[Concrete description of the triggering condition.]

## Root Cause
[Technical root cause — what assumption broke, what code path failed.]

## Resolution Implemented
- [Bullet: what was changed]
- [Bullet: defensive behavior added]

## Verification
- Tests passed: [list test files]
- Result: [N] passed
- Notes: [any pre-existing unrelated failures to ignore]

## Severity / Priority
- Priority: P1
- Rationale: [why this is P1 — user-visible outage, data loss, etc.]

## Follow-up
- [Optional: logging/observability improvements]
- [Optional: related code paths to harden]
```

---

#### Type 2: Bug (non-P1)

Used for reproducible defects that are not immediate outages.

```markdown
Title: Bug: <Short Description>

## Describe the bug
[Clear description of what is wrong.]

## To Reproduce
1. [Step 1]
2. [Step 2]
3. [Step 3 — observe the bug]

## Expected behavior
[What should happen instead.]

## Screenshots
(Add a screenshot if possible.)

## Environment
- Branch: [branch name]
- OS: [your OS]
- Browser: [your browser]

## Additional context
[When was this noticed, related context, etc.]

## Acceptance Criteria
- [Bullet: specific, testable condition that closes this issue]
- [Bullet: secondary condition if needed]
```

---

#### Type 3: UI Improvement / Enhancement

Used for layout, UX, or display improvements that are not bugs.

```markdown
Title: UI Improvement: <Short Description>

## Describe the improvement
[What should change and why it improves the experience.]

## Current Behavior
- [What it looks like/does now]

## Expected Behavior
- [What it should look like/do after the change]

## Acceptance Criteria
- [Bullet: testable outcome]
- [Bullet: layout/device scope — desktop, mobile, both]

## Additional context
- Branch: [branch if relevant]
- Applies to: [desktop / mobile / both]
```

---

#### Type 4: Feature Request / New Section

Used for new dashboard sections, data integrations, or significant new capabilities.

```markdown
Title: Feature: <Short Description>

## Summary
[One sentence: what this adds and why it matters.]

## Details
- [Bullet: data shown / behavior]
- [Bullet: visual element — chart, table, card, map, etc.]
- [Bullet: data source(s) if known]
- [Bullet: any variants or flags]

## Open Questions
- [Bullet: unresolved scope or design question]
- [Bullet: data availability / source question]

## Acceptance Criteria
- [Bullet: new section/feature is visible in dashboard]
- [Bullet: data is correct and sourced]
- [Bullet: UI is consistent and not cluttered]
- [Bullet: works on desktop and mobile]

## Additional context
- [Extensibility notes, related features, future work hooks]
```

---

#### Type 5: Architecture / Evaluation

Used for planning, ADR-level work, or compatibility/integration evaluation. See also `docs/uor/issue-9-uor-evaluation.md` as a reference example.

```markdown
Title: <System Name> Compatibility Evaluation and Plan

## Goal
[One paragraph: what is being evaluated and why.]

## Context
[Background, relevant links (repos, specs, docs).]

## Phase 1 Deliverables (This Issue)
1. [Deliverable 1]
2. [Deliverable 2]
3. [Deliverable 3: produce a phased plan with acceptance criteria]
4. [Deliverable 4: open follow-up implementation issues for each phase]

## Current Stack Snapshot
- Language/runtime: Python 3.x / Streamlit
- Tests: pytest
- [Other relevant components]

## Acceptance Criteria
- [Evaluation document or ADR produced]
- [Follow-up issues opened and linked]
- [Decision recorded]
```

---

### SOP: Opening a New Issue

1. **Identify issue type** from the four types above (P1 Bug, Bug, UI/Enhancement, Feature, Architecture).
2. **Copy the matching template** and fill in all fields — don't skip Acceptance Criteria.
3. **Title convention**:
   - P1 bugs: start with `P1` in the title.
   - Bugs: start with `Bug:`.
   - UI/Enhancement: start with `UI Improvement:` or `Enhancement:`.
   - Features: start with `Feature:`.
   - Architecture: use descriptive title; add `[eval]` or `[ADR]` tag if appropriate.
4. **Labels**: apply severity (`P1`, `bug`, `enhancement`, `feature`, `architecture`) per repo conventions.
5. **Traceability**: link to related issues, PRs, ADR docs, or chat session references where useful.
6. **Child issues**: for large issues (like #9), break into labeled sub-issues (9A, 9B, etc.) using `docs/uor/issue-9-followup-issues.md` as the reference pattern.
7. **Closing an issue via commit**: add `Closes #N` or `Fixes #N` to the commit message or PR description to auto-close.

---

## TODO

- [x] Add `.venv/` explicitly to `.gitignore` - agent suggested
- [x] Confirm `.env.example` reflects all current required keys - agent suggested
- [x] Decide whether `hist_cache/` CSVs should have a retention/cleanup policy - agent suggested
- [x] C4 diagrams to wiki SVG or PNG?
- [x] Add C4 diagrams to wiki (Model-Architecture-and-Behavior, PNG + SVG links per section, pushed 2026-04-23)
- [ ] Verify rain section behavior: investigate report that rain occurred but app showed no rain.
- [x] Extract and document issue template used by recent/current repo issues (extracted from chat03/chat04 session history, 2026-05-04).
- [x] Finalize and expand issue-template SOP section — see "Issue Template & SOP" above (2026-05-04).
- [ ] Rework C4 diagrams for wiki readability (left-to-right flow, more concept-map style, fewer crossing arrows).
- [x] Review and complete in-progress work from before 2026-05-04; identify any code ready to merge (reviewed 2026-05-04 — all real changes committed in f9a6a72, CRLF churn stashed, working tree clean).
