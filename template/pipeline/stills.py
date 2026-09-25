#!/usr/bin/env python3
"""Optional photographic plates for the backgrounds (film.config.json `stills`).

  npm run stills                 # every still that is missing
  npm run stills -- --force      # regenerate (spends credits)

Needs OPENAI_API_KEY and the OpenAI Python SDK (`pip install openai`). The
model comes from OPENAI_IMAGE_MODEL (default `gpt-image-1`); size and
quality come from each entry in the config.

The request is STREAMED through the SDK. A plain blocking HTTP call to the
image endpoint can sit silent for over a minute on a high quality image and
get cut off by a proxy or client timeout; the streamed call keeps the
connection alive and delivers the image in its final event.

With no key, or PF_NO_KEYS=1, the step is skipped and the film renders
without plates (<Plate> draws nothing for a still that does not exist).

Output: public/stills/<name>.png and public/generated/stills.json (the list
of stills that exist, read by the composition before the first frame).
"""
import argparse
import base64
import json
import os

import common as C

ap = argparse.ArgumentParser()
ap.add_argument("--force", action="store_true")
args = ap.parse_args()

cfg = C.cfg()
stills = cfg.get("stills", {})
folder = os.path.join(C.ROOT, "public", "stills")


def present():
    return sorted(n for n in stills if os.path.exists(os.path.join(folder, f"{n}.png")))


def write_list():
    with open(C.generated("stills.json"), "w") as f:
        json.dump(present(), f)


if C.no_keys() or not os.environ.get("OPENAI_API_KEY"):
    write_list()
    print(f"stills: skipped (no OpenAI key or PF_NO_KEYS=1); {len(present())} of {len(stills)} present, "
          "the film renders without the missing plates")
    raise SystemExit(0)

try:
    from openai import OpenAI
except ImportError:
    C.die("the OpenAI Python SDK is not installed: `pip install openai`", 2)

client = OpenAI()
model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
os.makedirs(folder, exist_ok=True)
for name, spec in stills.items():
    dst = os.path.join(folder, f"{name}.png")
    if os.path.exists(dst) and not args.force:
        print(f"{name}: exists")
        continue
    stream = client.images.generate(
        model=model,
        prompt=spec["prompt"],
        size=spec.get("size", "1536x1024"),
        quality=spec.get("quality", "medium"),
        n=1,
        stream=True,
        partial_images=0,
    )
    b64 = None
    for event in stream:
        if getattr(event, "type", "") == "image_generation.completed":
            b64 = event.b64_json
    if not b64:
        C.die(f"{name}: the image stream ended without a completed image")
    with open(dst, "wb") as f:
        f.write(base64.b64decode(b64))
    C.record_source(f"stills/{name}.png", f"OpenAI {model} ({spec.get('quality', 'medium')})")
    print(f"{name}: wrote public/stills/{name}.png")

write_list()
