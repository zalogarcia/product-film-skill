#!/bin/bash
# Final delivery encode for one cut, then the poster step.
#
#   npm run finish -- master      build/render/master.mp4 + build/mix/master.wav -> out/master.mp4
#   npm run finish -- vertical
#   npm run finish -- teaser      (after `npm run teaser`)
#   CRF=16 npm run finish -- master
#
# H.264 High, yuv420p LIMITED range with bt709 tags (what every player and
# platform expects; a render in full range is converted, not just relabelled),
# AAC 192k 48 kHz stereo, faststart. The encode lands in build/encode/<cut>.mp4
# at a high quality; `npm run poster` then bakes the cut's POSTER moment into
# frame 0 and writes out/<cut>.mp4 at the delivery CRF (default 18), checking
# that nothing but frame 0 changed. Then it prints the probe and the
# loudness and true peak measured on the FINAL file: the AAC encode overshoots
# the WAV's true peak, so the WAV's number is never the one that counts.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CUT="${1:-}"
if [ -z "$CUT" ]; then echo "usage: npm run finish -- <master|vertical|teaser>" >&2; exit 2; fi
BUILD="$(python3 -c 'import json;print(json.load(open("film.config.json")).get("buildDir","build"))')"
OUTD="$(python3 -c 'import json;print(json.load(open("film.config.json")).get("outDir","out"))')"
V="$BUILD/render/$CUT.mp4"
A="$BUILD/mix/$CUT.wav"
OUT="$OUTD/$CUT.mp4"
ENC="$BUILD/encode/$CUT.mp4"
for f in "$V" "$A"; do
  if [ ! -f "$f" ]; then echo "ERROR: missing $f (render, mix or teaser first)" >&2; exit 1; fi
done
mkdir -p "$OUTD" "$BUILD/encode"

# a full range render (yuvj420p or color_range=pc) is converted to limited range
RANGE="$(ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt,color_range -of csv=p=0 "$V")"
case "$RANGE" in
  *yuvj*|*pc*) IN=full ;;
  *) IN=limited ;;
esac

ffmpeg -hide_banner -loglevel error -y -i "$V" -i "$A" \
  -map 0:v:0 -map 1:a:0 \
  -vf "scale=in_range=$IN:out_range=limited:in_color_matrix=bt709:out_color_matrix=bt709,format=yuv420p,setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709" \
  -c:v libx264 -preset medium -crf 10 -profile:v high -pix_fmt yuv420p \
  -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -c:a aac -b:a 192k -ar 48000 -ac 2 -shortest -movflags +faststart "$ENC"

# the poster step writes the delivered file (at CRF, default 18) and checks it
bash pipeline/poster.sh "$CUT"

echo "== $OUT (input range: $IN)"
ffprobe -v error -show_entries stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,color_range,sample_rate,channels \
  -show_entries format=duration,size -of default=nw=1 "$OUT"
echo "== loudness of the final file"
ffmpeg -hide_banner -nostats -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | grep -A16 "Summary:" | grep -E "I:|LRA:|Peak:" || true
if [ -f "$BUILD/SOURCES.txt" ] && grep -q PLACEHOLDER "$BUILD/SOURCES.txt"; then
  echo "WARNING: this cut contains PLACEHOLDER assets (see $BUILD/SOURCES.txt). Timing and layout only; do not publish."
fi
