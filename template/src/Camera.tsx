import React from "react";
import { AbsoluteFill } from "remotion";

/**
 * UI in space. A <World> is a perspective stage with a camera pose; a <Plane>
 * places a flat surface at a 3D position. Depth of field blur comes from each
 * plane's distance to the camera's focus plane, so a pull focus is just an
 * animated `focus`. Never show UI flat and full screen for long: tilt it,
 * crop it, move the camera.
 *
 * Coordinates: x right, y down, z toward the viewer (px). Rotations in deg.
 */
export type Pose = { x?: number; y?: number; z?: number; rx?: number; ry?: number; rz?: number; zoom?: number };

const DofCtx = React.createContext<{ focus: number; dof: number }>({ focus: 0, dof: 0 });

export const World: React.FC<{
  cam: Pose;
  perspective?: number;
  focus?: number;
  dof?: number;
  children: React.ReactNode;
}> = ({ cam, perspective = 2000, focus = 0, dof = 0, children }) => {
  const { x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, zoom = 1 } = cam;
  return (
    <AbsoluteFill style={{ perspective, perspectiveOrigin: "50% 50%", overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          transformStyle: "preserve-3d",
          transform: `scale(${zoom}) rotateZ(${-rz}deg) rotateX(${-rx}deg) rotateY(${-ry}deg) translate3d(${-x}px, ${-y}px, ${z}px)`,
        }}
      >
        <DofCtx.Provider value={{ focus, dof }}>{children}</DofCtx.Provider>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/** A flat surface centred on (x, y, z). */
export const Plane: React.FC<{
  x?: number;
  y?: number;
  z?: number;
  rx?: number;
  ry?: number;
  rz?: number;
  scale?: number;
  opacity?: number;
  children: React.ReactNode;
}> = ({ x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, scale = 1, opacity = 1, children }) => {
  const { focus, dof } = React.useContext(DofCtx);
  const blur = (Math.abs(z - focus) / 1000) * dof;
  return (
    <div
      style={{
        position: "absolute",
        left: "50%",
        top: "50%",
        transformStyle: "preserve-3d",
        transform: `translate3d(${x}px, ${y}px, ${z}px) rotateX(${rx}deg) rotateY(${ry}deg) rotateZ(${rz}deg) scale(${scale})`,
        opacity,
      }}
    >
      <div style={{ transform: "translate(-50%, -50%)", filter: blur > 0.3 ? `blur(${blur.toFixed(2)}px)` : undefined }}>
        {children}
      </div>
    </div>
  );
};
