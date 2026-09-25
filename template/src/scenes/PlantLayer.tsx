import React from "react";
import { interpolate } from "remotion";
import { useF } from "../fx";
import { S, useFilm } from "../context";
import { INOUT, k, OUT } from "../motion";
import { EV, FPS } from "../timeline";
import { Plant } from "../ui/Plant";

/**
 * The plant lives on its own layer above the acts, so it stays continuous
 * across scene changes: position, size and thirst are keyframed on the
 * absolute clock, per cut (the vertical is a recomposition, not a crop).
 */
type Key = [number, number, number, number]; // seconds, centre x, centre y, width
const KEYS: Record<"master" | "vertical", Key[]> = {
  master: [
    [0, 560, 480, 560],
    [4.3, 560, 480, 560],
    [8.6, 520, 520, 540],
    [13.2, 520, 520, 540],
  ],
  vertical: [
    [0, 495, 700, 400],
    [4.3, 495, 700, 400],
    [5.0, 495, 870, 330],
    [8.6, 495, 870, 330],
    [9.2, 495, 1085, 270],
    [13.2, 495, 1085, 270],
  ],
};

export const PlantLayer: React.FC = () => {
  const f = useF();
  const { cut, isV } = useFilm();
  const keys = KEYS[isV ? "vertical" : "master"];
  const t = f / FPS;
  const times = keys.map((q) => q[0]);
  const at = (i: 1 | 2 | 3) =>
    interpolate(
      t,
      times,
      keys.map((q) => q[i]),
      { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: INOUT },
    );
  const w = at(3);
  // thirsty until the tick, then it drinks
  const droop = 1 - k(f, S(EV.tick), S(EV.tick + 1.4), 0, 1, OUT);
  const gone = k(f, S(cut.acts.end.from) - 6, S(cut.acts.end.from) + 8, 1, 0, OUT);
  const enter = k(f, 0, 10, 0.96, 1, OUT);
  if (gone <= 0) return null;
  return (
    <div
      style={{
        position: "absolute",
        left: at(1) - w / 2,
        top: at(2) - (w * 1.25) / 2,
        opacity: gone,
        scale: `${enter}`,
      }}
    >
      <Plant droop={droop} size={w} />
    </div>
  );
};
