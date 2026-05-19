import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

// https://astro.build/config
export default defineConfig({
  site: "https://www.alt-cloud.org",
  trailingSlash: "ignore",
  build: {
    format: "directory",
  },
  vite: {
    plugins: [tailwindcss()],
  },
});
