# The Farm Monitor

Streamlit weather monitor for Loveland, CO with forecast, current conditions, and historical comparison bands.

## Code Formatting (Ruff)

This repository uses Ruff as the canonical Python formatter.

### Local commands

Format all Python files:

python -m ruff format .

Check formatting only (no file changes):

python -m ruff format --check .

### CI behavior

Formatting checks run automatically on push and pull request workflows.
If formatting is not compliant, CI fails and the PR cannot be merged until formatting is fixed.

## Linting (Ruff)

This repository uses Ruff for linting (pycodestyle errors, Pyflakes, and warnings).

### Local commands

Run the linter:

python -m ruff check .

Auto-fix safe issues:

python -m ruff check --fix .

### CI behavior

Lint checks run automatically on push and pull request workflows alongside formatting checks.
If any lint errors are reported, CI fails and the PR cannot be merged until they are resolved.

## Test Command

Run the test suite locally:

python -m pytest -q

## Memo PDF Template Generation (Issue #62)

Generate a branded memo PDF from structured YAML/JSON input.

### Interactive UI (Streamlit)

Open a form-based UI where you can type memo content and download the PDF:

python -m streamlit run memo/ui.py

In the UI:

- Fill in all required fields.
- Click **Generate PDF**.
- Click **Download Memo PDF**.

Date format is required as: `DD-Mon-YYYY` (example: `21-Mar-2026`).

### Example command

python -m memo.cli --input memo/examples/memo_input_example.yaml --output memo_output.pdf

### Required input fields

- `date`
- `subject`
- `recipient`
- `background`
- `problem_statement`
- `updates_information`
- `additional_section_1`
- `additional_section_2`
- `additional_section_3`

Optional fields:

- `memo_title` (defaults to `subject`)
- `organization_name` (defaults to `The Farm`)
- `logo_path` (defaults to `memo/assets/the_farm_logo.png`)

### Logo File Recommendations

- Preferred format: `PNG` with transparent background
- Aspect ratio: `4:1` (width to height)
- Suggested size: `1600 x 400 px`
- High-res option: `2400 x 600 px`

Design layout suggestion:

- Left half (`2:1`): image mark/icon
- Right half (`2:1`): text mark `The Farm`

Generated output includes:

- Header with organization branding (`The Farm`) and optional logo
- Footer with memo title, organization name, and `Page X of Y`

## Dev API Guardrails

Issue #50 introduced development-time API guardrails to reduce accidental quota burn while still allowing live verification when explicitly enabled.

### Runtime Profiles

- `prod`: Always live API mode.
- `dev-safe`: Forces sample mode unless live access is explicitly allowed.
- `dev-live`: Dev mode with live API enabled by explicit opt-in.

### Required Dev Flags

- `ENV=dev`
- `DEV_ALLOW_LIVE_API=true` to permit live calls in dev.
- `DEV_USE_SAMPLE_DATA=true|false` to choose sample/live within dev-live.

### Guardrail Budget Variables

- `DEV_BUDGET_VC_FORECAST` (default: `12`)
- `DEV_BUDGET_VC_HISTORICAL` (default: `3`)
- `DEV_BUDGET_OPEN_METEO_WIND` (default: `24`)
- `DEV_API_COOLDOWN_MINUTES` (default: `30`)

Invalid values fall back to defaults. Negative budget values clamp to `0`.

### Persisted State

Guardrail state is stored at:

`.streamlit/guardrails/dev_api_state.json`

State keys:

- `date`
- `usage`
- `blocked`
- `cooldowns`

State is effectively day-scoped: when the saved `date` does not match today, the app starts from a fresh state for the new day.

### Operator Controls (Dev UI)

In the sidebar under **Dev API Guardrails**:

- `Reset usage + blocked`: clears daily usage and blocked counters.
- `Clear cooldowns`: removes active cooldown entries.
- `Show raw guardrail state`: displays persisted JSON state for debugging.

### Fallback Message Semantics

Guardrail-aware fallback copy distinguishes:

- Budget exhausted for a provider
- Cooldown active after a 429
- General transient API/request failure
