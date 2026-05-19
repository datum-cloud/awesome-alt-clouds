/**
 * Deploy profile — edit this file when switching fork preview ↔ production.
 *
 * Phase 6 cutover: set `preview: false` (and usually `blockSearchBots: false`).
 */
export const siteConfig = {
  /** Fork / staging on github.io — enables base path + default noindex */
  preview: true,

  /** Block all crawlers (robots.txt + meta robots). Defaults to `preview` when omitted */
  blockSearchBots: true,

  previewSite: "https://ronggur.github.io",
  previewBase: "/awesome-alt-clouds",

  productionSite: "https://www.alt-cloud.org",
  productionBase: undefined,
};
