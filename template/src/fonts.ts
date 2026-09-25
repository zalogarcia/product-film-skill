import { cancelRender, continueRender, delayRender, staticFile } from "remotion";

/**
 * Local font loading. The files live in public/fonts and are registered
 * through the FontFace API before the first frame, so a render never depends
 * on the network or on what is installed on the rendering machine.
 *
 * A slow load makes Remotion retry the frame. The Remotion CLI counts every
 * retry again and its progress bar can crash at high resolutions, which is
 * one reason the pipeline renders through the Node API (pipeline/render.cjs).
 */
export type FontSpec = { family: string; file: string; weight: string; style?: string };

const fmt = (file: string) =>
  file.endsWith(".woff2") ? "woff2" : file.endsWith(".woff") ? "woff" : file.endsWith(".otf") ? "opentype" : "truetype";

let started = false;
export const ensureFonts = (specs: FontSpec[]): void => {
  if (started) return;
  started = true;
  if (typeof document === "undefined" || typeof (globalThis as { FontFace?: unknown }).FontFace === "undefined") return;
  const handle = delayRender("fonts", { timeoutInMilliseconds: 60000, retries: 2 });
  Promise.all(
    specs.map(({ family, file, weight, style }) =>
      new FontFace(family, `url(${staticFile(file)}) format("${fmt(file)}")`, { weight, style: style ?? "normal" })
        .load()
        .then((loaded) => {
          (document.fonts as unknown as { add(f: FontFace): void }).add(loaded);
        }),
    ),
  )
    .then(() => continueRender(handle))
    .catch((err) => cancelRender(err));
};
