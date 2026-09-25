#!/bin/bash
# The example film, end to end, with NO paid APIs (PF_NO_KEYS=1):
#   voice    PLACEHOLDER: macOS `say`, else espeak-ng, else silence
#   music    PLACEHOLDER: a synthesized chord pad, one chord per act
#   sfx      PLACEHOLDER: synthesized chime, whoosh, click and hit
#   stills   skipped (the film renders without plates)
# Everything placeholder is listed in build/SOURCES.txt. The run proves the
# pipeline and the layout; it is not a film to publish.
#
#   npm run example                  half resolution (fast)
#   npm run example -- --scale 1     full resolution
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SCALE=0.5
while [ $# -gt 0 ]; do
  case "$1" in
    --scale) SCALE="$2"; shift 2 ;;
    *) echo "usage: npm run example -- [--scale N]" >&2; exit 2 ;;
  esac
done
export PF_NO_KEYS=1
step() { printf '\n== %s\n' "$*"; }

step "voice"; python3 pipeline/voice.py
step "words (whisper)"; python3 pipeline/words.py
step "music"; python3 pipeline/music.py
step "sfx"; python3 pipeline/sfx.py
step "stills"; python3 pipeline/stills.py

step "gate: timeline"; python3 pipeline/check_timeline.py
step "gate: captions"
if python3 -c 'import json,sys; sys.exit(0 if json.load(open("public/generated/words.json"))["backend"]=="none" else 1)'; then
  echo "NOTE: no whisper found, so word timings are proportional guesses. Fine for this demo;"
  echo "      install whisper.cpp or openai-whisper before a real film (README, prerequisites)."
  python3 pipeline/check_captions.py --allow-proportional
else
  python3 pipeline/check_captions.py
fi
step "gate: claims"; python3 pipeline/check_claims.py
step "gate: safe zones, master"; python3 pipeline/check_safe.py master --scale "$SCALE"
step "gate: safe zones, vertical"; python3 pipeline/check_safe.py vertical --scale "$SCALE"

step "render, mix and finish the three cuts (scale $SCALE)"; bash pipeline/cuts.sh --scale "$SCALE"

step "frame check: contact sheets to look at"
for C in master vertical teaser; do python3 pipeline/contact.py "out/$C.mp4"; done
printf '\nDone. Films: out/master.mp4, out/vertical.mp4, out/teaser.mp4 (placeholder audio).\n'
