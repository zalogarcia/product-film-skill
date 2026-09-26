/**
 * Where the timeline's events sit against a music track's beats, and where
 * they would land if snapped. Prints only; timing still changes in
 * src/timeline.ts and nowhere else.
 *
 *   npm run beats -- build/music/master.wav             # once: writes build/music/master.beats.json
 *   npm run snap -- master                              # every EV event vs the nearest beat and strong cue
 *   npm run snap -- master --major nudgeLands,endHit    # snap those to strong cues (within 0.15 s)
 *   npm run snap -- master --sequence a,b,c [--readable]   # snap those to consecutive beats (within 0.10 s)
 *   npm run snap -- path/to/track.beats.json --cut vertical
 *
 * Exit 0 when every requested snap locks and the plan breaks no rule, 1 when
 * one is out of reach or a rule is broken (the reasons are printed), 2 on bad
 * input. Needs Node 22.6 or newer, and no Python (it reads the JSON only).
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  formatSnaps,
  framesPerBeat,
  nearestIndex,
  parseBeatMap,
  placeTrack,
  planReveals,
  MIN_PULSE_CLARITY,
  READABLE_TEXT_MAX_BPM,
} from "../../src/beatSync.ts";
import type { RevealPlan } from "../../src/beatSync.ts";
import { CUTS, EV, FPS } from "../../src/timeline.ts";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const usage = () => {
  process.stderr.write(
    "usage: npm run snap -- <cut | file.beats.json> [--cut <cut>] [--major k1,k2] [--sequence k1,k2,k3] [--readable]\n",
  );
  process.exit(2);
};

const argv = process.argv.slice(2);
const target = argv[0];
if (!target || target.startsWith("--")) usage();
const opt = (name: string) => {
  const i = argv.indexOf(`--${name}`);
  if (i < 0) return "";
  const v = argv[i + 1];
  if (!v || v.startsWith("--")) usage();
  return v;
};
const list = (s: string) =>
  s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

const cutId = target.endsWith(".json") ? opt("cut") || "master" : target;
const cut = (CUTS as Record<string, (typeof CUTS)[keyof typeof CUTS]>)[cutId];
if (!cut) {
  process.stderr.write(
    `snap: unknown cut "${cutId}" (have: ${Object.keys(CUTS).join(", ")})\n`,
  );
  process.exit(2);
}
let buildDir = "build";
try {
  buildDir =
    JSON.parse(readFileSync(join(ROOT, "film.config.json"), "utf8")).buildDir ??
    "build";
} catch {
  // no config: the default build folder
}
const file = target.endsWith(".json")
  ? target
  : join(ROOT, buildDir, "music", `${cutId}.beats.json`);
if (!existsSync(file)) {
  process.stderr.write(
    `snap: no beat map at ${file}\n      make one with: npm run beats -- ${join(buildDir, "music", `${cutId}.wav`)}\n`,
  );
  process.exit(2);
}

let track;
try {
  track = parseBeatMap(JSON.parse(readFileSync(file, "utf8")));
} catch (e) {
  process.stderr.write(`snap: ${(e as Error).message} (${file})\n`);
  process.exit(2);
}
const map = placeTrack(track, { until: cut.dur });
const events = EV as Record<string, number>;
const fpb = framesPerBeat(track.bpm, FPS);
console.log(
  `${track.source?.file ?? file}: ${track.bpm} BPM, a beat every ${track.beatPeriod.toFixed(3)} s ` +
    `(${fpb.toFixed(1)} frames at ${FPS} fps), ${map.beats.length} beats and ${map.strongCues.length} strong cues inside the ${cut.dur} s ${cutId}`,
);
if (track.pulseClarity !== undefined && track.pulseClarity < MIN_PULSE_CLARITY)
  console.log(
    `WARNING: pulse clarity ${track.pulseClarity} is under ${MIN_PULSE_CLARITY}: this track has no steady beat, so the beat grid below is a guess; the strong cues may still be real (listen)`,
  );
if (track.bpm > READABLE_TEXT_MAX_BPM)
  console.log(
    `above ${READABLE_TEXT_MAX_BPM} BPM: readable text takes every other beat (--readable)`,
  );

console.log(
  "\nevent               at      nearest beat          nearest strong cue",
);
for (const [k, t] of Object.entries(events)) {
  const b = map.beats[nearestIndex(map.beats, t)];
  const c = map.strongCues[nearestIndex(map.strongCues, t)];
  const fmt = (p?: { time: number }) =>
    p
      ? `${p.time.toFixed(3)} (${(p.time - t >= 0 ? "+" : "") + (p.time - t).toFixed(3)} s)`
      : "none";
  console.log(
    `${k.padEnd(18)} ${t.toFixed(3).padStart(7)}   ${fmt(b).padEnd(20)}  ${fmt(c)}`,
  );
}

const majors = list(opt("major"));
const seq = list(opt("sequence"));
const unknown = [...majors, ...seq].filter((k) => !(k in events));
if (unknown.length) {
  process.stderr.write(
    `snap: not an EV event: ${unknown.join(", ")} (have: ${Object.keys(events).join(", ")})\n`,
  );
  process.exit(2);
}
if (!majors.length && !seq.length) process.exit(0);

const plan: RevealPlan[] = majors.map((k) => ({
  kind: "major",
  label: k,
  at: events[k],
}));
if (seq.length)
  plan.push({
    kind: "sequence",
    labels: seq,
    at: events[seq[0]],
    readableText: argv.includes("--readable"),
  });
const { snaps, warnings } = planReveals(map, plan, FPS);
console.log(`\n${formatSnaps(snaps)}`);
console.log(
  "\nto apply, set these in EV (src/timeline.ts), then re-run the gates:",
);
for (const s of snaps)
  if (s.locked) console.log(`  ${s.label}: ${s.snappedS.toFixed(3)},`);
console.log(`warnings: ${warnings.length ? warnings.join(" | ") : "none"}`);
process.exit(warnings.length ? 1 : 0);
