#!/usr/bin/env python3
"""Word timings for every spoken line, for the karaoke captions.

  npm run words

Transcribes each cleaned line (build/voice/<id>.wav) with whisper, aligns the
heard words onto the DISPLAY text from the timeline (the words the captions
show), corrects word onsets, and writes public/generated/words.json, which
the scenes load at render time.

Whisper backends, first one found wins:
  - whisper.cpp: `whisper-cli` on PATH (or WHISPER_CPP_BIN), model file at
    WHISPER_MODEL or models/ggml-base.en.bin (pipeline/get-whisper-model.sh
    downloads it)
  - openai-whisper: the `whisper` command (pip install openai-whisper),
    model name from WHISPER_PY_MODEL (default base.en)
  - none: words spread over the line by character count, flagged
    "proportional"; check:captions fails on it unless you pass
    --allow-proportional

Two corrections, measured on the voice file itself (10 ms RMS windows):
  - Drift: some whisper models (the small ones especially) stretch word
    times, so the last word "ends" well after the voice does. When the heard
    span overruns the audible speech by more than 0.15 s, the heard times are
    mapped linearly onto the audible span.
  - Onsets: whisper often hands the pause BEFORE a word to that word, so the
    caption would light the word while nothing is audible. A word that starts
    in silence, or opens on the previous word's tail and then a pause of
    100 ms or more, is moved to where the voice's energy comes back.
    `npm run check:captions` runs the same tests and fails what is left.

Bigger models time words better: `npm run whisper-model -- small.en` or
`npm run whisper-model -- large-v3-turbo-q5_0`, then point WHISPER_MODEL at it.
"""
import difflib
import json
import os
import re
import shutil
import subprocess
import tempfile

import common as C

cfg = C.cfg()
tl = C.timeline()
man_path = C.build("voice", "manifest.json")
if not os.path.exists(man_path):
    C.die("no build/voice/manifest.json: run `npm run voice` first")
manifest = json.load(open(man_path))


def backend():
    cpp = os.environ.get("WHISPER_CPP_BIN") or shutil.which("whisper-cli")
    model = os.environ.get("WHISPER_MODEL") or os.path.join(C.ROOT, "models", "ggml-base.en.bin")
    if cpp and os.path.exists(model):
        return ("cpp", cpp, model)
    if shutil.which("whisper"):
        return ("python", shutil.which("whisper"), os.environ.get("WHISPER_PY_MODEL", "base.en"))
    return ("none", None, None)


def transcribe(kind, exe, model, wav16):
    """Return heard words as [text, start, end] in seconds."""
    with tempfile.TemporaryDirectory() as td:
        if kind == "cpp":
            prefix = os.path.join(td, "w")
            C.run([exe, "-m", model, "-f", wav16, "-ml", "1", "-sow", "-oj", "-of", prefix, "-np"])
            segs = json.load(open(prefix + ".json"))["transcription"]
            toks = []
            for s in segs:
                txt = s["text"].strip()
                if not txt:
                    continue
                t0, t1 = s["offsets"]["from"] / 1000, s["offsets"]["to"] / 1000
                if re.fullmatch(r"[^\w$%]+", txt) and toks:  # a bare punctuation token joins the word before it
                    toks[-1][0] += txt
                    toks[-1][2] = t1
                    continue
                toks.append([txt, t0, t1])
            return toks
        C.run([exe, wav16, "--model", model, "--word_timestamps", "True", "--output_format", "json",
               "--output_dir", td, "--fp16", "False", "--language", "en"])
        data = json.load(open(os.path.join(td, os.path.splitext(os.path.basename(wav16))[0] + ".json")))
        return [[w["word"].strip(), w["start"], w["end"]] for s in data["segments"] for w in s.get("words", []) if w["word"].strip()]


def norm(w):
    return re.sub(r"[^a-z0-9$%]", "", w.lower())


def align(display, heard):
    """Map every display word onto heard timings. Returns (words, method)."""
    d = [norm(w) for w in display]
    h = [norm(w[0]) for w in heard]
    sm = difflib.SequenceMatcher(None, d, h, autojunk=False)
    times = [None] * len(display)
    exact = True
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                times[i1 + k] = (heard[j1 + k][1], heard[j1 + k][2])
        elif op == "replace":
            exact = False
            # spread the heard span over the display words by character count
            t0, t1 = heard[j1][1], heard[j2 - 1][2]
            lens = [max(1, len(display[i])) for i in range(i1, i2)]
            tot, acc = sum(lens), 0
            for k, i in enumerate(range(i1, i2)):
                times[i] = (t0 + (t1 - t0) * acc / tot, t0 + (t1 - t0) * (acc + lens[k]) / tot)
                acc += lens[k]
        elif op == "delete":
            exact = False  # display words nobody heard: squeezed in below
        elif op == "insert":
            exact = False  # heard words the captions do not show: ignored
    # fill any display word still without a time from its neighbours
    for i in range(len(times)):
        if times[i] is None:
            prev_e = next((times[j][1] for j in range(i - 1, -1, -1) if times[j]), 0.0)
            next_t = next((times[j][0] for j in range(i + 1, len(times)) if times[j]), prev_e + 0.3)
            times[i] = (prev_e, max(prev_e + 0.05, next_t))
    return [[w, t[0], t[1]] for w, t in zip(display, times)], ("aligned" if exact else "matched")


