#!/usr/bin/env python3
"""Gate: nothing a viewer must read or see sits outside the safe zone.

  npm run check:safe -- vertical                  # renders the probe, then checks it
  npm run check:safe -- master --scale 0.5        # a faster, half size probe
  npm run check:safe -- vertical --every 0.25     # sample every 0.25 s (default 0.5)
  npm run check:safe -- vertical --no-render      # re-check an existing probe

The probe is a special render (`--probe`): the background, grain, vignette,
photographic plates and everything wrapped in <Decor> are hidden, so only
content is left on black. Any lit pixel outside the cut's box in
film.config.json safeZones fails the check, with the time and the bounding
box of the offending content. On a 9:16 cut the default box keeps content
clear of the platform's top bar, the caption and button rail at the bottom,
and the like and share column on the right.
"""
import argparse
import os
import subprocess

import common as C

ap = argparse.ArgumentParser()
ap.add_argument("cut")
ap.add_argument("--scale", default="0.5")
ap.add_argument("--every", type=float, default=0.5)
ap.add_argument("--no-render", action="store_true")
args = ap.parse_args()

cfg = C.cfg()
tl = C.timeline()
if args.cut not in tl["cuts"]:
    C.die(f"unknown cut '{args.cut}'", 2)
cut = tl["cuts"][args.cut]
box = cfg["safeZones"][args.cut]
probe = C.build("probe", f"{args.cut}.mp4")
if not args.no_render:
    r = subprocess.run(["node", "pipeline/render.cjs", args.cut, "--probe", "--scale", args.scale, "--out", probe], cwd=C.ROOT)
    if r.returncode != 0:
        C.die("the probe render failed")
if not os.path.exists(probe):
    C.die(f"no probe at {os.path.relpath(probe, C.ROOT)}")

# decode sampled frames at a quarter of the cut's size, grey, raw
Q = 4
w, h = cut["w"] // Q, cut["h"] // Q
raw = subprocess.run(
    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", probe, "-vf",
     f"fps=1/{args.every},scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"],
    capture_output=True,
).stdout
n = len(raw) // (w * h)
x0, x1, y0, y1 = box["x0"] // Q, box["x1"] // Q, box["y0"] // Q, box["y1"] // Q
LIT = 40  # grey level that counts as content (antialiasing and faint text included)
fails = []
for i in range(n):
    fr = raw[i * w * h:(i + 1) * w * h]
    bx = [w, h, -1, -1]
    for y in range(h):
        row = fr[y * w:(y + 1) * w]
        # the parts of this row that lie outside the box
        spans = [(0, w)] if not (y0 <= y < y1) else [(0, x0), (x1, w)]
        for a, b in spans:
            if b > a and max(row[a:b]) > LIT:
                xs = [a + j for j, v in enumerate(row[a:b]) if v > LIT]
                bx = [min(bx[0], xs[0]), min(bx[1], y), max(bx[2], xs[-1]), max(bx[3], y)]
    if bx[2] >= 0:
        t = i * args.every
        fails.append(f"{t:5.2f} s: content at x {bx[0] * Q} to {bx[2] * Q + Q}, y {bx[1] * Q} to {bx[3] * Q + Q} "
                     f"(safe box x {box['x0']} to {box['x1']}, y {box['y0']} to {box['y1']})")

for f in fails:
    print(f"FAIL  {f}")
print(f"check:safe {args.cut}: {n} frames sampled every {args.every} s: " + ("PASS" if not fails else f"FAIL ({len(fails)} frames)"))
raise SystemExit(1 if fails or n == 0 else 0)
