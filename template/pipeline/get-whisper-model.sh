#!/bin/bash
# Download a whisper.cpp model into models/ (words.py looks there by default).
#
#   npm run whisper-model                 base.en, about 150 MB
#   npm run whisper-model -- small.en     better timings, about 490 MB
#
# Models come from the whisper.cpp project's model repository on Hugging Face.
# openai-whisper users do not need this: that package downloads its own.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
M="${1:-base.en}"
DEST="$ROOT/models/ggml-$M.bin"
mkdir -p "$ROOT/models"
if [ -s "$DEST" ]; then echo "exists: models/ggml-$M.bin"; exit 0; fi
curl -fsSL --retry 3 -o "$DEST.part" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-$M.bin"
mv "$DEST.part" "$DEST"
echo "wrote models/ggml-$M.bin ($(du -h "$DEST" | cut -f1))"
if [ "$M" != "base.en" ]; then echo "use it with: WHISPER_MODEL=models/ggml-$M.bin npm run words"; fi
