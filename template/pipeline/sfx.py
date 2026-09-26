#!/usr/bin/env python3
"""Sound effects for every cue name in film.config.json `sfx`.

  npm run sfx                  # every effect that changed
  npm run sfx -- --force       # regenerate (spends credits)

Engines, in order:
  1. A sound file, when the entry names one (`file`, a path in the project),
     for example the CC0 Kenney sounds in assets/sfx/. Its source and licence
     come from assets/sfx/manifest.json, matched by SHA-256; a file that is
     not listed there (or differs from the listed one) is recorded as
     LICENCE UNKNOWN, which `npm run check:final -- --publish` refuses.
     Remove `file` to generate the effect from `prompt` instead (`seconds`
     applies to the generated effects only; a file plays at its own length).
  2. ElevenLabs sound generation, when ELEVENLABS_API_KEY is set and
     PF_NO_KEYS is not 1 (text prompt and length from the config).
  3. Placeholder: a synthesized stand in made with ffmpeg (a chime, a
     whoosh, a click or a low hit, picked by the entry's `placeholder`).
     Labelled in build/SOURCES.txt; for timing only.

Output: build/sfx/<name>.wav (48 kHz stereo). Where and how loud each effect
plays is the timeline's job (sfxFor in src/timeline.ts), not this script's.
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os

import common as C

ap = argparse.ArgumentParser()
ap.add_argument("--force", action="store_true")
args = ap.parse_args()

cfg = C.cfg()
C.need("ffmpeg")
man_path = C.build("sfx", "manifest.json")
manifest = json.load(open(man_path)) if os.path.exists(man_path) else {}
keyed = not C.no_keys() and bool(os.environ.get("ELEVENLABS_API_KEY"))
LIB = os.path.join(C.ROOT, "assets", "sfx")
listed = json.load(open(os.path.join(LIB, "manifest.json"))).get("files", {}) \
    if os.path.exists(os.path.join(LIB, "manifest.json")) else {}


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def file_path(name, spec):
    src = os.path.join(C.ROOT, spec["file"])
    if not os.path.isfile(src):
        C.die(f"sfx '{name}': no such file {spec['file']} (film.config.json sfx.{name}.file)")
    return src


def from_file(name, spec, dst):
    src = file_path(name, spec)
    C.ffmpeg("-i", src, "-ac", "2", "-ar", "48000", "-c:a", "pcm_s24le", dst)
    m = listed.get(os.path.relpath(os.path.abspath(src), LIB).replace(os.sep, "/"))
    if m and m.get("sha256") == sha256(src):
        return f"{m['author']}, {m['pack']}, {m['license']} ({m['page']}): {spec['file']}"
    return f"LICENCE UNKNOWN: {spec['file']} is not listed with this SHA-256 in assets/sfx/manifest.json"

# ffmpeg sources for the placeholders: (lavfi source, extra filter)
SYNTH = {
    "chime": ("aevalsrc='0.35*sin(2*PI*1318.5*t)*exp(-4*t)+0.18*sin(2*PI*1975.5*t)*exp(-6*t)':s=48000:d={d}", "anull"),
    "whoosh": ("anoisesrc=c=pink:r=48000:a=0.5:d={d}", "highpass=f=400,lowpass=f=5000,afade=t=in:d={a},afade=t=out:st={a}:d={b}"),
    "click": ("aevalsrc='0.5*sin(2*PI*2200*t)*exp(-90*t)':s=48000:d={d}", "anull"),
    "hit": ("aevalsrc='0.8*sin(2*PI*55*t)*exp(-2.2*t)+0.3*sin(2*PI*110*t)*exp(-3*t)':s=48000:d={d}", "lowpass=f=900"),
}


def placeholder(name, spec, dst):
    kind = spec.get("placeholder", "click")
    if kind not in SYNTH:
        C.die(f"sfx '{name}': placeholder must be one of {sorted(SYNTH)}")
    d = float(spec.get("seconds", 1.0))
    src, af = SYNTH[kind]
    C.ffmpeg("-f", "lavfi", "-i", src.format(d=d), "-af", af.format(a=d * 0.4, b=d * 0.6),
             "-ac", "2", "-ar", "48000", "-c:a", "pcm_s24le", dst)
    return f"PLACEHOLDER synthesized {kind} (timing only, do not publish)"


def eleven(name, spec):
    raw = C.build("sfx", "raw", f"{name}.mp3")
    body = {"text": spec["prompt"], "duration_seconds": float(spec.get("seconds", 1.0)), "prompt_influence": 0.6}
    code = C.curl_json("https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_192",
                       body, C.eleven_headers(), raw)
    if code != 200:
        msg = open(raw, errors="replace").read()[:500] if os.path.exists(raw) else ""
        return name, None, f"HTTP {code}: {msg}"
    return name, raw, None


todo = []
for name, spec in cfg.get("sfx", {}).items():
    engine = "file" if spec.get("file") else "elevenlabs" if keyed else "placeholder"
    # a file entry also changes when the file's bytes change
    ident = [engine, spec] + ([sha256(file_path(name, spec))] if engine == "file" else [])
    key = hashlib.sha1(json.dumps(ident).encode()).hexdigest()
    dst = C.build("sfx", f"{name}.wav")
    if not args.force and manifest.get(name, {}).get("hash") == key and os.path.exists(dst):
        print(f"{name}: unchanged")
        continue
    todo.append((name, spec, key, dst, engine))

gen = [t for t in todo if t[4] == "elevenlabs"]
got = {}
if gen:
    with cf.ThreadPoolExecutor(2) as ex:
        got = {n: (raw, err) for n, raw, err in ex.map(lambda t: eleven(t[0], t[1]), gen)}
for name, spec, key, dst, engine in todo:
    if engine == "file":
        source = from_file(name, spec, dst)
    elif engine == "elevenlabs":
        raw, err = got[name]
        if err:
            C.die(f"sfx '{name}': ElevenLabs sound generation failed: {err}")
        C.ffmpeg("-i", raw, "-ac", "2", "-ar", "48000", "-c:a", "pcm_s24le", dst)
        source = "ElevenLabs sound generation"
    else:
        source = placeholder(name, spec, dst)
    manifest[name] = {"hash": key, "source": source}
    C.record_source(f"sfx/{name}.wav", source)
    print(f"{name}: {C.duration(dst):.2f} s  {source}")

with open(man_path, "w") as f:
    json.dump(manifest, f, indent=1)
