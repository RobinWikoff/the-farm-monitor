#!/usr/bin/env bash
# Generate SVG and PNG renderings of all C4 Mermaid diagrams.
# Usage: ./scripts/render_c4_diagrams.sh
#
# Diagram Standards:
#   - Title header: "The Farm Monitor App" top line + diagram name + generation date
#   - Font: DM Sans (Google Fonts), minimum 14px (≈12pt)
#   - Output: A4-friendly (794px viewport width at 96 DPI)
#
# Requirements:
#   - @mermaid-js/mermaid-cli (mmdc) on PATH: npm install -g @mermaid-js/mermaid-cli
#   - chromium on PATH (or set PUPPETEER_EXECUTABLE_PATH)
#   - Node.js with puppeteer (provided by mermaid-cli)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
C4_DIR="$REPO_ROOT/docs/c4"
OUT_DIR="$C4_DIR/rendered"
MMD_CONFIG="$SCRIPT_DIR/mermaid-config.json"
MMD_CSS="$SCRIPT_DIR/mermaid-styles.css"
PUPPETEER_CFG=$(mktemp /tmp/puppeteer_cfg_XXXXXX.json)
RENDER_DATE=$(date +%Y-%m-%d)

# A4 portrait width at 96 DPI (210mm ≈ 794px), with margins → 760px viewport
A4_WIDTH=760

mkdir -p "$OUT_DIR"

# ── DM Sans font check ────────────────────────────────────────────
if ! fc-list | grep -qi "DM Sans"; then
    echo "INFO  Installing DM Sans font..."
    sudo mkdir -p /usr/local/share/fonts/dm-sans
    sudo curl -sL "https://raw.githubusercontent.com/google/fonts/main/ofl/dmsans/DMSans%5Bopsz%2Cwght%5D.ttf" \
         -o /usr/local/share/fonts/dm-sans/DMSans-Variable.ttf
    sudo curl -sL "https://raw.githubusercontent.com/google/fonts/main/ofl/dmsans/DMSans-Italic%5Bopsz%2Cwght%5D.ttf" \
         -o /usr/local/share/fonts/dm-sans/DMSans-Italic-Variable.ttf
    sudo fc-cache -f /usr/local/share/fonts/dm-sans/
    echo "INFO  DM Sans installed."
fi

# Auto-detect chromium if PUPPETEER_EXECUTABLE_PATH is not set
if [[ -z "${PUPPETEER_EXECUTABLE_PATH:-}" ]]; then
    CHROMIUM_PATH=$(which chromium 2>/dev/null || which chromium-browser 2>/dev/null || which google-chrome 2>/dev/null || true)
    if [[ -n "$CHROMIUM_PATH" ]]; then
        export PUPPETEER_EXECUTABLE_PATH="$CHROMIUM_PATH"
    fi
fi

echo '{"args":["--no-sandbox","--disable-setuid-sandbox"]}' > "$PUPPETEER_CFG"

