/**
 * Unit tests for src/beatSync.ts. No npm dependency and no Python: Node's own
 * test runner with type stripping.
 *
 *   npm test
 *   node --no-warnings --experimental-strip-types --test tools/audio/beatSync.test.ts
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  MAJOR_CUE_TOLERANCE_S,
  SEQUENCE_BEAT_TOLERANCE_S,
  formatSnaps,
  nearestIndex,
  parseBeatMap,
  placeTrack,
  planReveals,
  sequenceStride,
  snapMajor,
  snapSequence,
} from "../../src/beatSync.ts";
import type { BeatMap } from "../../src/beatSync.ts";

/** synthetic grid: `bpm`, first beat at 0.02 s, cues on every 4th beat */
const grid = (bpm: number, n = 40): BeatMap => {
  const p = 60 / bpm;
  const beats = Array.from({ length: n }, (_, i) => ({
    time: 0.02 + i * p,
    intensity: i % 4 === 0 ? 1 : 0.6,
  }));
  return parseBeatMap({
    schemaVersion: 1,
    bpm,
    beatPeriod: p,
    duration: n * p,
    beats,
    strongCues: beats
      .filter((_, i) => i % 4 === 0)
      .map((b) => ({ ...b, kind: "strong_beat" })),
  });
};

test("parseBeatMap rejects malformed maps", () => {
  assert.throws(() => parseBeatMap(null), /not an object/);
  assert.throws(() => parseBeatMap({ schemaVersion: 2 }), /schemaVersion/);
  const base = {
    schemaVersion: 1,
    bpm: 120,
    duration: 4,
    beats: [
      { time: 0, intensity: 1 },
      { time: 0.5, intensity: 1 },
    ],
    strongCues: [],
  };
  assert.throws(() => parseBeatMap({ ...base, bpm: 0 }), /bpm/);
  assert.throws(
    () =>
      parseBeatMap({
        ...base,
        beats: [
          { time: 1, intensity: 1 },
          { time: 0.5, intensity: 1 },
        ],
      }),
    /not sorted/,
  );
  assert.throws(
    () =>
      parseBeatMap({
        ...base,
        beats: [
          { time: "x", intensity: 1 },
          { time: 1, intensity: 1 },
        ],
      }),
    /numeric/,
  );
  assert.equal(
    parseBeatMap(base).beatPeriod,
    0.5,
    "beatPeriod falls back to 60/bpm",
  );
});

test("parseBeatMap accepts the analyser's own output shape", () => {
  // the keys tools/audio/beats.py writes, extra ones included
  const m = parseBeatMap({
    schemaVersion: 1,
    tool: "tools/audio/beats.py",
    source: { file: "master.wav", sha256: "ab".repeat(32) },
    duration: 18.0,
    bpm: 100.45,
    beatPeriod: 0.5979,
    analysis: { sampleRate: 44100, hopLength: 512 },
    beats: [
      { time: 0.3, intensity: 0.8 },
      { time: 0.9, intensity: 0.5 },
    ],
    strongCues: [{ time: 0.3, intensity: 0.8, kind: "strong_beat" }],
  });
  assert.equal(m.bpm, 100.45);
  assert.equal(m.source?.file, "master.wav");
  assert.equal(m.strongCues[0].kind, "strong_beat");
});

test("nearestIndex finds the closest point", () => {
  const m = grid(120);
  assert.equal(nearestIndex(m.beats, 0), 0);
  assert.equal(nearestIndex(m.beats, 1.27), 2); // beats at 1.02 and 1.52
  assert.equal(nearestIndex(m.beats, 1.28), 3);
  assert.equal(nearestIndex(m.beats, 999), m.beats.length - 1);
  assert.equal(nearestIndex([], 1), -1);
});

test("snapMajor lands within 0.15 s of the nearest strong cue in reach", () => {
  const m = grid(120); // cues at 0.02, 2.02, 4.02, ...
  const s = snapMajor(m, "hero", 2.3, 30);
  assert.equal(s.targetS, 2.02);
  assert.ok(s.locked);
  assert.ok(s.distanceS! <= MAJOR_CUE_TOLERANCE_S);
  assert.equal(s.frame, 61); // round(2.02 * 30)
  // out of reach: keeps the planned time, reported free
  const far = snapMajor(m, "far", 3.0, 30); // nearest cues 2.02 / 4.02, 0.98 s away
  assert.equal(far.locked, false);
  assert.equal(far.targetS, null);
  assert.equal(far.frame, 90);
  // a wider reach lets it move
  assert.ok(snapMajor(m, "wide", 3.0, 30, { reachS: 1.2 }).locked);
});

test("snapSequence uses consecutive beats, each within 0.10 s", () => {
  const m = grid(100); // 0.6 s period, at or under 110 BPM
  const seq = snapSequence(m, ["a", "b", "c", "d"], 1.9, 30);
  const i0 = nearestIndex(m.beats, 1.9);
  seq.forEach((s, k) => {
    assert.equal(s.targetS, m.beats[i0 + k].time, `item ${k} on beat i0+${k}`);
    assert.ok(s.locked && s.distanceS! <= SEQUENCE_BEAT_TOLERANCE_S);
  });
});

