/**
 * THE TIMELINE. The one file that drives picture, captions and the audio mix.
 *
 * Every time is in SECONDS on the cut's own clock. The scenes read acts and
 * events from here, the captions read LINES from here (plus the word timings
 * that `npm run words` measures), and every pipeline script reads this file
 * through `npm run timeline` (Node type stripping), so a retime here moves
 * picture and sound together.
 *
 * Keep this file free of imports: Node loads it directly with
 * --experimental-strip-types, which does not resolve other TypeScript files.
 *
 * The example is a fictional houseplant app, "Fernwise". Replace everything
 * below with your own film; keep the shapes.
 */

export const FPS = 30;

/* ---------------------------------------------------------------- speakers */

/** Who speaks. Each speaker maps to a voice and an EQ chain in film.config.json. */
export type Who = "narrator";

/* ------------------------------------------------------------------- lines */

/**
 * One spoken line. `text` is what the captions show; `tts` (optional) is what
 * the voice engine reads when the two differ ("250 ml" shown, "two hundred
 * fifty milliliters" spoken). `at` is the start on the shared clock.
 * `claim` points at a row in film/claims.md (or "story" for a line that makes
 * no promise about the product).
 */
export type Line = {
  id: string;
  who: Who;
  text: string;
  tts?: string;
  at: number;
  claim: string;
  /** true when the same words are already on screen as type (an end card): no caption */
  onScreen?: boolean;
  /** this line only: speaking rate, 0.7 to 1.2 (overrides the speaker's settings.speed) */
  speed?: number;
};

export const LINES: Line[] = [
  {
    id: "L1",
    who: "narrator",
    text: "Your fern has been thirsty since Tuesday.",
    at: 0.5,
    claim: "story",
  },
  {
    id: "L2",
    who: "narrator",
    text: "Fernwise knows when each plant needs water.",
    at: 4.4,
    claim: "C1",
  },
  {
    id: "L3",
    who: "narrator",
    text: "One nudge, with the right amount.",
    at: 8.9,
    claim: "C2",
  },
  {
    id: "L4",
    who: "narrator",
    text: "Fernwise. Stop guessing.",
    at: 13.6,
    claim: "brand", onScreen: true,
  },
];

/* ------------------------------------------------------------------ events */

/** Named moments on the shared clock (both cuts). Scenes and sound cues read these. */
export const EV = {
  droop: 0.0,
  nudgeLands: 4.3,
  listIn: 8.6,
  tick: 10.4,
  endHit: 13.4,
};

/* -------------------------------------------------------------------- cuts */

export type Seg = { from: number; to: number };
export type CutId = "master" | "vertical";

export type CutSpec = {
  id: CutId;
  /** Remotion composition id */
  comp: string;
  w: number;
  h: number;
  dur: number;
  /** burn in the karaoke captions (default true); false gives a clean picture */
  captions?: boolean;
  acts: {
    hook: Seg;
    nudge: Seg;
    list: Seg;
    end: Seg;
    /** vertical only: hold frame 0 at the end so the platform loop is seamless */
    loop?: Seg;
  };
};

export const MASTER: CutSpec = {
  id: "master",
  comp: "Master",
  w: 1920,
  h: 1080,
  dur: 18.0,
  acts: {
    hook: { from: 0, to: 4.3 },
    nudge: { from: 4.3, to: 8.6 },
    list: { from: 8.6, to: 13.4 },
    end: { from: 13.4, to: 18.0 },
  },
};

export const VERTICAL: CutSpec = {
  id: "vertical",
  comp: "Vertical",
  w: 1080,
  h: 1920,
  dur: 18.0,
  acts: {
    hook: { from: 0, to: 4.3 },
    nudge: { from: 4.3, to: 8.6 },
    list: { from: 8.6, to: 13.4 },
    end: { from: 13.4, to: 17.4 },
    loop: { from: 17.4, to: 18.0 },
  },
};

export const CUTS: Record<CutId, CutSpec> = {
  master: MASTER,
  vertical: VERTICAL,
};

/* -------------------------------------------------------------- on screen */

/**
 * Every string the picture shows lives here, so `npm run check:claims` can
 * read all of it. `claim` is a row id in film/claims.md, or one of
 * "story" (fiction inside the film), "brand" (name, tagline), "label" (UI
 * chrome that promises nothing), "legal" (disclaimers).
 */
export type Copy = { text: string; claim: string };

