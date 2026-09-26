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
  - the music sections do not tile the cut (a gap, an overlap, or not
    from 0 to the cut's end), or one is shorter than 3 s (the ElevenLabs
    music minimum)
  - acts are out of order or leave a gap
  - an sfx cue names an effect that film.config.json does not define
  - a teaser segment is out of order, outside the vertical, or cuts
    inside a spoken word (40 ms margin)
  - a cut (or the teaser) has no POSTER moment, or it is not a frame from 1
    to the cut's last frame (a warning when it sits within 8 frames of an
    act edge, where the acts crossfade)
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
    secs = c["music"]["sections"]
    if not secs:
        fails.append(f"{cid}: MUSIC.sections is empty")
    else:
        if abs(secs[0]["from"]) > 1e-6:
            fails.append(f"{cid}: the first music section starts at {secs[0]['from']} s, not 0")
        for a, b in zip(secs, secs[1:]):
            if abs(b["from"] - a["to"]) > 1e-6:
                fails.append(f"{cid}: music section '{a['name']}' ends at {a['to']} s but '{b['name']}' starts at {b['from']} s "
                             "(sections must tile the cut; when merging two, extend one over the other)")
        if abs(secs[-1]["to"] - c["dur"]) > 1e-6:
            fails.append(f"{cid}: the last music section ends at {secs[-1]['to']} s, the cut is {c['dur']} s")
    for s in secs:
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

# poster: every delivered cut names a frame to bake into its frame 0
durs = {cid: c["dur"] for cid, c in tl["cuts"].items()}
if V:
    durs["teaser"] = sum(round(s["to"] * fps) / fps - round(s["from"] * fps) / fps for s in tl["teaser"])
poster = tl.get("poster") or {}
for cid, d in durs.items():
    p = poster.get(cid)
    if not isinstance(p, (int, float)):
        fails.append(f"POSTER has no moment for {cid} (src/timeline.ts)")
        continue
    k, n = C.poster_frame(p, fps), round(d * fps)
    if k < 1 or k > n - 1:
        fails.append(f"POSTER.{cid} is {p} s, frame {k}; it must be a frame from 1 to {n - 1} of the {d:.2f} s {cid}")
        continue
    edges = sorted({e for s in tl["cuts"][cid]["acts"].values() for e in (s["from"], s["to"]) if 0 < e < d}) if cid in tl["cuts"] else []
    for e in edges:
        if abs(p - e) < 8 / fps:
            warns.append(f"POSTER.{cid} is {p} s, within 8 frames of an act edge at {e} s: likely mid transition")

for w in warns:
    print(f"WARN  {w}")
for f in fails:
    print(f"FAIL  {f}")
total = sum(round(s["to"] * fps) / fps - round(s["from"] * fps) / fps for s in tl["teaser"])
print(f"check:timeline: {len(tl['lines'])} lines, {len(tl['cuts'])} cuts, teaser {total:.2f} s: "
      + ("PASS" if not fails else f"FAIL ({len(fails)})"))
raise SystemExit(1 if fails else 0)
