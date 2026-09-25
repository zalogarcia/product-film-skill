import React from "react";
import { AbsoluteFill, Freeze } from "remotion";
import { FilmProps, FilmProvider, S, useFilm } from "./context";
import { Grain, Vignette } from "./fx";
import { C } from "./tokens";
import { Act } from "./scenes/Stage";
import { Hook } from "./scenes/Hook";
import { Nudge } from "./scenes/Nudge";
import { List } from "./scenes/List";
import { End } from "./scenes/End";
import { PlantLayer } from "./scenes/PlantLayer";
import { Captions } from "./ui/Captions";

/**
 * One component renders every cut. Each act reads its timing from the
 * timeline and its layout from the cut (useFilm().isV), so the vertical is a
 * recomposition, not a crop of the master.
 */
const Body: React.FC = () => {
  const { cut, probe } = useFilm();
  const a = cut.acts;
  return (
    <AbsoluteFill style={{ background: probe ? "#000" : C.bg }}>
      <Act seg={a.hook}>
        <Hook />
      </Act>
      <Act seg={a.nudge}>
        <Nudge />
      </Act>
      <Act seg={a.list}>
        <List />
      </Act>
      <Act seg={a.end} pad={0}>
        <End />
      </Act>
      <PlantLayer />
      <Captions />
      {a.loop && (
        <Act seg={a.loop} pad={0}>
          {/* hold the exact first frame so the platform's loop back to frame 0 is seamless */}
          <Freeze frame={0}>
            <AbsoluteFill style={{ background: probe ? "#000" : C.bg }}>
              <Hook />
              <PlantLayer />
            </AbsoluteFill>
          </Freeze>
        </Act>
      )}
      {!probe && <Grain opacity={0.05} />}
      {!probe && <Vignette strength={0.45} />}
    </AbsoluteFill>
  );
};

export const Film: React.FC<FilmProps> = (p) => (
  <FilmProvider p={p}>
    <Body />
  </FilmProvider>
);

