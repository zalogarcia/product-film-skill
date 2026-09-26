#!/usr/bin/env python3
"""Download the Kenney CC0 sound packs (kenney.nl) into a local library, for
tools/audio/rate_sfx.py to rate. OPTIONAL: the example already ships the few
files it uses in assets/sfx/.

  python3 tools/audio/fetch_kenney.py                       # every pack -> sfx-library/
  python3 tools/audio/fetch_kenney.py --dest /tmp/kenney --pack impact-sounds --pack ui-audio

Standard library only; downloads go through curl, like the rest of the
pipeline. Every zip is checked against the SHA-256 in tools/audio/kenney-packs.json
before anything is extracted. A pack that Kenney has updated since fails that
check: open its page, download it, look at it, and update the entry on
purpose. Extracts each pack's .ogg files (not its Preview.ogg montage) and its
License.txt into <dest>/<pack>/, deletes the zip, and writes
<dest>/sources.json (the packs, their pages and licences) for rate_sfx.py.

Every Kenney pack is Creative Commons Zero (CC0 1.0): free to use, change and
publish, commercially too, with no credit required ("Kenney, kenney.nl" is a
kind courtesy).
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

ap = argparse.ArgumentParser()
ap.add_argument("--dest", default=os.path.join(ROOT, "sfx-library"))
ap.add_argument("--pack", action="append", default=[], help="only this pack (repeatable)")
args = ap.parse_args()

packs = json.load(open(os.path.join(HERE, "kenney-packs.json")))
want = args.pack or list(packs)
bad = [p for p in want if p not in packs]
if bad:
    sys.exit(f"fetch_kenney: unknown pack(s) {bad}; have {sorted(packs)}")
if not shutil.which("curl"):
    sys.exit("fetch_kenney: curl is not on PATH")
os.makedirs(args.dest, exist_ok=True)

done = {}
for name in want:
    p = packs[name]
    zp = os.path.join(args.dest, f"{name}.zip")
    r = subprocess.run(["curl", "-fsSL", "--max-time", "300", "-o", zp, p["zip"]], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"fetch_kenney: {name}: download failed ({r.stderr.strip()[:300]}); the pack page is {p['page']}")
    h = hashlib.sha256(open(zp, "rb").read()).hexdigest()
    if h != p["zipSha256"]:
        os.remove(zp)
        sys.exit(f"fetch_kenney: {name}: the zip's SHA-256 is {h}, kenney-packs.json expects {p['zipSha256']}. "
                 f"Kenney may have updated the pack: check {p['page']} and update the entry on purpose.")
    out = os.path.join(args.dest, name)
    os.makedirs(out, exist_ok=True)
    n = 0
    lic = False
    with zipfile.ZipFile(zp) as z:
        for info in z.infolist():
            base = os.path.basename(info.filename)  # flatten, and never write outside <dest>/<pack>
            if info.is_dir() or not base:
                continue
            if base.lower().endswith(".ogg") and base.lower() != "preview.ogg":
                target = os.path.join(out, base)
            elif base == "License.txt":
                target, lic = os.path.join(out, "License.txt"), True
            else:
                continue
            with z.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            n += base.lower().endswith(".ogg")
    os.remove(zp)
    if not lic:
        sys.exit(f"fetch_kenney: {name}: the zip has no License.txt; check {p['page']}")
    done[name] = {**p, "files": n, "licenseFile": f"{name}/License.txt"}
    print(f"{name}: {n} sounds, {p['license']}, from {p['page']}")

src = os.path.join(args.dest, "sources.json")
prev = json.load(open(src)) if os.path.exists(src) else {}
prev.update(done)
with open(src, "w") as f:
    json.dump(prev, f, indent=2)
    f.write("\n")
print(f"library: {args.dest} ({sum(v['files'] for v in prev.values())} sounds in {len(prev)} packs); "
      f"rate it with tools/audio/rate_sfx.py")
