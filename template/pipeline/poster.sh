#!/bin/bash
# The poster step: bake the cut's poster moment into frame 0 of the delivered file.
#
#   npm run poster -- master      build/encode/master.mp4 -> out/master.mp4 + out/master.poster.png
#   npm run poster -- vertical
#   npm run poster -- teaser
#   CRF=16 npm run poster -- master
#
# `npm run finish` runs this after its encode, so every cut gets it. Run it on its own
# after changing POSTER in src/timeline.ts: it redoes only this pass, not the encode.
#
# POSTER names a SETTLED moment (type fully in, not mid transition) on each cut's own
# clock. X, Slack, Discord and most players show frame 0 as the thumbnail before anyone
# presses play, so frame 0 becomes that moment; on playback it shows for one frame.
# pipeline/poster-frame0.sh does the work and checks it: same size, fps, frame count,
# duration and audio, frame 0 is the poster, frames 1 onward match the encode
# (PSNR >= 40 dB). `npm run check:final` measures the same things on the delivered file.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CUT="${1:-}"
if [ -z "$CUT" ]; then echo "usage: npm run poster -- <master|vertical|teaser>" >&2; exit 2; fi
BUILD="$(python3 -c 'import json;print(json.load(open("film.config.json")).get("buildDir","build"))')"
OUTD="$(python3 -c 'import json;print(json.load(open("film.config.json")).get("outDir","out"))')"
IN="$BUILD/encode/$CUT.mp4"
if [ ! -f "$IN" ]; then echo "ERROR: missing $IN (run \`npm run finish -- $CUT\`)" >&2; exit 1; fi
AT="$(node --no-warnings --experimental-strip-types pipeline/timeline-json.mjs |
  python3 -c 'import json, sys; p = json.load(sys.stdin).get("poster") or {}; c = sys.argv[1]
if c not in p: sys.exit(f"ERROR: POSTER in src/timeline.ts has no entry for {c}")
print(p[c])' "$CUT")"
echo "== poster for $CUT: its frame at $AT s becomes frame 0"
bash pipeline/poster-frame0.sh "$IN" "$OUTD/$CUT.mp4" --at "$AT" --crf "${CRF:-18}" --force
