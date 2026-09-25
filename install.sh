#!/bin/bash
# Install the product-film skill for Claude Code.
#
#   bash install.sh                        -> ~/.claude/skills/product-film
#   bash install.sh --dest <skills folder> -> <skills folder>/product-film
#
# Copies skill/product-film (SKILL.md and its references) and the starter
# project in template/ (without node_modules, renders or generated files)
# into the skill's folder, so the skill keeps working if this clone is moved
# or deleted. Re-running it replaces the installed copy of the template.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
while [ $# -gt 0 ]; do
  case "$1" in
    --dest) [ $# -ge 2 ] || { echo "usage: bash install.sh [--dest <skills folder>]" >&2; exit 2; }; DEST="$2"; shift 2 ;;
    *) echo "usage: bash install.sh [--dest <skills folder>]" >&2; exit 2 ;;
  esac
done
T="$DEST/product-film"
mkdir -p "$T"
cp -R "$HERE/skill/product-film/." "$T/"
rm -rf "$T/template"
mkdir -p "$T/template"
(cd "$HERE/template" && tar cf - \
  --exclude ./node_modules --exclude ./build --exclude ./out --exclude ./models \
  --exclude ./public/generated --exclude ./public/stills --exclude __pycache__ --exclude .DS_Store .) \
  | (cd "$T/template" && tar xf -)
echo "installed the product-film skill at $T"
echo "start a film:  cp -R \"$T/template\" my-film && cd my-film && npm ci && npm run example"
