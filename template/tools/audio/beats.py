#!/usr/bin/env python3
"""Find the beats and the strong cues in a music track, for beat synced reveals.

OPTIONAL: needs librosa, which lives in its own venv (tools/audio/setup.sh).
Run it through the wrapper, which builds the venv on first use:

    npm run beats -- <track.wav|mp3> [--out <track>.beats.json] [--md <file.md>] [--bpm-hint 120]
    npm run beats -- --selftest

Writes a JSON beat map that src/beatSync.ts reads (parseBeatMap) and
`npm run snap` prints against the timeline:

    bpm          the tempo estimate (librosa beat tracker)
    beatPeriod   the median gap between tracked beats, in seconds
    beats        the full beat grid: [{time, intensity}]  (seconds from track start)
    strongCues   high intensity moments (drops, swells, accents): [{time, intensity, kind}]
                 kind = "strong_beat" (a beat that scored high) or "onset_peak"
                 (a loud transient between beats)
    pulseClarity mean onset strength on the tracked beats over the track's mean.
                 The tracker ALWAYS reports a tempo, even on music with no beat;
                 this says whether there is one. A steady beat scores far above
                 PULSE_MIN (a produced score about 8, drums over a pad 15 to 18);
                 music with no pulse, like the starter's placeholder chord pad or
                 noise, scores 1 to 3. Under PULSE_MIN the tool warns, and
                 `npm run snap` refuses to call any snap good.

Intensity per moment = 0.45 onset strength + 0.25 local onset contrast
+ 0.20 RMS + 0.10 bass energy (30 to 180 Hz), each normalized per track to its
98th percentile. Strong cues are candidates at intensity >= 0.45, at least
0.18 s apart, the 64 strongest.

--selftest synthesizes a 120 BPM click track with an accent every 4th beat and
checks the tempo, the grid, the accents and the pulse clarity; then 12 s of
noise, which must score under PULSE_MIN (exit 1 on any miss).

Adapted from latent-spaces/brag `skills/brag/scripts/analyze_music_cues.py`
(MIT, Copyright (c) 2026 Shunit Haviv Hakimi, commit c893c5ed; the notice is in
tools/audio/NOTICE-brag.md). Changes here: our own output schema (bpm,
beatPeriod, source hash), a --bpm-hint for tracks the tracker reads at half or
double time, an optional markdown summary, and the self test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any

import librosa
import numpy as np

HOP_LENGTH = 512
FRAME_LENGTH = 2048
BASS_N_FFT = 4096
BASS_MIN_HZ = 30.0
BASS_MAX_HZ = 180.0
STRONG_CUE_MIN_INTENSITY = 0.45
STRONG_CUE_MIN_GAP_S = 0.18
STRONG_CUE_MAX_COUNT = 64
PULSE_MIN = 4.0


def _as_float(value: Any) -> float:
    array = np.asarray(value)
    if array.size == 0:
        return 0.0
    return float(array.reshape(-1)[0])


def _r(value: float, digits: int = 4) -> float:
    return round(float(value), digits) if math.isfinite(value) else 0.0


def _normalize(values: np.ndarray) -> np.ndarray:
    values = np.nan_to_num(np.asarray(values, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    if values.size == 0:
        return values
    values = np.maximum(values, 0.0)
    high = np.percentile(values, 98)
    if high <= 1e-12:
        high = np.max(values)
    if high <= 1e-12:
        return np.zeros_like(values)
    return np.clip(values / high, 0.0, 1.0)


def _at(feature: np.ndarray, frame: int) -> float:
    if feature.size == 0:
        return 0.0
    return float(feature[int(np.clip(frame, 0, feature.size - 1))])


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def analyze(path: Path, sr: int, bpm_hint: float) -> dict[str, Any]:
    y, sr = librosa.load(path, sr=sr, mono=True)
    duration = float(librosa.get_duration(y=y, sr=sr))

    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP_LENGTH)
    onset_n = _normalize(onset_env)

    radius = max(1, int(round(0.5 * sr / HOP_LENGTH)))
    contrast = np.array(
        [
            max(0.0, onset_n[i] - float(np.median(onset_n[max(0, i - radius) : i + radius + 1])))
            for i in range(onset_n.size)
        ]
    )
    contrast_n = _normalize(contrast)

    rms_n = _normalize(librosa.feature.rms(y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)[0])

    spec = np.abs(librosa.stft(y, n_fft=BASS_N_FFT, hop_length=HOP_LENGTH))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=BASS_N_FFT)
    mask = (freqs >= BASS_MIN_HZ) & (freqs <= BASS_MAX_HZ)
    bass_n = _normalize(np.mean(spec[mask], axis=0) if np.any(mask) else np.zeros(spec.shape[1]))

    def score(frame: int) -> float:
        v = (
            0.45 * _at(onset_n, frame)
            + 0.25 * _at(contrast_n, frame)
            + 0.20 * _at(rms_n, frame)
            + 0.10 * _at(bass_n, frame)
        )
        return float(np.clip(v, 0.0, 1.0))

    tempo, beat_frames = librosa.beat.beat_track(
        y=y, sr=sr, onset_envelope=onset_env, hop_length=HOP_LENGTH,
        start_bpm=bpm_hint, units="frames",
    )
    beat_frames = np.asarray(beat_frames, dtype=int)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=HOP_LENGTH)

    beats: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for frame, t in zip(beat_frames, beat_times):
        s = score(int(frame))
        beats.append({"time": _r(t), "intensity": _r(s)})
        candidates.append({"time": _r(t), "intensity": _r(s), "kind": "strong_beat"})

    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, hop_length=HOP_LENGTH, backtrack=False, units="frames"
    )
    for frame in np.asarray(onset_frames, dtype=int):
        t = float(librosa.frames_to_time(frame, sr=sr, hop_length=HOP_LENGTH))
        candidates.append({"time": _r(t), "intensity": _r(score(int(frame))), "kind": "onset_peak"})

    # strongest first, keep a candidate only if it is at least MIN_GAP from every kept one
    kept: list[dict[str, Any]] = []
    for c in sorted(candidates, key=lambda c: c["intensity"], reverse=True):
        if c["intensity"] < STRONG_CUE_MIN_INTENSITY:
            break
        if all(abs(c["time"] - k["time"]) >= STRONG_CUE_MIN_GAP_S for k in kept):
            kept.append(c)
        if len(kept) >= STRONG_CUE_MAX_COUNT:
            break
    strong = sorted(kept, key=lambda c: c["time"])

    gaps = np.diff(beat_times) if beat_times.size > 1 else np.array([])
    period = float(np.median(gaps)) if gaps.size else 0.0
    pulse = float(onset_env[beat_frames].mean() / (onset_env.mean() + 1e-9)) if beat_frames.size else 0.0

    return {
        "schemaVersion": 1,
        "tool": "tools/audio/beats.py",
        "source": {"file": path.name, "sha256": _sha256(path)},
        "duration": _r(duration, 3),
        "bpm": _r(_as_float(tempo), 2),
        "beatPeriod": _r(period),
        "pulseClarity": _r(pulse, 2),
        "analysis": {
            "sampleRate": int(sr),
            "hopLength": HOP_LENGTH,
            "bpmHint": bpm_hint,
            "librosa": librosa.__version__,
            "intensityFormula": "0.45*onset + 0.25*local_onset_contrast + 0.20*rms + 0.10*bass(30-180Hz)",
            "strongCueMinIntensity": STRONG_CUE_MIN_INTENSITY,
            "strongCueMinGapS": STRONG_CUE_MIN_GAP_S,
            "strongCueMaxCount": STRONG_CUE_MAX_COUNT,
            "pulseMin": PULSE_MIN,
        },
        "beats": beats,
        "strongCues": strong,
    }


def to_markdown(data: dict[str, Any]) -> str:
    times = ", ".join(f"{b['time']:.2f}" for b in data["beats"][:64])
    more = len(data["beats"]) - 64
    if more > 0:
        times += f", ... (+{more} more)"
    top = sorted(data["strongCues"], key=lambda c: c["intensity"], reverse=True)[:12]
    lines = [
        f"# Beats: {data['source']['file']}",
        "",
        f"- Duration: {data['duration']:.2f} s",
        f"- Tempo: {data['bpm']:.2f} BPM (beat period {data['beatPeriod']:.3f} s,"
        f" {30 * data['beatPeriod']:.2f} frames at 30 fps)",
        f"- Beats: {len(data['beats'])}, strong cues: {len(data['strongCues'])}",
        f"- Pulse clarity: {data['pulseClarity']:.2f}"
        + ("" if data["pulseClarity"] >= PULSE_MIN else f" (under {PULSE_MIN:g}: no steady beat, the tempo is a guess)"),
        "",
        "## Beat grid (s)",
        "",
        times or "none",
        "",
        "## Strongest cues",
        "",
        *[f"- {c['time']:.2f} s ({c['intensity']:.2f}, {c['kind']})" for c in sorted(top, key=lambda c: c['time'])],
        "",
    ]
    return "\n".join(lines)


def selftest() -> int:
    """120 BPM clicks, every 4th one accented, 12 s: the analyser must find them.
    Then 12 s of noise: it must NOT claim a steady beat."""
    import soundfile as sf

    sr, bpm, n = 44100, 120.0, 24
    period = 60.0 / bpm
    first = 0.5
    y = np.zeros(int(sr * (first + n * period + 1.0)), dtype=np.float32)
    t = np.arange(int(0.05 * sr)) / sr
    for i in range(n):
        amp = 0.9 if i % 4 == 0 else 0.3
        click = amp * np.sin(2 * np.pi * (180.0 if i % 4 == 0 else 1000.0) * t) * np.exp(-60 * t)
        s = int((first + i * period) * sr)
        y[s : s + click.size] += click.astype(np.float32)
    noise = (np.random.default_rng(7).standard_normal(sr * 12) * 0.1).astype(np.float32)
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "selftest-120bpm.wav"
        sf.write(wav, y, sr, subtype="PCM_16")
        data = analyze(wav, sr, 120.0)
        nwav = Path(td) / "selftest-noise.wav"
        sf.write(nwav, noise, sr, subtype="PCM_16")
        ndata = analyze(nwav, sr, 120.0)
    truth = [first + i * period for i in range(n)]
    accents = truth[::4]
    got = [b["time"] for b in data["beats"]]
    hits = sum(1 for tt in truth if got and min(abs(g - tt) for g in got) <= 0.05)
    cues = [c["time"] for c in data["strongCues"]]
    acc_hits = sum(1 for a in accents if cues and min(abs(c - a) for c in cues) <= 0.05)
    checks = [
        (abs(data["bpm"] - bpm) <= 2.0, f"tempo {data['bpm']} BPM (expected {bpm:.0f} +/- 2)"),
        (abs(data["beatPeriod"] - period) <= 0.02, f"beat period {data['beatPeriod']} s (expected {period} +/- 0.02)"),
        (hits >= n - 2, f"{hits} of {n} clicks have a tracked beat within 0.05 s (need {n - 2})"),
        (acc_hits == len(accents), f"{acc_hits} of {len(accents)} accents are strong cues within 0.05 s"),
        (data["pulseClarity"] >= PULSE_MIN, f"clicks: pulse clarity {data['pulseClarity']} (need >= {PULSE_MIN:g})"),
        (ndata["pulseClarity"] < PULSE_MIN, f"noise: pulse clarity {ndata['pulseClarity']} (need < {PULSE_MIN:g}, no beat)"),
    ]
    for ok, msg in checks:
        print(f"{'ok  ' if ok else 'FAIL'}  {msg}")
    passed = all(ok for ok, _ in checks)
    print(f"beats selftest: {'PASS' if passed else 'FAIL'} (librosa {librosa.__version__})")
    return 0 if passed else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Beat grid and strong cues for a music track.")
    ap.add_argument("track", type=Path, nargs="?")
    ap.add_argument("--out", type=Path, help="JSON path (default: <track>.beats.json next to the track)")
    ap.add_argument("--md", type=Path, help="optional markdown summary path")
    ap.add_argument("--bpm-hint", type=float, default=120.0, help="tracker start tempo (default 120)")
    ap.add_argument("--sr", type=int, default=44100)
    ap.add_argument("--selftest", action="store_true", help="analyse a synthesized 120 BPM click track")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if args.track is None:
        ap.error("a track is required (or --selftest)")
    if not args.track.is_file():
        raise SystemExit(f"beats.py: no such file: {args.track}")
    out = args.out or args.track.with_name(args.track.stem + ".beats.json")
    data = analyze(args.track, args.sr, args.bpm_hint)
    if len(data["beats"]) < 2:
        raise SystemExit("beats.py: the tracker found fewer than 2 beats (silent or beatless track?)")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(to_markdown(data), encoding="utf-8")
    print(
        f"{out}: {data['bpm']:.2f} BPM, {len(data['beats'])} beats, "
        f"{len(data['strongCues'])} strong cues, {data['duration']:.2f} s, pulse clarity {data['pulseClarity']:.2f}"
    )
    if data["pulseClarity"] < PULSE_MIN:
        print(f"WARNING: pulse clarity under {PULSE_MIN:g}: this track has no steady beat, so the tempo and the "
              "beat grid are guesses. The strong cues (swells, chord changes) may still be real; listen first.")


if __name__ == "__main__":
    main()
