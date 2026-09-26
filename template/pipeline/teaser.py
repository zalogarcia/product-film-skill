#!/usr/bin/env python3
"""Cut the teaser from the rendered vertical and its mix.

  npm run teaser      -> build/render/teaser.mp4 (silent) + build/mix/teaser.wav
  npm run finish -- teaser

The segments are TEASER in src/timeline.ts, in seconds on the vertical's
clock, snapped to whole frames here (Python's round) and cut by frame and
sample number, so the teaser has exactly the frames the gates model.
Picture: hard cuts. Sound: the same segments with 25 ms edge fades, then
the same loudness and true peak treatment as the films. `npm run
check:timeline` fails any segment edge that lands inside a spoken word, so
run it after every voice or timing change.
"""
import os

import common as C

cfg = C.cfg()
tl = C.timeline()
fps = tl["fps"]
V = C.build("render", "vertical.mp4")
A = C.build("mix", "vertical.wav")
for p, what in ((V, "render -- vertical"), (A, "mix -- vertical")):
    if not os.path.exists(p):
        C.die(f"missing {os.path.relpath(p, C.ROOT)}: run `npm run {what}` first")

# keep the render's pixel format (and so its colour range); finish converts it for delivery
pix = C.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=pix_fmt",
             "-of", "default=nw=1:nk=1", V]).stdout.strip() or "yuv420p"
sr = int(C.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate",
                 "-of", "default=nw=1:nk=1", A]).stdout.strip() or 48000)
# cut on frame and sample numbers, not on rounded times: a time like 3.1667 s lands a few
# timebase ticks past frame 95 and keeps (or drops) a frame, shifting picture against sound
frames = [(round(s["from"] * fps), round(s["to"] * fps)) for s in tl["teaser"]]
seg = [(fa / fps, fb / fps) for fa, fb in frames]
vf, af = [], []
for i, ((fa, fb), (a, b)) in enumerate(zip(frames, seg)):
    vf.append(f"[0:v]trim=start_frame={fa}:end_frame={fb},setpts=PTS-STARTPTS[v{i}]")
    af.append(f"[1:a]atrim=start_sample={round(fa * sr / fps)}:end_sample={round(fb * sr / fps)},asetpts=PTS-STARTPTS,"
              f"afade=t=in:d=0.025,afade=t=out:st={b - a - 0.025:.4f}:d=0.025[a{i}]")
n = len(seg)
graph = ";".join(vf + af) + ";" + "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vo];" \
    + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[ao]"
out_v = C.build("render", "teaser.mp4")
pre = C.build("mix", "teaser.pre.wav")
C.ffmpeg("-i", V, "-i", A, "-filter_complex", graph,
         "-map", "[vo]", "-c:v", "libx264", "-crf", "12", "-preset", "medium", "-pix_fmt", pix, out_v,
         "-map", "[ao]", "-c:a", "pcm_s24le", pre)
L = cfg["loudness"]
dst = C.build("mix", "teaser.wav")
I, gain = C.normalize(pre, dst, L["targetLufs"], L["limiterCeiling"])
print(f"teaser: {n} segments, {sum(b - a for a, b in seg):.2f} s, premix {I:.2f} LUFS, gain {gain:+.2f} dB")
