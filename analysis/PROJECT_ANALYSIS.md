# Deep Analysis: `awesome-alt-clouds`

## 1. What This Project Is

**`awesome-alt-clouds`** is a community-maintained "Awesome List" — a curated directory of **428+ alternative cloud providers** ("Alt Clouds") that serve as alternatives to hyperscalers (AWS / GCP / Azure). It's maintained by **Datum Cloud** and lives at [alt-cloud.org](https://www.alt-cloud.org).

What sets it apart from a typical awesome-list README is that **the entire submission → evaluation → publication pipeline is automated** using GitHub Actions, web scraping, the Anthropic Claude API, and Jina Reader. The README is the source of truth; everything else (the website, JSON, AI-readable files) is derived from it.

### Inclusion criteria (3 objective tests)

A service must meet at least **2 of 3** to be listed:

1. **Transparent Public Pricing** — a public pricing page
2. **Usage-based Self-Service** — sign up without sales contact
3. **Production Indicators** — public SLA or status page

Badges: 🟢 = 3/3, 🟡 = 2/3.

---

## 2. Repository Layout

```
README.md                    # Source of truth — the actual awesome list (~430 entries, 23 categories)
CONTRIBUTING.md              # Manual contribution guide
site.config.mjs              # Deploy profile (preview ↔ production switch; controls draft MDX visibility)
astro.config.mjs             # Astro/Vite config; @astrojs/sitemap; exposes __SITE_PREVIEW__ build-time global
src/                         # Astro site (Phase 2 migration — replaces docs/index.html as primary frontend)
  pages/
    index.astro              # Homepage card grid (reads clouds.json + featured detail pages)
    [slug].astro             # Per-cloud detail page; getStaticPaths() filters by publishability
    categories/[slug].astro  # Category landing pages — 23 static routes (Phase 4)
    compare.astro            # Side-by-side compare for 2–3 clouds; searchable pickers (Phase 4)
    blog/index.astro         # Blog index (Phase 3)
    blog/[slug].astro        # Blog post pages
    rss.xml.ts               # RSS feed of non-draft posts
    robots.txt.ts            # Build-time robots.txt (Disallow on preview; Sitemap on production)
    submit/, watchlist/      # Submission form + watchlist views
  content/
    clouds/<slug>.mdx        # Hand-authored + auto-generated detail pages (frontmatter: status, regions, …)
    blog/<slug>.md           # Editorial posts (frontmatter: title, publishDate, draft, tags, …)
  content.config.ts          # Zod schema for clouds + blog collections
  components/
    CloudCard.astro          # Shared provider card (homepage + category pages; Phase 4)
    CompareTray.astro        # Floating compare basket (localStorage, max 3; Phase 4)
    CompareButton.astro      # Detail-page compare toggle (Phase 4)
    CompareCloudPicker.astro # Type-to-search combobox for /compare columns (Phase 4)
    CompareTable.astro       # Side-by-side attribute table (Phase 4)
    CompareNavLink.astro     # Sidebar link to /compare (Phase 4)
    DraftBanner.astro        # Notice shown atop draft profiles on preview deploys
    BlogNavLink.astro        # Homepage sidebar link to /blog/
    DirectorySidebar.astro   # Site nav: Directory / Watchlist / Blog
    DetailSidebar.astro, DetailTopBar.astro, CloudSearchDropdown.astro, …
  layouts/
    CloudDetail.astro        # Detail-page chrome; Organization JSON-LD; DraftBanner when status === "draft"
    BlogPost.astro           # Blog post chrome (Phase 3)
  lib/
    profile.ts               # MergedCloud type + publish gate (getPublishableProfiles, getFeaturedSlugs, getAllMergedClouds)
    categories.ts            # 23 category descriptions + slug helpers (Phase 4; sync with generate_llms.py)
    compare.ts                 # Compare row definitions + formatting (Phase 4)
    compare-store.ts         # localStorage compare basket (`aac:compare`; Phase 4)
    compare-picker.ts        # Searchable picker logic for /compare (Phase 4)
    blog.ts                  # Blog publish gate (getPublishablePosts, sortedByDate, postUrl)
    site.ts                  # sitePreview constant (reads __SITE_PREVIEW__)
    clouds.ts                # slugify() — TS source of truth, mirrored in scripts/lib/slugify.py
docs/                        # Legacy SPA + machine-readable exports (still deployed during migration)
  index.html, submit/        # Vanilla-JS SPA + submission form
  clouds.json                # Machine-readable export of README
  llms.txt, llms-full.txt    # AI-readable summaries for LLM consumption
  superpowers/{plans,specs}/ # Design docs for the validation + duplicate features
scripts/
  check_duplicates.py        # Pre-evaluation duplicate guard
  evaluate_submission.py     # Main 3-stage evaluator (Jina → requests → Claude WebSearch)
  create_submission_pr.py    # Builds the README PR + stages auto-generated MDX (Phase 2a)
  split_submission.py        # Splits multi-URL issues into per-URL child issues
  parse_readme_to_json.py    # README → clouds.json (with dateAdded from git history)
  generate_llms.py           # clouds.json → llms.txt / llms-full.txt
  generate_cloud_profile.py  # Phase 2a: page fetch → Claude Sonnet → draft MDX detail page
  backfill_profiles.py       # Phase 2a: batch driver — generates MDX for clouds without one
  update_blog_posts.mjs      # Datum Strapi → docs/index.html Resources modal (legacy; kept alongside Astro blog)
  watchlist_add.py, generate_watchlist_json.py
  lib/
    fetcher.py               # Shared Jina-markdown → Jina-HTML → requests cascade (extracted Phase 2a)
    slugify.py               # Python mirror of src/lib/clouds.ts:slugify() (cross-checked vs all 429 names)
.github/workflows/
  evaluate-submission.yml    # Single-URL pipeline (now also stages a draft MDX via create_submission_pr.py)
  split-submission.yml       # Multi-URL pipeline
  admin-approve-submission.yml  # /approve command handler
  close-issue-on-pr-close.yml   # Cascade close: PR → child issue → parent tracker
  deploy-pages.yml           # Regenerates JSON + llms.txt on push to main
  backfill-profiles.yml      # Phase 2a: workflow_dispatch — batch-generate MDX for N candidates → PR
  update-blog-posts.yml      # Daily cron to refresh blog cards
  revalidate-submission.yml, watchlist.yml, auto-label-submission.yml, lint.yml
tests/                       # pytest suites for check_duplicates + evaluate_submission
data/candidates/             # Output of (apparent) auto-discovery scans
analysis/                    # Phase plans + this analysis doc
  2026-06-16-phase-5-seo-plan.md       # Sitemap, robots.txt, profile JSON-LD
  2026-06-30-phase-4-discovery-plan.md # Category landings, compare page, compare tray
```

