#!/usr/bin/env python3
"""Mix one cut, driven entirely by the timeline.

  npm run mix -- master        -> build/mix/master.wav
  npm run mix -- vertical      -> build/mix/vertical.wav

Three buses, summed:
  dialogue  every line of src/timeline.ts LINES at its `at`, through its
            speaker's EQ chain and gain (film.config.json voices, chains)
  sfx       every cue from sfxFor(cut), at its time and gain
  music     build/music/<cut>.wav with the MUSIC.gain keyframes, ducked by
            MUSIC.duckDb under every spoken line

Then two-pass loudness: measure the premix, gain it to loudness.targetLufs,
and run a true-peak limiter at loudness.limiterCeiling (linear; 0.708 is
about -3 dBFS). The ceiling sits well under the -1 dBTP delivery limit
because the AAC encode in `npm run finish` overshoots the WAV's true peak by
a dB or more; `npm run check:final` measures the ENCODED file.
"""
import json
import os
import sys

import common as C

if len(sys.argv) < 2:
    C.die("usage: npm run mix -- <cut>", 2)
cut_id = sys.argv[1]
cfg = C.cfg()
tl = C.timeline()
if cut_id not in tl["cuts"]:
    C.die(f"unknown cut '{cut_id}' (have: {', '.join(tl['cuts'])})", 2)
cut = tl["cuts"][cut_id]
DUR = cut["dur"]
voice_man = json.load(open(C.build("voice", "manifest.json"))) if os.path.exists(C.build("voice", "manifest.json")) else {}

inputs, filters, mixins = [], [], []


def add_input(path, what):
    if not os.path.exists(path):
        C.die(f"missing {os.path.relpath(path, C.ROOT)}: run `npm run {what}` first")
    inputs.extend(["-i", path])
    return len(inputs) // 2 - 1


# dialogue
spoken = []
for L in tl["lines"]:
    if L["at"] >= DUR:
        continue
    v = cfg["voices"][L["who"]]
    chain = cfg["chains"].get(v.get("chain", ""), "anull")
    i = add_input(C.build("voice", f"{L['id']}.wav"), "voice")
    ms = int(round(L["at"] * 1000))
    filters.append(f"[{i}:a]aformat=channel_layouts=mono,aresample=48000,{chain},volume={v.get('gainDb', 0)}dB,"
                   f"pan=stereo|c0=c0|c1=c0,adelay={ms}|{ms}[d{i}]")
    mixins.append(f"[d{i}]")
    spoken.append((L["at"], L["at"] + voice_man.get(L["id"], {}).get("dur", 0)))

# sfx
for q in cut["sfx"]:
    i = add_input(C.build("sfx", f"{q['name']}.wav"), "sfx")
    ms = int(round(q["at"] * 1000))
    filters.append(f"[{i}:a]aformat=channel_layouts=stereo,aresample=48000,volume={q['gainDb']}dB,adelay={ms}|{ms}[s{i}]")
    mixins.append(f"[s{i}]")


# music: keyframes plus ducking, both piecewise linear in dB, so their sum is
# piecewise linear over the union of their breakpoints
def kf_at(kf, t):
    if t <= kf[0][0]:
        return kf[0][1]
    for (t0, g0), (t1, g1) in zip(kf, kf[1:]):
        if t0 <= t <= t1:
            return g0 if t1 == t0 else g0 + (g1 - g0) * (t - t0) / (t1 - t0)
    return kf[-1][1]


duck = tl["music"]["duckDb"]
RAMP, PRE, POST = 0.15, 0.1, 0.25
# merge overlapping duck windows first
windows = []
for a, b in sorted(spoken):
    a, b = a - PRE, b + POST
    if windows and a <= windows[-1][1] + 2 * RAMP:
        windows[-1][1] = max(windows[-1][1], b)
    else:
        windows.append([a, b])
duck_kf = [(0.0, 0.0)]
for a, b in windows:
    duck_kf += [(max(0.0, a - RAMP), 0.0), (max(0.0, a), -duck), (b, -duck), (b + RAMP, 0.0)]
duck_kf.append((DUR, 0.0))
duck_kf = sorted(set(duck_kf))

gain_kf = [tuple(x) for x in cut["music"]["gain"]]
times = sorted({round(t, 3) for t, _ in gain_kf + duck_kf if 0 <= t <= DUR} | {0.0, DUR})
kf = [(t, kf_at(gain_kf, t) + kf_at(duck_kf, t)) for t in times]


def expr(kf):
    e = f"{kf[-1][1]:.2f}"
    for (t0, g0), (t1, g1) in reversed(list(zip(kf, kf[1:]))):
        if t1 <= t0:
            continue
        e = f"if(between(t,{t0},{t1}),{g0:.2f}+({g1:.2f}-({g0:.2f}))*(t-{t0})/({t1 - t0:.3f}),{e})"
    return f"pow(10,({e})/20)"


mi = add_input(C.build("music", f"{cut_id}.wav"), "music")
filters.append(f"[{mi}:a]aformat=channel_layouts=stereo,aresample=48000,atrim=0:{DUR},volume='{expr(kf)}':eval=frame[mus]")
mixins.append("[mus]")

fade = min(0.6, DUR / 4)
filters.append(f"{''.join(mixins)}amix=inputs={len(mixins)}:normalize=0:dropout_transition=0,"
               f"atrim=0:{DUR},apad=whole_dur={DUR},afade=t=out:st={DUR - fade:.3f}:d={fade:.3f}[sum]")
pre = C.build("mix", f"{cut_id}.pre.wav")
dst = C.build("mix", f"{cut_id}.wav")
C.ffmpeg(*inputs, "-filter_complex", ";".join(filters), "-map", "[sum]", "-ar", "48000", "-c:a", "pcm_s24le", pre)

L = cfg["loudness"]
I, gain = C.normalize(pre, dst, L["targetLufs"], L["limiterCeiling"])
m = C.loudness(dst)
print(f"{cut_id}: premix {I:.2f} LUFS, gain {gain:+.2f} dB -> {m['I']:.2f} LUFS, true peak {m['TP']:.2f} dBFS, "
      f"LRA {m['LRA']:.1f} LU ({len(spoken)} lines, {len(cut['sfx'])} sfx, music ducked {duck} dB under speech)")
