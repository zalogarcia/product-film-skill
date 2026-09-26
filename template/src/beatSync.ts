/**
 * BEAT SYNC (optional): snap planned reveal times to a music track's measured
 * beats.
 *
 * The data comes from `npm run beats -- <track>` (tools/audio/beats.py, an
 * optional Python tool in its own venv), which writes `<track>.beats.json`:
 * the tempo, the beat grid and the strong cues. `npm run snap` reads it and
 * prints where the timeline's events would land; you then move the numbers in
 * src/timeline.ts, the one place timing lives. A scene that wants the map at
 * render time can `loadBeatMap(staticFile("generated/<cut>.beats.json"))` in
 * `calculateMetadata`, or `parseBeatMap(JSON.parse(text))` in Node.
 * Everything here is a pure function of the map, so a render stays
 * deterministic.
 *
 * The rules (adapted from latent-spaces/brag, MIT, `step-3-compose.md`
 * "Beat sync"; the notice is in tools/audio/NOTICE-brag.md):
 *  - 1 to 3 MAJOR reveals per film land within 0.15 s of a strong cue
 *    (a drop, a swell, a downbeat accent). `snapMajor`.
 *  - Items that appear one after another snap to CONSECUTIVE beats, each within
 *    0.10 s of its beat. `snapSequence`.
 *  - Above about 110 BPM, readable text does not reveal on every beat (beats
 *    under ~0.55 s apart outrun reading): every other beat. Accents (flashes,
 *    ticks, dots) may still hit every beat. `snapSequence({ readableText })`.
 *  - Readability, the voice and the story win. A reveal with no cue in reach
 *    keeps its planned time and is reported `locked: false`.
 *
 * Snap the LANDING time, the moment the viewer perceives as the hit (the
 * sound cue, the stamp settling), then subtract the move's own lead in.
 *
 * No imports on purpose: tools/audio/beatSync.test.ts and tools/audio/snap.ts
 * run this file directly under `node --experimental-strip-types`.
 */

export interface BeatPoint {
  /** seconds from the start of the track (or of the cut, after placeTrack) */
  time: number;
  /** 0..1, per track normalized */
  intensity: number;
}

export interface StrongCue extends BeatPoint {
  kind: "strong_beat" | "onset_peak";
}

export interface BeatMap {
  schemaVersion: 1;
  bpm: number;
  /** median gap between tracked beats, seconds */
  beatPeriod: number;
  duration: number;
  beats: BeatPoint[];
  strongCues: StrongCue[];
  /**
   * onset strength on the beats over the track's mean; under
   * MIN_PULSE_CLARITY the track has no steady beat and the grid is a guess
   */
  pulseClarity?: number;
  source?: { file: string; sha256?: string };
}

export const MAJOR_CUE_TOLERANCE_S = 0.15;
export const SEQUENCE_BEAT_TOLERANCE_S = 0.1;
/** above this tempo, readable text takes every other beat */
export const READABLE_TEXT_MAX_BPM = 110;
export const MAX_MAJOR_REVEALS = 3;
/** how far a major reveal may MOVE from its planned time to reach a cue */
export const DEFAULT_MAJOR_REACH_S = 0.5;
/**
 * below this pulse clarity the beat tracker found no steady beat (it always
 * reports a tempo): a steady beat scores 8 or more, a pad or noise 1 to 3
 */
export const MIN_PULSE_CLARITY = 4;

const fail = (msg: string): never => {
  throw new Error(`beatSync: ${msg}`);
};

const isNum = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v);

const readPoints = (raw: unknown, name: string, cues: boolean) => {
  if (!Array.isArray(raw)) return fail(`${name} is not an array`);
  let prev = -Infinity;
  return raw.map((p, i) => {
    const o = p as Record<string, unknown>;
    if (!o || !isNum(o.time) || !isNum(o.intensity))
      return fail(`${name}[${i}] needs numeric time and intensity`);
    if (o.time < prev) return fail(`${name} is not sorted at index ${i}`);
    prev = o.time;
    if (!cues) return { time: o.time, intensity: o.intensity };
    const kind = o.kind === "onset_peak" ? "onset_peak" : "strong_beat";
    return { time: o.time, intensity: o.intensity, kind } as StrongCue;
  });
};

