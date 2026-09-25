#!/usr/bin/env python3
"""Gate: the captions light each word when it is heard, and are readable.

  npm run check:captions
  npm run check:captions -- --allow-proportional   # no whisper installed (layout only)

Fails (exit 1) when:
  - a line's timings were guessed (method "proportional") instead of
    measured by whisper
  - the word timings are stale: the line's text or its voice file changed
    since `npm run words`
  - a word starts where the voice is silent, after it has ended, or on the
    previous word's tail right before a pause (the pause trap: whisper hands
    the pause before a word to that word, so the caption would light early)
  - word times run backwards or past the end of the line
  - a line reads faster than captions.maxCharsPerSecond

Lines marked onScreen in the timeline are not captioned, so they are only
checked for staleness.
"""
import argparse
import json
import os

import common as C

ap = argparse.ArgumentParser()
ap.add_argument("--allow-proportional", action="store_true")
args = ap.parse_args()

cfg = C.cfg()
tl = C.timeline()
wp = os.path.join(C.ROOT, "public", "generated", "words.json")
if not os.path.exists(wp):
    C.die("no public/generated/words.json: run `npm run words` first")
words = json.load(open(wp))
man = json.load(open(C.build("voice", "manifest.json")))
cps_max = cfg.get("captions", {}).get("maxCharsPerSecond", 20)
silence_db = cfg.get("captions", {}).get("silenceDb", -30)

fails, notes = [], []
for L in tl["lines"]:
    lid = L["id"]
    W = words["lines"].get(lid)
    if not W:
        fails.append(f"{lid}: no word timings (run `npm run words`)")
        continue
    ws = W["words"]
    if [w["w"] for w in ws] != L["text"].split():
        fails.append(f"{lid}: the caption text changed since `npm run words` (re-run it)")
        continue
    if abs(W["dur"] - man.get(lid, {}).get("dur", -1)) > 0.01:
        fails.append(f"{lid}: the voice file changed since `npm run words` (re-run it)")
        continue
    if W["method"] == "proportional" and not args.allow_proportional:
        fails.append(f"{lid}: timings are proportional guesses, not measured (install whisper; see the README)")
    if L.get("onScreen"):
        continue
    prev = 0.0
    for w in ws:
        if w["t"] < prev - 0.01 or w["e"] <= w["t"] or w["e"] > W["dur"] + 0.01:
            fails.append(f"{lid}: '{w['w']}' has bad times ({w['t']:.2f} to {w['e']:.2f} s)")
        prev = w["t"]
    cps = len(L["text"]) / max(0.1, W["dur"])
    if cps > cps_max:
        fails.append(f"{lid}: {cps:.1f} characters per second, over the limit of {cps_max}")
    if W["method"] == "proportional":
        continue
    # onset check on the voice file itself: is there sound in the first 80 ms of each word?
    pcm = C.pcm_mono(C.build("voice", f"{lid}.wav"), 16000)
    rms = C.rms_frames(pcm, 160)  # 10 ms windows
    if not rms or max(rms) == 0:
        fails.append(f"{lid}: the voice file is silent")
        continue
    floor = max(rms) * 10 ** (silence_db / 20)
    late = []
    for w in ws:
        i0 = int(w["t"] * 100)
        window = rms[i0:i0 + 8]
        back = C.voice_return(rms, w["t"], w["e"], max(rms))
        if not window or max(window) < floor:
            late.append(f"'{w['w']}' at {w['t']:.2f} s (silent there)")
        elif back is not None:
            late.append(f"'{w['w']}' at {w['t']:.2f} s (the voice only starts it at {back:.2f} s, after a pause)")
    if late:
        fails.append(f"{lid}: words lit where the voice is silent or over: {', '.join(late)}")
    notes.append(f"{lid}: {len(ws)} words, {cps:.1f} chars/s, {W['method']}")

for n in notes:
    print(f"ok    {n}")
for f in fails:
    print(f"FAIL  {f}")
print(f"check:captions: backend {words.get('backend')}: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
raise SystemExit(1 if fails else 0)
