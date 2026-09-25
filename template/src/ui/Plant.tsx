import React from "react";
import { interpolateColors } from "remotion";
import { useF } from "../fx";
import { C } from "../tokens";

/**
 * The example's hero object: a potted fern drawn in SVG. `droop` 1 is
 * thirsty (fronds hang, colour dries out), 0 is healthy. Everything is
 * vector, so it stays sharp at any camera zoom and at 4K.
 */
const FRONDS = [-64, -42, -22, -6, 10, 28, 48, 68];

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export const Plant: React.FC<{ droop: number; size: number }> = ({ droop, size }) => {
  const f = useF();
  const d = Math.max(0, Math.min(1, droop));
  const color = interpolateColors(d, [0, 1], [C.leaf, C.leafDry]);
  const colorHi = interpolateColors(d, [0, 1], [C.leafHi, C.leafDry]);
  const base = { x: 200, y: 330 };
  return (
    <svg width={size} height={size * 1.25} viewBox="0 0 400 500" style={{ overflow: "visible" }}>
      {FRONDS.map((deg, i) => {
        const sway = Math.sin(f / 26 + i * 1.3) * (1.5 + d * 1.2);
        const side = Math.sign(deg) || 1;
        const theta = ((deg * (1 + 0.45 * d) + side * d * 24 + sway) * Math.PI) / 180;
        const L = 205 + (i % 3) * 22;
        const tip = { x: base.x + Math.sin(theta) * L, y: base.y - Math.cos(theta) * L + d * L * 0.35 };
        const ctl = {
          x: base.x + Math.sin(theta * 0.55) * L * 0.55,
          y: base.y - Math.cos(theta * 0.55) * L * 0.62,
        };
        const at = (t: number) => ({
          x: (1 - t) * (1 - t) * base.x + 2 * (1 - t) * t * ctl.x + t * t * tip.x,
          y: (1 - t) * (1 - t) * base.y + 2 * (1 - t) * t * ctl.y + t * t * tip.y,
        });
        const tan = (t: number) => {
          const dx = 2 * (1 - t) * (ctl.x - base.x) + 2 * t * (tip.x - ctl.x);
          const dy = 2 * (1 - t) * (ctl.y - base.y) + 2 * t * (tip.y - ctl.y);
          return (Math.atan2(dy, dx) * 180) / Math.PI;
        };
        const leaflets = [];
        for (let n = 0; n < 11; n++) {
          const t = lerp(0.22, 0.96, n / 10);
          const p = at(t);
          const a = tan(t);
          const len = lerp(34, 12, n / 10) * (1 - 0.25 * d);
          for (const s of [-1, 1]) {
            const ang = a + s * lerp(58, 78, d);
            leaflets.push(
              <ellipse
                key={`${n}${s}`}
                cx={p.x + Math.cos((ang * Math.PI) / 180) * len * 0.5}
                cy={p.y + Math.sin((ang * Math.PI) / 180) * len * 0.5}
                rx={len * 0.5}
                ry={len * 0.17}
                transform={`rotate(${ang} ${p.x + Math.cos((ang * Math.PI) / 180) * len * 0.5} ${p.y + Math.sin((ang * Math.PI) / 180) * len * 0.5})`}
                fill={n % 2 ? color : colorHi}
              />,
            );
          }
        }
        return (
          <g key={i}>
            <path d={`M ${base.x} ${base.y} Q ${ctl.x} ${ctl.y} ${tip.x} ${tip.y}`} stroke={color} strokeWidth={4} fill="none" strokeLinecap="round" />
            {leaflets}
          </g>
        );
      })}
      {/* pot */}
      <path d="M 128 336 L 272 336 L 254 470 Q 252 480 242 480 L 158 480 Q 148 480 146 470 Z" fill={C.pot} />
      <rect x={118} y={322} width={164} height={30} rx={6} fill="#c98763" />
      <path d="M 140 360 L 262 360" stroke="rgba(0,0,0,0.18)" strokeWidth={3} />
    </svg>
  );
};

/** The app's mark: a single leaf in a rounded square. */
export const LeafMark: React.FC<{ size: number }> = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 100 100">
    <rect width={100} height={100} rx={24} fill={C.leaf} />
    <path d="M 28 72 C 30 42 48 26 76 24 C 74 52 58 70 28 72 Z" fill={C.bg} />
    <path d="M 30 70 L 64 36" stroke={C.leaf} strokeWidth={4} strokeLinecap="round" />
  </svg>
);
