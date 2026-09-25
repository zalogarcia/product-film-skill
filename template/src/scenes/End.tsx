import React from "react";
import { AbsoluteFill } from "remotion";
import { useF } from "../fx";
import { S, T, useFilm } from "../context";
import { inn, k, LIN, OUT } from "../motion";
import { EV } from "../timeline";
import { C, F } from "../tokens";
import { Backdrop } from "./Stage";
import { LeafMark } from "../ui/Plant";

/** The end card: name on the hit, the tagline, one destination, then a quiet hold. */
export const End: React.FC = () => {
  const f = useF();
  const { cut, isV } = useFilm();
  const a = S(EV.endHit);
  const name = inn(f, a, 16, OUT);
  const tag = inn(f, a + 10, 16);
  const url = inn(f, a + 30, 16);
  const legal = inn(f, a + 36, 16);
  const drift = k(f, a, S(cut.dur), 1, 1.03, LIN);
  // the vertical fades its end card out just before the loop hold, so frame 0 follows cleanly
  const fade = cut.acts.loop ? 1 - k(f, S(cut.acts.loop.from) - 8, S(cut.acts.loop.from), 0, 1, LIN) : 1 - k(f, S(cut.dur) - 24, S(cut.dur), 0, 1, LIN);
  return (
    <AbsoluteFill style={{ opacity: fade }}>
      <Backdrop x={50} y={isV ? 40 : 45} warm={0.12} />
      <AbsoluteFill style={{ scale: `${drift}`, alignItems: "center", justifyContent: "center" }}>
        <div
          style={{
            position: "absolute",
            left: isV ? 95 : 0,
            width: isV ? 800 : 1920,
            top: isV ? 610 : 330,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: isV ? 26 : 32, opacity: name, translate: `0px ${(1 - name) * 18}px` }}>
            <LeafMark size={isV ? 104 : 118} />
            <div style={{ fontFamily: F.sans, fontWeight: 760, fontSize: isV ? 132 : 150, letterSpacing: "-0.04em", color: C.text }}>
              {T("appName")}
            </div>
          </div>
          <div style={{ fontFamily: F.sans, fontWeight: 500, fontSize: isV ? 64 : 68, color: C.text2, marginTop: 26, opacity: tag, letterSpacing: "-0.01em" }}>
            {T("tagline")}
          </div>
          <div style={{ fontFamily: F.mono, fontSize: isV ? 32 : 30, letterSpacing: "0.08em", color: C.leafHi, marginTop: 40, opacity: url }}>
            {T("url")}
          </div>
        </div>
        <div
          style={{
            position: "absolute",
            left: isV ? 95 : 0,
            width: isV ? 800 : 1920,
            top: isV ? 1440 : 960,
            textAlign: "center",
            fontFamily: F.mono,
            fontSize: isV ? 22 : 20,
            letterSpacing: "0.06em",
            color: C.faint,
            opacity: legal,
          }}
        >
          {T("disclaimer")}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