export const COPY = {
  lastLabel: { text: "Last watered", claim: "story" },
  lastDay: { text: "Tuesday.", claim: "story" },
  appName: { text: "Fernwise", claim: "brand" },
  nudgeTitle: { text: "Water the fern", claim: "C2" },
  nudgeBody: { text: "250 ml, the soil is dry", claim: "C2" },
  nudgeWhen: { text: "now", claim: "label" },
  listTitle: { text: "This week", claim: "C3" },
  plant1: { text: "Fern", claim: "story" },
  plant1When: { text: "Today", claim: "story" },
  plant1Amount: { text: "250 ml", claim: "story" },
  plant2: { text: "Monstera", claim: "story" },
  plant2When: { text: "Friday", claim: "story" },
  plant2Amount: { text: "400 ml", claim: "story" },
  plant3: { text: "Pothos", claim: "story" },
  plant3When: { text: "Sunday", claim: "story" },
  plant3Amount: { text: "150 ml", claim: "story" },
  tagline: { text: "Stop guessing.", claim: "brand" },
  url: { text: "fernwise.example", claim: "brand" },
  disclaimer: {
    text: "Example film. Fernwise is a fictional product.",
    claim: "legal",
  },
} satisfies Record<string, Copy>;

/* ------------------------------------------------------------------ sound */

/** A sound effect cue. `name` is a key of `sfx` in film.config.json. */
export type SfxCue = { name: string; at: number; gainDb: number };

export const sfxFor = (c: CutSpec): SfxCue[] => {
  const cues: SfxCue[] = [
    { name: "notify", at: EV.nudgeLands + 0.1, gainDb: -14 },
    { name: "whoosh", at: EV.listIn - 0.15, gainDb: -20 },
    { name: "tick", at: EV.tick, gainDb: -16 },
    { name: "hit", at: EV.endHit, gainDb: -9 },
  ];
  return cues.filter((q) => q.at < c.dur);
};

/**
 * Music. One section per act, so the score turns where the picture turns.
 * ElevenLabs music needs every section to be at least 3 s long; the timeline
 * check enforces it. `gain` is a list of [seconds, dB] keyframes for the music
 * bus; the mixer also ducks the music by `duckDb` under every spoken line.
 */
export type MusicSection = {
  name: string;
  from: number;
  to: number;
  styles: string[];
  avoid: string[];
};

export const MUSIC = {
  global: [
    "warm minimal electronic",
    "soft felt piano",
    "modern product film",
    "100 bpm",
    "C major",
  ],
  avoid: ["vocals", "lyrics", "choir", "EDM drop", "dubstep"],
  duckDb: 8,
  sections: (c: CutSpec): MusicSection[] => [
    {
      name: "Wilted",
      from: c.acts.hook.from,
      to: c.acts.hook.to,
      styles: ["sparse", "one low piano note", "hushed"],
      avoid: ["drums"],
    },
    {
      name: "Nudge",
      from: c.acts.nudge.from,
      to: c.acts.nudge.to,
      styles: ["gentle pulse enters", "hopeful"],
      avoid: ["loud drums"],
    },
    {
      name: "Week",
      from: c.acts.list.from,
      to: c.acts.list.to,
      styles: ["light percussion", "bright", "building"],
      avoid: ["aggressive"],
    },
    {
      name: "Resolve",
      from: c.acts.end.from,
      to: c.dur,
      styles: ["warm resolving chord", "long soft tail"],
      avoid: ["sudden cut"],
    },
  ],
  gain: (c: CutSpec): [number, number][] => [
    [0, -12],
    [c.acts.nudge.from - 0.2, -12],
    [c.acts.nudge.from + 0.4, -8],
    [c.acts.end.from - 0.1, -8],
    [c.acts.end.from + 0.2, -5],
    [c.dur, -5],
  ],
};

/* ----------------------------------------------------------------- poster */

/**
 * The poster: a SETTLED moment (type fully in, not mid transition) on each
 * cut's own clock, the teaser's on the teaser's. `npm run finish` bakes that
 * frame into frame 0 of the delivered file, because X, Slack, Discord and
 * most players show frame 0 as the thumbnail and ignore cover art. On
 * playback it shows for one frame (and on the vertical once per loop), so
 * pick a moment of the opening: the hook with its type in. At least one
 * frame in and before the last frame; `npm run check:timeline` checks it.
 */
export const POSTER: Record<CutId | "teaser", number> = {
  master: 3.5,
  vertical: 3.5,
  teaser: 2.5,
};

/* ----------------------------------------------------------------- teaser */

/**
 * The teaser is cut from the rendered VERTICAL and its mix. Segments are in
 * seconds on the vertical's clock. Every cut point must fall in a gap between
 * words; `npm run check:timeline` fails a segment edge that lands inside a word.
 */
export const TEASER: Seg[] = [
  { from: 0.0, to: 3.2 },
  { from: 4.3, to: 7.6 },
  { from: 13.4, to: 17.0 },
];
