#!/bin/bash
# Render, mix and finish all three cuts: 16:9 master, 9:16 vertical, teaser.
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
for CUT in master vertical; do
  node pipeline/render.cjs "$CUT" --scale "$SCALE"
  python3 pipeline/mix.py "$CUT"
done
python3 pipeline/teaser.py
for CUT in master vertical teaser; do
  bash pipeline/finish.sh "$CUT"
done
python3 pipeline/qc.py
