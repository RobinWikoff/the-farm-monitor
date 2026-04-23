# Model Documentation Process (Git-Based Wiki Workflow)

This document defines how to create and maintain model development documentation for The Farm Monitor using the GitHub Wiki as a separate git repository.

Scope:
- Primary content location: GitHub Wiki (not in-repo docs pages for authoritative model narrative)
- This file: process guidance and standards for writing, updating, and tracing wiki changes

---

## Why This Workflow

The git-based wiki workflow is preferred for model documentation because it provides:
- Versioned history for each wiki change
- Commit-level traceability back to issues and PRs
- Better support for larger structured updates than browser-only editing
- Repeatable maintenance process aligned with engineering practices

---

## Options for Updating Farm Monitor Wiki

1. Browser edit (quickest)
- Use for typo fixes or tiny edits.

2. Git-based wiki repo editing (recommended default)
- Use for all substantive model documentation updates.
- Best for structure/process/technical narrative changes.

3. Hybrid
- Use git for major changes, browser for minor touch-ups.

---

## Standard Workflow (Approach 2)

### Step 1: Clone the wiki repository

Run from a parent workspace folder (not inside the app repo):

```bash
cd /workspaces
git clone https://github.com/RobinWikoff/the-farm-monitor.wiki.git
cd the-farm-monitor.wiki
```

### Step 2: Verify branch and sync

```bash
git branch -a
git checkout master || git checkout main
git pull --ff-only
```

Note: Most GitHub wiki repos use `master`, but some use `main`.

### Step 3: Create or edit wiki pages

Common files:
- `Home.md` -> wiki landing page
- `_Sidebar.md` -> wiki navigation links
- Any additional pages as `Page-Title.md`

Naming convention:
- Use clear, stable page names.
- Prefer topic-oriented pages over date-oriented pages.

### Step 4: Write content with model-documentation standards

Every major page should answer:
1. What is this model for?
2. What problem does it address, and why is it better?
3. Why should stakeholders care?
4. How does it do what it is supposed to do?
5. How do we know it is doing what it is supposed to do?

Recommended page sections (Arc42-inspired):
- Purpose and Scope
- Context and Stakeholders
- Architecture/Behavior Narrative (words behind C4 diagrams)
- Key Assumptions and Constraints
- Validation and Evidence
- Risks and Limitations
- Change History / Traceability

### Step 5: Commit with issue traceability

```bash
git add .
git commit -m "docs(wiki): <short summary> (refs #<issue-number>)"
git push
```

Commit message format:
- Prefix: `docs(wiki):`
- Include issue reference for traceability
- Keep summary specific and concise

### Step 6: Add/update issue notes

After a meaningful wiki update, add an issue comment with:
- What changed (page names)
- Why it changed
- Evidence link(s) (commit hash, related PR, test/validation artifacts)
- Remaining open questions

---

## Change Governance

Use this minimum governance model:

- Rule 1: Any substantive model behavior change in code should have a corresponding wiki update, or an explicit issue comment: "No wiki change required".
- Rule 2: Wiki updates should reference issue numbers in commits.
- Rule 3: For major model changes, include references to:
  - related issue(s)
  - merged PR(s)
  - validation evidence (tests, metrics, or experiment results)
- Rule 4: Review wiki pages on a regular cadence (monthly or per release).

---

## Suggested Wiki Information Architecture

Minimum baseline pages:
- `Home.md`
- `Model-Purpose-and-Problem.md`
- `Model-Architecture-and-Behavior.md`
- `Model-Validation-and-Evidence.md`
- `Model-Limitations-and-Risks.md`
- `Model-Change-Log-and-Traceability.md`
- `Model-Documentation-Process.md`
- `_Sidebar.md`

---

## Template: Issue Comment for Wiki Updates

Use this template in the related issue after a wiki update:

```markdown
Wiki update completed.

Changed pages:
- <Page1.md>
- <Page2.md>

Reason:
- <why this update was needed>

Traceability:
- Wiki commit: <hash>
- Related code PR/commit: <link or hash>
- Validation evidence: <tests/logs/notes>

Open questions:
- <item>
```

---

## Practical Notes

- The wiki repository is separate from the application repository.
- Wiki commits will not appear in app-repo PR diffs.
- Keep this process file in-repo as a stable reference for contributors.

---

## C4 Maintenance Workflow (Single Active Process)

Use the single active script below to keep architecture docs aligned with code changes:

```bash
./scripts/c4_docs_workflow.sh --range HEAD~1..HEAD
```

What this script does:
- Detects architecture-relevant code/config changes in the selected git range.
- Detects whether `docs/c4/*.md` files were updated in the same range.
- Generates a report at `docs/c4/.maintenance/latest-c4-update-report.md`.
- Provides a manual wiki sync checklist.

Policy:
- If architecture-relevant files changed, update C4 docs in this repo before finalizing the change.
- Then manually update the wiki architecture narrative page(s), especially `Model-Architecture-and-Behavior.md`.
- Keep the wiki Q2 traceability section aligned to current `docs/c4/*` source files.

Legacy note:
- Older C4 rendering scripts are archived under `scripts/archive/legacy-c4-rendering/`.
- Those archived scripts are not part of the current maintenance process.
