# Astro Migration RFC — Evolving alt-cloud.org into a Community Destination

> Status: **Phase 1–5 complete — Phase 6 (cutover) next**
> Author: planning session, 2026-05-19
> Branch: `feat/astro-migration`
> Tracks: [Issue #164](https://github.com/datum-cloud/awesome-alt-clouds/issues/164)

## Migration progress

| Phase | Status | Notes |
|---|---|---|
| 0 — RFC + decisions locked | ✅ done | Decisions in §11 below |
| 1 — Astro scaffold with parity | ✅ done (2026-05-19) | See "Phase 1 — what landed" below |
| 2 — Deeper company profiles (`/<slug>`) | ✅ done (2026-05-20) | Flat URL chosen instead of `/clouds/[slug]`. Plan: [2026-05-20-phase-2-detail-pages-plan.md](./2026-05-20-phase-2-detail-pages-plan.md). 5 sample MDX files seeded; architecture scales to 429+. |
| 2a — Auto-generated profile MDX | ✅ done (2026-05-22) | Bot generates `status: draft` MDX on submission + batch backfill workflow. Plan: [2026-05-22-phase-2a-auto-profile-generation-plan.md](./2026-05-22-phase-2a-auto-profile-generation-plan.md). Flow: [2026-05-22-submission-to-mdx-flow.md](./2026-05-22-submission-to-mdx-flow.md). |
| 3 — Editorial / blog + RSS | ✅ done (2026-06-15) | Plan: [2026-06-15-phase-3-blog-plan.md](./2026-06-15-phase-3-blog-plan.md). `/blog`, `/blog/<slug>`, `/rss.xml`; 2 seed posts. Legacy `update_blog_posts.mjs` + `update-blog-posts.yml` **kept**. |
| 4 — Comparison & discovery aids | ✅ done (2026-06-30) | Category landings, `/compare`, versus-style tray, search pickers. Plan: [2026-06-30-phase-4-discovery-plan.md](./2026-06-30-phase-4-discovery-plan.md). |
| 5 — SEO polish | ✅ done (2026-06-16) | Plan: [2026-06-16-phase-5-seo-plan.md](./2026-06-16-phase-5-seo-plan.md). `@astrojs/sitemap`, build-time `robots.txt`, per-profile `Organization` JSON-LD. |
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

### Phase 2 — what landed

- **URL shape**: flat `/<slug>` (e.g. `/neon/`), not `/clouds/[slug]` as originally sketched in §5.
- **Content collection**: `src/content/clouds/*.mdx` with zod schema in `src/content.config.ts` (tagline, headquarters, regions, services, pricingModel, socials, etc.).
- **Pages**: `src/pages/[slug].astro` — `getStaticPaths()` over publishable MDX profiles merged with `clouds.json` base data.
- **Layout**: `src/layouts/CloudDetail.astro` with `DetailSidebar`, `DetailTopBar`, prose styling.
- **Featured signal**: a cloud card links to a detail page iff a publishable MDX file exists (no separate `featured: true` field).
- **Seeds**: 5 hand-authored profiles (`neon`, `hetzner`, `cloudflare`, `render`, `digital-ocean`) marked `status: reviewed`.
- **Homepage**: cards with publishable profiles become clickable; search dropdown respects the same filter via `getFeaturedSlugs()`.

### Phase 2a — what landed

Phase 2a extends the submission pipeline and adds a batch backfill path so detail pages can be generated at scale without hand-writing every MDX file.

**Publish gate**

- MDX frontmatter carries `status: "draft" | "reviewed"` (default `"draft"`).
- `getPublishableProfiles()` / `isProfilePublished()` in `src/lib/profile.ts` — reviewed profiles always build; draft profiles build only when `site.config.mjs` has `preview: true`.
- Build-time flag via `__SITE_PREVIEW__` → `sitePreview` in `src/lib/site.ts` (never re-import `site.config.mjs` at runtime).
- `DraftBanner.astro` renders on draft detail pages in preview deploys with an "Edit on GitHub" link.

**Generator pipeline** (`scripts/`)

| File | Role |
|---|---|
| `lib/fetcher.py` | Shared Jina markdown → Jina HTML → requests cascade (extracted from `evaluate_submission.py`) |
| `lib/slugify.py` | Python mirror of `src/lib/clouds.ts:slugify()` — verified against all 429 cloud names |
| `generate_cloud_profile.py` | Fetch page → Claude Sonnet → write `status: draft` MDX; never overwrite existing files |
| `backfill_profiles.py` | Batch driver: reads `public/clouds.json`, skips existing MDX, filters by score/category, caps batch size |

**CI integration**

- `create_submission_pr.py` — calls `generate_and_stage_mdx()` before commit; draft MDX lands in the same commit as the README entry. Generation failure is non-fatal.
- `backfill-profiles.yml` — `workflow_dispatch` with `batch_size`, `category_filter`, `score_filter`; opens a PR labelled `generated-profiles, needs-verification`.
- `evaluate-submission.yml` — passes `ANTHROPIC_API_KEY` to the PR creation step.

**Human review workflow**

1. Bot opens PR with `status: draft` MDX.
2. Maintainer spot-checks on fork preview deploy (`preview: true` shows draft pages + DraftBanner).
3. Follow-up PR flips `status: reviewed` on accurate profiles.
4. Production deploy (`preview: false`) picks up reviewed profiles only.

**Locked decisions (Phase 2a)**

| Decision | Choice |
|---|---|
| MDX merge policy | Auto-commit as `status: draft` + `needs-verification` label; flip to `reviewed` in follow-up PR |
| Regeneration | Bot skips slug that already has MDX (no silent overwrite) |
| Backfill scope | Pilot 20–30 clouds first; expand after quality review |
| Refresh / cron | Deferred to Phase 3 — no `/refresh` trigger yet |

### Phase 3 — what landed

Maps to [Issue #164](https://github.com/datum-cloud/awesome-alt-clouds/issues/164) **Idea 2 — Editorial / blog**. Full plan: [2026-06-15-phase-3-blog-plan.md](./2026-06-15-phase-3-blog-plan.md).

- **Content collection**: `blog` in `src/content.config.ts` with zod schema (`title`, `description`, `publishDate`, `author`, `tags`, `draft`, optional `heroImage`).
- **Lib**: `src/lib/blog.ts` — `getPublishablePosts()`, `isPostPublished()`, `sortedByDate()`, `postUrl()`, `formatPostDate()`. Draft posts excluded from production builds (same pattern as profile `status: draft`).
- **Routes**: `/blog/` (index), `/blog/<slug>/` (posts), `/rss.xml` (RSS via `@astrojs/rss`).
- **Layouts & components**:
  - `src/layouts/BlogPost.astro` — mirrors `CloudDetail.astro` shell; uses `DirectorySidebar` + `DetailTopBar`.
  - `DirectorySidebar.astro` — third nav item "Blog" alongside Directory / Watchlist.
  - `BlogNavLink.astro` — homepage sidebar + mobile drawer link.
  - `.prose-content` styles moved to `src/styles/global.css` (shared with cloud detail pages).
- **SEO**: per-post `BlogPosting` JSON-LD; RSS auto-discovery `<link>` in `Base.astro`; `seo.blog` block in `site.config.mjs`.
- **Seed posts**: `2026-06-welcome-to-alt-cloud.md`, `2026-06-what-is-an-alt-cloud.md`.
- **Docs**: `CONTRIBUTING.md` §3 — full blog authoring spec.
- **Legacy scraper kept**: `scripts/update_blog_posts.mjs` and `.github/workflows/update-blog-posts.yml` remain active. They continue to patch Datum blog cards into the legacy `docs/index.html` Resources modal — separate from the new in-repo Astro blog at `/blog/`.

**Deferred from Phase 3 MVP**

- Homepage "Latest from the blog" strip
- Tag landing pages (`/blog/tags/<tag>/`)
- Automated external RSS/HTML ingest into `src/content/blog/`

### Phase 3 — planned (next)

Maps to [Issue #164](https://github.com/datum-cloud/awesome-alt-clouds/issues/164) **Idea 2 — Editorial / blog**.

**Goal:** Host short-form content (trends, new entrants, commentary) in-repo so the site stays fresh without duplicating the README as source of truth for listings.

**Content model**

```
src/content/blog/
  2026-06-welcome-to-alt-cloud.md   # date-prefixed slug convention
```

Zod schema (extend `src/content.config.ts`):

```typescript
const blog = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    publishDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    author: z.string(),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),   // excluded from production build when true
    heroImage: z.string().optional(),
  }),
});
```

**Pages & routes**

| Route | File | Notes |
|---|---|---|
| `/blog` | `src/pages/blog/index.astro` | Post list, newest first; filter by tag (optional MVP+) |
| `/blog/<slug>` | `src/pages/blog/[slug].astro` | Full post with OG/Twitter meta, `BlogPosting` JSON-LD |
| `/rss.xml` | `src/pages/rss.xml.ts` or `@astrojs/rss` | Feed of non-draft posts |

**Layout & components**

- `src/layouts/Post.astro` — article chrome matching site tokens (serif headings, warm-stone body).
- Reuse `Base.astro` for meta; add per-post OG when `heroImage` is set.
- Homepage: optional "Latest from the blog" strip (1–3 recent posts) — defer if scope tight.

**Editorial workflow**

1. Contributor opens PR adding/editing a file under `src/content/blog/`.
2. Maintainer review (same as profile MDX — human gate, no bot generation for launch).
3. Merge → `deploy-pages.yml` picks up new post on next build.
4. `draft: true` posts build only on preview deploys (same pattern as cloud profile `status: draft`).

**Retire legacy scraper**

- ~~Delete or archive `scripts/update_blog_posts.py` and `update-blog-posts.yml` once Astro blog is live.~~ **Decision reversed (2026-06-15):** keep `scripts/update_blog_posts.mjs` and `update-blog-posts.yml`. The Astro blog (`/blog/`) and the legacy Datum scraper (`docs/index.html` Resources modal) serve different surfaces and coexist.
- The old script patched Datum blog cards into `docs/index.html` Resources modal — replace with either:
  - **Option A (recommended):** hand-curated `src/content/blog/` posts only; or
  - **Option B:** a thin ingest script that converts external RSS/HTML into MDX PRs (out of MVP).

**Deliverables**

- [x] `blog` content collection + 1–2 seed posts (e.g. welcome post, "what is an alt cloud")
- [x] `/blog`, `/blog/<slug>`, `/rss.xml`
- [x] `CONTRIBUTING.md` — blog authoring section (frontmatter, draft flag, review process)
- [x] Legacy scraper kept (`update_blog_posts.mjs` + `update-blog-posts.yml`)

**Estimate:** 1–2 days.

---

### Phase 4 — what landed (Comparison & discovery aids)

Maps to [Issue #164](https://github.com/datum-cloud/awesome-alt-clouds/issues/164) **Idea 3 — Comparison & discovery aids**. Full plan: [2026-06-30-phase-4-discovery-plan.md](./2026-06-30-phase-4-discovery-plan.md).

**Routes**

| Route | Purpose |
|---|---|
| `/categories/<slug>` | Static landing page per category — SEO-friendly, shareable URL, filtered card grid |
| `/compare` | Pick 2–3 providers; side-by-side attribute table |
| `/compare?a=neon&b=hetzner` | Shareable deep link (query params → pre-selected clouds) |

**Category landing pages** — `src/pages/categories/[slug].astro` with `getStaticPaths` over 23 categories; intro copy from `src/lib/categories.ts` (synced with `generate_llms.py:_CAT_DESCRIPTIONS`); shared `CloudCard.astro` grid; `CollectionPage` JSON-LD; `sitemap-categories-0.xml`.

**Compare page** — `src/pages/compare.astro` + `CompareTable.astro`; data from `clouds.json` merged with MDX frontmatter via `getAllMergedClouds()`. Type-to-search column pickers (`CompareCloudPicker.astro`, `compare-picker.ts`) replace native `<select>` dropdowns.

**Versus-style compare tray** — `CompareTray.astro` in `Base.astro`; `compare-store.ts` persists up to 3 providers in `localStorage`; **Compare +** on detail pages and cloud cards; floating **Compare (n)** navigates to `/compare?a=&b=&c=`.

**Deliverables**

- [x] `/categories/<slug>` for all 23 categories
- [x] `/compare` with 2–3 cloud picker + attribute table
- [x] Query-param deep links (`?a=&b=&c=`)
- [x] Nav link from homepage sidebar / category pages
- [x] Compare CTA on detail pages and cloud cards
- [x] Compare tray (localStorage basket + floating button)
- [x] Searchable combobox pickers on compare page

**Out of scope (deferred):** full-text profile search, auth-backed saved lists, "similar providers", >3 clouds, per-page OG images.

---

### Phase 5 — what landed

Maps to [Issue #164](https://github.com/datum-cloud/awesome-alt-clouds/issues/164) **Idea 5 — Metadata footprint**. Full plan: [2026-06-16-phase-5-seo-plan.md](./2026-06-16-phase-5-seo-plan.md).

- **`@astrojs/sitemap`** — integrated in `astro.config.mjs`; build emits `sitemap-index.xml` + `sitemap-0.xml` covering all static routes (~400+ profile pages, blog, submit, watchlist, homepage).
- **Build-time `robots.txt`** — `src/pages/robots.txt.ts` endpoint (same pattern as `rss.xml.ts`). Preview deploys (`blockSearchBots: true`) → `Disallow: /`. Production cutover flips automatically when `preview: false` — no manual file edit.
- **Per-profile JSON-LD** — `CloudDetail.astro` injects `@graph` with `Organization` (cloud provider) + `WebPage` (profile page) via `<Fragment slot="head">`. Fields from `MergedCloud`: name, url, description, logo, sameAs, headquarters, foundedYear.
- **Already in place from earlier phases**: homepage JSON-LD graph in `Base.astro`; `BlogPosting` JSON-LD in `BlogPost.astro`; canonical/OG/Twitter meta on all pages; RSS auto-discovery.

**Deferred from Phase 5 MVP**

- Per-page OG images (favicon-based or generated)
- `BreadcrumbList` JSON-LD on profile/blog/category pages

**Phase 5 verification**

- `npm run build` → 408 pages; sitemap generated
- `dist/robots.txt` reflects `blockSearchBots` (preview: `Disallow: /`)
- Profile HTML includes valid `Organization` + `WebPage` JSON-LD (e.g. `/neon/`)

---

## 1. Issue #164 — What's actually being asked

[Issue #164](https://github.com/datum-cloud/awesome-alt-clouds/issues/164) reframes the site from "a surface for the list" into a community destination. Five proposed ideas, phased:

| # | Idea | Issue #164 scope | RFC phase | Status |
|---|---|---|---|---|
| 1 | Deeper per-company profiles | ✅ MVP | Phase 2 + 2a | ✅ **Delivered** — Astro MDX at `/<slug>`, auto-gen pipeline, publish gate |
| 2 | Editorial / blog | ✅ MVP | Phase 3 | ✅ **Delivered** — `/blog/`, `/rss.xml`; plan: [2026-06-15-phase-3-blog-plan.md](./2026-06-15-phase-3-blog-plan.md) |
| 3 | Comparison & discovery aids | 🟡 Prepare structure | Phase 4 | ✅ **Delivered** — category landings + compare; plan: [2026-06-30-phase-4-discovery-plan.md](./2026-06-30-phase-4-discovery-plan.md) |
| 4 | Community & events, newsletter | ❌ Later | — | Not scoped |
| 5 | Metadata footprint (OG, structured data, sitemap) | 🟢 Free win in Astro | Phase 5 | ✅ **Delivered** — sitemap, build-time robots.txt, profile JSON-LD; plan: [2026-06-16-phase-5-seo-plan.md](./2026-06-16-phase-5-seo-plan.md). Per-page OG images still TBD. |

**Hard constraint from the issue itself**: *"The list in GitHub remains the canonical source of truth."* The migration preserves `README.md` as the single editable source for directory listings — profile MDX and blog posts only *enrich*, never replace.

**Issue #164 acceptance criteria — current scorecard**

| Criterion | Status |
|---|---|
| Phase 1 scope agreed in writing | ✅ This RFC |
| List in GitHub remains canonical | ✅ README → clouds.json; MDX/blog are additive |
| At least one of: deeper profiles, blog, or discovery aid live | ✅ **Profiles, blog, categories + compare live** on `feat/astro-migration` |

## 2. Where the project is today (grounded)

*Updated 2026-06-30 after Phase 4.*

- **`README.md`** (~430 entries, 23 categories) remains the canonical source for listings.
- **Build pipeline:** `deploy-pages.yml` regenerates `public/clouds.json` + `llms*.txt` at CI time, then `npm run build` → Astro static site in `dist/`.
- **Frontend:** Astro 5 + Tailwind v4 on branch `feat/astro-migration` (preview deploy on GitHub Pages).
  - `/` — directory grid with search, category filter, sort; cards link to detail pages when publishable MDX exists.
  - `/<slug>` — cloud detail pages from `src/content/clouds/*.mdx` merged with `clouds.json`; per-page `Organization` JSON-LD.
  - `/categories/<slug>` — 23 category landing pages with filtered card grids (Phase 4).
  - `/compare` — side-by-side attribute table for 2–3 clouds; searchable pickers; `?a=&b=&c=` deep links (Phase 4).
  - `/submit/`, `/watchlist/`, `/blog/`, `/rss.xml` — Astro routes.
  - `/sitemap-index.xml`, `/robots.txt` — build-time SEO artifacts (Phase 5).
- **Compare tray:** site-wide floating basket (`localStorage`, max 3) via `CompareTray.astro` in `Base.astro` (Phase 4).
- **Profile coverage:** 168+ reviewed MDX profiles (backfill) + bot pipeline for auto-generated `status: draft` MDX.
- **Legacy `docs/`:** still present for reference; production cutover (Phase 6) pending.

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

**After (Phase 1 + 2 + 2a)**

```
README.md ──→ parse_readme_to_json.py ──→ public/clouds.json (still public at /clouds.json)
                                          ↓
                                   import in Astro build
                                          +
                              src/content/clouds/*.mdx (hand-authored or bot-generated)
                              src/content/blog/*.md       (editorial — Phase 3)
                                          ↓
                                   astro build → dist/
                                   (draft MDX excluded in production via publish gate)
                                          ↓
                                  actions/deploy-pages

New submission (score ≥ 2):
  evaluate_submission.py → create_submission_pr.py
    → README entry + generate_cloud_profile.py → src/content/clouds/<slug>.mdx (status: draft)

Batch backfill (manual workflow_dispatch):
  backfill_profiles.py → generate_cloud_profile.py → PR with N draft MDX files
```

Key invariant preserved: **README is still the only place to edit listings.** Profile MDs enrich cards with narrative content, pricing detail, and metadata — they cannot create or remove directory entries. Auto-generated MDX always ships as `status: draft` until a maintainer marks it `reviewed`.

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
│   │   ├── [slug].astro            # ← Idea 1: flat profile URL (Phase 2 — landed)
│   │   ├── categories/[slug].astro # ← Idea 3 prep: category landing pages
│   │   ├── compare.astro           # ← Idea 3 placeholder + schema docs
│   │   ├── blog/
│   │   │   ├── index.astro         # ← Idea 2: blog index (Phase 3)
│   │   │   └── [slug].astro        # blog post
│   │   ├── rss.xml.ts              # @astrojs/rss (Phase 3)
│   │   ├── robots.txt.ts           # build-time robots.txt (Phase 5)
│   │   ├── submit/index.astro      # ported from docs/submit/index.html (URL preserved)
│   │   └── watchlist/              # watchlist page (Phase 1 extension)
│   ├── content/
│   │   ├── config.ts               # zod schemas — clouds collection (Phase 2)
│   │   ├── clouds/                 # one .mdx per profile (Phase 2 + 2a)
│   │   │   ├── neon.mdx            # hand-authored, status: reviewed
│   │   │   └── …                   # bot-generated, status: draft
│   │   └── blog/                   # Phase 3
│   ├── layouts/
│   │   ├── Base.astro              # shared <head>, OG, JSON-LD, Fathom
│   │   └── CloudDetail.astro       # profile layout + DraftBanner (Phase 2a)
│   ├── components/
│   │   ├── DraftBanner.astro       # draft-profile notice (Phase 2a)
│   │   ├── DetailSidebar.astro, DetailTopBar.astro, CloudSearchDropdown.astro, …
│   │   └── CompareTable.astro      # stub for Idea 3
│   ├── lib/
│   │   ├── clouds.ts               # loads clouds.json + slugify()
│   │   ├── profile.ts              # MergedCloud merge + publish gate (Phase 2 + 2a)
│   │   └── site.ts                 # sitePreview build-time flag
│   └── styles/global.css
├── public/                         # copied as-is into dist/
│   ├── altclouds-logo.png
│   ├── og-image.png
│   ├── clouds.json                 # ← /clouds.json URL preserved
│   ├── llms.txt
│   ├── llms-full.txt
│   └── CNAME                       # NEW: must add to preserve alt-cloud.org domain
├── scripts/                        # Python pipeline
│   ├── parse_readme_to_json.py     # output path → public/clouds.json
│   ├── generate_llms.py            # output dir → public/
│   ├── evaluate_submission.py      # 3-stage evaluation cascade
│   ├── create_submission_pr.py     # README PR + inline MDX generation (Phase 2a)
│   ├── generate_cloud_profile.py   # Claude → draft MDX (Phase 2a)
│   ├── backfill_profiles.py        # batch MDX driver (Phase 2a)
│   ├── lib/
│   │   ├── fetcher.py              # shared Jina → requests cascade (Phase 2a)
│   │   └── slugify.py              # Python slugify mirror (Phase 2a)
│   ├── split_submission.py         # multi-URL split
│   ├── check_duplicates.py         # reads public/clouds.json
│   └── update_blog_posts.mjs       # Datum blog → docs/index.html Resources modal (kept)
├── site.config.mjs                 # preview ↔ production switch (Phase 2a publish gate)
├── tests/                          # existing pytests
├── docs/                           # ⚠ RETIRED after cutover (Pages source switches to Actions)
└── .github/workflows/
    ├── deploy-pages.yml            # Python → Node → Astro → Pages Actions
    ├── evaluate-submission.yml     # single-URL pipeline (+ MDX gen in PR step)
    ├── backfill-profiles.yml       # batch MDX generation (Phase 2a)
    ├── split-submission.yml
    ├── admin-approve-submission.yml
    ├── close-issue-on-pr-close.yml
    └── update-blog-posts.yml       # Daily cron: Datum blog → docs/index.html (kept)
```

## 6. Content collection schemas (illustrative)

```typescript
// src/content.config.ts (as landed — clouds collection, not profiles/)
import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const clouds = defineCollection({
  loader: glob({ pattern: '**/*.mdx', base: './src/content/clouds' }),
  schema: z.object({
    status: z.enum(['draft', 'reviewed']).default('draft'),  // Phase 2a publish gate
    tagline: z.string().optional(),
    headquarters: z.string().optional(),
    foundedYear: z.number().int().optional(),
    regions: z.array(z.string()).optional(),
    services: z.array(z.string()).optional(),
    openSource: z.boolean().optional(),
    pricingModel: z.enum(['hourly', 'monthly', 'usage-based', 'subscription', 'mixed']).optional(),
    socials: z.object({
      x: z.string().optional(),
      linkedin: z.string().optional(),
      github: z.string().optional(),
      website: z.string().optional(),
    }).optional(),
    logo: z.string().optional(),
  }),
});

const blog = defineCollection({ /* Phase 3 */ });

export const collections = { clouds, blog };
```

Profile page algorithm (`src/pages/[slug].astro` — as landed):

1. `getStaticPaths` calls `getPublishableProfiles()` — only MDX with `status: reviewed`, or any status when `preview: true`.
2. For each publishable profile, merge MDX frontmatter + body with the matching `clouds.json` entry via `mergeCloudWithProfile()`.
3. Homepage cards link to detail pages only when the slug appears in `getFeaturedSlugs()` (same publish filter).

→ Detail pages exist only when an MDX file is present **and** publishable for the current deploy. Bot-generated profiles start as `draft` and require a maintainer flip to `reviewed` before production HTML is built.

## 7. URL stability checklist (zero broken links)

| URL | Status after migration |
|---|---|
| `/` | Same content, Astro-rendered |
| `/clouds.json` | Preserved via `public/clouds.json` |
| `/llms.txt`, `/llms-full.txt` | Preserved via `public/` |
| `/submit/` | Preserved as `src/pages/submit/index.astro` |
| `/og-image.png`, `/altclouds-logo.png` | Preserved via `public/` |
| `/<slug>` | **NEW (Phase 2)** — flat per-cloud profile pages (only when publishable MDX exists) |
| `/blog`, `/blog/<slug>` | **NEW (Phase 3)** — editorial |
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
| **2** | **Idea 1**: profile pages at `/<slug>`, 5 seeds hand-authored + publish gate | ✅ done |
| **2a** | **Auto-generated profiles**: bot writes `status: draft` MDX on submission + batch backfill workflow | ✅ done |
| **3** | **Idea 2**: blog collection, `/blog`, `/rss.xml`, retire scraper, 1–2 seed posts | ✅ done |
| **4** | **Idea 3**: `/categories/<slug>` landings + `/compare` (2–3 clouds, query deep links) | 1–2 days |
| **5** | SEO polish: per-page OG, dynamic JSON-LD, sitemap | ✅ done |
| **6** | Production cutover: verify CNAME, switch Pages source, monitor | ½ day |

**Total: ~7–10 working days** for a single engineer.

### Phase-by-phase acceptance criteria

**Phase 1 — Parity.** Visiting `/`, `/submit/`, `/clouds.json`, `/llms.txt`, `/og-image.png` produces visually & functionally identical output to the current site. Search, category filter (URL hash), sort (alphabetical / recent) all work. No new pages exposed yet.

**Phase 2 — Profiles.** Clouds with a publishable MDX file at `src/content/clouds/<slug>.mdx` have a working `/<slug>` page. 5 hand-authored seeds marked `status: reviewed`. Homepage cards link only to publishable profiles. Draft profiles visible on preview deploys only.

**Phase 2a — Auto-generated profiles.** New submissions (score ≥ 2) get a draft MDX staged in the same PR as the README entry. `backfill-profiles.yml` batch-generates profiles for clouds lacking MDX. All bot output is `status: draft`; maintainer follow-up PR flips to `reviewed` for production. No silent MDX overwrite.

**Phase 3 — Blog.** `/blog` index lists non-draft posts sorted by `publishDate` desc. `/blog/<slug>` renders with OG tags and `BlogPosting` JSON-LD. `/rss.xml` validates. `CONTRIBUTING.md` documents post authoring. At least 1 inaugural post live. Legacy `update_blog_posts.mjs` scraper kept (patches `docs/index.html` Resources modal separately).

**Phase 4 — Comparison & discovery.** `/categories/<slug>` static pages exist for all 23 categories with filtered card grids and category descriptions. `/compare` renders a side-by-side attribute table for 2–3 selected clouds; shareable via `?a=&b=&c=` query params. Homepage search/filter/sort unchanged. Compare reads `clouds.json` + MDX frontmatter where available.

**Phase 5 — SEO.** Per-page JSON-LD `Organization` on profiles, `BlogPosting` on posts. `@astrojs/sitemap` covers all routes. Per-page OG images TBD (out of MVP).

**Phase 6 — Cutover.** Pages source switched from "branch `main` /docs" to "GitHub Actions". Custom domain `www.alt-cloud.org` still resolves. Fathom analytics still firing. Monitor for 48 h.

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Lose `alt-cloud.org` custom domain on cutover | Add `public/CNAME` with the exact domain string; verify in Pages settings + `dig` post-deploy |
| Break `/clouds.json` consumers (incl. our own current site if rolled back) | Ship `public/clouds.json` from day 1; smoke-test the URL on preview |
| README contributors confused which file to edit | Update `CONTRIBUTING.md` + `.cursor/rules/docs-frontend.mdc` with the new layout |
| Build adds Node dep to a Python-centric repo | Document in README; pin `package.json` + commit `package-lock.json` |
| Existing `update_blog_posts.mjs` scraper | **Kept** — patches legacy `docs/index.html` Resources modal; Astro blog at `/blog/` is a separate in-repo editorial surface |
| URL slug collisions (e.g., two clouds with same slug) | `slug.ts` returns slug + checks uniqueness at build time; fail build if collision |
| Cursor rules (`docs-frontend.mdc`, etc.) become stale immediately | Update them in the same PR that lands Phase 1 |
| Submission evaluation pipeline references `docs/clouds.json` paths | Audit `check_duplicates.py`, `evaluate_submission.py`, tests; bump all path constants together |

## 11. Decisions locked

| # | Question | Decision |
|---|---|---|
| 1 | Deploy mechanism | **A — Pages Actions** (`actions/upload-pages-artifact` + `actions/deploy-pages`) |
| 2 | Commit `clouds.json` / `llms*.txt` back to git? | **No — artifact-only.** They're regenerated by every CI build. Git no longer carries derived files. |
| 3 | Profile slug source | **Derive from `name`** via `slugify` (collisions fail the build) |
| 4 | Profile authoring workflow | **Phase 2 (original): PRs only, no auto-stub.** **Phase 2a (updated):** bot auto-generates `status: draft` MDX on submission + batch backfill; maintainer flips to `reviewed` for production. See [2026-05-22-phase-2a-auto-profile-generation-plan.md](./2026-05-22-phase-2a-auto-profile-generation-plan.md). |
| 5 | `update_blog_posts.mjs` future | **Keep** — continues patching Datum blog cards into legacy `docs/index.html` Resources modal; independent of Astro `/blog/` |
| 6 | Styling | **Tailwind CSS v4** (user-requested override of the original "Astro scoped CSS" default) |
| 7 | PR previews | **GitHub Pages only.** No Cloudflare / Netlify preview deploys (avoids extra services). |
| 8 | TypeScript? | **Yes everywhere.** strict tsconfig; zod schemas for content collections in Phase 2/3. |
| 9 | Blog authoring | **PR-only.** `draft: true` excluded from production (mirrors profile publish gate). No bot generation at launch. |
| 10 | Compare data source | **`clouds.json` base + MDX frontmatter overlay.** Missing profile fields show "—"; no new data store. |
| 11 | Category page slugs | **Derive from README `##` headings** via same slugify rules as cloud names. |

---

## 12. Recommended execution order (post Phase 2a)

```
Phase 3 (blog)  ──►  Phase 5 (SEO) ✅  ──►  Phase 4 (categories + compare) ✅  ──►  Phase 6 (cutover)
```

**Phase 4 landed 2026-06-30** — category landings, `/compare`, versus-style compare tray, and searchable column pickers. See [2026-06-30-phase-4-discovery-plan.md](./2026-06-30-phase-4-discovery-plan.md).

**Phase 5 landed 2026-06-16** ahead of Phase 4 because it has no UX surface — only sitemap, robots.txt, and profile JSON-LD.

**Next:** Phase 6 production cutover (flip Pages source from legacy `docs/` to Actions artifact).

## Appendix A — Reference reading

- Current architecture deep-dive: [`analysis/PROJECT_ANALYSIS.md`](./PROJECT_ANALYSIS.md)
- Phase 2 detail pages plan: [`analysis/2026-05-20-phase-2-detail-pages-plan.md`](./2026-05-20-phase-2-detail-pages-plan.md)
- Phase 2a auto-generation plan: [`analysis/2026-05-22-phase-2a-auto-profile-generation-plan.md`](./2026-05-22-phase-2a-auto-profile-generation-plan.md)
- Phase 3 blog plan: [`analysis/2026-06-15-phase-3-blog-plan.md`](./2026-06-15-phase-3-blog-plan.md)
- Phase 4 discovery plan: [`analysis/2026-06-30-phase-4-discovery-plan.md`](./2026-06-30-phase-4-discovery-plan.md)
- Phase 5 SEO plan: [`analysis/2026-06-16-phase-5-seo-plan.md`](./2026-06-16-phase-5-seo-plan.md)
- End-to-end submission → MDX flow: [`analysis/2026-05-22-submission-to-mdx-flow.md`](./2026-05-22-submission-to-mdx-flow.md)
- Submission validation spec: `docs/superpowers/specs/2026-03-30-submission-validation-improvement-design.md`
- Issue tracker: [datum-cloud/awesome-alt-clouds#164](https://github.com/datum-cloud/awesome-alt-clouds/issues/164)
- Astro Content Collections: <https://docs.astro.build/en/guides/content-collections/>
- GitHub Pages with Actions: <https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site#publishing-with-a-custom-github-actions-workflow>
