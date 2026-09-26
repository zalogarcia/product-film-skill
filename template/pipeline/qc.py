#!/usr/bin/env python3
"""Gate: the delivered files are right, measured on the files themselves.

  npm run check:final                   # every cut in out/
  npm run check:final -- --publish      # also fail if any asset is a placeholder

For every cut in the timeline (out/master.mp4, out/vertical.mp4) and the
teaser (out/teaser.mp4); a missing file fails:
  - one H.264 video stream, yuv420p, limited range, and one AAC stereo 48 kHz stream
  - the picture has the cut's aspect ratio (any scale) and even dimensions
  - the duration matches the timeline (teaser: the sum of its segments) to one frame
  - the moov atom sits before the media (faststart, so the file plays while it loads)
  - integrated loudness within loudness.lufsTolerance of loudness.targetLufs,
    and true peak at or under loudness.truePeakMaxDb, measured on the ENCODED audio
  - the poster step ran: frame 0 is the cut's POSTER moment (PSNR >= 40 dB
    against that frame of build/encode/<cut>.mp4, the encode it was made
    from), frames 1 onward match that encode (min PSNR >= 40 dB), and the
    frame count and the audio packets are unchanged

It also prints where each asset THIS film uses came from (build/SOURCES.txt,
limited to the current lines, cues, cuts and stills), and fails:
  - with --publish, when any of those assets is a placeholder or unrecorded
  - always, when a delivered file is older than anything it was made from:
    its render and mix in build/, the assets and word timings above, the
    stills, film.config.json and every source file under src/ (re-run
    `npm run cuts`)
"""
import argparse
import json
import os
import re
import subprocess
import tempfile

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


def psnr(a, b, graph):
    """ffmpeg's psnr filter over `graph` (inputs a and b); returns the average, or None."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", a, "-i", b, "-filter_complex", graph,
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"average:(inf|[\d.]+)", r.stderr)
    return None if not m else (float("inf") if m[-1] == "inf" else float(m[-1]))


def audio_md5(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", path, "-map", "0:a:0",
                        "-c", "copy", "-f", "md5", "-"], capture_output=True, text=True)
    return r.stdout.strip() or None


def nb_frames(path):
    r = C.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=nb_frames",
               "-of", "default=nw=1:nk=1", path])
    return r.stdout.strip()


def poster_fails(cid, name, path):
    """Frame 0 is the POSTER moment and nothing else moved, measured against the encode."""
    enc = C.build("encode", f"{cid}.mp4")
    at = (tl.get("poster") or {}).get(cid)
    if at is None:
        return [f"{name}: POSTER in src/timeline.ts has no moment for {cid}"]
    if not os.path.exists(enc):
        return [f"{name}: no build/encode/{cid}.mp4, so the poster step never ran (`npm run finish -- {cid}`)"]
    k = C.poster_frame(at, fps)
    out_ = []
    if nb_frames(path) != nb_frames(enc):
        out_.append(f"{name}: {nb_frames(path)} frames, its encode has {nb_frames(enc)}")
    if audio_md5(path) != audio_md5(enc):
        out_.append(f"{name}: the audio differs from build/encode/{cid}.mp4 (the poster step must copy it)")
    p0 = psnr(path, enc, f"[0:v]trim=end_frame=1,setpts=PTS-STARTPTS[a];"
                         f"[1:v]trim=start_frame={k}:end_frame={k + 1},setpts=PTS-STARTPTS[b];[a][b]psnr")
    if p0 is None or p0 < 40:
        out_.append(f"{name}: frame 0 is not the poster (PSNR {p0} dB against frame {k} of the encode, POSTER.{cid} = {at} s): "
                    f"run `npm run poster -- {cid}`")
    with tempfile.TemporaryDirectory() as td:
        stats = os.path.join(td, "psnr.log")
        subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", path, "-i", enc,
                        "-filter_complex", f"[0:v][1:v]psnr=stats_file={stats}", "-f", "null", "-"],
                       capture_output=True, text=True)
        rows = []
        if os.path.exists(stats):
            for line in open(stats):
                n = re.search(r"\bn:(\d+)", line)
                v = re.search(r"psnr_avg:(inf|[\d.]+)", line)
                if n and v:
                    rows.append((int(n.group(1)), float("inf") if v.group(1) == "inf" else float(v.group(1))))
    rest = [v for n, v in rows if n >= 2]
    worst = min(rest) if rest else None
    if not rest or worst < 40:
        out_.append(f"{name}: frames 1 onward differ from build/encode/{cid}.mp4 (min PSNR {worst} dB over {len(rest)} frames)")
    if not out_:
        print(f"poster {name}: frame 0 = frame {k} ({at} s, PSNR {p0:.1f} dB), frames 1 to {len(rest)} "
              f"unchanged (min PSNR {worst:.1f} dB), audio copied")
    return out_


def moov_first(path):
    with open(path, "rb") as f:
        head = f.read(4 * 1024 * 1024)
    m, d = head.find(b"moov"), head.find(b"mdat")
    return m != -1 and (d == -1 or m < d)


fails, checked = [], 0
for cid, (W, H, D) in expect.items():
    p = C.out(f"{cid}.mp4")
    if not os.path.exists(p):
        fails.append(f"out/{cid}.mp4 is missing (run `npm run cuts`)")
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
    fails += poster_fails(cid, name, p)

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
sources = [os.path.join(C.ROOT, "film.config.json")]
for d, _, fs in os.walk(os.path.join(C.ROOT, "src")):
    sources += [os.path.join(d, f) for f in fs if f.endswith((".ts", ".tsx"))]
for cid, inputs in per_cut.items():
    p = C.out(f"{cid}.mp4")
    if not os.path.exists(p):
        continue
    t_out = os.path.getmtime(p)
    paths = [C.build(*a.split("/")) for a in inputs] + [words_json, C.build("render", f"{cid}.mp4"),
                                                         C.build("mix", f"{cid}.wav"),
                                                         C.build("encode", f"{cid}.mp4")] + sources
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
