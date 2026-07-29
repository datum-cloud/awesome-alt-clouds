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
    title: "Alternative Cloud Providers Directory - 470+ Options | Neo Cloud Comparison Tool",
    description:
      "Compare 470+ specialized cloud, GPU, and infrastructure providers across pricing, regions, and uptime.",
    /** Short brand suffix for templated per-page titles (cloud detail, category, compare) — kept separate from `title` above so those don't inherit the long homepage-specific title. */
    siteName: "Neo Cloud Comparison Tool",
    /** Appended to titles when `preview: true` (browser tab clarity on fork deploys) */
    previewTitleSuffix: " (Preview)",
    submit: {
      title: "Submit your cloud provider for listing | Neo Cloud Comparison Tool",
      description:
        "List your alternative cloud service, auto-evaluated against 3 core criteria: public pricing, self-serve signup, transparent uptime",
    },
    blog: {
      title: "Blog | Awesome Alt Clouds",
      description:
        "Editorial notes on alternative cloud providers — trends, new entrants, and commentary from the Awesome Alt Clouds community.",
    },
  },
};
