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

## Issue Template & SOP (Placeholder)

This section is a placeholder to capture the issue template and SOP process without executing any related work yet.

### Issue Template Source Note

- The template appears to match recent/current repo issues.
- If direct template lookup fails, extract the structure from recent issues and add it here.

### SOP Outline Placeholder

1. Define issue type and expected outcome.
2. Draft using the agreed issue template fields.
3. Add acceptance criteria and test/validation notes.
4. Add traceability references (related docs, issue links, PR links).
5. Submit and label according to repo conventions.

---

## TODO

- [x] Add `.venv/` explicitly to `.gitignore` - agent suggested
- [x] Confirm `.env.example` reflects all current required keys - agent suggested
- [x] Decide whether `hist_cache/` CSVs should have a retention/cleanup policy - agent suggested
- [x] C4 diagrams to wiki SVG or PNG?
- [x] Add C4 diagrams to wiki (Model-Architecture-and-Behavior, PNG + SVG links per section, pushed 2026-04-23)
- [ ] Verify rain section behavior: investigate report that rain occurred but app showed no rain.
- [ ] Extract and document issue template used by recent/current repo issues.
- [ ] Finalize and expand issue-template SOP in the new "Issue Template & SOP" section.
- [ ] Rework C4 diagrams for wiki readability (left-to-right flow, more concept-map style, fewer crossing arrows).
- [ ] Review and complete in-progress work from before 2026-05-04; identify any code ready to merge.
