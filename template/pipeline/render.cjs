#!/usr/bin/env node
// Render a cut (silent, near lossless) through the Remotion Node API.
//
//   npm run render -- master                     -> build/render/master.mp4
//   npm run render -- vertical --scale 0.5       -> half resolution (fast previews)
//   npm run render -- master --scale 2           -> 4K from the 1080p comp
//   npm run render -- vertical --probe --out build/probe/vertical.mp4
//   npm run render -- master --still 4.5 --out build/stills/master-4.5.png
//
// Options: --scale N (1), --crf N (12), --concurrency N (half the cores),
// --out PATH, --probe (safe-zone probe render), --still SECONDS (one PNG).
//
// Why the Node API and not `npx remotion render`: a slow font load makes
// Remotion retry the frame, the CLI counts every retry again, and at high
// resolutions its progress bar computes a negative width and crashes the
// whole render. The API has no progress bar, so a retried frame costs time,
// never the render. The 120 s page timeout survives a machine under load.
const fs = require("fs");
const os = require("os");
const path = require("path");
const { bundle } = require("@remotion/bundler");
const { renderMedia, renderStill, selectComposition } = require("@remotion/renderer");

const ROOT = path.resolve(__dirname, "..");
const COMPS = { master: "Master", vertical: "Vertical" };

const argv = process.argv.slice(2);
const cut = argv[0];
const opt = (name, def) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : def;
};
const flag = (name) => argv.includes(`--${name}`);
if (!cut || !COMPS[cut]) {
  process.stderr.write("usage: npm run render -- <master|vertical> [--scale N] [--crf N] [--concurrency N] [--out PATH] [--probe] [--still SECONDS]\n");
  process.exit(2);
}
const scale = Number(opt("scale", process.env.SCALE || "1"));
const crf = Number(opt("crf", "12"));
const concurrency = Number(opt("concurrency", String(Math.max(1, Math.floor(os.cpus().length / 2)))));
const probe = flag("probe");
const still = opt("still", null);
const out = path.resolve(
  ROOT,
  opt("out", still !== null ? `build/stills/${cut}-${still}.png` : `build/render/${cut}${probe ? ".probe" : ""}.mp4`),
);
fs.mkdirSync(path.dirname(out), { recursive: true });

const log = (s) => process.stdout.write(`${new Date().toISOString().slice(11, 19)} ${s}\n`);

const main = async () => {
  if (!fs.existsSync(path.join(ROOT, "public", "generated", "words.json"))) {
    throw new Error("public/generated/words.json is missing: run `npm run voice` and `npm run words` first");
  }
  log(`bundle src/index.ts`);
  const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.ts"), publicDir: path.join(ROOT, "public") });
  const inputProps = { cut, probe };
  const composition = await selectComposition({ serveUrl, id: COMPS[cut], inputProps, timeoutInMilliseconds: 120000 });
  if (still !== null) {
    const frame = Math.min(composition.durationInFrames - 1, Math.round(Number(still) * composition.fps));
    await renderStill({ composition, serveUrl, output: out, frame, scale, inputProps, timeoutInMilliseconds: 120000, overwrite: true });
    log(`wrote ${path.relative(ROOT, out)} (frame ${frame})`);
    return;
  }
  log(
    `${composition.id} ${composition.width}x${composition.height} x${scale}, ${composition.durationInFrames} frames at ` +
      `${composition.fps} fps, crf ${crf}, concurrency ${concurrency}${probe ? ", PROBE" : ""}`,
  );
  let last = -10;
  await renderMedia({
    composition,
    serveUrl,
    codec: "h264",
    crf,
    scale,
    concurrency,
    inputProps,
    timeoutInMilliseconds: 120000,
    imageFormat: "jpeg",
    jpegQuality: 95,
    outputLocation: out,
    overwrite: true,
    logLevel: "warn",
    onProgress: ({ progress }) => {
      const pct = Math.floor(progress * 100);
      if (pct >= last + 10) {
        last = pct;
        log(`${pct}%`);
      }
    },
  });
  log(`wrote ${path.relative(ROOT, out)}`);
};

main().catch((err) => {
  process.stderr.write(`render failed: ${err && err.stack ? err.stack : err}\n`);
  process.exit(1);
});
