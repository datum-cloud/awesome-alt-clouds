# Astro Migration RFC — Evolving alt-cloud.org into a Community Destination

> Status: **Phase 1 complete (parity scaffold) — Phase 2 next**
> Author: planning session, 2026-05-19
> Branch: `feat/astro-migration`
> Tracks: [Issue #164](https://github.com/datum-cloud/awesome-alt-clouds/issues/164)

## Migration progress

| Phase | Status | Notes |
|---|---|---|
| 0 — RFC + decisions locked | ✅ done | Decisions in §11 below |
| 1 — Astro scaffold with parity | ✅ done (2026-05-19) | See "Phase 1 — what landed" below |
| 2 — Deeper company profiles (`/clouds/[slug]`) | ⏳ pending | |
| 3 — Editorial / blog + RSS | ⏳ pending | `update_blog_posts.yml` cron paused in Phase 1 |
| 4 — Discovery prep (`/categories/[slug]`, `/compare` stub) | ⏳ pending | |
| 5 — SEO polish | ⏳ pending | |
| 6 — Production cutover | ⏳ pending | Pages source needs flipping from "branch /docs" → "GitHub Actions" |

### Phase 1 — what landed

- **Branch**: `feat/astro-migration` cut from latest `main`.
- **Stack**: Astro 5.x + Tailwind v4 (`@tailwindcss/vite`) + TypeScript strict.
  - Astro 6 + Rolldown was tried first but is currently incompatible with `@tailwindcss/vite` 4 → pinned to Astro 5 (well-supported; trivial bump later).
- **Files added**:
  - `package.json`, `package-lock.json`, `astro.config.mjs`, `tsconfig.json`
  - `src/layouts/Base.astro` — SEO meta, OG/Twitter, JSON-LD (Dataset+CollectionPage+Organization+WebSite), Fathom analytics, fonts.
  - `src/pages/index.astro` — homepage with all ~430 cards SSR'd into the static HTML; client-side filter / search / sort works against the pre-rendered cards (no `fetch()` round trip).
  - `src/pages/submit/index.astro` — submission form ported 1:1 (honeypot, URL normalization, mobile copy-paste fallback all preserved).
  - `src/lib/clouds.ts` — typed accessor for `public/clouds.json`.
  - `src/styles/global.css` — Tailwind v4 with design tokens via `@theme` (warm-stone / soft-sage / clay-beige / rich-earth / bright-tangerine / cream / charcoal).
  - `public/CNAME` — `www.alt-cloud.org` (preserves custom domain on Pages-Actions cutover).
- **Files moved/copied to `public/`**: `clouds.json`, `llms.txt`, `llms-full.txt`, `og-image.png`, `altclouds-logo.png`.
- **Python scripts updated**:
  - `scripts/parse_readme_to_json.py` — no code change; CI now passes `public/clouds.json` as output path.
  - `scripts/generate_llms.py` — defaults shifted from `docs/` → `public/`; module docstring updated.
  - `scripts/check_duplicates.py` — `_CLOUDS_JSON_PATH` retargeted to `public/clouds.json` (tests use `patch.object`, so they still pass without modification).
- **Workflows**:
  - `.github/workflows/deploy-pages.yml` — fully rewritten. Uses `actions/upload-pages-artifact@v3` + `actions/deploy-pages@v4`. No more `[skip ci]` auto-commit loop; `clouds.json` and `llms*.txt` are produced inside the build job and live only in the deployed artifact.
  - `.github/workflows/update-blog-posts.yml` — cron schedule commented out (the script patches `docs/index.html` which is being retired); kept as `workflow_dispatch` only until Phase 3 replaces it.
- **Docs**: `CONTRIBUTING.md` rewritten with three contribution flows (listings via README, website via Astro, blog placeholder). `.cursor/rules/docs-frontend.mdc` replaced — now describes the Astro layout, Tailwind tokens, URL stability contract, and retired pieces.
- **`.gitignore`**: adds `node_modules/`, `dist/`, `.astro/`, `.env*`, `.worktrees/`, `analysis/` (the last keeps RFC drafts as local-only scratch space).
- **`docs/` folder**: intentionally **not deleted yet** — kept as a legacy reference until Phase 6 cutover. The Pages source still points there until we flip the toggle, so live traffic remains unaffected while reviewers compare the two implementations side-by-side.

### Phase 1 verification

- `npm run build` succeeds → emits `dist/index.html` (807 KB, all 429 cards SSR'd) + `dist/submit/index.html` (13 KB) + all `public/` assets preserved at root URLs.
- `python scripts/parse_readme_to_json.py README.md public/clouds.json` → 429 services, 23 categories, 0 multi-category. ✅
- `python scripts/generate_llms.py public/clouds.json public/` → both llms files regenerate cleanly. ✅
- SEO meta, JSON-LD, Fathom analytics, all 23 categories, search/filter/sort behavior, modals, mobile drawer — all match original.

### What Phase 2 will pick up

1. Define `profiles` content collection with zod schema (regions, services, pricing model, etc.).
2. Build `src/pages/clouds/[slug].astro` using `getStaticPaths` over `clouds.json` — every cloud gets a page automatically.
3. Layout: profile hero, criteria scorecard, related providers.
4. Seed 5–10 featured providers with hand-written enrichment MDs.
5. Cross-link homepage cards to the new profile pages.

---


---

## 1. Issue #164 — What's actually being asked

[Issue #164](https://github.com/datum-cloud/awesome-alt-clouds/issues/164) reframes the site from "a surface for the list" into a community destination. Five proposed ideas, phased:

| # | Idea | MVP scope |
|---|---|---|
| 1 | Deeper per-company profiles (data-driven from the repo) | ✅ MVP |
| 2 | Editorial / blog | ✅ MVP |
| 3 | Comparison & discovery aids (filter, side-by-side) | 🟡 Prepare structure |
| 4 | Community & events, newsletter | ❌ Later |
| 5 | Metadata footprint (OG, structured data, sitemap) | 🟢 Free win in Astro |

**Hard constraint from the issue itself**: *"The list in GitHub remains the canonical source of truth."* The migration must preserve `README.md` as the single editable source for the directory listings — profile MDs only *enrich*, never replace.

## 2. Where the project is today (grounded)

- **`README.md`** (~67 KB, ~430 entries across 23 categories) is the canonical source.
- Auto-pipeline derives `docs/clouds.json`, `docs/llms.txt`, `docs/llms-full.txt` on every merge via `deploy-pages.yml` (Python: `parse_readme_to_json.py`, `generate_llms.py`).
- Frontend is **two vanilla-JS HTML files**: `docs/index.html` (~66 KB, fetches `clouds.json` at runtime) + `docs/submit/index.html` (form → GitHub issue URL).
- GitHub Pages serves from `docs/` on `main` (folder-based publish, not Actions-based).
- `alt-cloud.org` custom domain configured in Pages settings — **no `CNAME` file in repo** (verified).
- External runtime deps: Google Fonts + Fathom analytics only.
- 23-category taxonomy duplicated in `scripts/evaluate_submission.py:CATEGORIES` and `scripts/generate_llms.py:_CAT_DESCRIPTIONS`.

## 3. Is GitHub Pages + Astro feasible?

**Yes — Astro is essentially the canonical choice for this exact pattern.**

- Astro outputs pure static HTML/CSS/JS → Pages serves it natively, no servers needed.
- Content Collections + zod schemas are purpose-built for blog + profile data.
- `getStaticPaths()` generates all ~430 profile pages from `clouds.json` at build time.
- Two deploy mechanisms both work on Pages:
  - **A. Modern Pages Actions** (`actions/upload-pages-artifact` + `actions/deploy-pages`) → build to `dist/`, upload as artifact, deploy. **Cleaner.** No git-commit loops.
  - **B. Branch-based** — build to `docs/` and commit. Matches current model but pollutes git with build output.
- Build time for ~430 static pages on a GH runner: <30 s in practice.

**Recommendation: option A.** Eliminates the `[skip ci]` auto-commit dance for HTML output and gives PR preview support if desired.

## 4. Data flow — before vs. after

**Before**

```
README.md → parse_readme_to_json.py → docs/clouds.json
                                      ↓
                                   fetch() at runtime in docs/index.html
```

**After**

```
README.md ──→ parse_readme_to_json.py ──→ public/clouds.json (still public at /clouds.json)
                                          ↓
                                   import in Astro build
                                          +
                              src/content/profiles/*.md (optional enrichment)
                              src/content/blog/*.md       (editorial)
                                          ↓
                                   astro build → dist/
                                          ↓
                                  actions/deploy-pages
```

Key invariant preserved: **README is still the only place to edit listings.** Profile MDs only add extra fields (regions, services, hero, long-form description); they cannot create or remove entries.

## 5. Proposed project structure

```
awesome-alt-clouds/
├── README.md                       # unchanged — source of truth
├── CONTRIBUTING.md                 # updated: profile + blog authoring sections
├── package.json                    # new
├── astro.config.mjs                # new
├── tsconfig.json                   # new
├── src/
│   ├── pages/
│   │   ├── index.astro             # directory (current homepage parity)
│   │   ├── clouds/[slug].astro     # ← Idea 1: deeper profile (all ~430 pages)
│   │   ├── categories/[slug].astro # ← Idea 3 prep: category landing pages
│   │   ├── compare.astro           # ← Idea 3 placeholder + schema docs
│   │   ├── blog/
│   │   │   ├── index.astro         # ← Idea 2: blog index
│   │   │   └── [slug].astro        # blog post
│   │   ├── rss.xml.js              # @astrojs/rss
│   │   └── submit/index.astro      # ported from docs/submit/index.html (URL preserved)
│   ├── content/
│   │   ├── config.ts               # zod schemas for profiles + blog
│   │   ├── profiles/               # one .md per featured cloud (optional)
│   │   │   ├── neon.md
│   │   │   └── digital-ocean.md
│   │   └── blog/
│   │       └── 2026-06-welcome-to-alt-cloud.md
│   ├── layouts/
│   │   ├── Base.astro              # shared <head>, OG, JSON-LD, Fathom
│   │   ├── Profile.astro
│   │   └── Post.astro
│   ├── components/
│   │   ├── CloudCard.astro
│   │   ├── ProfileHeader.astro
│   │   ├── CategoryFilter.astro    # client island
│   │   ├── SearchBox.astro         # client island (vanilla, no framework)
│   │   └── CompareTable.astro      # stub for Idea 3
│   ├── lib/
│   │   ├── clouds.ts               # loads + merges clouds.json + profile MD
│   │   └── slug.ts                 # canonical slug derivation
│   └── styles/global.css
├── public/                         # copied as-is into dist/
│   ├── altclouds-logo.png
│   ├── og-image.png
│   ├── clouds.json                 # ← /clouds.json URL preserved
│   ├── llms.txt
│   ├── llms-full.txt
│   ├── robots.txt
│   └── CNAME                       # NEW: must add to preserve alt-cloud.org domain
├── scripts/                        # Python pipeline mostly unchanged
│   ├── parse_readme_to_json.py     # output path → public/clouds.json
│   ├── generate_llms.py            # output dir → public/
│   ├── evaluate_submission.py      # unchanged
│   ├── create_submission_pr.py     # unchanged
│   ├── split_submission.py         # unchanged
│   ├── check_duplicates.py         # path update: reads public/clouds.json
│   ├── update_blog_posts.py        # ⚠ may be retired (see Open Q #5)
│   └── scaffold_profiles.py        # NEW (optional): generate empty profile MDs
├── tests/                          # existing pytests, path-update only
├── docs/                           # ⚠ RETIRED after cutover (Pages source switches to Actions)
└── .github/workflows/
    ├── deploy-pages.yml            # MODIFIED: Python → Node → Astro → Pages Actions
    ├── evaluate-submission.yml     # path updates only (clouds.json moves)
    ├── split-submission.yml        # unchanged
    ├── admin-approve-submission.yml # unchanged
    ├── close-issue-on-pr-close.yml  # unchanged
    └── update-blog-posts.yml       # ⚠ retire OR retarget to Astro blog
```

## 6. Content collection schemas (illustrative)

```typescript
// src/content/config.ts
import { defineCollection, z } from 'astro:content';

const profiles = defineCollection({
  type: 'content',
  schema: z.object({
    slug: z.string(),                        // must match slug(clouds.json.name)
    headquarters: z.string().optional(),
    regions: z.array(z.string()).optional(),
    services: z.array(z.string()).optional(),
    openSource: z.boolean().optional(),
    pricingModel: z.enum(['hourly', 'monthly', 'usage-based', 'subscription', 'mixed']).optional(),
    foundedYear: z.number().optional(),
    socials: z.object({
      x: z.string().optional(),
      linkedin: z.string().optional(),
      github: z.string().optional(),
    }).optional(),
    logo: z.string().optional(),
    featured: z.boolean().default(false),
  }),
});

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    publishDate: z.date(),
    updatedDate: z.date().optional(),
    author: z.string(),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
    heroImage: z.string().optional(),
  }),
});

export const collections = { profiles, blog };
```

Profile page algorithm (`src/pages/clouds/[slug].astro`):

1. `getStaticPaths` iterates every entry in `clouds.json`.
2. For each, look up matching MD in `getCollection('profiles')` by slug.
3. Merge: JSON is required base; MD frontmatter overrides; MD body becomes long-form description.

→ Every cloud gets a page (auto). Featured ones get rich content (manual MD).

## 7. URL stability checklist (zero broken links)

| URL | Status after migration |
|---|---|
| `/` | Same content, Astro-rendered |
| `/clouds.json` | Preserved via `public/clouds.json` |
| `/llms.txt`, `/llms-full.txt` | Preserved via `public/` |
| `/submit/` | Preserved as `src/pages/submit/index.astro` |
| `/og-image.png`, `/altclouds-logo.png` | Preserved via `public/` |
| `/clouds/<slug>` | **NEW** — per-cloud profile pages |
| `/blog`, `/blog/<slug>` | **NEW** — editorial |
| `/categories/<slug>` | **NEW** — category landing |
| `/compare` | **NEW** — placeholder |
| `/rss.xml` | **NEW** — for blog feed |
| `/sitemap-index.xml` | **NEW** — `@astrojs/sitemap` |

## 8. `deploy-pages.yml` redesign (sketch)

```yaml
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]
    paths:
      - 'README.md'
      - 'src/**'
      - 'public/**'
      - 'astro.config.mjs'
      - 'package.json'
      - 'scripts/parse_readme_to_json.py'
      - 'scripts/generate_llms.py'
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: python scripts/parse_readme_to_json.py README.md public/clouds.json
      - run: python scripts/generate_llms.py public/clouds.json public/
      - uses: actions/setup-node@v4
        with: { node-version: '20', cache: 'npm' }
      - run: npm ci
      - run: npm run build
      - uses: actions/upload-pages-artifact@v3
        with: { path: ./dist }

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

Notable changes:

- No more `[skip ci]` auto-commit (HTML is artifact-only).
- `clouds.json` / `llms.txt` no longer committed back to git — they're derived at build time. **Trade-off**: history of `clouds.json` is lost. If we want to keep that, add a second job that commits them back like today.
- App token is no longer needed (no git push), simpler permissions.

## 9. Phased delivery roadmap

| Phase | Scope | Est. |
|---|---|---|
| **0** | RFC committed to `analysis/`, decisions locked, branch created | ½ day |
| **1** | Astro scaffold with **parity** to current site (same UX, no new features). Cutover-ready. | 2–3 days |
| **2** | **Idea 1**: profile pages live for all ~430 clouds, 5–10 seeded with rich content | 2–3 days |
| **3** | **Idea 2**: blog + RSS, 1–2 launch posts | 1–2 days |
| **4** | **Idea 3 prep**: category landing pages + `/compare` stub + schema for compare-fields | 1 day |
| **5** | SEO polish: per-page OG, dynamic JSON-LD, sitemap | ½ day |
| **6** | Production cutover: verify CNAME, switch Pages source, monitor | ½ day |

**Total: ~7–10 working days** for a single engineer.

### Phase-by-phase acceptance criteria

**Phase 1 — Parity.** Visiting `/`, `/submit/`, `/clouds.json`, `/llms.txt`, `/og-image.png` produces visually & functionally identical output to the current site. Search, category filter (URL hash), sort (alphabetical / recent) all work. No new pages exposed yet.

**Phase 2 — Profiles.** Every cloud in `clouds.json` has a working `/clouds/<slug>` page. 5–10 featured providers have hand-written enrichment via `src/content/profiles/<slug>.md`. Profile cards on `/` link to these pages.

**Phase 3 — Blog.** `/blog` index lists posts sorted by `publishDate` desc. `/blog/<slug>` pages render with OG tags. `/rss.xml` validates. `CONTRIBUTING.md` documents post authoring. At least 1 inaugural post live.

**Phase 4 — Discovery prep.** `/categories/<slug>` pages exist for all 23 categories (showing filtered cloud lists). `/compare` is a documented placeholder route. Profile schema has been extended with comparison-friendly optional fields (`regions`, `services`, `pricingModel`, etc.) so future side-by-side views are additive, not breaking.

**Phase 5 — SEO.** Per-page JSON-LD `Organization` schema on profiles, `BlogPosting` on posts. Sitemap covers all routes. `og-image.png` retained; per-page OG image generation TBD (out of MVP).

**Phase 6 — Cutover.** Pages source switched from "branch `main` /docs" to "GitHub Actions". Custom domain `www.alt-cloud.org` still resolves. Fathom analytics still firing. Monitor for 48 h.

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Lose `alt-cloud.org` custom domain on cutover | Add `public/CNAME` with the exact domain string; verify in Pages settings + `dig` post-deploy |
| Break `/clouds.json` consumers (incl. our own current site if rolled back) | Ship `public/clouds.json` from day 1; smoke-test the URL on preview |
| README contributors confused which file to edit | Update `CONTRIBUTING.md` + `.cursor/rules/docs-frontend.mdc` with the new layout |
| Build adds Node dep to a Python-centric repo | Document in README; pin `package.json` + commit `package-lock.json` |
| Existing `update_blog_posts.py` scraper conflicts with new blog | Decide explicitly: retire it OR retarget to ingest external posts into `src/content/blog/` |
| URL slug collisions (e.g., two clouds with same slug) | `slug.ts` returns slug + checks uniqueness at build time; fail build if collision |
| Cursor rules (`docs-frontend.mdc`, etc.) become stale immediately | Update them in the same PR that lands Phase 1 |
| Submission evaluation pipeline references `docs/clouds.json` paths | Audit `check_duplicates.py`, `evaluate_submission.py`, tests; bump all path constants together |

## 11. Decisions locked

| # | Question | Decision |
|---|---|---|
| 1 | Deploy mechanism | **A — Pages Actions** (`actions/upload-pages-artifact` + `actions/deploy-pages`) |
| 2 | Commit `clouds.json` / `llms*.txt` back to git? | **No — artifact-only.** They're regenerated by every CI build. Git no longer carries derived files. |
| 3 | Profile slug source | **Derive from `name`** via `slugify` (collisions fail the build) |
| 4 | Profile authoring workflow | **PRs only.** No auto-stub generation on submission. |
| 5 | `update_blog_posts.py` future | **Retire** after Phase 3. For Phase 1: cron paused, workflow kept as manual trigger. |
| 6 | Styling | **Tailwind CSS v4** (user-requested override of the original "Astro scoped CSS" default) |
| 7 | PR previews | **GitHub Pages only.** No Cloudflare / Netlify preview deploys (avoids extra services). |
| 8 | TypeScript? | **Yes everywhere.** strict tsconfig; zod schemas for content collections in Phase 2/3. |

---

## Appendix A — Reference reading

- Current architecture deep-dive: [`analysis/PROJECT_ANALYSIS.md`](./PROJECT_ANALYSIS.md)
- Submission validation spec: `docs/superpowers/specs/2026-03-30-submission-validation-improvement-design.md`
- Issue tracker: [datum-cloud/awesome-alt-clouds#164](https://github.com/datum-cloud/awesome-alt-clouds/issues/164)
- Astro Content Collections: <https://docs.astro.build/en/guides/content-collections/>
- GitHub Pages with Actions: <https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site#publishing-with-a-custom-github-actions-workflow>
