import React, { createContext, useContext } from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { rand } from "./motion";

/**
 * Sub-frame time. Components read time through useF() instead of
 * useCurrentFrame(), so <MotionBlur> can re-render a subtree at fractional
 * frame offsets (Remotion's <Freeze> rounds to whole frames, which gives no
 * blur at all on a fast move).
 */
const Offset = createContext(0);
export const useF = () => useCurrentFrame() + useContext(Offset);

/**
 * Motion blur by temporal supersampling: the children render `samples` times
 * at sub-frame offsets across the shutter and are averaged (layer i gets
 * opacity 1/(i+1), which makes the stack an equal weight average). It costs
 * `samples` times the render work while `active`, so switch it on only for
 * the frames of a fast move.
 */
export const MotionBlur: React.FC<{
  active: boolean;
  samples?: number;
  shutter?: number;
  /** opaque backdrop inside every sample: averaging only works when each layer fully covers the one below */
  bg?: string;
  children: React.ReactNode;
}> = ({ active, samples = 6, shutter = 0.5, bg = "transparent", children }) => {
  const base = useContext(Offset);
  if (!active) return <AbsoluteFill>{children}</AbsoluteFill>;
  const layers = [];
  for (let i = 0; i < samples; i++) {
    const off = base - shutter * (1 - i / (samples - 1));
    layers.push(
      <AbsoluteFill key={i} style={{ opacity: 1 / (i + 1), background: bg }}>
        <Offset.Provider value={off}>{children}</Offset.Provider>
      </AbsoluteFill>,
    );
  }
  return <AbsoluteFill>{layers}</AbsoluteFill>;
};

/** Animated film grain (SVG turbulence, reseeded every frame). */
export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.05 }) => {
  const frame = useCurrentFrame();
  const seed = Math.floor(rand(frame) * 1000);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity, mixBlendMode: "overlay" }}>
      <svg width="100%" height="100%">
        <filter id={`grain${seed}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves={2} seed={seed} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter={`url(#grain${seed})`} />
      </svg>
    </AbsoluteFill>
  );
};

/** Edge vignette. */
export const Vignette: React.FC<{ strength?: number }> = ({ strength = 0.5 }) => (
  <AbsoluteFill
    style={{
      pointerEvents: "none",
      background: `radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0) 45%, rgba(0,0,0,${strength}) 100%)`,
    }}
  />
);
