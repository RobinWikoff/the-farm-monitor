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
