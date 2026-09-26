// Every caption page each cut shows, with how long it stays settled (fully in,
// not yet leaving), sampled frame by frame with the renderer's own functions
// (src/captionPages.ts). `npm run check:captions` reads this to apply the
// reading time rule to the master, the vertical and the teaser.
//
//   node --no-warnings --experimental-strip-types pipeline/caption-pages.mjs
//
// Needs Node 22.6 or newer (type stripping) and public/generated/words.json.
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, "..");
const t = await import(pathToFileURL(path.join(root, "src", "timeline.ts")).href);
const cp = await import(pathToFileURL(path.join(root, "src", "captionPages.ts")).href);
const words = JSON.parse(readFileSync(path.join(root, "public", "generated", "words.json"), "utf8")).lines;

const range = (a, b) => Array.from({ length: Math.max(0, b - a) }, (_, i) => a + i);
// the renderer's frame of a time (src/context.tsx S, half up) ...
const S = (s) => Math.round(s * t.FPS);
// ... and the frame pipeline/teaser.py cuts at: Python's round(), half to even
const pyRound = (x) => {
  const f = Math.floor(x);
  return x - f === 0.5 ? (f % 2 === 0 ? f : f + 1) : Math.round(x);
};
const T = (s) => pyRound(s * t.FPS);
// the vertical's loop tail draws a frozen first frame over everything, captions included
const hiddenFor = (c) => (c.acts.loop ? (f) => f >= S(c.acts.loop.from) && f < S(c.acts.loop.to) : () => false);
const maxChars = (id) => cp.captionLayout(id === "vertical").maxChars;

const pages = [];
for (const [id, c] of Object.entries(t.CUTS)) {
  if (c.captions === false) continue;
  pages.push(...cp.readPages(id, t.LINES, words, maxChars(id), t.FPS, range(0, S(c.dur)), hiddenFor(c)));
}
// the teaser is cut from the vertical: its frames are the vertical's frames inside TEASER
const V = t.CUTS.vertical;
if (V && V.captions !== false && t.TEASER.length) {
  const frames = t.TEASER.flatMap((s) => range(T(s.from), T(s.to)));
  pages.push(...cp.readPages("teaser", t.LINES, words, maxChars("vertical"), t.FPS, frames, hiddenFor(V)));
}
process.stdout.write(JSON.stringify({ fps: t.FPS, pages }, null, 1) + "\n");
