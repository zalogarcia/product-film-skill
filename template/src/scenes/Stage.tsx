import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { S, useFilm } from "../context";
import { Seg } from "../timeline";
import { C } from "../tokens";
import { Decor } from "../ui/Decor";

/**
 * An act: its children render only while the absolute frame is inside the
 * act (plus `pad` frames of overlap for a crossfade). Scenes read ABSOLUTE
 * time through useF(), so a <Freeze frame={0}> around a scene holds the
 * exact first frame (the vertical's loop).
 */
export const Act: React.FC<{ seg: Seg; pad?: number; children: React.ReactNode }> = ({ seg, pad = 8, children }) => {
  const f = useCurrentFrame();
  if (f < S(seg.from) - pad || f >= S(seg.to) + pad) return null;
  return <AbsoluteFill>{children}</AbsoluteFill>;
};

/** The film's background: tinted near-black with one soft pool of light. Decoration, hidden in the probe render. */
export const Backdrop: React.FC<{ x?: number; y?: number; warm?: number }> = ({ x = 30, y = 45, warm = 0.1 }) => {
  const { probe } = useFilm();
  if (probe) return <AbsoluteFill style={{ background: "#000" }} />;
  return (
    <Decor>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at ${x}% ${y}%, rgba(125,187,106,${warm}) 0%, transparent 55%), radial-gradient(ellipse at 50% 40%, ${C.bg2} 0%, ${C.bg} 75%)`,
        }}
      />
    </Decor>
  );
};
