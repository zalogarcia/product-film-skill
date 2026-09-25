import React from "react";
import { useF } from "../fx";
import { useFilm } from "../context";
import { k, OUT } from "../motion";
import { C, F } from "../tokens";
import { FPS, LINES, Line } from "../timeline";
import type { Word } from "../context";

/**
 * Burned-in karaoke captions for every spoken line (sound-off viewing): one
 * page of at most two lines at a time, the word being spoken lit. Timing comes
 * from whisper (public/generated/words.json), so a caption never lights a
 * word before it is heard. Lines marked `onScreen` in the timeline are
 * skipped because their words are already on screen as type.
 */
const HOLD = 0.35; // seconds a finished line stays up

const lineAt = (t: number, lines: Line[], dur: (id: string) => number) => {
  let cur: Line | null = null;
  for (const L of lines) {
    if (t >= L.at - 0.05 && t < L.at + dur(L.id) + HOLD) cur = L;
  }
  return cur;
};

/**
 * Split words into caption pages and return the page being spoken. The page
 * count comes from the line length, then every page aims at an equal share,
 * so a line never ends on a lonely one word page; a sentence end near the
 * target is preferred as the break.
 */
const pageOf = (ws: Word[], lt: number, maxChars: number): Word[] => {
  const total = ws.reduce((a, w) => a + w.w.length + 1, -1);
  const n = Math.max(1, Math.ceil(total / maxChars));
  const target = total / n;
  const pages: Word[][] = [];
  let cur: Word[] = [];
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
  let idx = 0;
  pages.forEach((p, i) => {
    if (lt >= p[0].t - 0.05) idx = i;
  });
  return pages[idx] ?? [];
};

export const Captions: React.FC = () => {
  const f = useF();
  const { isV, words } = useFilm();
  const t = f / FPS;
  const dur = (id: string) => words.lines[id]?.dur ?? 0;
  const L = lineAt(
    t,
    LINES.filter((l) => !l.onScreen),
    dur,
  );
  if (!L) return null;
  const ws = words.lines[L.id]?.words ?? [];
  if (!ws.length) return null;
  const lt = t - L.at;
  const size = isV ? 66 : 46;
  const width = isV ? 800 : 1300;
  const page = pageOf(ws, lt, Math.floor((width / (size * 0.5)) * 2));
  const enter = k(lt - (page[0]?.t ?? 0), -0.1, 0.18, 0, 1, OUT);
  const leave = k(lt, dur(L.id) + HOLD - 0.15, dur(L.id) + HOLD, 1, 0, OUT);
  return (
    <div
      style={{
        position: "absolute",
        left: isV ? 95 : (1920 - width) / 2,
        width,
        // vertical: inside the safe box (y 250 to 1520), clear of the caption bar; master: lower third
        top: isV ? 1300 : undefined,
        bottom: isV ? undefined : 96,
        textAlign: "center",
        fontFamily: F.sans,
        fontWeight: 650,
        fontSize: size,
        lineHeight: 1.18,
        letterSpacing: "-0.01em",
        color: C.text,
        textShadow: "0 2px 18px rgba(0,0,0,0.65)",
        opacity: Math.min(enter, leave),
        translate: `0px ${(1 - enter) * 10}px`,
        ...({ textWrap: "balance" } as React.CSSProperties),
      }}
    >
      {page.map((w, i) => {
        const heard = lt >= w.t - 0.03;
        const speaking = heard && lt < w.e + 0.06;
        return (
          <span key={i} style={{ opacity: heard ? 1 : 0.32, color: speaking ? C.leafHi : undefined }}>
            {w.w}{" "}
          </span>
        );
      })}
    </div>
  );
};