# ── SVG header injection ──────────────────────────────────────────
# Injects a two-line header ("The Farm Monitor App" + diagram subtitle)
# into the rendered SVG by expanding the viewBox and prepending text.
inject_svg_header() {
    local svg_file="$1"
    local subtitle="$2"
    local header_height=70

    # XML-escape the subtitle for safe SVG injection
    subtitle="${subtitle//&/&amp;}"
    subtitle="${subtitle//</&lt;}"
    subtitle="${subtitle//>/&gt;}"
    subtitle="${subtitle//\"/&quot;}"

    # Extract current viewBox (x y width height)
    local vb
    vb=$(grep -oP 'viewBox="\K[^"]+' "$svg_file" | head -1)
    if [[ -z "$vb" ]]; then return 1; fi

    read -r vb_x vb_y vb_w vb_h <<< "$vb"
    local new_h
    new_h=$(awk "BEGIN{print $vb_h + $header_height}")

    # Build header SVG group
    local header_group
    header_group=$(cat <<SVGEOF
<g class="diagram-header" transform="translate($(awk "BEGIN{print $vb_w / 2}"), 10)">
  <text text-anchor="middle" y="22" style="font-family: 'DM Sans', sans-serif; font-size: 18px; font-weight: 700; fill: #333;">The Farm Monitor App</text>
  <text text-anchor="middle" y="44" style="font-family: 'DM Sans', sans-serif; font-size: 14px; font-weight: 400; fill: #666;">$subtitle</text>
</g>
SVGEOF
)

    # Update viewBox, shift existing content down, insert header
    sed -i \
        -e "s|viewBox=\"${vb_x} ${vb_y} ${vb_w} ${vb_h}\"|viewBox=\"${vb_x} ${vb_y} ${vb_w} ${new_h}\"|" \
        -e "s|style=\"max-width:|style=\"max-width:|" \
        "$svg_file"

    # Find first <g> or <style> and insert header + wrapper before it
    # Shift all diagram content down by header_height using a transform wrapper
    # Also strip the mermaid-native title text to avoid duplication
    python3 -c "
import re, sys
with open('$svg_file', 'r') as f:
    svg = f.read()
# Remove mermaid-native title elements (text with class containing 'title' or
# the C4 title <text> that duplicates our injected header)
svg = re.sub(r'<text[^>]*class=\"[^\"]*[Tt]itle[^\"]*\"[^>]*>.*?</text>', '', svg, flags=re.DOTALL)
# Remove standalone title <text> (C4 and frontmatter) containing Generated date
svg = re.sub(r'<text[^>]*>[^<]*Generated\s+\d{4}-\d{2}-\d{2}[^<]*</text>', '', svg)
# Find the opening <svg...> closing >
m = re.search(r'(<svg[^>]*>)', svg)
if not m:
    sys.exit(1)
insert_pos = m.end()
# Wrap everything after <svg...> in a group that shifts down
tail = svg[insert_pos:]
# Find the closing </svg>
close_idx = tail.rfind('</svg>')
inner = tail[:close_idx]
after = tail[close_idx:]
header = '''$header_group'''
new_svg = svg[:insert_pos] + header + '<g transform=\"translate(0,$header_height)\">' + inner + '</g>' + after
with open('$svg_file', 'w') as f:
    f.write(new_svg)
"
}

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

            # Inject render date into placeholder
            sed -i "s/%%RENDER_DATE%%/$RENDER_DATE/g" "$tmp_mmd"

            # Determine output name
            if [[ $block_idx -eq 1 ]]; then
                out_name="$base_name"
            else
                out_name="${base_name}-${block_idx}"
            fi

            svg_out="$OUT_DIR/${out_name}.svg"
            png_out="$OUT_DIR/${out_name}.png"

            # Extract subtitle from the mermaid title directive or frontmatter
            local_subtitle=$(grep -oP '^\s*title\s+\K.+' "$tmp_mmd" | head -1 || true)
            if [[ -z "$local_subtitle" ]]; then
                local_subtitle=$(grep -oP '^title:\s*"?\K[^"]+' "$tmp_mmd" | head -1 || true)
            fi
            # Strip any leftover frontmatter delimiters
            local_subtitle="${local_subtitle//---/}"
            local_subtitle="${local_subtitle## }"

            echo "RENDER $md_file (block $block_idx) -> $out_name.svg / .png"
            TOTAL=$((TOTAL + 1))

            # 1) Render SVG via mmdc
            if mmdc -i "$tmp_mmd" -o "$svg_out" -b transparent -w "$A4_WIDTH" -c "$MMD_CONFIG" -C "$MMD_CSS" -p "$PUPPETEER_CFG" 2>/dev/null; then
                # 2) Inject two-line header into SVG
                if inject_svg_header "$svg_out" "$local_subtitle"; then
                    echo "  OK   $svg_out (with header)"
                else
                    echo "  OK   $svg_out (no header injected)"
                fi
            else
                echo "  FAIL $svg_out"
                ERRORS=$((ERRORS + 1))
            fi

            # 3) Convert post-processed SVG to PNG via Puppeteer/Chromium (2x scale for print)
            if [[ -f "$svg_out" ]]; then
                if NODE_PATH=/usr/local/lib/node_modules/@mermaid-js/mermaid-cli/node_modules \
                   node "$SCRIPT_DIR/svg-to-png.js" "$svg_out" "$png_out" 2 2>/dev/null; then
                    echo "  OK   $png_out"
                else
                    echo "  FAIL $png_out (svg-to-png)"
                    ERRORS=$((ERRORS + 1))
                fi
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
