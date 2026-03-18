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

## Test Command

Run the test suite locally:

python -m pytest -q
