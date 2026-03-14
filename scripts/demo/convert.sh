#!/usr/bin/env bash
set -euo pipefail

# Convert WebM recordings to MP4 and extract GIF for README
# Usage: ./scripts/demo/convert.sh

DEMO_DIR="/tmp/binex_demo"
OUT_DIR="/Users/alex/Desktop/Binex/docs/demo"

mkdir -p "$OUT_DIR"

echo "==> Converting WebM files to MP4..."

for webm in "$DEMO_DIR"/*.webm; do
    [ -f "$webm" ] || continue
    name=$(basename "$webm" .webm)
    mp4="$OUT_DIR/${name}.mp4"
    echo "    $webm → $mp4"
    ffmpeg -y -i "$webm" -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p "$mp4" 2>/dev/null
done

echo ""
echo "==> Creating GIF for README (first MP4, 15 seconds)..."

first_mp4=$(ls "$OUT_DIR"/*.mp4 2>/dev/null | head -1)
if [ -n "$first_mp4" ]; then
    gif="$OUT_DIR/binex-demo.gif"
    # Extract 15s starting from 5s, scale to 720px wide, 10fps
    ffmpeg -y -ss 5 -t 15 -i "$first_mp4" \
        -vf "fps=10,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
        "$gif" 2>/dev/null
    echo "    GIF: $gif"
fi

echo ""
echo "==> Done! Files in $OUT_DIR:"
ls -lh "$OUT_DIR"/
