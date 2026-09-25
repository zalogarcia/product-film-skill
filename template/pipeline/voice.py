#!/usr/bin/env python3
"""Voice every line of the timeline, then clean it for the mix.

  npm run voice                 # every line that changed since the last run
  npm run voice -- --only L2    # just one line
  npm run voice -- --force      # regenerate everything (spends credits)

Engines, in order:
  1. ElevenLabs text to speech, when ELEVENLABS_API_KEY and the speaker's
     voice id variable (film.config.json voices.<who>.elevenlabsVoiceEnv) are
     set and PF_NO_KEYS is not 1. You bring your own key and voice.
  2. Placeholder: macOS `say`, else `espeak-ng`, else silence of a plausible
     length. Placeholders are labelled in build/SOURCES.txt and are for
     timing and layout only, never for publishing.

Output: build/voice/<id>.wav (48 kHz mono, leading and trailing silence
trimmed) and build/voice/manifest.json with every line's measured duration.
A regenerated line almost always changes length: run `npm run words` and
`npm run check:timeline` after this, every time.
"""
import argparse
import hashlib
import json
import os
import shutil

import common as C

ap = argparse.ArgumentParser()
ap.add_argument("--only", action="append", default=[])
ap.add_argument("--force", action="store_true")
args = ap.parse_args()

cfg = C.cfg()
tl = C.timeline()
C.need("ffmpeg")
man_path = C.build("voice", "manifest.json")
manifest = json.load(open(man_path)) if os.path.exists(man_path) else {}


def engine_for(who):
    v = cfg["voices"].get(who)
    if v is None:
        C.die(f"speaker '{who}' has no entry under voices in film.config.json")
    voice_id = os.environ.get(v.get("elevenlabsVoiceEnv", ""), "")
    if not C.no_keys() and os.environ.get("ELEVENLABS_API_KEY") and voice_id:
        return "elevenlabs", v, voice_id
    if shutil.which("say"):
        return "say", v, None
    if shutil.which("espeak-ng"):
        return "espeak-ng", v, None
    return "silence", v, None


def settings_for(line, v):
    """The speaker's voice settings, with this line's own speed on top."""
    s = dict(v.get("settings") or {})
    if line.get("speed") is not None:
        s["speed"] = line["speed"]
    return s


def synth(line, engine, v, voice_id, raw):
    text = line.get("tts") or line["text"]
    settings = settings_for(line, v)
    if engine == "elevenlabs":
        body = {"text": text, "model_id": v.get("elevenlabsModel", "eleven_multilingual_v2")}
        if settings:
            body["voice_settings"] = settings
        code = C.curl_json(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128",
            body, C.eleven_headers(), raw,
        )
        if code != 200:
            msg = open(raw, errors="replace").read()[:500] if os.path.exists(raw) else ""
            C.die(f"ElevenLabs TTS returned HTTP {code} for {line['id']}: {msg}")
        return "ElevenLabs TTS (" + body["model_id"] + ")"
    if engine == "say":
        # words per minute (175 is the default); say moves in coarse steps, so small speeds may not change it
        rate = str(int(175 * settings.get("speed", 1.0)))
        r = C.subprocess.run(["say", "-v", v.get("sayVoice", "Samantha"), "-r", rate, "-o", raw, text], capture_output=True)
        if r.returncode != 0:  # the named voice is not installed: use the default one
            C.run(["say", "-r", rate, "-o", raw, text])
        return "PLACEHOLDER macOS say (timing and layout only, do not publish)"
    if engine == "espeak-ng":
        C.run(["espeak-ng", "-s", str(int(175 * settings.get("speed", 1.0))), "-w", raw, text])
        return "PLACEHOLDER espeak-ng (timing and layout only, do not publish)"
    dur = 0.35 * len(text.split()) + 0.3
    C.ffmpeg("-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono", "-t", f"{dur:.2f}", raw)
    return "PLACEHOLDER silence (no voice engine found; timing only)"


def clean(raw, dst):
    """48 kHz mono, trim silence at both ends, 10 ms fades."""
    tmp = dst + ".tmp.wav"
    trim = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02"
    C.ffmpeg("-i", raw, "-ac", "1", "-ar", "48000", "-af", f"{trim},areverse,{trim},areverse", "-c:a", "pcm_s24le", tmp)
    d = C.duration(tmp)
    if d < 0.05:  # all silence (the silent placeholder): keep it as it is
        C.ffmpeg("-i", raw, "-ac", "1", "-ar", "48000", "-c:a", "pcm_s24le", tmp)
        d = C.duration(tmp)
    C.ffmpeg("-i", tmp, "-af", f"afade=t=in:d=0.01,afade=t=out:st={max(0, d - 0.01):.3f}:d=0.01", "-c:a", "pcm_s24le", dst)
    os.remove(tmp)
    return C.duration(dst)


for line in tl["lines"]:
    lid = line["id"]
    if args.only and lid not in args.only:
        continue
    engine, v, voice_id = engine_for(line["who"])
    text = line.get("tts") or line["text"]
    key = hashlib.sha1(json.dumps([engine, voice_id and hashlib.sha1(voice_id.encode()).hexdigest(), text,
                                   settings_for(line, v), v.get("elevenlabsModel"), v.get("sayVoice")],
                                  sort_keys=True).encode()).hexdigest()
    dst = C.build("voice", f"{lid}.wav")
    if not args.force and manifest.get(lid, {}).get("hash") == key and os.path.exists(dst):
        print(f"{lid}: unchanged ({manifest[lid]['dur']:.2f} s)")
        continue
    ext = {"elevenlabs": "mp3", "say": "aiff", "espeak-ng": "wav", "silence": "wav"}[engine]
    raw = C.build("voice", "raw", f"{lid}.{ext}")
    source = synth(line, engine, v, voice_id, raw)
    d = clean(raw, dst)
    old = manifest.get(lid, {}).get("dur")
    manifest[lid] = {"dur": round(d, 3), "hash": key, "source": source}
    C.record_source(f"voice/{lid}.wav", source)
    moved = f" (was {old:.2f} s: re-run words and check:timeline)" if old and abs(old - d) > 0.02 else ""
    print(f"{lid}: {d:.2f} s  {source}{moved}")

with open(man_path, "w") as f:
    json.dump(manifest, f, indent=1)