/** Validate the tool's JSON at the boundary. Throws with the reason. */
export function parseBeatMap(raw: unknown): BeatMap {
  const o = raw as Record<string, unknown>;
  if (!o || typeof o !== "object") return fail("beat map is not an object");
  if (o.schemaVersion !== 1)
    return fail(`unsupported schemaVersion ${String(o.schemaVersion)}`);
  if (!isNum(o.bpm) || o.bpm <= 0) return fail("bpm must be a positive number");
  if (!isNum(o.duration)) return fail("duration must be a number");
  const beats = readPoints(o.beats, "beats", false);
  if (beats.length < 2) return fail("need at least 2 beats");
  const strongCues = readPoints(
    o.strongCues,
    "strongCues",
    true,
  ) as StrongCue[];
  const period =
    isNum(o.beatPeriod) && o.beatPeriod > 0 ? o.beatPeriod : 60 / o.bpm;
  const src = o.source as Record<string, unknown> | undefined;
  return {
    schemaVersion: 1,
    bpm: o.bpm,
    beatPeriod: period,
    duration: o.duration,
    beats,
    strongCues,
    pulseClarity: isNum(o.pulseClarity) ? o.pulseClarity : undefined,
    source:
      src && typeof src.file === "string"
        ? {
            file: src.file,
            sha256: typeof src.sha256 === "string" ? src.sha256 : undefined,
          }
        : undefined,
  };
}

/** Fetch and validate a beat map; pass `staticFile("generated/x.beats.json")`. */
export async function loadBeatMap(url: string): Promise<BeatMap> {
  const res = await fetch(url);
  if (!res.ok) return fail(`could not load ${url}: HTTP ${res.status}`);
  return parseBeatMap(await res.json());
}

/**
 * Move a track's map onto the CUT's clock. The track, trimmed by `trimStart`
 * seconds, starts playing at cut second `at` (default 0). Points before
 * second 0, or at or after `until` (the cut's length; a landing there could
 * never render), are dropped. The pipeline's music tracks already start at 0
 * on the cut's clock, so for them this only applies `until`.
 */
export function placeTrack(
  map: BeatMap,
  opts: { trimStart?: number; at?: number; until?: number } = {},
): BeatMap {
  const shift = (opts.at ?? 0) - (opts.trimStart ?? 0);
  const until = opts.until ?? Infinity;
  const keep = <T extends BeatPoint>(p: T): T | null => {
    const t = p.time + shift;
    return t >= 0 && t < until ? { ...p, time: t } : null;
  };
  return {
    ...map,
    duration: Math.min(until, map.duration + shift),
    beats: map.beats.map(keep).filter((p): p is BeatPoint => p !== null),
    strongCues: map.strongCues
      .map(keep)
      .filter((p): p is StrongCue => p !== null),
  };
}

/** index of the point nearest to t (points sorted by time) */
export function nearestIndex(points: BeatPoint[], t: number): number {
  if (points.length === 0) return -1;
  let lo = 0;
  let hi = points.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (points[mid].time <= t) lo = mid;
    else hi = mid;
  }
  return Math.abs(points[lo].time - t) <= Math.abs(points[hi].time - t)
    ? lo
    : hi;
}

export const secondsToFrame = (s: number, fps: number) => Math.round(s * fps);
export const framesPerBeat = (bpm: number, fps: number) => (fps * 60) / bpm;

export interface Snap {
  label: string;
  kind: "major" | "sequence";
  plannedS: number;
  /** the landing frame */
  frame: number;
  /** frame / fps, the time the reveal actually lands */
  snappedS: number;
  /** the cue or beat it locked to, null when nothing was in reach */
  targetS: number | null;
  /** |snappedS - targetS| after frame rounding, null when unlocked */
  distanceS: number | null;
  toleranceS: number;
  locked: boolean;
}

const makeSnap = (
  label: string,
  kind: Snap["kind"],
  plannedS: number,
  targetS: number | null,
  fps: number,
  toleranceS: number,
): Snap => {
  const frame = secondsToFrame(targetS ?? plannedS, fps);
  const snappedS = frame / fps;
  const distanceS = targetS === null ? null : Math.abs(snappedS - targetS);
  return {
    label,
    kind,
    plannedS,
    frame,
    snappedS,
    targetS,
    distanceS,
    toleranceS,
    locked: distanceS !== null && distanceS <= toleranceS,
  };
};

/**
 * A MAJOR reveal (an act turn, the product's entrance, the end card hit):
 * move it to the nearest strong cue, if one is within `reachS` of the planned
 * time.
 */
export function snapMajor(
  map: BeatMap,
  label: string,
  plannedS: number,
  fps: number,
  opts: { reachS?: number; toleranceS?: number } = {},
): Snap {
  const reach = opts.reachS ?? DEFAULT_MAJOR_REACH_S;
  const tol = opts.toleranceS ?? MAJOR_CUE_TOLERANCE_S;
  const i = nearestIndex(map.strongCues, plannedS);
  const cue = i >= 0 ? map.strongCues[i] : null;
  const target =
    cue && Math.abs(cue.time - plannedS) <= reach ? cue.time : null;
  return makeSnap(label, "major", plannedS, target, fps, tol);
}

/** beats between consecutive items: 2 for readable text above 110 BPM */
export const sequenceStride = (map: BeatMap, readableText: boolean) =>
  readableText && map.bpm > READABLE_TEXT_MAX_BPM ? 2 : 1;

