/** Pixel-art icons from the Figma blog frame (node 1:3561), keyed by name. */
export const PIXEL_ICONS = ["question", "peace", "pumpkin", "frog", "computer"] as const;
export type PixelIconName = (typeof PIXEL_ICONS)[number];

/** Stable fallback so a post without `icon:` still gets the same icon every build. */
export function iconForSlug(slug: string): PixelIconName {
  let h = 0;
  for (const ch of slug) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return PIXEL_ICONS[h % PIXEL_ICONS.length];
}
