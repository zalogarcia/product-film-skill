#!/usr/bin/env python3
"""Gate: the delivered files are right, measured on the files themselves.

  npm run check:final                   # every cut in out/
  npm run check:final -- --publish      # also fail if any asset is a placeholder

For out/master.mp4, out/vertical.mp4 and out/teaser.mp4 (those that exist):
  - one H.264 video stream, yuv420p, limited range, and one AAC stereo 48 kHz stream
  - the picture has the cut's aspect ratio (any scale) and even dimensions
  - the duration matches the timeline (teaser: the sum of its segments) to one frame
  - the moov atom sits before the media (faststart, so the file plays while it loads)
  - integrated loudness within loudness.lufsTolerance of loudness.targetLufs,
    and true peak at or under loudness.truePeakMaxDb, measured on the ENCODED audio

It also prints where each asset THIS film uses came from (build/SOURCES.txt,
limited to the current lines, cues, cuts and stills), and fails:
  - with --publish, when any of those assets is a placeholder or unrecorded
  - always, when a delivered file is older than an asset or the word
    timings it was made from (re-run `npm run cuts`)
"""
import argparse
import json
import os

import common as C

ap = argparse.ArgumentParser()
ap.add_argument("--publish", action="store_true")
args = ap.parse_args()

cfg = C.cfg()
tl = C.timeline()
fps = tl["fps"]
L = cfg["loudness"]
teaser_dur = sum(round(s["to"] * fps) / fps - round(s["from"] * fps) / fps for s in tl["teaser"])
expect = {cid: (c["w"], c["h"], c["dur"]) for cid, c in tl["cuts"].items()}
v = tl["cuts"].get("vertical")
if v:
    expect["teaser"] = (v["w"], v["h"], teaser_dur)


def moov_first(path):
    with open(path, "rb") as f:
        head = f.read(4 * 1024 * 1024)
    m, d = head.find(b"moov"), head.find(b"mdat")
    return m != -1 and (d == -1 or m < d)


fails, checked = [], 0
for cid, (W, H, D) in expect.items():
    p = C.out(f"{cid}.mp4")
    if not os.path.exists(p):
        continue
    checked += 1
    info = json.loads(C.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", p]).stdout)
    vs = [s for s in info["streams"] if s["codec_type"] == "video"]
    aus = [s for s in info["streams"] if s["codec_type"] == "audio"]
    name = f"out/{cid}.mp4"
    if len(vs) != 1 or vs[0]["codec_name"] != "h264":
        fails.append(f"{name}: expected one H.264 video stream")
        continue
    s = vs[0]
    if s.get("pix_fmt") != "yuv420p" or s.get("color_range") != "tv":
        fails.append(f"{name}: {s.get('pix_fmt')} {s.get('color_range')}, expected yuv420p tv (limited)")
    w, h = s["width"], s["height"]
    if w % 2 or h % 2 or abs(w / h - W / H) > 0.01:
        fails.append(f"{name}: {w}x{h} is not the cut's {W}:{H} shape with even sides")
    if len(aus) != 1 or aus[0]["codec_name"] != "aac" or aus[0].get("channels") != 2 or aus[0].get("sample_rate") != "48000":
        fails.append(f"{name}: expected one AAC stereo 48 kHz audio stream")
    d = float(info["format"]["duration"])
    if abs(d - D) > 1.5 / fps:
        fails.append(f"{name}: {d:.3f} s, the timeline says {D:.3f} s")
    if not moov_first(p):
        fails.append(f"{name}: not faststart (moov after mdat)")
    m = C.loudness(p)
    if m["I"] is None or abs(m["I"] - L["targetLufs"]) > L["lufsTolerance"]:
        fails.append(f"{name}: {m['I']} LUFS, target {L['targetLufs']} +/- {L['lufsTolerance']}")
    if m["TP"] is None or m["TP"] > L["truePeakMaxDb"]:
        fails.append(f"{name}: true peak {m['TP']} dBFS, limit {L['truePeakMaxDb']}")
    size = int(info["format"]["size"]) / 1e6
    print(f"file  {name}: {w}x{h}, {d:.2f} s, {size:.1f} MB, {m['I']} LUFS, true peak {m['TP']} dBFS")

# provenance: only the assets this timeline and config actually use
lines = [L["id"] for L in tl["lines"]]
stills_json = os.path.join(C.ROOT, "public", "generated", "stills.json")
stills = json.load(open(stills_json)) if os.path.exists(stills_json) else []
per_cut = {}
for cid in tl["cuts"]:
    per_cut[cid] = ([f"voice/{i}.wav" for i in lines if next(L for L in tl["lines"] if L["id"] == i)["at"] < tl["cuts"][cid]["dur"]]
                    + [f"sfx/{q['name']}.wav" for q in tl["cuts"][cid]["sfx"]] + [f"music/{cid}.wav"])
if "vertical" in per_cut:
    per_cut["teaser"] = per_cut["vertical"]
assets = sorted({a for v in per_cut.values() for a in v} | {f"stills/{n}.png" for n in stills})
rows = {}
src = C.build("SOURCES.txt")
if os.path.exists(src):
    for line in open(src, encoding="utf-8"):
        if "\t" in line:
            k, v = line.rstrip("\n").split("\t", 1)
            rows[k] = v
print("sources of the assets this film uses (build/SOURCES.txt):")
placeholders, unknown = [], []
for a in assets:
    v = rows.get(a)
    print(f"      {a}\t{v or 'UNKNOWN (no record)'}")
    if v is None:
        unknown.append(a)
    elif "PLACEHOLDER" in v:
        placeholders.append(a)
if placeholders or unknown:
    msg = (f"{len(placeholders)} placeholder and {len(unknown)} unrecorded assets: "
           "timing and layout only, NOT publishable")
    if args.publish:
        fails.append(msg)
    else:
        print(f"WARN  {msg}")

# staleness: a delivered file older than anything it was made from
words_json = os.path.join(C.ROOT, "public", "generated", "words.json")
for cid, inputs in per_cut.items():
    p = C.out(f"{cid}.mp4")
    if not os.path.exists(p):
        continue
    t_out = os.path.getmtime(p)
    paths = [C.build(*a.split("/")) for a in inputs] + [words_json]
    paths += [os.path.join(C.ROOT, "public", "stills", f"{n}.png") for n in stills]
    newer = [os.path.relpath(x, C.ROOT) for x in paths if os.path.exists(x) and os.path.getmtime(x) > t_out]
    if newer:
        fails.append(f"out/{cid}.mp4 is older than {', '.join(newer[:4])}{' ...' if len(newer) > 4 else ''}: "
                     "re-run `npm run cuts`")
if not checked:
    fails.append("no finished cuts in out/ (run `npm run cuts`)")
for f in fails:
    print(f"FAIL  {f}")
print(f"check:final: {checked} files: " + ("PASS" if not fails else f"FAIL ({len(fails)})"))
raise SystemExit(1 if fails else 0)
