#!/usr/bin/env python3
"""Score each cut from the timeline's music plan.

  npm run music                      # every cut whose plan changed
  npm run music -- --cut master      # one cut
  npm run music -- --takes 2         # two takes per cut, to pick from by ear
  npm run music -- --use 2           # promote take 2 to the cut's track (no API call)
  npm run music -- --force           # regenerate (spends credits)

Engines, in order:
  1. ElevenLabs Music, when ELEVENLABS_API_KEY is set and PF_NO_KEYS is not 1.
     The request is a composition plan: global styles plus one section per
     act of the cut (src/timeline.ts MUSIC.sections), each with its exact
     duration, so the score turns where the picture turns.
  2. Placeholder: a soft synthesized chord pad, one chord per section, made
     with ffmpeg. Labelled in build/SOURCES.txt; for timing only.

Output: build/music/<cut>.wav (48 kHz stereo). Takes are kept as
build/music/raw/<cut>.take<N>.mp3.

Two limits of the ElevenLabs music API shape this script: every section must
be at least 3 s long (check:timeline enforces it), and an account runs at
most 2 music requests at a time, so takes are generated 2 at a time.
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os

import common as C

ap = argparse.ArgumentParser()
ap.add_argument("--cut", action="append", default=[])
ap.add_argument("--takes", type=int, default=1)
ap.add_argument("--use", type=int, default=0, help="promote an existing take to the cut's track")
ap.add_argument("--force", action="store_true")
args = ap.parse_args()

tl = C.timeline()
C.need("ffmpeg")
man_path = C.build("music", "manifest.json")
manifest = json.load(open(man_path)) if os.path.exists(man_path) else {}
MIN_SECTION_MS = 3000


def plan_for(cut):
    """The ElevenLabs composition plan for one cut, section durations summing to the cut exactly."""
    total = int(round(cut["dur"] * 1000))
    sections, used = [], 0
    secs = cut["music"]["sections"]
    for i, s in enumerate(secs):
        if abs(s["from"] * 1000 - used) > 1:
            C.die(f"{cut['id']}: music section '{s['name']}' starts at {s['from']} s, but the sections before it end at "
                  f"{used / 1000} s. Sections must tile the cut (run `npm run check:timeline`).")
        if i == len(secs) - 1 and abs(s["to"] - cut["dur"]) > 0.001:
            C.die(f"{cut['id']}: the last music section ends at {s['to']} s, the cut is {cut['dur']} s")
        ms = total - used if i == len(secs) - 1 else int(round((s["to"] - s["from"]) * 1000))
        used += ms
        if ms < MIN_SECTION_MS:
            C.die(f"{cut['id']}: music section '{s['name']}' is {ms} ms; ElevenLabs music needs 3000 ms or more. "
                  "Merge it with a neighbour in MUSIC.sections (src/timeline.ts).")
        sections.append({
            "section_name": s["name"],
            "positive_local_styles": s["styles"],
            "negative_local_styles": s["avoid"],
            "duration_ms": ms,
            "lines": [],
        })
    return {
        "positive_global_styles": tl["music"]["global"],
        "negative_global_styles": tl["music"]["avoid"],
        "sections": sections,
    }


def eleven(cut_id, plan, take):
    raw = C.build("music", "raw", f"{cut_id}.take{take}.mp3")
    code = C.curl_json(
        "https://api.elevenlabs.io/v1/music/stream?output_format=mp3_44100_192",
        {"composition_plan": plan, "model_id": "music_v1"},
        C.eleven_headers(), raw, timeout=900,
    )
    if code != 200:
        msg = open(raw, errors="replace").read()[:500] if os.path.exists(raw) else ""
        return take, None, f"HTTP {code}: {msg}"
    return take, raw, None


# One chord per section (C, Am, F, G, then back to C for the last section).
CHORDS = [
    (130.81, 196.00, 261.63, 329.63),
    (110.00, 164.81, 220.00, 261.63),
    (87.31, 130.81, 174.61, 220.00),
    (98.00, 146.83, 196.00, 246.94),
]
RESOLVE = (65.41, 130.81, 196.00, 261.63, 329.63)


def placeholder(cut_id, plan):
    parts = []
    n = len(plan["sections"])
    for i, s in enumerate(plan["sections"]):
        d = s["duration_ms"] / 1000
        notes = RESOLVE if i == n - 1 and n > 1 else CHORDS[i % len(CHORDS)]
        amp = 0.05 + 0.015 * min(i, 3)
        voices = "+".join(f"sin(2*PI*{f}*t)" for f in notes)
        expr = f"{amp}*({voices})*(0.75+0.25*sin(2*PI*0.2*t))"
        p = C.build("music", "raw", f"{cut_id}.ph{i}.wav")
        C.ffmpeg("-f", "lavfi", "-i", f"aevalsrc='{expr}':s=48000:d={d:.3f}",
                 "-af", f"lowpass=f=1800,afade=t=in:d=0.25,afade=t=out:st={max(0, d - 0.3):.3f}:d=0.3",
                 "-ac", "2", "-c:a", "pcm_s16le", p)
        parts.append(p)
    lst = C.build("music", "raw", f"{cut_id}.ph.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    raw = C.build("music", "raw", f"{cut_id}.placeholder.wav")
    C.ffmpeg("-f", "concat", "-safe", "0", "-i", lst, "-c:a", "pcm_s16le", raw)
    for p in parts:
        os.remove(p)
    os.remove(lst)
    return raw


def to_track(raw, cut):
    dst = C.build("music", f"{cut['id']}.wav")
    C.ffmpeg("-i", raw, "-ac", "2", "-ar", "48000", "-af", f"apad=whole_dur={cut['dur']},atrim=0:{cut['dur']}",
             "-c:a", "pcm_s24le", dst)
    return dst


cuts = [c for cid, c in tl["cuts"].items() if not args.cut or cid in args.cut]
keyed = not C.no_keys() and bool(os.environ.get("ELEVENLABS_API_KEY"))
take_path = lambda cid, t: C.build("music", "raw", f"{cid}.take{t}.mp3")


def save():
    with open(man_path, "w") as f:
        json.dump(manifest, f, indent=1)


if args.use:
    # check every cut first, so a missing take never leaves some cuts promoted and others not
    missing = [c["id"] for c in cuts if not os.path.exists(take_path(c["id"], args.use))]
    if missing:
        C.die(f"no take {args.use} for: {', '.join(missing)} (generate it with --takes {args.use}, or pass --cut)")
    for cut in cuts:
        cid = cut["id"]
        to_track(take_path(cid, args.use), cut)
        manifest.setdefault(cid, {})["take"] = args.use
        C.record_source(f"music/{cid}.wav", f"ElevenLabs Music (music_v1), take {args.use}")
        save()
        print(f"{cid}: take {args.use} is now build/music/{cid}.wav")
    raise SystemExit(0)

for cut in cuts:
    cid = cut["id"]
    plan = plan_for(cut)
    engine = "elevenlabs" if keyed else "placeholder"
    key = hashlib.sha1(json.dumps([engine, plan]).encode()).hexdigest()
    dst = C.build("music", f"{cid}.wav")
    fresh = manifest.get(cid, {}).get("hash") == key and os.path.exists(dst) and not args.force
    if engine == "placeholder":
        if fresh:
            print(f"{cid}: unchanged")
            continue
        to_track(placeholder(cid, plan), cut)
        source = "PLACEHOLDER synthesized chord pad (timing only, do not publish)"
        manifest[cid] = {"hash": key, "take": 1, "source": source}
    else:
        if not fresh:
            # the plan changed (or --force): takes of the old plan must not be promotable
            for f in os.listdir(os.path.dirname(take_path(cid, 1))):
                if f.startswith(f"{cid}.take") and f.endswith(".mp3"):
                    os.remove(os.path.join(os.path.dirname(take_path(cid, 1)), f))
        want = [t for t in range(1, args.takes + 1) if not os.path.exists(take_path(cid, t))]
        if not want:
            print(f"{cid}: unchanged ({args.takes} take(s) on disk; --use N to switch, --force to regenerate)")
            continue
        # at most 2 requests in flight: the API refuses a third concurrent one
        with cf.ThreadPoolExecutor(2) as ex:
            results = list(ex.map(lambda t: eleven(cid, plan, t), want))
        bad = [f"take {t}: {err}" for t, _, err in results if err]
        if bad:
            C.die(f"{cid}: ElevenLabs music failed: " + "; ".join(bad))
        chosen = manifest.get(cid, {}).get("take", 1) if fresh else 1
        if not fresh:
            to_track(take_path(cid, 1), cut)
        source = f"ElevenLabs Music (music_v1), take {chosen}"
        manifest[cid] = {"hash": key, "take": chosen, "source": source}
        if len(want) < args.takes or args.takes > 1:
            print(f"{cid}: generated take(s) {', '.join(map(str, want))}; listen, then `npm run music -- --use N`")
    C.record_source(f"music/{cid}.wav", source)
    save()
    names = ", ".join(f"{s['section_name']} {s['duration_ms'] / 1000:.1f} s" for s in plan["sections"])
    print(f"{cid}: {C.duration(dst):.2f} s  {source}  [{names}]")

with open(man_path, "w") as f:
    json.dump(manifest, f, indent=1)
