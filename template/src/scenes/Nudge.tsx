import React from "react";
import { AbsoluteFill } from "remotion";
import { useF } from "../fx";
import { S, T, useFilm } from "../context";
import { World, Plane } from "../Camera";
import { inn, k, LIN, out, OUT } from "../motion";
import { EV } from "../timeline";
import { C, F } from "../tokens";
import { Backdrop } from "./Stage";
import { LeafMark } from "../ui/Plant";

/** The notification card. Plain words, the app's own layout, no chrome. */
export const NudgeCard: React.FC<{ w: number }> = ({ w }) => (
  <div
    style={{
      width: w,
      padding: "30px 34px 34px",
      borderRadius: 30,
      background: C.card,
      border: `1px solid ${C.line}`,
      boxShadow: "0 40px 90px rgba(0,0,0,0.55)",
      fontFamily: F.sans,
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
      <LeafMark size={52} />
      <div style={{ fontFamily: F.mono, fontWeight: 500, fontSize: 24, letterSpacing: "0.16em", color: C.muted, flex: 1 }}>
        {T("appName").toUpperCase()}
      </div>
      <div style={{ fontFamily: F.mono, fontSize: 24, color: C.faint }}>{T("nudgeWhen")}</div>
    </div>
    <div style={{ fontSize: 54, fontWeight: 720, letterSpacing: "-0.02em", color: C.text, marginTop: 22 }}>{T("nudgeTitle")}</div>
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 10 }}>
      <svg width={26} height={34} viewBox="0 0 26 34">
        <path d="M13 2 C 13 2 2 16 2 22 A 11 11 0 0 0 24 22 C 24 16 13 2 13 2 Z" fill={C.water} />
      </svg>
      <div style={{ fontSize: 36, fontWeight: 500, color: C.text2 }}>{T("nudgeBody")}</div>
    </div>
  </div>
);

/** 4.3 to 8.6 s: the product arrives as the thing the viewer would see, a notification. */
export const Nudge: React.FC = () => {
  const f = useF();
  const { cut, isV } = useFilm();
  const a = S(cut.acts.nudge.from);
  const end = S(cut.acts.nudge.to);
  const land = inn(f, S(EV.nudgeLands), 20, OUT);
  const push = k(f, S(EV.nudgeLands) + 10, end, 1, 1.05, LIN);
  const leave = out(f, end - 8, 10);
  const vis = inn(f, a - 8, 10);
  return (
    <AbsoluteFill style={{ opacity: Math.min(vis, leave) }}>
      <Backdrop x={isV ? 50 : 70} y={isV ? 22 : 50} warm={0.08} />
      <World cam={{ zoom: push }} perspective={1800}>
        <Plane
          x={isV ? 495 - 540 : 1330 - 960}
          y={(isV ? 430 - 960 : 540 - 540) + (1 - land) * -70}
          rx={(1 - land) * 24}
          opacity={land}
        >
          <NudgeCard w={isV ? 800 : 700} />
        </Plane>
      </World>
    </AbsoluteFill>
  );
};
