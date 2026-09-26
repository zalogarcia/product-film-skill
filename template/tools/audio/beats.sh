#!/usr/bin/env bash
# Beat map for a music track (optional). Builds or updates tools/audio/.venv
# first whenever it is missing or older than requirements.lock.txt.
#
#   npm run beats -- <track.wav|mp3> [--out <json>] [--md <md>] [--bpm-hint 120]
#   npm run beats -- --selftest
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cmp -s "$HERE/requirements.lock.txt" "$HERE/.venv/.installed-lock.txt" || bash "$HERE/setup.sh" >&2
exec "$HERE/.venv/bin/python" "$HERE/beats.py" "$@"
