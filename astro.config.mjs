import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import tailwindcss from "@tailwindcss/vite";
import { siteConfig } from "./site.config.mjs";

const preview = siteConfig.preview;
const blockSearchBots = siteConfig.blockSearchBots ?? preview;

// https://docs.astro.build/en/guides/deploy/github/
export default defineConfig({
  site: preview ? siteConfig.previewSite : siteConfig.productionSite,
  base: preview ? siteConfig.previewBase : siteConfig.productionBase,
  trailingSlash: "ignore",
  integrations: [mdx()],
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
