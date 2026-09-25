/**
 * Design tokens for the example film. Replace with your product's own
 * colors and fonts: the film should look like the product.
 *
 * Tinted near-black and near-white instead of pure #000 and #FFF, one accent
 * family, no purple gradients, no glow on everything.
 */
export const C = {
  bg: "#0c0f0b",
  bg2: "#141a12",
  card: "#1a2117",
  cardHi: "#222b1e",
  line: "rgba(243,241,234,0.10)",
  text: "#f3f1ea",
  text2: "#c9cbbf",
  muted: "#8f9486",
  faint: "#5d6357",
  leaf: "#7dbb6a",
  leafHi: "#a6d98f",
  leafDry: "#9a8a5c",
  water: "#6fb3d9",
  pot: "#b8744f",
} as const;

export const F = {
  sans: `"Figtree", -apple-system, "Helvetica Neue", sans-serif`,
  mono: `"IBM Plex Mono", ui-monospace, Menlo, monospace`,
} as const;

/** Bundled OFL fonts (public/fonts, licenses alongside). */
export const FONT_SPECS = [
  { family: "Figtree", file: "fonts/Figtree-Variable.ttf", weight: "300 900" },
  { family: "IBM Plex Mono", file: "fonts/IBMPlexMono-Regular.ttf", weight: "400" },
  { family: "IBM Plex Mono", file: "fonts/IBMPlexMono-Medium.ttf", weight: "500" },
];
