#!/usr/bin/env python3
"""Frame check: a contact sheet of a video, and single frames, to LOOK at.

  npm run frames -- out/master.mp4                    # sheet, one frame every 1.5 s
  npm run frames -- out/vertical.mp4 --every 1
  npm run frames -- out/master.mp4 --at 0,4.5,13.8    # full size PNGs at those times

Writes build/frames/<name>-sheet.jpg (tiles in time order, left to right,
top to bottom) and build/frames/<name>-<t>.png for each --at time. Look at
every one: first frame (the poster), every act turn, every caption page,
the end card, and on the vertical the last frame next to frame 1 (the loop;
`--at 0.02` is frame 1, since frame 0 is the poster).
"""
import argparse
import math
import os

import common as C

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("--every", type=float, default=1.5)
ap.add_argument("--cols", type=int, default=0)
ap.add_argument("--at", default="")
args = ap.parse_args()

src = os.path.abspath(args.video)
if not os.path.exists(src):
    C.die(f"no such file: {args.video}")
name = os.path.splitext(os.path.basename(src))[0]
d = C.duration(src)
if args.at:
    for t in [float(x) for x in args.at.split(",") if x.strip()]:
        p = C.build("frames", f"{name}-{t:g}.png")
        C.ffmpeg("-ss", f"{min(t, d - 0.05):.3f}", "-i", src, "-frames:v", "1", p)
        print(os.path.relpath(p, C.ROOT))
n = max(1, int(d / args.every))
info = C.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", src]).stdout
w, h = (int(x) for x in info.strip().split(",")[:2])
cols = args.cols or (6 if w > h else 8)
rows = math.ceil(n / cols)
tw = 320 if w > h else 180
sheet = C.build("frames", f"{name}-sheet.jpg")
C.ffmpeg("-i", src, "-vf", f"fps=1/{args.every},scale={tw}:-2,tile={cols}x{rows}:padding=4:color=0x333333",
         "-frames:v", "1", "-q:v", "3", sheet)
print(f"{os.path.relpath(sheet, C.ROOT)}  ({n} frames, one every {args.every} s, {cols} per row)")
