import eslint from "@eslint/js";
import eslintConfigPrettier from "eslint-config-prettier";
import eslintPluginAstro from "eslint-plugin-astro";
import tseslint from "typescript-eslint";

export default [
  {
    ignores: [
      "dist/**",
      "node_modules/**",
      ".astro/**",
      "docs/**",
      "public/clouds.json",
      "package-lock.json",
    ],
  },
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  ...eslintPluginAstro.configs.recommended,
  eslintConfigPrettier,
  {
    files: ["**/*.astro"],
    rules: {
      // Inline scripts in .astro pages are intentional (filter UI, submit form).
      "astro/no-unused-define-vars-in-style": "off",
    },
  },
];
