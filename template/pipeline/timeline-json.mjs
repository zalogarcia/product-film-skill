// Print the timeline (src/timeline.ts) as JSON, with every per-cut function
// already evaluated, so the Python pipeline reads the SAME numbers the
// scenes render from.
//
//   node --no-warnings --experimental-strip-types pipeline/timeline-json.mjs
//
// Needs Node 22.6 or newer (type stripping).
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const t = await import(pathToFileURL(path.join(here, "..", "src", "timeline.ts")).href);

const cuts = {};
for (const [id, c] of Object.entries(t.CUTS)) {
  cuts[id] = {
    ...c,
    sfx: t.sfxFor(c),
    music: {
      sections: t.MUSIC.sections(c),
      gain: t.MUSIC.gain(c),
    },
  };
}

process.stdout.write(
  JSON.stringify(
    {
      fps: t.FPS,
      lines: t.LINES,
      events: t.EV,
      copy: t.COPY,
      cuts,
      music: { global: t.MUSIC.global, avoid: t.MUSIC.avoid, duckDb: t.MUSIC.duckDb },
      teaser: t.TEASER,
      poster: t.POSTER,
    },
    null,
    1,
  ) + "\n",
);
