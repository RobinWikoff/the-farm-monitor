#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RENDERED_DIR="$REPO_ROOT/docs/c4/rendered"
SNIPPET_DIR="$REPO_ROOT/docs/c4/.maintenance"
SNIPPET_PATH="$SNIPPET_DIR/wiki-c4-embed-snippets.md"
WIKI_REPO_PATH="/workspaces/the-farm-monitor.wiki"
WIKI_IMAGES_SUBDIR="images/c4"

usage() {
    cat <<'EOF'
Usage: ./scripts/c4_wiki_sync.sh [options]

Options:
  --wiki-repo <path>        Path to the wiki repo checkout
  --wiki-images-dir <path>  Images directory inside wiki repo (default: images/c4)
  --snippet-out <path>      Path to generated markdown snippet file
  --skip-copy               Only generate snippets; do not copy image files
  -h, --help                Show this help

Purpose:
  1) Copy docs/c4/rendered PNG and SVG assets into the wiki repo.
  2) Generate paste-ready markdown blocks for the C4 wiki page(s).
EOF
}

SKIP_COPY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --wiki-repo)
            WIKI_REPO_PATH="$2"
            shift 2
            ;;
        --wiki-images-dir)
            WIKI_IMAGES_SUBDIR="$2"
            shift 2
            ;;
        --snippet-out)
            SNIPPET_PATH="$2"
            shift 2
            ;;
        --skip-copy)
            SKIP_COPY=true
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

if [[ ! -d "$RENDERED_DIR" ]]; then
    echo "Rendered diagram directory not found: $RENDERED_DIR" >&2
    exit 1
fi

DIAGRAM_BASENAMES=(
    "c1-system-context"
    "c2-container-diagram"
    "c3-component-diagram"
    "c4-code-level-diagram"
)

mkdir -p "$(dirname "$SNIPPET_PATH")"

if [[ "$SKIP_COPY" == false ]]; then
    if [[ ! -d "$WIKI_REPO_PATH" ]]; then
        echo "Wiki repo path not found: $WIKI_REPO_PATH" >&2
        echo "Tip: clone wiki first, then rerun with --wiki-repo <path>." >&2
        exit 2
    fi

    WIKI_IMAGES_DIR="$WIKI_REPO_PATH/$WIKI_IMAGES_SUBDIR"
    mkdir -p "$WIKI_IMAGES_DIR"

    for base in "${DIAGRAM_BASENAMES[@]}"; do
        cp "$RENDERED_DIR/$base.png" "$WIKI_IMAGES_DIR/$base.png"
        cp "$RENDERED_DIR/$base.svg" "$WIKI_IMAGES_DIR/$base.svg"
    done

    for ui_map in "$RENDERED_DIR"/c4-ui-feature-map-*.png "$RENDERED_DIR"/c4-ui-feature-map-*.svg; do
        [[ -e "$ui_map" ]] || continue
        cp "$ui_map" "$WIKI_IMAGES_DIR/"
    done
fi

NOW_UTC="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"

{
    echo "# C4 Wiki Embed Snippets"
    echo
    echo "Generated: $NOW_UTC"
    echo
    echo "Recommended wiki display format: PNG (for consistent rendering)."
    echo
    echo "Optional companion link format: SVG (for zoom/high fidelity)."
    echo
    echo "## C4 Descriptions Page Block"
    echo

    for base in "${DIAGRAM_BASENAMES[@]}"; do
        case "$base" in
            c1-system-context)
                title="C1 - System Context"
                ;;
            c2-container-diagram)
                title="C2 - Container Diagram"
                ;;
            c3-component-diagram)
                title="C3 - Component Diagram"
                ;;
            c4-code-level-diagram)
                title="C4 - Code-Level Diagram"
                ;;
            *)
                title="$base"
                ;;
        esac

        echo "### $title"
        echo ""
        echo "![$title]($WIKI_IMAGES_SUBDIR/$base.png)"
        echo ""
        echo "[SVG version]($WIKI_IMAGES_SUBDIR/$base.svg)"
        echo ""
    done

    echo "## Optional Appendix: C4 UI Feature Maps"
    echo ""
    for ui_map_png in "$RENDERED_DIR"/c4-ui-feature-map-*.png; do
        [[ -e "$ui_map_png" ]] || continue
        file_name="$(basename "$ui_map_png")"
        map_title="${file_name%.png}"
        echo "### ${map_title//-/ }"
        echo ""
        echo "![${map_title//-/ }]($WIKI_IMAGES_SUBDIR/$file_name)"
        echo ""
    done
} > "$SNIPPET_PATH"

echo "Generated snippet file: $SNIPPET_PATH"
if [[ "$SKIP_COPY" == false ]]; then
    echo "Copied rendered C4 assets into: $WIKI_REPO_PATH/$WIKI_IMAGES_SUBDIR"
fi

echo "C4 wiki sync helper complete."
