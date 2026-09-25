import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { useFilm } from "../context";

/**
 * Wrap anything that is decoration, not information (a background glow, a
 * plate, a shape bleeding off frame). The safe-zone probe render hides it, so
 * `npm run check:safe` only judges content a viewer has to read or see.
 * Anything NOT inside <Decor> must sit inside the safe zone.
 */
export const Decor: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { probe } = useFilm();
  return probe ? null : <>{children}</>;
};

/** A photographic plate from public/stills (made by `npm run stills`), defocused and dimmed. */
export const Plate: React.FC<{ name: string; blur?: number; bright?: number; scale?: number }> = ({
  name,
  blur = 10,
  bright = 0.45,
  scale = 1.08,
}) => {
  const { stills } = useFilm();
  if (!stills.includes(name)) return null;
  return (
    <Decor>
      <AbsoluteFill style={{ overflow: "hidden" }}>
        <Img
          src={staticFile(`stills/${name}.png`)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: `blur(${blur}px) brightness(${bright})`,
            scale: `${scale}`,
          }}
        />
      </AbsoluteFill>
    </Decor>
  );
};
