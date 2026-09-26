/**
 * Caption pages: how a spoken line is split into pages, which page is up at a
 * given time, and how long each page stays SETTLED (fully in, not yet
 * leaving). One source for both sides: src/ui/Captions.tsx renders with these
 * functions, and `npm run check:captions` measures the same pages frame by
 * frame (through pipeline/caption-pages.mjs), so the gate reads exactly what
 * the film shows.
 *
 * The reading time rule (fast in, then hold; from latent-spaces/brag
 * `step-2-plan.md`, MIT, notice in tools/audio/NOTICE-brag.md): a page of 1
 * to 3 words stays settled at least 0.8 s; a longer page 0.3 s per word, at
 * least 1.2 s. The last page of a line holds until it has had its reading
 * time (and never less than MIN_HOLD after the voice ends); a page the voice
 * leaves too early, or one the next line, the loop or a teaser edge cuts
 * short, fails the gate.
 *
 * No imports on purpose: Node runs this file directly with type stripping.
 */

/** a word with its measured start and end, seconds from the line's start */
export type PageWord = { w: string; t: number; e: number };
/** the fields of a timeline line the captions use */
export type CaptionLine = { id: string; at: number; onScreen?: boolean };
/** word timings per line id (public/generated/words.json `lines`) */
export type LineWords = Record<string, { dur: number; words: PageWord[] }>;

/** a line (and each page after the first) comes up this long before its first word */
export const LEAD = 0.05;
/** a page fades in from 0.1 s before its first word to ENTER after it */
export const ENTER = 0.18;
/** the last page fades out over the final LEAVE seconds of its hold */
export const LEAVE = 0.15;
/** a finished line stays up at least this long after the voice ends */
export const MIN_HOLD = 0.35;
/** margin the hold adds over the bare reading time, about a frame and a half */
const HOLD_MARGIN = 0.05;

/** caption type per layout: font size, box width and the characters a page may hold */
export const captionLayout = (isV: boolean) => {
  const size = isV ? 66 : 46;
  const width = isV ? 800 : 1300;
  return { size, width, maxChars: Math.floor((width / (size * 0.5)) * 2) };
};

/** The reading time rule: seconds a page of `words` words must stay settled. */
export const readSeconds = (words: number) =>
  words <= 3 ? 0.8 : Math.max(1.2, 0.3 * words);

/**
 * Split words into caption pages. The page count comes from the line length,
 * then every page aims at an equal share, so a line never ends on a lonely one
 * word page; a sentence end near the target is preferred as the break.
 */
export const splitPages = <W extends PageWord>(
  ws: W[],
  maxChars: number,
): W[][] => {
  const total = ws.reduce((a, w) => a + w.w.length + 1, -1);
  const n = Math.max(1, Math.ceil(total / maxChars));
  const target = total / n;
  const pages: W[][] = [];
  let cur: W[] = [];
  let len = 0;
  ws.forEach((w, i) => {
    cur.push(w);
    len += w.w.length + (cur.length > 1 ? 1 : 0);
    const next = ws[i + 1];
    if (!next || pages.length === n - 1) return;
    const sentence = /[.?!,]$/.test(w.w) && len >= target * 0.6;
    if (sentence || len + next.w.length + 1 > target * 1.15) {
      pages.push(cur);
      cur = [];
      len = 0;
    }
  });
  if (cur.length) pages.push(cur);
  return pages;
};

/**
 * How long a line stays up after its voice ends: MIN_HOLD, or longer when its
 * last page needs more time to be read (fast in, then hold).
 */
export const holdFor = (ws: PageWord[], dur: number, maxChars: number) => {
  const pages = splitPages(ws, maxChars);
  const last = pages[pages.length - 1];
  if (!last) return MIN_HOLD;
  const settledWithout = dur - LEAVE - (last[0].t + ENTER);
  return Math.max(
    MIN_HOLD,
    readSeconds(last.length) - settledWithout + HOLD_MARGIN,
  );
};

export type CaptionState = {
  line: CaptionLine;
  pages: PageWord[][];
  index: number;
  page: PageWord[];
  /** seconds since the line's start */
  lt: number;
  dur: number;
  hold: number;
};

/**
 * The caption on screen at cut time t (seconds), or null. Lines marked
 * onScreen are never captioned. When two lines' windows overlap, the later one
 * in LINES wins.
 */
export const captionAt = (
  t: number,
  lines: CaptionLine[],
  words: LineWords,
  maxChars: number,
): CaptionState | null => {
  let cur: CaptionState | null = null;
  for (const L of lines) {
    if (L.onScreen) continue;
    const W = words[L.id];
    if (!W || !W.words.length) continue;
    const hold = holdFor(W.words, W.dur, maxChars);
    if (t >= L.at - LEAD && t < L.at + W.dur + hold) {
      const lt = t - L.at;
      const pages = splitPages(W.words, maxChars);
      let index = 0;
      pages.forEach((p, i) => {
        if (lt >= p[0].t - LEAD) index = i;
      });
      cur = {
        line: L,
        pages,
        index,
        page: pages[index] ?? [],
        lt,
        dur: W.dur,
        hold,
      };
    }
  }
  return cur;
};

/** fully in and not leaving: the page's own fade in is done and the line's fade out has not begun */
export const isSettled = (c: CaptionState) =>
  c.page.length > 0 &&
  c.lt >= c.page[0].t + ENTER &&
  c.lt <= c.dur + c.hold - LEAVE;

export type PageReading = {
  cut: string;
  line: string;
  page: number;
  text: string;
  words: number;
  /** seconds the page is settled and visible */
  settled: number;
  /** seconds the reading time rule asks for */
  need: number;
  /** seconds it would be settled if nothing cut it short (its own voice and hold only) */
  natural: number;
  /** first and last settled frame, seconds on the cut's clock (-1 when never settled) */
  from: number;
  to: number;
};

/**
 * Every caption page that is on screen in `frames`, with the time it is
 * settled, sampled frame by frame the way the renderer draws it.
 * `frames` lists the frame numbers on the cut's clock that viewers see
 * (all of them for a cut; the teaser's segments for the teaser);
 * `hidden(f)` marks frames where something covers the captions.
 */
export const readPages = (
  cut: string,
  lines: CaptionLine[],
  words: LineWords,
  maxChars: number,
  fps: number,
  frames: number[],
  hidden: (f: number) => boolean = () => false,
): PageReading[] => {
  const acc = new Map<string, PageReading>();
  for (const f of frames) {
    if (hidden(f)) continue;
    const c = captionAt(f / fps, lines, words, maxChars);
    if (!c || !c.page.length) continue;
    const key = `${c.line.id}#${c.index}`;
    let r = acc.get(key);
    if (!r) {
      const next = c.pages[c.index + 1];
      const start = c.page[0].t + ENTER;
      const end = next ? next[0].t - LEAD : c.dur + c.hold - LEAVE;
      r = {
        cut,
        line: c.line.id,
        page: c.index,
        text: c.page.map((w) => w.w).join(" "),
        words: c.page.length,
        settled: 0,
        need: readSeconds(c.page.length),
        natural: Math.max(0, end - start),
        from: -1,
        to: -1,
      };
      acc.set(key, r);
    }
    if (isSettled(c)) {
      r.settled += 1 / fps;
      if (r.from < 0) r.from = f / fps;
      r.to = f / fps;
    }
  }
  return [...acc.values()];
};
