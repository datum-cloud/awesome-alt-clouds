/**
 * Deploy profile — edit this file when switching fork preview ↔ production.
 *
 * Phase 6 cutover: set `preview: false` (and usually `blockSearchBots: false`).
 *
 * Cloud profile MDX pages:
 * - `status: reviewed` → built in all deploys (production + preview)
 * - `status: draft` → built only when `preview: true` (fork/staging)
 */
export const siteConfig = {
  /** Fork / staging on github.io — enables base path + default noindex; also publishes draft MDX profiles */
  preview: false,

  /** Block all crawlers (robots.txt + meta robots). Defaults to `preview` when omitted */
  blockSearchBots: false,

  previewSite: "https://ronggur.github.io",
  previewBase: "/awesome-alt-clouds/",

  productionSite: "https://www.alt-cloud.org",
  productionBase: undefined,

  seo: {
    title: "Awesome Alt Clouds | Alternative Cloud Providers for Developers",
    description:
      "Discover specialized cloud infrastructure providers built for developers who have specialized requirements and need alternatives to hyperscalers.",
    /** Appended to titles when `preview: true` (browser tab clarity on fork deploys) */
    previewTitleSuffix: " (Preview)",
    submit: {
      title: "Add a Cloud - Awesome Alt Clouds",
      description:
        "Submit a cloud service for evaluation against the 3 inclusion criteria. Auto-evaluated by our bot.",
    },
    blog: {
      title: "Blog | Awesome Alt Clouds",
      description:
        "Editorial notes on alternative cloud providers — trends, new entrants, and commentary from the Awesome Alt Clouds community.",
    },
  },
};