/**
 * Items that appear one after another: the first lands on the beat nearest
 * `startS`, each next one `stride` beats later on the SAME grid (consecutive
 * beats, or every other beat for readable text above 110 BPM). If no beat lies
 * within `reachS` of `startS` (default: one beat period, i.e. the grid does not
 * cover that time), every item keeps its planned time and reports locked: false.
 */
export function snapSequence(
  map: BeatMap,
  labels: string[],
  startS: number,
  fps: number,
  opts: {
    readableText?: boolean;
    stride?: number;
    toleranceS?: number;
    reachS?: number;
  } = {},
): Snap[] {
  const stride = opts.stride ?? sequenceStride(map, opts.readableText ?? false);
  const tol = opts.toleranceS ?? SEQUENCE_BEAT_TOLERANCE_S;
  const reach = opts.reachS ?? map.beatPeriod;
  const near = nearestIndex(map.beats, startS);
  const i0 =
    near >= 0 && Math.abs(map.beats[near].time - startS) <= reach ? near : -1;
  const firstT = i0 >= 0 ? map.beats[i0].time : startS;
  return labels.map((label, k) => {
    const planned = firstT + k * stride * map.beatPeriod;
    const beat = i0 >= 0 ? map.beats[i0 + k * stride] : undefined;
    return makeSnap(
      label,
      "sequence",
      k === 0 ? startS : planned,
      beat ? beat.time : null,
      fps,
      tol,
    );
  });
}

export type RevealPlan =
  | { kind: "major"; label: string; at: number; reachS?: number }
  | {
      kind: "sequence";
      labels: string[];
      at: number;
      readableText?: boolean;
      stride?: number;
      reachS?: number;
    };

export interface PlanResult {
  snaps: Snap[];
  /** frame lookup by label */
  frames: Record<string, number>;
  warnings: string[];
}

/** Snap a whole plan and check it against the rules. */
export function planReveals(
  map: BeatMap,
  plan: RevealPlan[],
  fps: number,
): PlanResult {
  const snaps: Snap[] = [];
  const warnings: string[] = [];
  for (const p of plan) {
    if (p.kind === "major") {
      snaps.push(snapMajor(map, p.label, p.at, fps, { reachS: p.reachS }));
    } else {
      const seq = snapSequence(map, p.labels, p.at, fps, {
        readableText: p.readableText,
        stride: p.stride,
        reachS: p.reachS,
      });
      if (p.readableText && seq.length > 1) {
        // the grid gap, not the frame-rounded one: rounding alone can make a
        // 108 BPM gap read shorter than the 110 BPM threshold
        const at = (s: Snap) => s.targetS ?? s.plannedS;
        const gap = at(seq[1]) - at(seq[0]);
        if (gap < 60 / READABLE_TEXT_MAX_BPM)
          warnings.push(
            `sequence "${p.labels.join(", ")}" reveals readable text ${gap.toFixed(2)} s apart; use stride 2 or reveal fast and hold`,
          );
      }
      snaps.push(...seq);
    }
  }
  if (map.pulseClarity !== undefined && map.pulseClarity < MIN_PULSE_CLARITY)
    warnings.push(
      `pulse clarity ${map.pulseClarity} is under ${MIN_PULSE_CLARITY}: the track has no steady beat, so these snaps are to a guessed grid`,
    );
  const majors = snaps.filter((s) => s.kind === "major").length;
  if (majors > MAX_MAJOR_REVEALS)
    warnings.push(
      `${majors} major reveals; the rule is 1 to ${MAX_MAJOR_REVEALS} per film`,
    );
  for (const s of snaps)
    if (!s.locked)
      warnings.push(
        `"${s.label}" found no ${s.kind === "major" ? "strong cue" : "beat"} in reach; kept at ${s.plannedS.toFixed(2)} s`,
      );
  const frames: Record<string, number> = {};
  for (const s of snaps) {
    if (s.label in frames) warnings.push(`duplicate label "${s.label}"`);
    frames[s.label] = s.frame;
  }
  return { snaps, frames, warnings };
}

/** plain text table: planned, snapped, target and distance per reveal */
export function formatSnaps(snaps: Snap[]): string {
  const rows = snaps.map((s) =>
    [
      s.label.padEnd(18),
      s.kind.padEnd(8),
      s.plannedS.toFixed(3).padStart(7),
      String(s.frame).padStart(5),
      s.snappedS.toFixed(3).padStart(7),
      (s.targetS === null ? "none" : s.targetS.toFixed(3)).padStart(7),
      (s.distanceS === null ? "n/a" : s.distanceS.toFixed(3)).padStart(6),
      s.toleranceS.toFixed(2).padStart(5),
      s.locked ? "LOCKED" : "FREE",
    ].join("  "),
  );
  return [
    "label               kind      planned  frame  snapped   target    dist    tol  state",
    ...rows,
  ].join("\n");
}
