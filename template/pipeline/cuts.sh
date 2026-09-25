#!/bin/bash
# Render, mix and finish every cut in src/timeline.ts CUTS (the example has a
# 16:9 master and a 9:16 vertical), then the teaser cut from the vertical.
#
#   npm run cuts                   full resolution
#   npm run cuts -- --scale 0.5    half resolution (a fast preview of everything)
#
# Assumes voice, words, music and sfx are done (and stills, if you use them),
# and that the checks passed. Each step stops the run on failure.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SCALE=1
while [ $# -gt 0 ]; do
  case "$1" in
    --scale) SCALE="$2"; shift 2 ;;
    *) echo "usage: npm run cuts -- [--scale N]" >&2; exit 2 ;;
  esac
done
CUTS="$(node --no-warnings --experimental-strip-types pipeline/timeline-json.mjs |
  python3 -c 'import json, sys; c = json.load(sys.stdin)["cuts"]; print(" ".join(list(c) + (["teaser"] if "vertical" in c else [])))')"
for CUT in $CUTS; do
  [ "$CUT" = teaser ] && continue
  node pipeline/render.cjs "$CUT" --scale "$SCALE"
  python3 pipeline/mix.py "$CUT"
done
case " $CUTS " in *" teaser "*) python3 pipeline/teaser.py ;; esac
for CUT in $CUTS; do
  bash pipeline/finish.sh "$CUT"
done
python3 pipeline/qc.py
