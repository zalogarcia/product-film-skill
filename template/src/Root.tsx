import React from "react";
import { CalculateMetadataFunction, Composition, staticFile } from "remotion";
import { Film } from "./Film";
import { FilmProps, WordsData } from "./context";
import { ensureFonts } from "./fonts";
import { CUTS, FPS } from "./timeline";
import { FONT_SPECS } from "./tokens";

ensureFonts(FONT_SPECS);

/**
 * Load the measured data the pipeline wrote into public/generated before the
 * first frame: word timings (required, from `npm run words`) and the list of
 * stills (optional, from `npm run stills`).
 */
const withData: CalculateMetadataFunction<FilmProps> = async ({ props }) => {
  const res = await fetch(staticFile("generated/words.json"));
  if (!res.ok) {
    throw new Error("public/generated/words.json is missing: run `npm run voice` and `npm run words` first (or `npm run example`).");
  }
  const words = (await res.json()) as WordsData;
  let stills: string[] = [];
  try {
    const s = await fetch(staticFile("generated/stills.json"));
    if (s.ok) stills = (await s.json()) as string[];
  } catch {
    stills = [];
  }
  return { props: { ...props, words, stills } };
};

export const Root: React.FC = () => (
  <>
    {Object.values(CUTS).map((c) => (
      <Composition
        key={c.id}
        id={c.comp}
        component={Film}
        defaultProps={{ cut: c.id } as FilmProps}
        calculateMetadata={withData}
        durationInFrames={Math.round(c.dur * FPS)}
        fps={FPS}
        width={c.w}
        height={c.h}
      />
    ))}
  </>
);
