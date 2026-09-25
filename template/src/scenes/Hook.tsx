import React from "react";
import { AbsoluteFill } from "remotion";
import { useF } from "../fx";
import { S, T, useFilm } from "../context";
import { inn, k, LIN, out, OUT, typed } from "../motion";
import { C, F } from "../tokens";
import { Backdrop } from "./Stage";
import { Plate } from "../ui/Decor";

/** 0 to 4.3 s: the problem, stated by the object itself. Frame 0 already shows the thirsty plant. */
export const Hook: React.FC = () => {
  const f = useF();
  const { cut, isV } = useFilm();
  const end = S(cut.acts.hook.to);
  const label = typed(f, 8, T("lastLabel").toUpperCase(), 26);
  const day = inn(f, 22, 20);
  const leave = out(f, end - 10, 12);
  const drift = k(f, 0, end, 1, 1.035, LIN);
  return (
    <AbsoluteFill>
      <Backdrop x={isV ? 50 : 30} y={isV ? 36 : 50} />
      <Plate name="windowsill" />
      <AbsoluteFill style={{ scale: `${drift}`, opacity: leave }}>
        <div
          style={{
            position: "absolute",
            left: isV ? 95 : 1010,
            width: isV ? 800 : 800,
            top: isV ? 1020 : 420,
            textAlign: isV ? "center" : "left",
          }}
        >
          <div style={{ fontFamily: F.mono, fontWeight: 500, fontSize: isV ? 32 : 30, letterSpacing: "0.18em", color: C.muted, height: 44 }}>
            {label}
          </div>
          <div
            style={{
              fontFamily: F.sans,
              fontWeight: 750,
              fontSize: isV ? 150 : 160,
              letterSpacing: "-0.035em",
              lineHeight: 1,
              color: C.text,
              marginTop: 12,
              opacity: day,
              translate: `0px ${(1 - day) * 22}px`,
              filter: `blur(${(1 - k(f, 22, 34, 0, 1, OUT)) * 6}px)`,
            }}
          >
            {T("lastDay")}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
