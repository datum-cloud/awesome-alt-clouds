# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`awesome-alt-clouds` is a curated "awesome list" of 400+ alternative cloud providers, published as an Astro static site at [alt-cloud.org](https://www.alt-cloud.org). Its distinguishing feature: submissions are evaluated and merged by an automated GitHub Actions + Python + Claude API pipeline, not just by hand.

**`README.md` is the single source of truth.** Every other artifact — `public/clouds.json`, `public/llms.txt`/`llms-full.txt`, and the website itself — is regenerated from it on every merge to `main`. Never hand-edit `public/clouds.json` or `public/llms*.txt`; they get overwritten by `scripts/parse_readme_to_json.py` / `scripts/generate_llms.py` in `deploy-pages.yml`.

For the full pipeline breakdown (submission → evaluation → PR → deploy), read `analysis/PROJECT_ANALYSIS.md` first — it's a complete architecture doc and stays more current than trying to re-derive the flow from scripts alone.

## Commands

```bash
npm install
npm run dev            # Astro dev server, http://localhost:4321
npm run build          # astro build -> dist/ (postbuild rewrites relative paths for GitHub Pages)
npm run preview
npm run check           # astro check
npm run lint            # eslint . && astro check
npm run lint:fix
npm run format           # prettier --write .
npm run format:check
```

Python (submission pipeline scripts + tests — not run in any CI workflow, run manually):

```bash
python3 -m pip install --user --break-system-packages -r requirements-dev.txt
pytest tests/
ruff check scripts/ tests/
ruff format scripts/ tests/
```

Single test: `pytest tests/test_evaluate_submission.py::TestClassName::test_name`

Regenerate derived files locally (mirrors `deploy-pages.yml`):

```bash
python scripts/parse_readme_to_json.py README.md public/clouds.json
python scripts/generate_llms.py public/clouds.json public/
python scripts/generate_watchlist_json.py
```

## Architecture

### Astro frontend (`src/`)

- `src/pages/index.astro` — homepage card grid; `[slug].astro` — per-cloud detail page; `categories/[slug].astro` — 23 static category pages; `compare.astro` — side-by-side comparison (localStorage basket, max 3); `blog/`, `submit/`, `watchlist/`.
- `src/content/clouds/<slug>.mdx` — per-provider detail pages, schema in `src/content.config.ts`. Key frontmatter field: `status: "draft" | "reviewed"` (default `"draft"`).
- `src/content/blog/<slug>.md` — editorial posts, frontmatter includes `draft: boolean` (default `false`).
- `src/lib/profile.ts` / `src/lib/blog.ts` — the **publish gate**: `getPublishableProfiles()` / `getPublishablePosts()` filter drafts out unless the build is in preview mode. This same filter drives both route generation (`getStaticPaths()`) and homepage/search link visibility, so a route and its links never drift apart. Don't build a new draft-aware feature without going through this gate.
- `src/lib/clouds.ts` — canonical `slugify()`. Mirrored byte-for-byte in `scripts/lib/slugify.py`; MDX filenames in `src/content/clouds/` must match the slug this produces. Keep both in sync if you touch either.
- `src/lib/categories.ts` — the 23-category taxonomy + slugs. Must stay in sync with `scripts/evaluate_submission.py:CATEGORIES` and `scripts/generate_llms.py:_CAT_DESCRIPTIONS` (three places, one taxonomy).

### Preview vs. production build

`site.config.mjs` is the single deploy-profile switch (`preview: true | false`, `blockSearchBots`). It controls, via `astro.config.mjs`'s `__SITE_PREVIEW__` define and `src/lib/site.ts`'s `sitePreview` export:

- base path (`/awesome-alt-clouds/` on preview vs. site root in production)
- whether `status: draft` MDX / `draft: true` posts get built at all
- robots.txt / meta-robots crawler blocking

Always read `sitePreview` from `src/lib/site.ts`, never re-import `site.config.mjs` directly at runtime — Vite inlines the value at config-load time and a live re-import risks a stale value.

### Submission pipeline (`scripts/` + `.github/workflows/`)

```
submit form → GitHub issue (label: submission)
  → check_duplicates.py (fail-open guard against clouds.json + open issues)
  → evaluate_submission.py (3-stage fetch cascade: Jina Reader → requests → Claude web_search)
     → 3 criteria checks (pricing / self-service / SLA-status) + Claude-generated name/description/category
  → create_submission_pr.py (alphabetical insert into README.md; also drafts an MDX profile via generate_cloud_profile.py in the same commit)
  → admin merge (or /approve override) → deploy-pages.yml regenerates clouds.json + llms*.txt + astro build
```

