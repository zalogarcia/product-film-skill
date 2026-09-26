#!/usr/bin/env bash
# Build (or repair) the OPTIONAL audio venv at tools/audio/.venv: librosa and
# friends for `npm run beats` and tools/audio/rate_sfx.py. The film pipeline
# never needs it; the example renders without it.
#
#   bash tools/audio/setup.sh            create the venv if missing, install the lock
#   bash tools/audio/setup.sh --relock   re-resolve requirements.lock.txt first (needs uv)
#
# Python: with uv on PATH (https://docs.astral.sh/uv/), a uv managed CPython
# 3.12, a native build for this machine. Without uv, the first python3.12 or
# newer on PATH that runs natively. On Apple silicon the venv must be arm64: an
# x86_64 Python under Rosetta gets wheels that fail to import or run slowly, so
# setup skips one, and refuses a venv built with one.
#
# Supply chain: the lock pins every package with its hashes and was resolved
# with --exclude-newer CUTOFF, so no version released after the cutoff can
# enter it. Move CUTOFF on purpose, to a date at least 7 days before the day
# you relock, so every package has been public for a week.
#
# A finished install leaves a copy of the lock in the venv; beats.sh re-runs
# this script whenever that copy is missing or differs from the lock.
set -euo pipefail

CUTOFF="2026-09-18T00:00:00Z"
HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="$HERE/.venv"
LOCK="$HERE/requirements.lock.txt"
MARK="$VENV/.installed-lock.txt"
have() { command -v "$1" >/dev/null 2>&1; }
ARM=0
if [ "$(uname -s)" = "Darwin" ] && [ "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" = "1" ]; then ARM=1; fi
# a usable Python: 3.12 or newer, and native arm64 on Apple silicon
usable() {
  "$1" -c 'import platform, sys
sys.exit(0 if sys.version_info >= (3, 12) and (sys.argv[1] == "0" or platform.machine() == "arm64") else 1)' "$ARM" 2>/dev/null
}

if [ "${1:-}" = "--relock" ]; then
  have uv || { echo "setup.sh: --relock needs uv (https://docs.astral.sh/uv/)" >&2; exit 2; }
  (cd "$HERE" && uv pip compile --universal --python-version 3.12 --generate-hashes \
    --exclude-newer "$CUTOFF" --custom-compile-command "bash tools/audio/setup.sh --relock" \
    requirements.in -o requirements.lock.txt)
fi

CREATED=0
if [ ! -x "$VENV/bin/python" ]; then
  rm -f "$MARK"
  if have uv; then
    uv venv --python 3.12 --python-preference only-managed "$VENV"
  else
    PY=""
    for c in python3.14 python3.13 python3.12 python3; do
      if have "$c" && usable "$c"; then PY="$c"; break; fi
    done
    [ -n "$PY" ] || { echo "setup.sh: needs uv, or a native Python 3.12 or newer on PATH" >&2; exit 2; }
    "$PY" -m venv "$VENV"
  fi
  CREATED=1
fi

if ! usable "$VENV/bin/python"; then
  WHAT="$("$VENV/bin/python" -c 'import platform, sys; print(sys.version.split()[0], platform.machine())' 2>/dev/null || echo "a broken")"
  if [ "$CREATED" = 1 ]; then rm -rf "$VENV"; fi
  echo "setup.sh: the venv's Python is $WHAT; it needs 3.12 or newer, native arm64 on Apple silicon." >&2
  [ "$CREATED" = 1 ] || echo "          delete $VENV and re-run (uv installs a native Python)" >&2
  exit 2
fi

if have uv; then
  uv pip install --python "$VENV/bin/python" --require-hashes -r "$LOCK"
else
  "$VENV/bin/python" -m pip install --quiet --require-hashes -r "$LOCK"
fi

"$VENV/bin/python" - <<'PY'
import platform, sys
import numpy, scipy, soundfile, librosa
print(f"audio venv ok: python {sys.version.split()[0]} {platform.machine()}, "
      f"numpy {numpy.__version__}, scipy {scipy.__version__}, "
      f"soundfile {soundfile.__version__}, librosa {librosa.__version__}")
PY
cp "$LOCK" "$MARK"