def envelope(wav16):
    """10 ms RMS windows of the line, and the silence floor from the config."""
    rms = C.rms_frames(C.pcm_mono(wav16, 16000), 160)
    pk = max(rms) if rms else 0
    return rms, pk * 10 ** (cfg.get("captions", {}).get("silenceDb", -30) / 20)


def fix_drift(heard, rms, floor):
    """Map a stretched transcript onto the audible span. Returns True if it did."""
    lit = [i for i, v in enumerate(rms) if v >= floor]
    if not heard or not lit:
        return False
    s0, s1 = lit[0] / 100, (lit[-1] + 1) / 100
    h0, h1 = heard[0][1], heard[-1][2]
    if h1 <= s1 + 0.15 or h1 <= h0:
        return False
    k = (s1 - s0) / (h1 - h0)
    for w in heard:
        w[1], w[2] = s0 + (w[1] - h0) * k, s0 + (w[2] - h0) * k
    return True


def snap_onsets(words, rms, floor):
    """Move every word that starts in silence, or opens into a pause, to where
    the voice comes back. Returns the count."""
    peak = max(rms) if rms else 0
    moved = 0
    for n, w in enumerate(words):
        i0 = int(round(w[1] * 100))
        back = C.voice_return(rms, w[1], w[2], peak)
        if back is None and i0 < len(rms) and max(rms[i0:i0 + 6]) < floor:
            j = i0
            while j < len(rms) and rms[j] < floor:
                j += 1
            back = j / 100 if j < len(rms) else None
        if back is None or back <= w[1]:
            continue
        w[1] = back
        w[2] = max(w[2], w[1] + 0.05)
        moved += 1
        for later in words[n + 1:]:  # keep the order
            later[1] = max(later[1], w[1])
            later[2] = max(later[2], later[1] + 0.01)
    return moved


kind, exe, model = backend()
print(f"whisper backend: {kind}" + (f" ({os.path.basename(str(model))})" if model else ""))
out = {"backend": kind, "lines": {}}
with tempfile.TemporaryDirectory() as td:
    for line in tl["lines"]:
        lid = line["id"]
        wav = C.build("voice", f"{lid}.wav")
        if not os.path.exists(wav) or lid not in manifest:
            C.die(f"{lid} has no voice file: run `npm run voice` first")
        dur = C.duration(wav)
        display = line["text"].split()
        wav16 = os.path.join(td, f"{lid}.wav")
        C.ffmpeg("-i", wav, "-ar", "16000", "-ac", "1", wav16)
        heard = transcribe(kind, exe, model, wav16) if kind != "none" else []
        notes = []
        if heard:
            rms, floor = envelope(wav16)
            if fix_drift(heard, rms, floor):
                notes.append("drift corrected")
            words, method = align(display, heard)
            moved = snap_onsets(words, rms, floor)
            if moved:
                notes.append(f"{moved} onsets moved out of pauses")
        else:
            tot = sum(len(w) for w in display)
            acc, words = 0, []
            for w in display:
                words.append([w, acc / tot * dur, (acc + len(w)) / tot * dur])
                acc += len(w)
            method = "proportional"
        out["lines"][lid] = {
            "dur": round(dur, 3),
            "method": method,
            "heard": " ".join(h[0] for h in heard),
            "words": [{"w": w, "t": round(max(0, t), 3), "e": round(min(dur, e), 3)} for w, t, e in words],
        }
        extra = f"  ({', '.join(notes)})" if notes else ""
        print(f"{lid}: {method:12s} {len(display)} words, {dur:.2f} s   heard: {out['lines'][lid]['heard']!r}{extra}")

# write only when the timings changed: check:final treats a newer words.json as a reason to re-render
path = C.generated("words.json")
old = None
if os.path.exists(path):
    try:
        old = json.load(open(path, encoding="utf-8"))
    except ValueError:
        pass
if old == out:
    print("public/generated/words.json unchanged")
else:
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print("wrote public/generated/words.json")
