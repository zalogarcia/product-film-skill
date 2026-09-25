import React from "react";
import { AbsoluteFill } from "remotion";
import { MotionBlur, useF } from "../fx";
import { S, T, useFilm } from "../context";
import { World, Plane } from "../Camera";
import { inn, k, INOUT, LIN, out, OUT } from "../motion";
import { EV } from "../timeline";
import { C, F } from "../tokens";
import { Backdrop } from "./Stage";

type Row = { name: "plant1" | "plant2" | "plant3"; when: "plant1When" | "plant2When" | "plant3When"; amt: "plant1Amount" | "plant2Amount" | "plant3Amount" };
const ROWS: Row[] = [
  { name: "plant1", when: "plant1When", amt: "plant1Amount" },
  { name: "plant2", when: "plant2When", amt: "plant2Amount" },
  { name: "plant3", when: "plant3When", amt: "plant3Amount" },
];

const Check: React.FC<{ p: number }> = ({ p }) => (
  <svg width={46} height={46} viewBox="0 0 46 46">
    <rect x={2} y={2} width={42} height={42} rx={12} fill={p > 0 ? C.leaf : "none"} fillOpacity={p} stroke={p > 0.5 ? C.leaf : C.faint} strokeWidth={3} />
    <path d="M 12 24 L 20 32 L 35 15" fill="none" stroke={C.bg} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={40} strokeDashoffset={40 * (1 - p)} />
  </svg>
);

/** The week at a glance: the schedule card, one row ticked on the beat. */
export const ListCard: React.FC<{ w: number; f: number }> = ({ w, f }) => {
  const tick = k(f, S(EV.tick), S(EV.tick) + 9, 0, 1, OUT);
  return (
    <div
      style={{
        width: w,
        padding: "34px 36px 26px",
        borderRadius: 32,
        background: C.card,
        border: `1px solid ${C.line}`,
        boxShadow: "0 50px 110px rgba(0,0,0,0.6)",
        fontFamily: F.sans,
      }}
    >
      <div style={{ fontFamily: F.mono, fontWeight: 500, fontSize: 26, letterSpacing: "0.18em", color: C.muted, marginBottom: 18 }}>
        {T("listTitle").toUpperCase()}
      </div>
      {ROWS.map((r, i) => {
        const row = inn(f, S(EV.listIn) + 10 + i * 3, 16);
        const done = i === 0 ? tick : 0;
        return (
          <div
            key={r.name}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 22,
              padding: "20px 18px",
              marginTop: 8,
              borderRadius: 20,
              background: i === 0 ? `rgba(125,187,106,${0.1 * done})` : "transparent",
              borderTop: i === 0 ? "none" : `1px solid ${C.line}`,
              opacity: row,
              translate: `0px ${(1 - row) * 14}px`,
            }}
          >
            <Check p={done} />
            <div style={{ flex: 1, fontSize: 44, fontWeight: 680, color: C.text, letterSpacing: "-0.015em" }}>{T(r.name)}</div>
            <div style={{ fontSize: 32, fontWeight: 500, color: i === 0 ? C.leafHi : C.muted, width: 150 }}>{T(r.when)}</div>
            <div
              style={{
                fontFamily: F.mono,
                fontSize: 26,
                color: C.water,
                padding: "8px 14px",
                borderRadius: 12,
                background: "rgba(111,179,217,0.12)",
              }}
            >
              {T(r.amt)}
            </div>
          </div>
        );
      })}
    </div>
  );
};

/** 8.6 to 13.4 s: the card swings in on a tilted plane (motion blur on the fast frames) and settles. */
export const List: React.FC = () => {
  const f = useF();
  const { cut, isV, probe } = useFilm();
  const a = S(cut.acts.list.from);
  const end = S(cut.acts.list.to);
  const swing = k(f, a, a + 12, 0, 1, INOUT);
  const settle = k(f, a + 12, end, 0, 1, LIN);
  const vis = inn(f, a - 6, 8);
  const leave = out(f, end - 8, 10);
  const cam = { zoom: 1 + settle * 0.04, rx: 0 };
  return (
    <AbsoluteFill style={{ opacity: Math.min(vis, leave) }}>
      {/* every blur sample carries its own opaque backdrop, or the average smears */}
      <MotionBlur active={f >= a && f < a + 12} bg={probe ? "#000" : C.bg}>
        <Backdrop x={isV ? 50 : 70} y={isV ? 30 : 50} warm={0.08} />
        <World cam={cam} perspective={2000}>
          <Plane
            x={(isV ? 495 - 540 : 1320 - 960) + (1 - swing) * (isV ? 0 : 520)}
            y={(isV ? 590 - 960 : 0) + (1 - swing) * (isV ? 480 : 0)}
            rx={14 - swing * 8 - settle * 6}
            ry={isV ? 0 : -16 + swing * 10 + settle * 6}
            rz={isV ? -3 + settle * 3 : -2 + settle * 2}
            opacity={swing}
          >
            <ListCard w={isV ? 820 : 760} f={f} />
          </Plane>
        </World>
      </MotionBlur>
    </AbsoluteFill>
  );
};
