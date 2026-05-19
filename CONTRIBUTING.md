# Contributing to Awesome Alt Clouds

Thanks for your interest in contributing! There are now three different things you can contribute to, each with a different workflow.

## 1. Adding or editing a cloud listing

`README.md` is the **single source of truth** for every entry in the directory. The website, `clouds.json`, `llms.txt`, and (later) per-cloud profile pages are all derived from it on every merge to `main`.

The easiest way to add a service is to use the submission form at <https://www.alt-cloud.org/submit/> — our bot will evaluate the URL and open a PR for you automatically.

If you'd rather open the PR yourself:

1. Fork the repository.
2. Create a new branch.
3. Edit `README.md` only — entries are alphabetized within each category and must follow this exact shape:

   ```
   * 🟢 [Service Name](https://example.com/) - Short description starting with a verb.
   ```

   - Bullet is `*` (not `-`).
   - Badge `🟢` (3/3 criteria) or `🟡` (2/3 criteria) is required.
   - Description ≤ 200 chars, ends with a period.

4. Open a pull request. The deploy workflow will regenerate `public/clouds.json` and `public/llms*.txt` on merge — never hand-edit those.

Inclusion criteria: services must meet at least 2 of 3 — (1) transparent public pricing, (2) self-service signup, (3) public SLA or status page.

## 2. Working on the website

The site is an [Astro](https://astro.build) static site with Tailwind CSS v4, hosted on GitHub Pages.

```bash
npm install
npm run dev            # local server at http://localhost:4321
npm run build          # outputs dist/
npm run lint           # ESLint + astro check
npm run format:check   # Prettier
```

Open the repo in VS Code/Cursor and install the recommended extensions (`.vscode/extensions.json`) for Astro, ESLint, Tailwind, and Ruff.

Layout:

- `src/pages/` — routes (`index.astro` for the homepage, `submit/index.astro` for the form)
- `src/layouts/Base.astro` — shared `<head>`, SEO meta, JSON-LD, Fathom
- `src/lib/clouds.ts` — typed accessor for `public/clouds.json`
- `src/styles/global.css` — Tailwind + design tokens (`@theme`)
- `public/` — static assets served as-is (`clouds.json`, `llms.txt`, `CNAME`, images)

See `.cursor/rules/docs-frontend.mdc` for conventions and URL stability rules.

## 3. Writing on the blog (Phase 3, coming soon)

The blog (`src/content/blog/`) will use Astro Content Collections with TypeScript + zod frontmatter validation. Until Phase 3 lands, please open an issue if you'd like to propose a post.

## Architectural notes

- Listings are the **source of truth in `README.md`** — automation everywhere else.
- The Python submission pipeline (issue → AI evaluation → PR) lives in `scripts/` and runs in `.github/workflows/`. See `analysis/PROJECT_ANALYSIS.md` for the full pipeline.
- The Astro migration is tracked in `analysis/2026-05-19-astro-migration-rfc.md` (Phase 1 complete).

For questions or suggestions, [open an issue](https://github.com/datum-cloud/awesome-alt-clouds/issues).

Thank you!
