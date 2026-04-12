#!/usr/bin/env bash
# Generate SVG and PNG renderings of all C4 Mermaid diagrams.
# Usage: ./scripts/render_c4_diagrams.sh
#
# Requirements:
#   - @mermaid-js/mermaid-cli (mmdc) on PATH: npm install -g @mermaid-js/mermaid-cli
#   - chromium on PATH (or set PUPPETEER_EXECUTABLE_PATH)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
C4_DIR="$REPO_ROOT/docs/c4"
OUT_DIR="$C4_DIR/rendered"
PUPPETEER_CFG=$(mktemp /tmp/puppeteer_cfg_XXXXXX.json)

mkdir -p "$OUT_DIR"

# Auto-detect chromium if PUPPETEER_EXECUTABLE_PATH is not set
if [[ -z "${PUPPETEER_EXECUTABLE_PATH:-}" ]]; then
    CHROMIUM_PATH=$(which chromium 2>/dev/null || which chromium-browser 2>/dev/null || which google-chrome 2>/dev/null || true)
    if [[ -n "$CHROMIUM_PATH" ]]; then
        export PUPPETEER_EXECUTABLE_PATH="$CHROMIUM_PATH"
    fi
fi

echo '{"args":["--no-sandbox","--disable-setuid-sandbox"]}' > "$PUPPETEER_CFG"

# Map of markdown files to diagram names.
# Files with multiple mermaid blocks get numbered suffixes.
declare -A FILES=(
    ["c1-system-context.md"]="c1-system-context"
    ["c2-container-diagram.md"]="c2-container-diagram"
    ["c3-component-diagram.md"]="c3-component-diagram"
    ["c4-code-level-diagram.md"]="c4-code-level-diagram"
    ["c4-ui-feature-map.md"]="c4-ui-feature-map"
)

TOTAL=0
ERRORS=0

for md_file in "${!FILES[@]}"; do
    base_name="${FILES[$md_file]}"
    md_path="$C4_DIR/$md_file"

    if [[ ! -f "$md_path" ]]; then
        echo "SKIP  $md_file (not found)"
        continue
    fi

    # Extract all mermaid code blocks from the markdown
    block_idx=0
    in_block=false
    tmp_mmd=""

    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ ^\`\`\`mermaid ]]; then
            in_block=true
            block_idx=$((block_idx + 1))
            tmp_mmd=$(mktemp /tmp/mermaid_XXXXXX.mmd)
            continue
        fi
        if $in_block && [[ "$line" =~ ^\`\`\` ]]; then
            in_block=false

            # Determine output name
            if [[ $block_idx -eq 1 ]]; then
                out_name="$base_name"
            else
                out_name="${base_name}-${block_idx}"
            fi

            svg_out="$OUT_DIR/${out_name}.svg"
            png_out="$OUT_DIR/${out_name}.png"

            echo "RENDER $md_file (block $block_idx) -> $out_name.svg / .png"
            TOTAL=$((TOTAL + 1))

            if mmdc -i "$tmp_mmd" -o "$svg_out" -b transparent -p "$PUPPETEER_CFG" 2>/dev/null; then
                echo "  OK   $svg_out"
            else
                echo "  FAIL $svg_out"
                ERRORS=$((ERRORS + 1))
            fi

            if mmdc -i "$tmp_mmd" -o "$png_out" -b white -s 2 -p "$PUPPETEER_CFG" 2>/dev/null; then
                echo "  OK   $png_out"
            else
                echo "  FAIL $png_out"
                ERRORS=$((ERRORS + 1))
            fi

            rm -f "$tmp_mmd"
            continue
        fi
        if $in_block; then
            echo "$line" >> "$tmp_mmd"
        fi
    done < "$md_path"

    # Check total block count for this file
    if [[ $block_idx -eq 0 ]]; then
        echo "SKIP  $md_file (no mermaid blocks)"
    elif [[ $block_idx -gt 1 ]]; then
        # Rename first output from base_name to base_name-1
        for ext in svg png; do
            if [[ -f "$OUT_DIR/${base_name}.${ext}" ]]; then
                mv "$OUT_DIR/${base_name}.${ext}" "$OUT_DIR/${base_name}-1.${ext}"
                echo "  RENAME ${base_name}.${ext} -> ${base_name}-1.${ext}"
            fi
        done
    fi
done

echo ""
echo "Done. Rendered $TOTAL diagram(s) with $ERRORS error(s)."
echo "Output: $OUT_DIR/"
rm -f "$PUPPETEER_CFG"