---

## 3. End-to-End Workflow / Process

### Stage A — Submission Intake

A contributor either:

1. Visits `alt-cloud.org/submit/` (`docs/submit/index.html`), enters 1–5 URLs + optional notes.
2. The form builds an issue body with numbered URLs, then opens GitHub with `?labels=submission` and either prefilled body (desktop) or copy-paste fallback (mobile, due to GitHub mobile app stripping params).

Result: a GitHub issue with the `submission` label.

### Stage B — Routing on `labeled` event

Both `evaluate-submission.yml` and `split-submission.yml` listen to `issues: labeled`. Each does a guard:

- `split-submission.yml` runs **only** if the body contains > 1 numbered URL.
- `evaluate-submission.yml` **skips** if > 1 URL (the splitter handles it).

This avoids the double-fire that GitHub causes when an issue template applies a label at creation (both `opened` and `labeled` fire — they chose `labeled` only).

### Stage C — Multi-URL Split (`scripts/split_submission.py`)

For each URL in the parent issue:

1. Creates a child `[Submission] <domain>` issue with `submission` label.
2. Inlines `evaluate_submission.py` with a synthetic single-URL body against the child.
3. Comments evaluation results on the child.
4. If score ≥ 2: labels `auto-approved` + runs `create_submission_pr.py` to open a PR.
5. If score < 2: labels `needs-review` + posts the admin-override instructions.