- Multi-URL issues are split by `split_submission.py` into per-URL child issues before the same evaluate → PR flow runs on each.
- Inclusion needs ≥2 of 3 criteria (transparent pricing, self-service signup, public SLA/status page): 🟢 = 3/3, 🟡 = 2/3.
- Fetch cascade lives in `scripts/lib/fetcher.py`, shared by `evaluate_submission.py` and `generate_cloud_profile.py` — never call `requests.get()` directly when evaluating a candidate site, use `fetch_page_with_fallback()`.
- Python scripts are CLI automation invoked by Actions, not importable libraries: they read inputs from `os.environ` (`ISSUE_BODY`, `ISSUE_NUMBER`, `REPO`, `ANTHROPIC_API_KEY`, `ADMIN_APPROVED`, …), write side-effect files (`evaluation_results.md`, `submission_data.json`), and append `key=value` to `$GITHUB_OUTPUT`.
- **Fail-open philosophy**: automation must never block a legitimate submission. On error, log a warning, write a safe default, exit 0.
- Auto-generated MDX profiles always land as `status: draft` and are never overwritten by a re-run (`generate_cloud_profile.py` / `backfill_profiles.py` both skip-if-exists) — a maintainer's `status: reviewed` flip can't be reverted by the bot.
- Workflows that need to bypass org rulesets or trigger downstream workflows use a GitHub App token (`APP_ID`/`APP_PRIVATE_KEY`), not `secrets.GITHUB_TOKEN` — see `deploy-pages.yml`, `admin-approve-submission.yml`, `close-issue-on-pr-close.yml`.
- Workflows trigger on `issues.labeled`, not `opened`, to avoid double-firing when an issue template pre-applies the `submission` label.

### `README.md` entry format

Strict, since `scripts/parse_readme_to_json.py` parses it:

```
* 🟢 [Service Name](https://example.com/) - Short description starting with a verb.
```

Bullet is `*` (not `-`); badge is required; separator is exactly `-`; alphabetical (case-insensitive) within each `## Category` section. `dateAdded` is never written manually — it's reconstructed by walking `git log -p` for each URL's first commit.

### Watchlist

`WATCHLIST.md` tracks 1-of-3-criteria candidates submitted 2+ times. `scripts/generate_watchlist_json.py` turns it into `public/watchlist.json`, rendered at `/watchlist/`.

### Graduation pipeline (moving out of "Emerging & Unverified Providers")

`"Emerging & Unverified Providers"` is a normal entry in `evaluate_submission.py:CATEGORIES` — its entries are published (unlike Watchlist rows) but flagged as needing verification. The graduation flow re-checks one of these entries and, if it now qualifies, moves it into a real category:

```
"[Graduation] <Name>" issue (from the browser extension, or opened manually)
  → graduation-request.yml → evaluate_graduation.py
     (locates the existing README.md entry by name, re-runs the same
     evaluate_service()/generate_metadata() cascade against its URL)
  → comments a fresh score; labels graduation-request (+ graduation-ready if >=2/3)
  → maintainer comments /approve-graduation [Category Name] on the issue
  → approve-graduation.yml re-runs evaluate_graduation.py in admin mode
     → create_graduation_pr.py (removes the old bullet, inserts the
       corrected one into the target category) → PR for review
```

- Shares `evaluate_service()`/`generate_metadata()` with the submission pipeline (`scripts/evaluate_submission.py`) — don't duplicate the fetch/scoring logic.
- README bullet add/remove/lookup helpers live in `scripts/lib/readme_entries.py`, shared by `create_submission_pr.py` and `create_graduation_pr.py`.
- Nothing writes to README.md without an explicit maintainer command (`/approve-graduation`), matching the submission pipeline's `/approve` gate — the initial issue-open evaluation only comments.
- `scripts/audit_emerging_badges.py` (via the `Audit Emerging Badges` workflow, `workflow_dispatch` only) is a one-off maintenance job that re-scores every Emerging entry and corrects its badge; it flags but never removes entries scoring below 2/3.

## Notes on stale docs

- `.cursor/rules/docs-frontend.mdc` describes a legacy vanilla-JS `docs/` SPA (dependency-free static site, `docs/index.html` + `docs/submit/index.html`). That folder has since been removed from this branch as part of the Astro migration cutover (see `analysis/2026-07-20-phase-6-production-cutover-checklist.md`); the Astro site under `src/` is now the only frontend, and `public/clouds.json`/`public/llms*.txt` replace the old `docs/` equivalents. Ignore that rule file's specifics; its regex/anti-spam/SEO cautions about the _submission form_ still apply conceptually to `src/pages/submit/index.astro`.
- `scripts/update_blog_posts.mjs` + `.github/workflows/update-blog-posts.yml` are a separate legacy system (Datum Strapi blog → resources modal) independent of the in-repo Astro blog at `/blog/`.
- `analysis/*.md` are dated phase-plan docs written during the Astro migration; treat them as historical design records, not always-current state — cross-check against actual code (e.g. `analysis/PROJECT_ANALYSIS.md` still describes a `docs/` folder that no longer exists).
