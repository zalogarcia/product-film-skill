#!/usr/bin/env python3
"""Rate every sound in a library folder and rank candidates for the four
kinds of effect the starter uses (the `placeholder` kinds in film.config.json).

OPTIONAL: needs the audio venv (bash tools/audio/setup.sh), and a library
(python3 tools/audio/fetch_kenney.py downloads the Kenney CC0 packs).

  tools/audio/.venv/bin/python tools/audio/rate_sfx.py sfx-library [--top 6]

Writes <library>/ratings.json (every file: features, labels, role scores, and
the top candidates per role) and <library>/RATINGS.md (the readable summary).
Then LISTEN to the top few for a role, copy the one you pick (with its pack's
License.txt) under assets/sfx/, list it in assets/sfx/manifest.json, and point
the effect's `file` at it in film.config.json.

Per file (mono, 44.1 kHz, 1024 point STFT, hop 256 = 5.8 ms):

  duration, peakDb, rmsDb, crestFactor
  attackS        start of the active region to the loudness peak
  decayTo10S     loudness peak to the first frame 20 dB below it
  activeS        time within 30 dB of the peak frame
  latenessRatio  where the peak sits inside the active region (0 = start, 1 = end)
  rmsSlopeDbPerS, centroidSlopeHzPerS   linear fits over the active region
  centroidP50Hz, centroidP90Hz, rolloff90P90Hz, flatness (0 tonal .. 1 noise)
  energyLow/Mid/High   share of energy below 250 Hz, 250 to 4000 Hz, 4 to 16 kHz
  highActiveS    active time where the 4 to 16 kHz band holds over 25 % of the frame's energy
  brightBurden   sum over frames of (high band share) x (frame level / peak level)^2 x frame time:
                 bright energy weighted by level and duration, so a long glassy ring
                 scores far above a short click

Labels: brightness warm / balanced / bright, highFrequencyRisk low / medium / high
(bright sounds tire the ear when repeated; keep high risk ones for single, quiet
hits), envelope transient / textured / continuous. Thresholds are constants below.

The rating method follows latent-spaces/brag `skills/brag/assets/sfx/sfx-analysis.md`
(MIT; the notice is in tools/audio/NOTICE-brag.md); the code, thresholds and
role models are our own. Scores rank candidates; they do not replace listening.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import librosa
import numpy as np

SR = 44100
N_FFT = 1024
HOP = 256
DT = HOP / SR
ACTIVE_DB = -30.0

# label thresholds
WARM_CENTROID_HZ = 1200.0
BRIGHT_CENTROID_HZ = 3500.0
BRIGHT_HIGH_SHARE = 0.30
RISK_LOW_HIGH_SHARE = 0.08
RISK_LOW_BURDEN = 0.004
RISK_HIGH_BURDEN = 0.02
RISK_HIGH_SHARE = 0.35
RISK_HIGH_ACTIVE_S = 0.10
# a sound that is mostly 4 to 16 kHz is high risk however short (bright clicks fatigue when repeated)
RISK_HIGH_DOMINANT_SHARE = 0.5

ROLES = ("chime", "whoosh", "click", "hit")
ROLE_BRIEF = {
    "chime": "a notification: one soft, tonal, bell like tone with a short tail",
    "whoosh": "a transition: a quick swish or slide that builds briefly and falls away",
    "click": "a UI tick: tiny, crisp, over in a few hundredths of a second",
    "hit": "an end card or turn: a deep, soft impact with a warm low end and a tail",
}


def _db(x: float) -> float:
    return 20.0 * math.log10(max(x, 1e-12))


def _r(x: float, d: int = 4) -> float:
    return round(float(x), d) if math.isfinite(x) else 0.0


def _slope(t: np.ndarray, v: np.ndarray) -> float:
    if t.size < 3 or np.ptp(t) <= 0:
        return 0.0
    return float(np.polyfit(t, v, 1)[0])


def features(path: Path) -> dict[str, Any]:
    y, _ = librosa.load(path, sr=SR, mono=True)
    if y.size < N_FFT:
        y = np.pad(y, (0, N_FFT - y.size))
    dur = y.size / SR
    peak = float(np.max(np.abs(y)))
    rms_all = float(np.sqrt(np.mean(y**2)))

    rms = librosa.feature.rms(y=y, frame_length=N_FFT, hop_length=HOP)[0]
    rmax = float(np.max(rms)) or 1e-12
    env_db = 20 * np.log10(np.maximum(rms, 1e-12) / rmax)
    active = env_db > ACTIVE_DB
    idx = np.flatnonzero(active)
    first, last = (int(idx[0]), int(idx[-1])) if idx.size else (0, 0)
    ipk = int(np.argmax(rms))
    t = np.arange(rms.size) * DT

    after = np.flatnonzero(env_db[ipk:] < -20.0)
    decay10 = float(after[0] * DT) if after.size else float((rms.size - ipk) * DT)
    span = max(last - first, 1)

    S = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP)) ** 2
    n = min(S.shape[1], rms.size)
    S, active_n, t_n = S[:, :n], active[:n], t[:n]
    freqs = librosa.fft_frequencies(sr=SR, n_fft=N_FFT)
    tot = S.sum(axis=0) + 1e-20
    low = S[freqs < 250].sum(axis=0)
    mid = S[(freqs >= 250) & (freqs < 4000)].sum(axis=0)
    high = S[(freqs >= 4000) & (freqs <= 16000)].sum(axis=0)
    grand = float(tot.sum())
    hf_frac = high / tot

    centroid = (freqs[:, None] * S).sum(axis=0) / tot
    rolloff = librosa.feature.spectral_rolloff(S=S, sr=SR, roll_percent=0.9)[0][:n]
    flat = librosa.feature.spectral_flatness(S=np.sqrt(S))[0][:n]

    a = active_n if active_n.any() else np.ones(n, dtype=bool)
    lvl2 = (rms[:n] / rmax) ** 2
    return {
        "duration": _r(dur, 3),
        "peakDb": _r(_db(peak), 2),
        "rmsDb": _r(_db(rms_all), 2),
        "crestFactor": _r(peak / max(rms_all, 1e-12), 3),
        "attackS": _r(max(0, ipk - first) * DT, 3),
        "decayTo10S": _r(decay10, 3),
        "activeS": _r(active.sum() * DT, 3),
        "peakAtS": _r(ipk * DT, 3),
        "latenessRatio": _r((ipk - first) / span, 3),
        "rmsSlopeDbPerS": _r(_slope(t[active], env_db[active]), 2),
        "centroidSlopeHzPerS": _r(_slope(t_n[a], centroid[a]), 1),
        "centroidP50Hz": _r(float(np.percentile(centroid[a], 50)), 1),
        "centroidP90Hz": _r(float(np.percentile(centroid[a], 90)), 1),
        "rolloff90P90Hz": _r(float(np.percentile(rolloff[a], 90)), 1),
        "flatness": _r(float(np.mean(flat[a])), 4),
        "energyLow": _r(float(low.sum()) / grand),
        "energyMid": _r(float(mid.sum()) / grand),
        "energyHigh": _r(float(high.sum()) / grand),
        "highActiveS": _r(float(((hf_frac > 0.25) & active_n).sum() * DT), 3),
        "brightBurden": _r(float((hf_frac * lvl2).sum() * DT), 5),
    }


def labels(f: dict[str, Any]) -> dict[str, str]:
    if f["centroidP50Hz"] > BRIGHT_CENTROID_HZ or f["energyHigh"] > BRIGHT_HIGH_SHARE:
        bright = "bright"
    elif f["centroidP50Hz"] < WARM_CENTROID_HZ:
        bright = "warm"
    else:
        bright = "balanced"
    if (
        f["brightBurden"] > RISK_HIGH_BURDEN
        or f["energyHigh"] > RISK_HIGH_DOMINANT_SHARE
        or (f["energyHigh"] > RISK_HIGH_SHARE and f["highActiveS"] > RISK_HIGH_ACTIVE_S)
    ):
        risk = "high"
    elif f["energyHigh"] < RISK_LOW_HIGH_SHARE and f["brightBurden"] < RISK_LOW_BURDEN:
        risk = "low"
    else:
        risk = "medium"
    active_ratio = f["activeS"] / max(f["duration"], 1e-6)
    if f["attackS"] <= 0.03 and (f["decayTo10S"] <= 0.15 or f["decayTo10S"] <= 0.35 * f["duration"]):
        env = "transient"
    elif active_ratio > 0.7 and f["decayTo10S"] > 0.5 * f["duration"]:
        env = "continuous"
    else:
        env = "textured"
    return {"brightness": bright, "highFrequencyRisk": risk, "envelope": env}


def band(x: float, lo: float, hi: float, soft: float) -> float:
    """1 inside [lo, hi], falling linearly to 0 at `soft` outside it."""
    if lo <= x <= hi:
        return 1.0
    d = lo - x if x < lo else x - hi
    return max(0.0, 1.0 - d / soft)


RISK_FIT = {"low": 1.0, "medium": 0.75, "high": 0.4}


def role_scores(f: dict[str, Any], lab: dict[str, str]) -> dict[str, float]:
    """0..1 fit per role; a role is absent when a hard gate fails.

    Each role is modelled on ROLE_BRIEF: the component list below is the whole
    model, averaged with equal weight.
    """
    risk = RISK_FIT[lab["highFrequencyRisk"]]
    audible = f["peakDb"] >= -18.0
    s: dict[str, float] = {}
    # chime: tonal, clean, rings out briefly after a fast attack
    if audible and 0.2 <= f["duration"] <= 1.5 and f["attackS"] <= 0.06:
        s["chime"] = float(np.mean([
            band(f["flatness"], 0.0, 0.005, 0.03),
            band(f["centroidP50Hz"], 700, 3500, 2500),
            band(f["decayTo10S"], 0.15, 0.8, 0.6),
            {"low": 1.0, "medium": 0.8, "high": 0.3}[lab["highFrequencyRisk"]],
            1.0 if lab["envelope"] in ("continuous", "textured") else 0.6,
        ]))
    # whoosh: builds for a moment, then falls away; some noise in it, not a tone
    if audible and 0.25 <= f["duration"] <= 1.5:
        s["whoosh"] = float(np.mean([
            band(f["attackS"], 0.03, 0.3, 0.3),
            band(f["decayTo10S"], 0.03, 0.3, 0.3),
            band(f["centroidP50Hz"], 800, 5000, 2500),
            band(f["flatness"], 0.001, 1.0, 0.01),
            {"low": 1.0, "medium": 0.9, "high": 0.6}[lab["highFrequencyRisk"]],
        ]))
    # click: tiny and crisp, over in a few hundredths of a second
    if audible and f["duration"] <= 0.15 and f["attackS"] <= 0.02:
        s["click"] = float(np.mean([
            band(f["decayTo10S"], 0.005, 0.05, 0.1),
            band(f["activeS"], 0.01, 0.06, 0.1),
            band(f["centroidP50Hz"], 800, 3500, 2500),
            risk,
        ]))
    # hit: a deep, soft impact with a warm low end and a tail
    if audible and f["duration"] <= 2.5 and f["attackS"] <= 0.04:
        s["hit"] = float(np.mean([
            band(f["energyLow"], 0.7, 1.0, 0.4),
            band(f["centroidP50Hz"], 0, 300, 600),
            band(f["decayTo10S"], 0.12, 0.8, 0.4),
            band(f["duration"], 0.4, 2.5, 0.5),
            risk,
        ]))
    return {k: _r(v, 3) for k, v in s.items()}


def rate_dir(root: Path, sources: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for p in sorted(root.rglob("*.ogg")) + sorted(root.rglob("*.wav")):
        rel = p.relative_to(root).as_posix()
        pack = rel.split("/")[0] if "/" in rel else ""
        f = features(p)
        lab = labels(f)
        src = sources.get(pack, {})
        out.append({
            "file": rel,
            "pack": pack,
            "packName": src.get("name", pack),
            "sourceUrl": src.get("page", ""),
            "license": src.get("license", ""),
            "labels": lab,
            "roleScores": role_scores(f, lab),
            "features": f,
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("library", type=Path)
    ap.add_argument("--top", type=int, default=6)
    args = ap.parse_args()

    src_path = args.library / "sources.json"
    sources = json.loads(src_path.read_text()) if src_path.exists() else {}
    entries = rate_dir(args.library, sources)
    if not entries:
        raise SystemExit(f"rate_sfx: no .ogg or .wav files under {args.library}")
    ranking = {}
    for role in ROLES:
        cands = sorted(
            (e for e in entries if role in e["roleScores"]),
            key=lambda e: e["roleScores"][role], reverse=True,
        )
        ranking[role] = {
            "of": len(cands),
            "top": [{"file": e["file"], "score": e["roleScores"][role]} for e in cands[: args.top]],
        }

    out = {
        "schemaVersion": 1,
        "tool": "tools/audio/rate_sfx.py",
        "fileCount": len(entries),
        "analysis": {"sampleRate": SR, "nFft": N_FFT, "hopLength": HOP, "activeDb": ACTIVE_DB,
                     "highBandHz": [4000, 16000], "lowBandHz": [0, 250]},
        "roles": ROLE_BRIEF,
        "ranking": ranking,
        "sources": sources,
        "files": entries,
    }
    (args.library / "ratings.json").write_text(json.dumps(out, indent=1) + "\n")

    L = [f"# Sound effect ratings ({len(entries)} files)", "",
         "Scores rank candidates for each role; listen to the top few before you pick.", ""]
    by_file = {e["file"]: e for e in entries}
    for role in ROLES:
        L += [f"## {role}: {ROLE_BRIEF[role]} ({ranking[role]['of']} candidates)", ""]
        for c in ranking[role]["top"]:
            e = by_file[c["file"]]
            f, lab = e["features"], e["labels"]
            L.append(f"- `{c['file']}` score {c['score']:.3f}: {f['duration']:.2f} s, "
                     f"{lab['brightness']}, HF risk {lab['highFrequencyRisk']}, {lab['envelope']}, "
                     f"centroid {f['centroidP50Hz']:.0f} Hz, flatness {f['flatness']:.3f}, "
                     f"attack {f['attackS'] * 1000:.0f} ms, decay {f['decayTo10S']:.2f} s")
        L.append("")
    (args.library / "RATINGS.md").write_text("\n".join(L))
    print(f"rated {len(entries)} files -> {args.library / 'ratings.json'}, {args.library / 'RATINGS.md'}")


if __name__ == "__main__":
    main()