Parent is relabeled from `submission` → `tracking` and gets a summary comment listing all child issues.

### Stage D — Single-URL Evaluation (`scripts/evaluate_submission.py`)

This is the most sophisticated part. After dedup, evaluation goes through a **3-stage fetch cascade** (per `docs/superpowers/specs/2026-03-30-submission-validation-improvement-design.md`):

```
Stage 1: Jina Reader (markdown then HTML, renders JS, bypasses CDN blocks)
   ↓ fails
Stage 2: Direct requests (cheap fallback for static sites)
   ↓ fails
Stage 3: Claude `web_search_20250305` tool (last resort, AI agentic browsing)
```

(Note: code order actually tries Jina first, then requests — cheaper and more reliable in practice than the spec suggests.)

For each stage that yields a soup, three heuristic checks run:

- `check_pricing_page` — scans for "pricing/plans" links + price tokens (`$`, `/mo`, `pay-as-you-go`, etc.); falls back to homepage scan + probing `/pricing`, `/plans`.
- `check_self_service` — scans for sign-up CTAs and forms; probes `/signup`, `/login`.
- `check_production_indicators` — scans for status links, "SLA"/"99.9%" in text; probes `status.{domain}` and `*.statuspage.io`.

If all stages fail, Claude WebSearch generates the full evaluation in one call (criteria + metadata + URL evidence + a one-line recommendation).

Then Claude Sonnet generates `{name, description ≤ 200 chars, category}` from the page content using the fixed 23-category taxonomy.

Outputs:
- `evaluation_results.md` — posted as a comment.
- `evaluation_score.txt` — used for labeling.
- `submission_data.json` — input to PR creation.

### Stage E — Pre-evaluation Duplicate Guard (`scripts/check_duplicates.py`)

Before Stage D runs, checks for:

| Match | Source | Action |
|---|---|---|
| Exact domain | `docs/clouds.json` | Comment + `duplicate` label + **close** |
| Fuzzy name (normalized, noise words removed) | `clouds.json` | Comment + label (issue stays open) |
| Existing open submission with same domain | GitHub Issues API (paginates ≤ 500) | Comment + label + **close** |

Always exits 0 (fail-open) — never blocks a legitimate submission.

### Stage F — PR Creation (`scripts/create_submission_pr.py`)

1. Branch: `submission-<issue>-<slug>` or `submission-<issue>-N-services`.
2. Finds the target category section in `README.md`.
3. Inserts the new entry alphabetically: `* 🟢/🟡 [Name](url) - description`.
4. Commits with `Closes #<issue>`.
5. `gh pr create` with auto-generated body (includes "needs verification" warning if Claude WebSearch was the source).
6. Skips if a PR already exists (idempotent).

### Stage G — Admin Override (`admin-approve-submission.yml`)

Maintainers comment one of:

- `/approve` — force-approve all URLs
- `/approve 3` — force with score override
- `/approve warp.dev 3` — target one URL in a multi-URL issue
- `/approve all 3`

The workflow re-evaluates with `ADMIN_APPROVED=true` and the override flags, bypassing the score-gate in `create_submission_pr.py`. Permission is gated on collaborator level (`admin`, `maintain`, `write`).

### Stage H — Merge & Auto-deploy (`deploy-pages.yml`)

When a PR is merged to `main` (any change to `README.md` or `docs/**`):

