import React from "react";
import { useF } from "../fx";
import { useFilm } from "../context";
import { k, OUT } from "../motion";
import { C, F } from "../tokens";
import { FPS, LINES } from "../timeline";
import { captionAt, captionLayout, ENTER, LEAVE } from "../captionPages";

/**
 * Burned-in karaoke captions for every spoken line (sound-off viewing): one
 * page of at most two lines at a time, the word being spoken lit. Timing comes
 * from whisper (public/generated/words.json), so a caption never lights a
 * word before it is heard. Lines marked `onScreen` in the timeline are
 * skipped because their words are already on screen as type.
 *
 * Paging, the hold after a line and the reading time rule live in
 * src/captionPages.ts, which `npm run check:captions` measures frame by frame.
 */
export const Captions: React.FC = () => {
  const f = useF();
  const { isV, words } = useFilm();
  const { size, width, maxChars } = captionLayout(isV);
  const c = captionAt(f / FPS, LINES, words.lines, maxChars);
  if (!c || !c.page.length) return null;
  const { page, lt, dur, hold } = c;
  const enter = k(lt - page[0].t, -0.1, ENTER, 0, 1, OUT);
  const leave = k(lt, dur + hold - LEAVE, dur + hold, 1, 0, OUT);
  return (
    <div
      style={{
        position: "absolute",
        left: isV ? 95 : (1920 - width) / 2,
        width,
        // vertical: inside the safe box (y 250 to 1520), clear of the caption bar; master: lower third
        top: isV ? 1300 : undefined,
        bottom: isV ? undefined : 96,
        textAlign: "center",
        fontFamily: F.sans,
        fontWeight: 650,
        fontSize: size,
        lineHeight: 1.18,
        letterSpacing: "-0.01em",
        color: C.text,
        textShadow: "0 2px 18px rgba(0,0,0,0.65)",
        opacity: Math.min(enter, leave),
        translate: `0px ${(1 - enter) * 10}px`,
        ...({ textWrap: "balance" } as React.CSSProperties),
      }}
    >
      {page.map((w, i) => {
        const heard = lt >= w.t - 0.03;
        const speaking = heard && lt < w.e + 0.06;
        return (
          <span key={i} style={{ opacity: heard ? 1 : 0.32, color: speaking ? C.leafHi : undefined }}>
            {w.w}{" "}
          </span>
        );
      })}
    </div>
  );
};
