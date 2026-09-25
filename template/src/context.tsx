import React, { createContext, useContext } from "react";
import { COPY, CUTS, CutId, CutSpec, FPS, MASTER } from "./timeline";

/** Word timings measured by `npm run words` (public/generated/words.json). */
export type Word = { w: string; t: number; e: number };
export type WordsData = {
  backend: string;
  lines: Record<string, { dur: number; method: string; words: Word[] }>;
};

export type FilmProps = {
  cut: CutId;
  /** safe-zone probe render: no background, grain, vignette, plates or <Decor> */
  probe?: boolean;
  words?: WordsData;
  /** stills that exist in public/stills (listed by `npm run stills`) */
  stills?: string[];
};

type Ctx = { cut: CutSpec; isV: boolean; probe: boolean; words: WordsData; stills: string[] };
const FilmCtx = createContext<Ctx>({ cut: MASTER, isV: false, probe: false, words: { backend: "none", lines: {} }, stills: [] });

export const FilmProvider: React.FC<{ p: FilmProps; children: React.ReactNode }> = ({ p, children }) => {
  const cut = CUTS[p.cut];
  return (
    <FilmCtx.Provider
      value={{ cut, isV: cut.id === "vertical", probe: !!p.probe, words: p.words ?? { backend: "none", lines: {} }, stills: p.stills ?? [] }}
    >
      {children}
    </FilmCtx.Provider>
  );
};

export const useFilm = () => useContext(FilmCtx);

/** Seconds to frames. */
export const S = (sec: number) => Math.round(sec * FPS);

/** A visible string from the timeline's COPY table (the only place on-screen text lives). */
export const T = (id: keyof typeof COPY) => COPY[id].text;
