# The Farm Monitor — Operations Reference

This document covers secrets management, repo access policy, and restore procedures.
It is the authoritative reference for what is NOT in git and how to recover this project.

---

## Secrets: What Is Not in Git

The following items are intentionally excluded from version control and must be stored
separately by the repo owner.

| Secret | Where it is used | Where to store it |
|---|---|---|
| `VISUAL_CROSSING_API_KEY` | Live weather and AQI data (app + CI live tests) | Streamlit Cloud secrets + personal password manager |
| `.streamlit/secrets.toml` (local dev file) | Local Streamlit development only | Never commit; regenerate from password manager |

### Rules

- `.streamlit/secrets.toml` is listed in `.gitignore` and must never be committed.
- If a secret is accidentally committed to any branch, treat it as compromised immediately:
  rotate the key at the provider (Visual Crossing dashboard), then purge the commit history.
- GitHub secret scanning is enabled and will alert on known secret patterns pushed to the repo.

---

## Restore Procedure

In the event of accidental deletion, corruption, or needing to move to a new machine or
Codespace, full recovery requires three steps:

### Step 1 — Re-clone the repository

```bash
git clone https://github.com/RobinWikoff/the-farm-monitor.git
cd the-farm-monitor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

All source code, tests, architecture docs, and chat history are fully restored from git.

### Step 2 — Restore local secrets

Create `.streamlit/secrets.toml` with:

```toml
VISUAL_CROSSING_API_KEY = "<key from password manager>"
ENV = "dev"
```

Retrieve the Visual Crossing API key from your personal password manager.

### Step 3 — Re-connect Streamlit Cloud deployment

If the Streamlit Cloud deployment needs to be rebuilt:

1. Log in to [share.streamlit.io](https://share.streamlit.io).
2. Create a new app pointing to `RobinWikoff/the-farm-monitor`, branch `main`, file `app.py`.
3. In the app's Secrets settings, add `VISUAL_CROSSING_API_KEY` and `ENV = "prod"`.

That is the full restore. There is no database and no stateful infrastructure to rebuild.

---

## Repo Access and Protection Policy

### Branch protection on `main`

`main` is the production branch. The following protections should be enabled
(see GitHub Settings → Branches → Branch protection rules):

- Require status checks to pass before merging:
  - `Ruff format check` (from `format.yml`)
  - `Unit and integration tests (non-live)` (from `tests.yml`)
- Require branches to be up to date before merging.
- Do not allow force pushes.
- Do not allow deletion of `main`.

### Fork PR Actions approval gate

External contributors can fork this public repo and open pull requests. To prevent forked PRs
from automatically running GitHub Actions workflows (which could expose secrets or consume
quota), set: Settings → Actions → General → "Require approval for all outside collaborators."

### Collaborator access

This is a solo-owner repository. No write collaborators should be present unless explicitly
granted for a specific purpose. Review periodically: Settings → Collaborators and teams.

### Account security

The GitHub account owner should have 2FA enabled. Account compromise bypasses all repo-level
protections. Verify at: GitHub account Settings → Password and authentication.

---

## Periodic Offsite Backup (Optional)

The `.github/workflows/bundle-backup.yml` workflow generates a portable git bundle of the
repository and uploads it as a GitHub Actions artifact. It can be triggered manually at any
time from the Actions tab. This provides a point-in-time offsite snapshot against GitHub
platform unavailability.

To trigger: Actions → "Repo Bundle Backup" → Run workflow.

Bundle artifacts are retained for 90 days in GitHub Actions.
