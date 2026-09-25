#!/usr/bin/env python3
"""Gate: the timeline still fits the audio that was actually generated.

  npm run check:timeline

A regenerated voice line almost always comes back a different length, so
every number in the timeline has to be re-checked against the MEASURED
durations (build/voice/manifest.json) and word timings
(public/generated/words.json), not against the durations you planned for.

Fails (exit 1) when:
  - two spoken lines overlap, or sit closer than 0.1 s
  - a line runs past the end of a cut it starts in
  - a line starts inside an act but runs 0.5 s or more past it (warning)
  - a music section is shorter than 3 s (the ElevenLabs music minimum)
  - acts are out of order or leave a gap
  - an sfx cue names an effect that film.config.json does not define
  - a teaser segment is out of order, outside the vertical, or cuts
    inside a spoken word (40 ms margin)
"""
import json
import os

import common as C

cfg = C.cfg()
tl = C.timeline()
man_path = C.build("voice", "manifest.json")
if not os.path.exists(man_path):
    C.die("no build/voice/manifest.json: run `npm run voice` first")
man = json.load(open(man_path))
words_path = os.path.join(C.ROOT, "public", "generated", "words.json")
words = json.load(open(words_path)) if os.path.exists(words_path) else None

fails, warns = [], []
dur = {}
for L in tl["lines"]:
    if L["id"] not in man:
        fails.append(f"{L['id']}: no measured voice (run `npm run voice`)")
        continue
    dur[L["id"]] = man[L["id"]]["dur"]

ids = [L["id"] for L in tl["lines"]]
if len(ids) != len(set(ids)):
    fails.append("line ids are not unique")

spans = sorted((L["at"], L["at"] + dur.get(L["id"], 0), L["id"]) for L in tl["lines"])
for (a0, a1, ai), (b0, b1, bi) in zip(spans, spans[1:]):
    if b0 < a1 + 0.1:
        fails.append(f"{ai} ends at {a1:.2f} s but {bi} starts at {b0:.2f} s (overlap or gap under 0.1 s)")

for cid, c in tl["cuts"].items():
    acts = sorted(((s["from"], s["to"], n) for n, s in c["acts"].items()))
    if acts[0][0] != 0:
        fails.append(f"{cid}: the first act starts at {acts[0][0]} s, not 0")
    for (a0, a1, an), (b0, b1, bn) in zip(acts, acts[1:]):
        if abs(b0 - a1) > 1e-6:
            fails.append(f"{cid}: act '{an}' ends at {a1} s but '{bn}' starts at {b0} s")
    if abs(acts[-1][1] - c["dur"]) > 1e-6:
        fails.append(f"{cid}: the last act ends at {acts[-1][1]} s, the cut is {c['dur']} s")
    for L in tl["lines"]:
        if L["at"] >= c["dur"] or L["id"] not in dur:
            continue
        end = L["at"] + dur[L["id"]]
        if end > c["dur"]:
            fails.append(f"{cid}: {L['id']} ends at {end:.2f} s, after the cut ends ({c['dur']} s)")
        for n, s in c["acts"].items():
            if s["from"] <= L["at"] < s["to"] and end > s["to"] + 0.5:
                warns.append(f"{cid}: {L['id']} starts in act '{n}' but runs {end - s['to']:.2f} s past it")
    for s in c["music"]["sections"]:
        if s["to"] - s["from"] < 3.0 - 1e-6:
            fails.append(f"{cid}: music section '{s['name']}' is {s['to'] - s['from']:.2f} s; the minimum is 3 s")
    for q in c["sfx"]:
        if q["name"] not in cfg.get("sfx", {}):
            fails.append(f"{cid}: sfx cue '{q['name']}' is not defined in film.config.json")

# teaser: on the vertical's clock, and every edge in a gap between words
V = tl["cuts"].get("vertical")
fps = tl["fps"]
spoken_words = []
if words:
    for L in tl["lines"]:
        for w in words["lines"].get(L["id"], {}).get("words", []):
            spoken_words.append((L["at"] + w["t"], L["at"] + w["e"], w["w"], L["id"]))
elif tl["teaser"]:
    warns.append("no public/generated/words.json yet: teaser edges not checked against words (run `npm run words`)")
last = -1
for i, s in enumerate(tl["teaser"]):
    a, b = round(s["from"] * fps) / fps, round(s["to"] * fps) / fps
    if a < last or b <= a:
        fails.append(f"teaser segment {i + 1} ({a:.2f} to {b:.2f} s) is out of order or empty")
    if V and b > V["dur"]:
        fails.append(f"teaser segment {i + 1} ends at {b:.2f} s, past the vertical ({V['dur']} s)")
    last = b
    for edge in (a, b):
        for t0, t1, w, lid in spoken_words:
            if t0 + 0.04 < edge < t1 - 0.04:
                fails.append(f"teaser segment {i + 1} edge {edge:.2f} s cuts inside '{w}' ({lid}, {t0:.2f} to {t1:.2f} s)")

for w in warns:
    print(f"WARN  {w}")
for f in fails:
    print(f"FAIL  {f}")
total = sum(round(s["to"] * fps) / fps - round(s["from"] * fps) / fps for s in tl["teaser"])
print(f"check:timeline: {len(tl['lines'])} lines, {len(tl['cuts'])} cuts, teaser {total:.2f} s: "
      + ("PASS" if not fails else f"FAIL ({len(fails)})"))
raise SystemExit(1 if fails else 0)
