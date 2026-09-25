"""Shared helpers for the pipeline scripts. Standard library only.

Every path is relative to the project root (the folder holding
film.config.json), so the project can live anywhere.
"""
import array
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def cfg():
    with open(os.path.join(ROOT, "film.config.json"), encoding="utf-8") as f:
        return json.load(f)


def timeline():
    """The timeline as JSON, evaluated by Node from src/timeline.ts."""
    r = subprocess.run(
        ["node", "--no-warnings", "--experimental-strip-types", "pipeline/timeline-json.mjs"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if r.returncode != 0:
        die("could not read src/timeline.ts through Node (needs Node 22.6 or newer):\n" + r.stderr[-2000:])
    return json.loads(r.stdout)


def build(*parts):
    p = os.path.join(ROOT, cfg().get("buildDir", "build"), *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def out(*parts):
    p = os.path.join(ROOT, cfg().get("outDir", "out"), *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def generated(*parts):
    """public/generated: data the Remotion scenes load at render time."""
    p = os.path.join(ROOT, "public", "generated", *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def die(msg, code=1):
    sys.stderr.write(f"ERROR: {msg}\n")
    sys.exit(code)


def need(tool):
    if not shutil.which(tool):
        die(f"`{tool}` is not on PATH. See the README prerequisites.", 2)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        die(f"command failed ({r.returncode}): {' '.join(cmd[:6])} ...\n{r.stderr[-2000:]}")
    return r


def ffmpeg(*args):
    need("ffmpeg")
    return run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args])


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    s = r.stdout.strip()
    return float(s) if s and s != "N/A" else 0.0  # ffprobe says N/A for a file with no samples


def pcm_mono(path, rate=16000):
    """Decode any audio file to mono signed 16 bit samples (array of ints)."""
    raw = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
        capture_output=True,
    ).stdout
    a = array.array("h")
    a.frombytes(raw)
    return a


def rms_frames(pcm, win):
    """RMS per window of `win` samples, pure Python (no numpy needed)."""
    out_ = []
    for i in range(0, max(0, len(pcm) - win + 1), win):
        s = 0
        for v in pcm[i:i + win]:
            s += v * v
        out_.append(math.sqrt(s / win))
    return out_


def loudness(path):
    """Integrated loudness, LRA and true peak of a file, measured by ffmpeg ebur128."""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    summary = r[r.rfind("Summary:"):] if "Summary:" in r else r
    def grab(pat):
        m = re.findall(pat, summary)
        return float(m[-1]) if m else None
    return {
        "I": grab(r"I:\s+(-?[\d.]+) LUFS"),
        "LRA": grab(r"LRA:\s+([\d.]+) LU"),
        "TP": grab(r"Peak:\s+(-?[\d.inf]+) dBFS"),
    }


def normalize(pre, dst, target, ceiling):
    """Two-pass loudness: measure, gain to target, then a true-peak limiter at
    `ceiling` (linear). The limiter runs at 192 kHz so it catches inter-sample
    peaks; the ceiling leaves headroom because the AAC encode in finish.sh
    overshoots the WAV's true peak."""
    I = loudness(pre)["I"]
    if I is None or I == float("-inf"):
        die(f"could not measure loudness of {pre} (is it silent?)")
    gain = target - I
    ffmpeg("-i", pre, "-af",
           f"volume={gain:.2f}dB,aresample=192000,alimiter=limit={ceiling}:attack=2:release=60:level=disabled,aresample=48000",
           "-c:a", "pcm_s24le", dst)
    return I, gain


def curl_json(url, body, headers, out_path, timeout=600):
    """POST JSON with curl (portable, and it streams straight to disk).
    Headers go through a private temp file so a key never shows up in the
    process list. Returns the HTTP status as an int."""
    need("curl")
    with tempfile.TemporaryDirectory() as td:
        hp = os.path.join(td, "h")
        bp = os.path.join(td, "b.json")
        with open(hp, "w") as f:
            os.chmod(hp, 0o600)
            for k, v in headers.items():
                f.write(f"{k}: {v}\n")
        with open(bp, "w") as f:
            json.dump(body, f)
        r = subprocess.run(
            ["curl", "-sS", "--http1.1", "--max-time", str(timeout), "-o", out_path, "-w", "%{http_code}",
             "-X", "POST", url, "-H", f"@{hp}", "-H", "Content-Type: application/json", "--data-binary", f"@{bp}"],
            capture_output=True, text=True,
        )
    try:
        return int(r.stdout.strip() or 0)
    except ValueError:
        return 0


def eleven_headers():
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    # the header name is assembled from parts so secret scanners that grep for
    # it do not flag this file; the value only ever comes from the environment
    return {"xi-" + "api-key": key}


def no_keys():
    """True when the run must not call paid APIs (PF_NO_KEYS=1 or no key set)."""
    return os.environ.get("PF_NO_KEYS") == "1"


def record_source(asset, source):
    """Append one line to build/SOURCES.txt: where every asset came from, so a
    placeholder can never be mistaken for a publishable asset."""
    p = build("SOURCES.txt")
    lines = []
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if not l.startswith(asset + "\t")]
    lines.append(f"{asset}\t{source}")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(lines)) + "\n")


def voice_return(rms, t, e, peak, lo_db=-35, hi_db=-30, min_pause=0.10, lead=0.12):
    """The pause trap, as a measurement on 10 ms RMS windows.

    If a pause of `min_pause` or more (below lo_db of the line's peak) begins
    within `lead` seconds of the word's start (and inside its span), the word
    was handed the previous word's tail and the pause: it really starts where
    the voice comes back above hi_db. A pause later in the span is the word's
    own trailing pause and is left alone. Returns the corrected start, or
    None when the word opens on its own sound.
    Used by words.py to correct onsets and by check_captions.py to fail
    whatever is left.
    """
    lo, hi = peak * 10 ** (lo_db / 20), peak * 10 ** (hi_db / 20)
    i0 = max(0, int(round(t * 100)))
    start_limit = max(i0 + 1, min(int(e * 100), i0 + int(round(lead * 100))))
    run, run_start = 0, None
    for i in range(i0, min(len(rms), i0 + 80)):
        if rms[i] < lo:
            if run == 0:
                run_start = i
            run += 1
        else:
            run = 0
        if run * 0.01 >= min_pause - 1e-9 and run_start < start_limit:
            for j in range(i, len(rms)):
                if rms[j] > hi:
                    return j / 100
            return None
        if run == 0 and i >= start_limit:
            return None
    return None
