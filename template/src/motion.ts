import { Easing, interpolate } from "remotion";

/**
 * Motion vocabulary. Three curves, no springs, nothing bounces: overshoot and
 * elastic easing read as a toy and are a known tell of generated design.
 *   OUT    entrances, type landing, UI arriving (expo out)
 *   INOUT  camera moves between framings (eased both ends)
 *   LIN    counters, typing, clocks
 */
export const OUT = Easing.bezier(0.16, 1, 0.3, 1);
export const INOUT = Easing.bezier(0.65, 0, 0.35, 1);
export const LIN = Easing.linear;

const CL = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** Clamped two-point interpolate with an easing. */
export const k = (f: number, f0: number, f1: number, v0: number, v1: number, ease: (t: number) => number = OUT) =>
  interpolate(f, [f0, f1], [v0, v1], { ...CL, easing: ease });

/** 0 to 1 entrance starting at `at` (frames), lasting `dur` frames. */
export const inn = (f: number, at: number, dur = 18, ease = OUT) => k(f, at, at + dur, 0, 1, ease);

/** 1 to 0 exit starting at `at`, lasting `dur`. */
export const out = (f: number, at: number, dur = 12, ease = INOUT) => k(f, at, at + dur, 1, 0, ease);

/** In at `a`, out at `b`: the envelope of an element that lives [a, b]. */
export const life = (f: number, a: number, b: number, inDur = 16, outDur = 12) =>
  Math.min(inn(f, a, inDur), out(f, b - outDur, outDur));

/** Deterministic pseudo random in [0, 1) from an integer seed. */
export const rand = (seed: number) => {
  const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
};

/** Typewriter: the visible part of `text` at frame f. */
export const typed = (f: number, at: number, text: string, cps = 28, fps = 30) =>
  text.slice(0, Math.max(0, Math.floor(((f - at) / fps) * cps)));