1. `parse_readme_to_json.py README.md docs/clouds.json` — re-parses the README, deduplicates entries appearing in multiple sections (merging their `categories` arrays), and **computes `dateAdded` for each URL by walking `git log -p` and finding its first additive diff**.
2. `generate_llms.py` — emits:
   - `llms.txt` — short index page following the [llms.txt convention](https://llmstxt.org/).
   - `llms-full.txt` — full directory with per-category descriptions + key services.
3. Bot commits the regenerated files with `[skip ci]` and pushes.

Visible in the commit log: `Auto-update clouds.json from README [skip ci]` after every merge.

### Stage I — Cascade Issue Close (`close-issue-on-pr-close.yml`)

When a PR closes (merged or not):

1. Parses `Closes #N` from the PR body, closes that child issue.
2. If the child was a `Split from multi-service submission #M` child, queries open siblings.
3. When no open siblings remain, closes parent tracking issue M.

### Stage J — Periodic Maintenance

- **`update-blog-posts.yml`** (daily 06:00 UTC): scrapes Zac Smith's Datum author page and patches the Resources modal in `docs/index.html`, then opens a PR labeled `automated`.
- **`data/candidates/scan-*.json`**: appears to be output from an external auto-discovery scanner (timestamped, but currently 0 candidates) — likely feeds future submissions but the discovery script itself isn't in this repo.

---

## 4. Frontend

### Current — Astro site (`src/`, Phase 2 migration on `feat/astro-migration`)

The primary frontend is an Astro static site that builds the directory grid (`src/pages/index.astro`), per-cloud detail pages (`src/pages/[slug].astro`), and an in-repo editorial blog (`src/pages/blog/` + `/rss.xml`). Detail pages are MDX files in `src/content/clouds/`; blog posts are Markdown in `src/content/blog/`. Build also emits `/sitemap-index.xml` and `/robots.txt` (Phase 5).

Key pieces:

- **Sidebar + top bar** components (`DetailSidebar.astro`, `DetailTopBar.astro`, `DirectorySidebar.astro`) wrap detail, watchlist, and blog pages; `CloudSearchDropdown.astro` powers the in-page search.
- **`BlogPost.astro`** renders blog articles with the same chrome as cloud detail pages; `BlogNavLink.astro` links to `/blog/` from the homepage sidebar.
- **`DraftBanner.astro`** renders only when the rendered profile carries `status: "draft"`, signalling that the page is auto-generated and pending human review.
- **`site.config.mjs`** controls a single deploy switch (`preview: true | false`) that flips the base path, noindex defaults, draft-profile visibility, crawler blocking (`blockSearchBots`), and `robots.txt` content in one place.
- **Build-time flag** `__SITE_PREVIEW__` is defined by `astro.config.mjs` and re-exported as `sitePreview` from `src/lib/site.ts`. This guarantees every module sees the same value across the build — never re-import `site.config.mjs` directly from runtime code.

### Legacy — vanilla SPA (`docs/index.html`, still deployed)

A single-file vanilla-JS SPA: `fetch('clouds.json')` on load, renders cards into a grid, client-side filtering by category (URL hash), search (URL query), and sort (alphabetical / recent via `dateAdded`). Rich SEO: Open Graph, Twitter cards, JSON-LD `Dataset` schema, canonical URL. Resources modal with auto-updated blog posts.

The submission form (`docs/submit/index.html`) is a single-file form with anti-spam honeypot, URL normalization, mobile fallback, and constructs the GitHub `issues/new?...` URL directly — no backend. The Astro version under `src/pages/submit/` mirrors it.

---

## 5. Key Design Choices Worth Noting

1. **README as the single source of truth.** All derived artifacts (`clouds.json`, `llms*.txt`, the website) are regenerated from README on every merge. Contributors never edit JSON.
2. **`dateAdded` from git history.** No metadata fields are stored in README; the parser reconstructs entry age by walking `git log -p` for the first addition of each URL.
3. **Three-stage fetch cascade with cost-aware ordering.** Free scrapers first; expensive Claude WebSearch only when both fail. Documented in `docs/superpowers/specs/`. The cascade lives in `scripts/lib/fetcher.py` and is shared by `evaluate_submission.py` and `generate_cloud_profile.py`.
4. **Fail-open duplicate detection.** A duplicate-check failure never blocks evaluation — robustness over strictness.
5. **GitHub App token (not `GITHUB_TOKEN`)** is used in workflows that need to bypass org rulesets / trigger downstream workflows (`APP_ID` + `APP_PRIVATE_KEY` secrets).
6. **Idempotent PR creation** (`git push --force` + skip-if-exists check) so re-runs after fixes don't create duplicates.
7. **Multi-category support.** A service listed under two `##` sections is deduplicated in `clouds.json` with both categories merged into one entry.
8. **AI-readability is a first-class concern.** `llms.txt` and `llms-full.txt` are intentionally generated for LLM crawler consumption alongside the JSON/HTML.
9. **Slug parity across languages.** `src/lib/clouds.ts:slugify()` is the canonical implementation; `scripts/lib/slugify.py` mirrors it byte-for-byte (cross-checked against all 429 cloud names). Filenames in `src/content/clouds/` must agree with the slug of the matching entry in `clouds.json`.
10. **Draft-by-default for auto-generated content.** Any MDX written by the bot lands as `status: draft` and only renders on preview deploys; only a human-flipped `status: reviewed` ships HTML on production. The publish gate is a single shared filter (`isProfilePublished()` in `src/lib/profile.ts`) used by both `getStaticPaths()` and homepage link generation, so route and link visibility never drift apart.

---

## 6. Phase 2 / 2a — Detail Pages & Auto-Generated Profiles

The Astro migration introduces a parallel **detail-page side-channel** that runs alongside the README→clouds.json flow. The README stays canonical; MDX files in `src/content/clouds/` enrich the cards with hand-written or AI-generated narratives, pricing, and metadata.

### Content collection schema (`src/content.config.ts`)

```ts
status: z.enum(["draft", "reviewed"]).default("draft"),
tagline, headquarters, foundedYear, regions, services,
openSource, pricingModel, socials, logo
```

All fields are optional except `status`, which gates publication.

### Production publish gate (Task 2b, landed)

| `status` | `preview: false` (production) | `preview: true` (fork/staging) |
|---|---|---|
| `reviewed` | HTML built; card links; search clickable | same |
| `draft` | **not built**; card not linked; search disabled | HTML built; card linked; search clickable |

Implemented by:

- `getProfileStatus(profile)` — reads frontmatter, defaults to `"draft"`.
- `isProfilePublished(profile, preview)` — `reviewed` always, `draft` only when `preview === true`.
- `getPublishableProfiles()` — drives `src/pages/[slug].astro` `getStaticPaths()`.
- `getFeaturedSlugs()` — same filter; drives homepage card links and search dropdown.

The build-time flag comes from `sitePreview` (`__SITE_PREVIEW__`), not a re-import of `site.config.mjs` — Vite inlines the value at config load, and a runtime re-import would risk stale caches.

### Auto-generation pipeline (Phase 2a, landed)

```text
clouds.json  ──┐
               ▼
   ┌────────────────────────────┐
   │ scripts/backfill_profiles  │  ← workflow_dispatch from backfill-profiles.yml
   │   - select N candidates    │
   │   - skip existing MDX      │
   │   - filter by score/cat    │
   └──────────┬─────────────────┘
              │ per candidate
              ▼
   ┌────────────────────────────┐
   │ scripts/generate_cloud_    │
   │   profile.py               │
   │   - fetch_page_with_       │
   │     fallback (lib/fetcher) │
   │   - Claude Sonnet prompt   │
   │   - write status: draft    │
   │     MDX, never overwrite   │
   └──────────┬─────────────────┘
              │ writes
              ▼
   src/content/clouds/<slug>.mdx (status: draft)
              │
              ▼
   PR labeled `generated-profiles, needs-verification`
              │
              ▼
   Maintainer reviews on preview deploy →
   follow-up PR flips status: reviewed → production HTML
```

The same generator is also invoked **inline** from `create_submission_pr.py` whenever a single submission produces a PR: the draft MDX is staged in the same commit as the README change, so every new entry ships with a detail-page draft from day one. Generation failure is non-fatal — the README PR still goes out.

### Why drafts never leak to production

Four overlapping safeguards:

1. **Schema default**: omitting `status` ⇒ `"draft"`.
2. **`getPublishableProfiles()`** excludes drafts unless `preview: true`.
3. **`getFeaturedSlugs()`** uses the same filter, so the homepage card isn't even a link.
4. **No silent overwrite**: both `generate_cloud_profile.py` and `backfill_profiles.py` refuse to touch an existing MDX file (so a maintainer's `reviewed` flip can never be reverted by re-running the bot).

### Detailed plans

- [`analysis/2026-05-20-phase-2-detail-pages-plan.md`](./2026-05-20-phase-2-detail-pages-plan.md) — overall Phase 2 architecture.
- [`analysis/2026-05-22-phase-2a-auto-profile-generation-plan.md`](./2026-05-22-phase-2a-auto-profile-generation-plan.md) — auto-generation pipeline, prompt design, publish gate.
- [`analysis/2026-06-15-phase-3-blog-plan.md`](./2026-06-15-phase-3-blog-plan.md) — in-repo blog, RSS, publish gate, UI chrome, legacy scraper coexistence.

---

## 7. Phase 3 — Editorial Blog + RSS

Phase 3 adds short-form editorial content at `/blog/` without changing README as the listings source of truth. Posts live in `src/content/blog/` as Markdown with zod-validated frontmatter.

### Content collection schema (`src/content.config.ts`)

```ts
title, description, publishDate, updatedDate?, author,
tags (default []), draft (default false), heroImage?
```

### Publish gate (`src/lib/blog.ts`)

Mirrors the profile `status: draft` pattern:

- `draft: false` → built in all deploys; included in `/rss.xml`
- `draft: true` → built only when `site.config.mjs` has `preview: true`

`getPublishablePosts()` drives `getStaticPaths()` on blog post pages and the RSS endpoint.

### Routes

| Route | Source |
|---|---|
| `/blog/` | `src/pages/blog/index.astro` |
| `/blog/<slug>/` | `src/pages/blog/[slug].astro` |
| `/rss.xml` | `src/pages/rss.xml.ts` (`@astrojs/rss`) |

### Two blog systems

1. **Astro in-repo blog** — PR-authored Markdown → `/blog/` (Phase 3)
2. **Legacy Datum scraper** — `update_blog_posts.mjs` patches `docs/index.html` Resources modal; workflow kept running independently

See [`analysis/2026-06-15-phase-3-blog-plan.md`](./2026-06-15-phase-3-blog-plan.md) for full architecture, UI layout, and verification steps.

---

## 8. Phase 5 — SEO Polish

Phase 5 adds build-time SEO artifacts and per-profile structured data without new UI routes.

### Sitemap (`@astrojs/sitemap`)

Integrated in `astro.config.mjs`. On `astro build`, emits `sitemap-index.xml` + `sitemap-0.xml` listing all static HTML routes (homepage, profiles, blog, submit, watchlist). Draft profiles and draft blog posts are excluded automatically because they are not built in production (`preview: false`).

### Build-time `robots.txt`

`src/pages/robots.txt.ts` is an Astro endpoint that runs at build time (same pattern as `rss.xml.ts`) — not runtime dynamic. On GitHub Pages the output is a static file in `dist/`.

- Preview (`blockSearchBots: true`): `Disallow: /`
- Production: `Allow: /` + `Sitemap: <absoluteUrl>/sitemap-index.xml`

### Profile JSON-LD

`CloudDetail.astro` injects `@graph` with:

- `Organization` — the cloud provider (name, url, description, logo, sameAs, headquarters, foundingDate)
- `WebPage` — the profile page itself

Homepage JSON-LD (`WebSite`, `Organization`, `Dataset`, `CollectionPage`) remains in `Base.astro`. Blog posts carry `BlogPosting` JSON-LD from Phase 3.

See [`analysis/2026-06-16-phase-5-seo-plan.md`](./2026-06-16-phase-5-seo-plan.md) for decisions, verification, and deferred items (per-page OG images, BreadcrumbList).

---

## 9. TL;DR

> A self-curating awesome list. Anyone submits a URL via a web form → GitHub issue → a Python+Claude bot scrapes the site, checks 3 objective inclusion criteria, generates name/description/category with AI, opens a PR. **A second Claude call drafts a full MDX detail page in the same PR, staged as `status: draft` so it only renders on preview deploys until a maintainer reviews it.** Maintainers can `/approve` to override the score gate or flip `status: reviewed` for production. On merge, the website's JSON, LLM-readable files, and Astro detail pages regenerate automatically. The README is the source of truth; everything else is derived.

---

## Pipeline Diagram

```
┌──────────────────────┐
│  alt-cloud.org/submit│  (docs/submit/index.html)
└──────────┬───────────┘
           │ opens GitHub issue with `submission` label
           ▼
┌──────────────────────────────────────────────────────┐
│ GitHub issue (labeled: submission)                   │
└──────────┬───────────────────────────┬───────────────┘
           │ 1 URL                     │ >1 URL
           ▼                           ▼
┌────────────────────┐      ┌──────────────────────────┐
│ evaluate-submission│      │ split-submission         │
│ .yml               │      │ .yml                     │
└──────────┬─────────┘      └──────────┬───────────────┘
           │                            │ creates child issues
           │                            ▼
           │                ┌──────────────────────────┐
           │                │ For each URL:            │
           │                │  - new child issue       │
           │                │  - inline evaluate       │
           │                │  - inline PR create      │
           │                └──────────┬───────────────┘
           ▼                            │
┌────────────────────────┐              │
│ check_duplicates.py    │ ─── dup? ──→ close + label │
└──────────┬─────────────┘                            │
           │                                           │
           ▼                                           │
┌──────────────────────────────────────┐               │
│ evaluate_submission.py               │               │
│   Stage 1: Jina Reader (markdown)   │               │
│   Stage 2: Jina Reader (HTML)        │               │
│   Stage 3: requests                  │               │
│   Stage 4: Claude web_search         │               │
│   → 3 criteria checks                │               │
│   → Claude metadata generation       │               │
└──────────┬───────────────────────────┘               │
           │ score ≥ 2                                  │
           ▼                                           │
┌──────────────────────────────────────┐               │
│ create_submission_pr.py              │ ◄─────────────┘
│   - Insert entry alphabetically      │
│   - generate_and_stage_mdx() →       │
│     scripts/generate_cloud_profile   │
│     writes status: draft MDX, git    │
│     add to same commit               │
│   - Open PR with Closes #N           │
└──────────┬───────────────────────────┘
           │ admin merges
           ▼
┌──────────────────────────────────────┐
│ deploy-pages.yml                     │
│   - parse_readme_to_json.py          │
│   - generate_llms.py                 │
│   - astro build (drafts excluded     │
│     in production via publish gate)  │
│   - commit [skip ci]                 │
└──────────┬───────────────────────────┘
           │
           ▼
   alt-cloud.org refreshes
```

### Parallel detail-page side-channel (Phase 2a)

```text
┌──────────────────────────┐
│ backfill-profiles.yml    │  (manual workflow_dispatch)
│   batch_size, category,  │
│   score filters          │
└──────────┬───────────────┘
           ▼
┌──────────────────────────────────────┐
│ scripts/backfill_profiles.py         │
│   - load clouds.json                 │
│   - skip existing MDX                │
│   - filter score/category, cap N     │
│   - subprocess generate_cloud_       │
│     profile.py per candidate         │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ scripts/generate_cloud_profile.py    │
│   - lib.fetcher.fetch_page_with_     │
│     fallback (Jina → requests)       │
│   - Claude Sonnet → MDX              │
│   - prepend `status: draft` (idempo) │
│   - skip-if-exists                   │
└──────────┬───────────────────────────┘
           ▼
   src/content/clouds/<slug>.mdx
   labelled `generated-profiles,
   needs-verification` on the PR
           │
           │ maintainer review on preview deploy
           ▼
   follow-up PR flips status: reviewed
           ▼
   production deploy picks it up
```
