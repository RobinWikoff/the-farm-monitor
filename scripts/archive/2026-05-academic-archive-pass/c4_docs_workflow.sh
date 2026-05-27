#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPORT_DIR="$REPO_ROOT/docs/c4/.maintenance"
REPORT_PATH="$REPORT_DIR/latest-c4-update-report.md"

RANGE="HEAD~1..HEAD"
FAIL_ON_MISSING_C4_UPDATES=true
WIKI_REPO_PATH="/workspaces/the-farm-monitor.wiki"

usage() {
    cat <<'EOF'
Usage: ./scripts/c4_docs_workflow.sh [options]

Options:
  --range <git-range>              Git diff range to inspect (default: HEAD~1..HEAD)
  --wiki-repo <path>               Path to wiki repo (default: /workspaces/the-farm-monitor.wiki)
  --no-fail-on-missing-c4-updates  Report missing C4 docs changes without non-zero exit
  -h, --help                       Show this help message

Purpose:
  Single maintenance workflow for C4 docs and manual wiki handoff.
  1) Detect architecture-impacting code changes.
  2) Check whether docs/c4 markdown files were updated in the same range.
  3) Generate docs/c4/.maintenance/latest-c4-update-report.md
  4) Provide explicit manual wiki sync checklist.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --range)
            RANGE="$2"
            shift 2
            ;;
        --wiki-repo)
            WIKI_REPO_PATH="$2"
            shift 2
            ;;
        --no-fail-on-missing-c4-updates)
            FAIL_ON_MISSING_C4_UPDATES=false
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
done

cd "$REPO_ROOT"

if ! git rev-parse --verify "${RANGE%%..*}" >/dev/null 2>&1; then
    echo "Invalid range start in --range: $RANGE" >&2
    exit 1
fi

if ! git rev-parse --verify "${RANGE##*..}" >/dev/null 2>&1; then
    echo "Invalid range end in --range: $RANGE" >&2
    exit 1
fi

mapfile -t CHANGED_FILES < <(git diff --name-only "$RANGE")

ARCH_CHANGE_REGEX='^(app.py|memo/|requirements.txt|pyproject.toml|tests/|\.github/workflows/|docs/feature-requirements\.md|docs/uor/)'
C4_DOC_REGEX='^docs/c4/.*\.md$'

ARCHITECTURE_RELEVANT=()
C4_DOC_CHANGES=()

for file in "${CHANGED_FILES[@]:-}"; do
    [[ -z "$file" ]] && continue
    if [[ "$file" =~ $ARCH_CHANGE_REGEX ]]; then
        ARCHITECTURE_RELEVANT+=("$file")
    fi
    if [[ "$file" =~ $C4_DOC_REGEX ]]; then
        C4_DOC_CHANGES+=("$file")
    fi
done

mkdir -p "$REPORT_DIR"

timestamp_utc="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"

{
    echo "# C4 Documentation Maintenance Report"
    echo
    echo "- Generated: $timestamp_utc"
    echo "- Git range: $RANGE"
    echo "- Repo branch: $(git rev-parse --abbrev-ref HEAD)"
    echo
    echo "## Changed Files In Range"
    if [[ ${#CHANGED_FILES[@]} -eq 0 ]]; then
        echo "- (none)"
    else
        for f in "${CHANGED_FILES[@]}"; do
            echo "- $f"
        done
    fi
    echo
    echo "## Architecture-Relevant Changes"
    if [[ ${#ARCHITECTURE_RELEVANT[@]} -eq 0 ]]; then
        echo "- No architecture-relevant code/config/docs files detected by workflow pattern."
    else
        for f in "${ARCHITECTURE_RELEVANT[@]}"; do
            echo "- $f"
        done
    fi
    echo
    echo "## C4 Doc Changes (docs/c4/*.md)"
    if [[ ${#C4_DOC_CHANGES[@]} -eq 0 ]]; then
        echo "- (none)"
    else
        for f in "${C4_DOC_CHANGES[@]}"; do
            echo "- $f"
        done
    fi
    echo
    echo "## Workflow Decision"
    if [[ ${#ARCHITECTURE_RELEVANT[@]} -gt 0 && ${#C4_DOC_CHANGES[@]} -eq 0 ]]; then
        echo "- STATUS: ACTION REQUIRED"
        echo "- Architecture-relevant files changed, but C4 markdown docs were not updated."
        echo "- Required action: update one or more docs in docs/c4 before closing the change." 
    elif [[ ${#ARCHITECTURE_RELEVANT[@]} -gt 0 && ${#C4_DOC_CHANGES[@]} -gt 0 ]]; then
        echo "- STATUS: C4 UPDATES DETECTED"
        echo "- Architecture-relevant changes are accompanied by C4 doc updates."
    else
        echo "- STATUS: NO C4 UPDATE REQUIRED (by pattern)"
        echo "- No architecture-relevant file changes were detected in this range."
    fi
    echo
    echo "## Manual Wiki Sync Checklist"
    echo "1. Verify the final C4 narrative updates in docs/c4/*.md are complete in this repo."
    echo "2. Generate wiki-ready C4 embed snippets from rendered diagrams:"
    echo "   - ./scripts/c4_wiki_sync.sh --skip-copy"
    echo "   - Review docs/c4/.maintenance/wiki-c4-embed-snippets.md"
    echo "3. Open wiki repo and pull latest changes:"
    echo "   - cd $WIKI_REPO_PATH"
    echo "   - git pull --ff-only"
    echo "4. Sync rendered C4 diagrams into wiki assets:"
    echo "   - ./scripts/c4_wiki_sync.sh --wiki-repo $WIKI_REPO_PATH"
    echo "5. Update wiki C4 description page(s) with PNG embeds and SVG links from snippet file."
    echo "6. Update Model-Architecture-and-Behavior.md in wiki to reflect C1/C2/C3/C4 and Baseline Inference Flow deltas."
    echo "7. Ensure wiki Q2 traceability links still match docs/c4 source files."
    echo "8. Commit and push wiki changes with a docs(wiki) commit message."
    echo
    echo "## Notes"
    echo "- This report is generated by scripts/c4_docs_workflow.sh."
    echo "- Legacy render scripts are archived under scripts/archive/."
} > "$REPORT_PATH"

echo "Generated report: $REPORT_PATH"

if [[ ${#ARCHITECTURE_RELEVANT[@]} -gt 0 && ${#C4_DOC_CHANGES[@]} -eq 0 ]]; then
    if [[ "$FAIL_ON_MISSING_C4_UPDATES" == true ]]; then
        echo "ERROR: Architecture-relevant changes detected without docs/c4 markdown updates." >&2
        echo "Re-run with --no-fail-on-missing-c4-updates to allow a warning-only result." >&2
        exit 2
    fi
    echo "WARNING: Missing docs/c4 markdown updates for architecture-relevant changes."
fi

echo "C4 workflow check complete."