test("readable text above 110 BPM takes every other beat", () => {
  const fast = grid(128);
  assert.equal(sequenceStride(fast, true), 2);
  assert.equal(sequenceStride(fast, false), 1, "accents may hit every beat");
  assert.equal(sequenceStride(grid(100), true), 1);
  const seq = snapSequence(fast, ["x", "y", "z"], 1.0, 30, {
    readableText: true,
  });
  const i0 = nearestIndex(fast.beats, 1.0);
  assert.deepEqual(
    seq.map((s) => s.targetS),
    [fast.beats[i0].time, fast.beats[i0 + 2].time, fast.beats[i0 + 4].time],
  );
  assert.ok(seq[1].snappedS - seq[0].snappedS > 0.9);
});

test("a sequence that runs off the end of the grid is reported free", () => {
  const m = grid(120, 6);
  const seq = snapSequence(m, ["a", "b", "c"], 2.3, 30);
  assert.equal(seq[0].locked, true);
  assert.equal(seq[2].locked, false);
});

test("placeTrack shifts the grid onto the cut's clock and drops what is outside", () => {
  const m = grid(120);
  const p = placeTrack(m, { trimStart: 4, at: 1, until: 5 });
  // track 4.02 plays at cut 1.02
  assert.equal(p.beats[0].time.toFixed(2), "0.02"); // track 3.02 -> cut 0.02
  assert.ok(p.beats.every((b) => b.time >= 0 && b.time <= 5));
  assert.ok(p.strongCues.some((c) => Math.abs(c.time - 1.02) < 1e-9));
});

test("placeTrack drops a point exactly at `until` (it could never render)", () => {
  const m = grid(120); // beat at 2.02
  const p = placeTrack(m, { until: 2.02 });
  assert.ok(p.beats.every((b) => b.time < 2.02));
});

test("planReveals warns on more than 3 majors and on rushed readable text", () => {
  const m = grid(120);
  const r = planReveals(
    m,
    [
      { kind: "major", label: "m1", at: 2 },
      { kind: "major", label: "m2", at: 4 },
      { kind: "major", label: "m3", at: 6 },
      { kind: "major", label: "m4", at: 8 },
      {
        kind: "sequence",
        labels: ["a", "b"],
        at: 10,
        readableText: true,
        stride: 1,
      },
    ],
    30,
  );
  assert.ok(r.warnings.some((w) => /4 major reveals/.test(w)));
  assert.ok(
    r.warnings.some((w) => /reveals readable text 0\.50 s apart/.test(w)),
    "every beat at 120 BPM is flagged for readable text",
  );
  assert.equal(r.frames.m1, 61);
  assert.match(formatSnaps(r.snaps), /m1 .* LOCKED/);
});

test("a sequence with no beat in reach keeps its planned times, reported free", () => {
  const m = grid(120, 6); // beats 0.02 .. 2.52 s
  const seq = snapSequence(m, ["a", "b"], 10, 30);
  assert.deepEqual(
    seq.map((s) => s.locked),
    [false, false],
  );
  assert.equal(seq[0].frame, 300, "kept at the planned 10.0 s");
  const placed = placeTrack(grid(120), { at: 3 }); // music starts at cut 3.02 s
  const r = planReveals(
    placed,
    [{ kind: "sequence", labels: ["one"], at: 0.5 }],
    30,
  );
  assert.equal(r.snaps[0].locked, false);
  assert.ok(r.warnings.some((w) => /"one" found no beat in reach/.test(w)));
});

test("no readable-text warning at 108 BPM on every beat (under the 110 rule)", () => {
  for (let off = 0; off < 1; off += 0.025) {
    const r = planReveals(
      grid(108),
      [
        {
          kind: "sequence",
          labels: ["a", "b", "c", "d", "e"],
          at: 2 + off,
          readableText: true,
        },
      ],
      30,
    );
    assert.deepEqual(r.warnings, [], `offset ${off.toFixed(3)}`);
  }
});

test("a track with no steady beat is flagged in every plan", () => {
  const flat = parseBeatMap({ ...grid(120), pulseClarity: 2.4 });
  assert.equal(flat.pulseClarity, 2.4);
  const r = planReveals(flat, [{ kind: "major", label: "m", at: 2 }], 30);
  assert.ok(r.snaps[0].locked, "the grid still snaps");
  assert.ok(r.warnings.some((w) => /no steady beat/.test(w)));
  const steady = parseBeatMap({ ...grid(120), pulseClarity: 8.4 });
  assert.deepEqual(
    planReveals(steady, [{ kind: "major", label: "m", at: 2 }], 30).warnings,
    [],
  );
});

test("duplicate labels are reported", () => {
  const r = planReveals(
    grid(120),
    [
      { kind: "major", label: "x", at: 2 },
      { kind: "major", label: "x", at: 4 },
    ],
    30,
  );
  assert.ok(r.warnings.some((w) => /duplicate label "x"/.test(w)));
});
