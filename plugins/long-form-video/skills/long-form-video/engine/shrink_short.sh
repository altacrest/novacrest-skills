#!/bin/bash
# shrink_short.sh: re-encode one short to just under 9.6 MB (Claude in Chrome's file upload takes under 10 MB a call):
# two-pass x264, audio copied, then the SSIM against the original (0.97 or more looks the same at full size).
#   bash engine/shrink_short.sh <video folder>/out/shorts/short-seg-004.mp4 <video folder>/out/shorts_small/short-seg-004.mp4
set -e
src=$1; dst=$2
[ -f "$src" ] && [ -n "$dst" ] || { echo "usage: shrink_short.sh <short.mp4> <smaller.mp4>"; exit 1; }
mkdir -p "$(dirname "$dst")"
log=$(mktemp -d)/pass
d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$src")
ab=$(ffprobe -v error -select_streams a:0 -show_entries stream=bit_rate -of csv=p=0 "$src")
vb=$(python3 -c "print(int((9.6e6*8/$d - $ab) * 0.97 / 1000))")
ffmpeg -v error -y -i "$src" -c:v libx264 -preset slow -b:v ${vb}k -pass 1 -passlogfile "$log" -an -f mp4 /dev/null
ffmpeg -v error -y -i "$src" -c:v libx264 -preset slow -b:v ${vb}k -pass 2 -passlogfile "$log" -pix_fmt yuv420p -c:a copy -movflags +faststart "$dst"
ssim=$(ffmpeg -hide_banner -i "$dst" -i "$src" -lavfi "[0:v][1:v]ssim" -f null - 2>&1 | grep -o "All:[0-9.]*" | tail -1)
echo "$(basename "$dst"): $(du -h "$dst" | cut -f1), SSIM $ssim"
