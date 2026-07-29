# Contributing to Alt Cloud

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

### Borderline submissions

The [Watchlist](WATCHLIST.md) tracks services that show real potential but haven't crossed the qualification threshold yet.

| Score | Outcome                                                                                |
| ----- | -------------------------------------------------------------------------------------- |
| 0 / 3 | Declined. No pricing, no self-service, no status page — nothing to build on.           |
| 1 / 3 | Watchlist candidate. One signal is present; a maintainer may add it to track progress. |
| 2 / 3 | Included (needs-review). A PR is opened automatically for admin sign-off.              |
| 3 / 3 | Included automatically.                                                                |

If your service lands on the watchlist, the "Criteria Needed" column shows exactly what must change. Address those gaps and re-submit, or comment on your original issue with evidence that the missing criteria are now met.

The public watchlist page lives at `/watchlist/` and is generated from `WATCHLIST.md` on every deploy.

### Graduating an "Emerging & Unverified Providers" listing

Some services are listed under [Emerging & Unverified Providers](README.md#emerging--unverified-providers) — they're in the directory, but flagged as needing verification (usually pricing or self-service details the bot couldn't confirm). Unlike the Watchlist, these entries are already published.

To request a re-check, open an issue titled `[Graduation] <Service Name>` (the Alt Cloud browser extension does this for you) — the bot re-runs the 3-criteria evaluation against the current listing and comments the result. If it now scores 2/3 or higher and the bot has a better-fitting category, a maintainer confirms with `/approve-graduation` (or `/approve-graduation <Category Name>` to pick the category) to open a PR moving the entry out of Emerging & Unverified Providers.

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

## 3. Writing on the blog

The blog lives at `/blog/` and is built from Markdown files in `src/content/blog/`. Posts use Astro Content Collections with TypeScript + zod frontmatter validation.

### Adding a post

1. Fork the repository and create a branch.
2. Add a new file under `src/content/blog/` using the naming convention `YYYY-MM-short-slug.md` (for example, `2026-06-welcome-to-alt-cloud.md`).
3. Fill in the required frontmatter:

   ```yaml
   ---
   title: Your post title
   description: One-sentence summary for the index page and RSS feed.
   publishDate: 2026-06-15
   author: Your Name
   tags:
     - guide
   draft: false
   ---
   ```

   Optional fields:
   - `updatedDate` — set when you revise a published post
   - `heroImage` — path under `public/` (for example, `/blog-images/my-cover.png`)

4. Write the body in Markdown below the frontmatter.
5. Open a pull request. A maintainer reviews before merge.

### Draft posts

Set `draft: true` to keep a post out of production builds. Draft posts appear only on preview deploys (`preview: true` in `site.config.mjs`), mirroring the cloud profile `status: draft` workflow.

### What not to edit

- Do not add listings in blog posts — `README.md` remains the canonical source for directory entries.
- Do not hand-edit build output in `dist/`.

### RSS

Non-draft posts are published to `/rss.xml` automatically on every deploy.

### Legacy Datum blog scraper (separate system)

`scripts/update_blog_posts.mjs` and `.github/workflows/update-blog-posts.yml` are **kept**. That automation fetches Datum blog posts from Strapi and patches the Resources modal in the legacy `docs/index.html` file. It is independent of the in-repo Astro blog at `/blog/` — both can run in parallel until Phase 6 cutover retires `docs/`.

## Architectural notes

- Listings are the **source of truth in `README.md`** — automation everywhere else.
- The Python submission pipeline (issue → AI evaluation → PR) lives in `scripts/` and runs in `.github/workflows/`. See `analysis/PROJECT_ANALYSIS.md` for the full pipeline.
- The Astro migration is tracked in `analysis/2026-05-19-astro-migration-rfc.md` (Phase 3 complete).

For questions or suggestions, [open an issue](https://github.com/datum-cloud/awesome-alt-clouds/issues).

Thank you!
