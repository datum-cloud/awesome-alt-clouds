import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";
import tailwindcss from "@tailwindcss/vite";
import { siteConfig } from "./site.config.mjs";
import { legacyCategoryRedirects } from "./src/lib/legacy-redirects.ts";
import { sitemapChunks } from "./src/lib/sitemap-chunks.ts";

const preview = siteConfig.preview;
const blockSearchBots = siteConfig.blockSearchBots ?? preview;
const base = preview ? siteConfig.previewBase : siteConfig.productionBase;

// Astro does not prepend `base` to redirect destinations, so do it here (no-op in production).
const withBase = (path) => (base ? `${base.replace(/\/$/, "")}${path}` : path);
const redirects = Object.fromEntries(
  Object.entries(legacyCategoryRedirects).map(([from, to]) => [from, withBase(to)])
);

// https://docs.astro.build/en/guides/deploy/github/
export default defineConfig({
  site: preview ? siteConfig.previewSite : siteConfig.productionSite,
  base,
  trailingSlash: "ignore",
  redirects,
  integrations: [mdx(), sitemap({ chunks: sitemapChunks })],
  build: {
    format: "directory",
  },
  vite: {
    plugins: [tailwindcss()],
    define: {
      __SITE_PREVIEW__: JSON.stringify(preview),
      __SITE_BLOCK_BOTS__: JSON.stringify(blockSearchBots),
    },
  },
});
