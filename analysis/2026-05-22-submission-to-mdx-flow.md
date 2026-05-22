# End-to-End Flow: From User Submission to MDX Profile on Main

> **Scope:** Covers the single-URL happy path — user submits one cloud provider via the website form,
> the bot evaluates it, a PR is opened containing both a README change and a draft MDX detail page,
> a maintainer reviews and merges, and the site regenerates with the new entry live.
>
> For multi-URL submissions see [Stage C](#stage-c--multi-url-split) below.

---

## Overview

```
User fills form on alt-cloud.org/submit
         │
         ▼
GitHub issue created  (label: submission)
         │
         ├─── duplicate? ──────────────────────────► close + comment
         │
         ▼
evaluate_submission.py
  Jina markdown → Jina HTML → requests → Claude WebSearch
  → 3 criteria checks → score 0–3
         │
         ├─── score < 2 ──────────────────────────► needs-review label, no PR
         │
         ▼  score ≥ 2
create_submission_pr.py
  - insert README entry (alphabetical)
  - generate_cloud_profile.py → draft MDX
  - git commit README.md + <slug>.mdx
  - gh pr create
         │
         ▼
Maintainer reviews PR on fork preview deploy
  - README diff looks correct
  - draft MDX detail page renders (DraftBanner shown)
         │
         ▼
PR merged to main
         │
         ▼
deploy-pages.yml
  - parse_readme_to_json.py  →  public/clouds.json
  - generate_llms.py         →  llms.txt / llms-full.txt
  - astro build              →  dist/
  - deploy to GitHub Pages
         │
         ▼
alt-cloud.org live  (entry visible; MDX page status: draft, not yet production HTML)
         │
         ▼
Maintainer flips  status: draft → status: reviewed  in a follow-up PR
         │
         ▼
Next production deploy builds the full HTML detail page
```

---

## Stage A — User Fills the Submission Form

**URL:** `alt-cloud.org/submit/` (`docs/submit/index.html`)

1. User enters 1–5 cloud URLs and optional notes.
2. The form normalises URLs, strips trailing slashes, deduplicates.
3. On submit it opens `github.com/.../issues/new?...` with a prefilled body:
   - Single URL → field format: `**URL:** https://example.com`
   - Multiple URLs → numbered list format: `1. https://example.com`
4. GitHub creates the issue. A label `submission` is applied — either by the issue
   template or by the `auto-label-submission.yml` workflow.

> **Mobile fallback:** GitHub's mobile app strips URL params, so the form falls back to
> a copy-paste block that the user pastes manually before submitting.

---

## Stage B — Routing: Single vs Multi-URL

Two workflows listen on `issues: [opened, labeled]`:

| Workflow | Runs when |
|---|---|
| `evaluate-submission.yml` | Exactly **1** URL in the issue body |
| `split-submission.yml` | **> 1** URLs in the issue body |

`evaluate-submission.yml` has a guard step that exits early if it detects multiple URLs
(counts lines matching `^\d+\. https?://`). This prevents double-processing.

---

## Stage C — Multi-URL Split

> Skip this section if the submission is a single URL.

`scripts/split_submission.py` handles multi-URL issues:

1. For each URL, creates a child issue `[Submission] <domain>` with the `submission` label.
2. Runs `evaluate_submission.py` inline for each child.
3. If score ≥ 2: runs `create_submission_pr.py` inline, opens a PR per URL.
4. Comments a summary on the parent issue listing all child issues.
5. Re-labels the parent `submission` → `tracking`.

When all child PRs are eventually merged (or closed), `close-issue-on-pr-close.yml`
automatically closes the parent tracking issue.

---

## Stage D — Duplicate Detection

**Script:** `scripts/check_duplicates.py`  
**Triggered before evaluation.**

Three checks are performed:

| Check | Source | Action on match |
|---|---|---|
| Exact domain match | `public/clouds.json` | Comment + `duplicate` label + **close** |
| Fuzzy name match (normalised) | `public/clouds.json` | Comment + `duplicate` label (stays open) |
| Existing open submission with same domain | GitHub Issues API | Comment + `duplicate` label + **close** |

The script always exits `0` (fail-open) — a check failure never blocks a legitimate
submission.

If `is_duplicate == true`, all downstream steps in the workflow are skipped.

---

## Stage E — Evaluation

**Script:** `scripts/evaluate_submission.py`  
**Env vars:** `ISSUE_BODY`, `ISSUE_NUMBER`, `ANTHROPIC_API_KEY`

### 1. URL extraction

Parses the URL from the issue body. Accepts both the `**URL:** https://...` (single) and
`1. https://...` (numbered list) formats.

### 2. Three-stage fetch cascade

```
Stage 1a — Jina Reader (markdown mode)
  Renders JavaScript; best for SPAs and CDN-blocked sites.
  Returns markdown text → converted to pseudo-BeautifulSoup.
  ↓ thin or failed

Stage 1b — Jina Reader (HTML mode)
  Good for static / server-rendered sites.
  ↓ thin or failed

Stage 2 — Direct requests
  Cheap fallback; fails on JS-heavy or Cloudflare-protected sites.
  ↓ failed

Stage 3 — Claude web_search tool
  Last resort; fully agentic; most expensive.
  Never fails (Claude synthesises from web knowledge).
```

The cascade lives in `scripts/lib/fetcher.py` (`fetch_page_with_fallback`), shared by
both `evaluate_submission.py` and `generate_cloud_profile.py`.

### 3. Three criteria checks

For whichever stage yields a page:

- **Transparent Public Pricing** — looks for pricing page link + price tokens (`$`, `/mo`,
  `pay-as-you-go`, etc.). Falls back to probing `/pricing`, `/plans`.
- **Usage-based Self-Service** — looks for sign-up CTAs and forms. Falls back to probing
  `/signup`, `/login`.
- **Production Indicators** — looks for status page links, "SLA"/"99.9%" in text.
  Probes `status.<domain>` and `*.statuspage.io`.

### 4. Score calculation

| Score | Meaning | Next step |
|---|---|---|
| **3/3** | All criteria met | Label `auto-approved`; PR created automatically |
| **2/3** | 2 criteria met | Label `needs-review`; PR created automatically |
| **1/3 or 0/3** | Too few criteria | Label `needs-review`; **no PR**; admin must `/approve` |

### 5. Metadata generation

Claude Sonnet generates `name`, `description` (≤ 200 chars), and `category` from the page
content, selecting from the fixed 23-category taxonomy.

### 6. Outputs written to disk

| File | Used by |
|---|---|
| `evaluation_results.md` | Posted as a GitHub comment on the issue |
| `evaluation_score.txt` | Read by subsequent workflow steps for branching |
| `submission_data.json` | Input to `create_submission_pr.py` |

---

## Stage F — PR Creation

**Script:** `scripts/create_submission_pr.py`  
**Triggered only when:** score ≥ 2 and `submission_data.json` exists.  
**Env vars:** `GH_TOKEN`, `ISSUE_NUMBER`, `ANTHROPIC_API_KEY`

### Step 1 — Create branch

Branch name: `submission-<issue_number>-<service-name-slug>`

### Step 2 — Insert README entry

Finds the target `## <category>` section in `README.md` and inserts the new entry
**alphabetically** within that section:

```
* 🟢 [Service Name](https://example.com) - One-line description.
```

- 🟢 = score 3/3, 🟡 = score 2/3.

### Step 3 — Generate draft MDX detail page

`generate_and_stage_mdx(service)` is called for each added service:

1. Derives the slug from the service name using `scripts/lib/slugify.py`
   (mirrors `src/lib/clouds.ts:slugify()` exactly — cross-checked on all 429 names).
2. Checks whether `src/content/clouds/<slug>.mdx` already exists → **skips if it does**.
3. Calls `scripts/generate_cloud_profile.py` as a subprocess with env vars:

   ```
   CLOUD_NAME, CLOUD_URL, CLOUD_SCORE, CLOUD_CATEGORIES, CLOUD_DESCRIPTION, OUTPUT_PATH
   ```

4. Inside `generate_cloud_profile.py`:
   - Fetches the cloud's website via the same Jina → requests cascade (`lib/fetcher`).
   - Sends a structured prompt to **Claude Sonnet** asking for a YAML frontmatter +
     Markdown body with specific sections (What makes it different / Pricing model /
     When it fits / When it doesn't / Inclusion criteria).
   - Prepends `status: draft` to the frontmatter (idempotent — won't duplicate it).
   - Writes the file to `src/content/clouds/<slug>.mdx`.
   - Writes `profile_generation_report.json` `{slug, fetch_method, output_path, needs_verification}`.

5. Runs `git add src/content/clouds/<slug>.mdx`.

> **Non-fatal:** if MDX generation fails for any reason, the README PR still proceeds.
> The MDX step never blocks the submission flow.

### Step 4 — Commit

Both `README.md` and (if generated) `src/content/clouds/<slug>.mdx` are staged, then
committed in one shot:

```bash
git add README.md
git add src/content/clouds/<slug>.mdx   # when generation succeeded
git commit -m "Add <Name> to <Category>\n\nCloses #<issue_number>"
```

**Single service example:**

```
Add Civo to Infrastructure Clouds

Closes #1234
```

**Multiple services example:**

```
Add 3 services: Civo, Beam, Arcade

Closes #1234
```

**Backfill batch PR** (from `backfill-profiles.yml`):

```
feat(profiles): auto-generate 20 cloud detail profiles [needs-verification]
```

**Follow-up review PR** (maintainer flips draft → reviewed):

```
feat(profiles): mark civo, beam profiles as reviewed
```

### Step 5 — Push and open PR

```
git push --force origin <branch>
gh pr create --title "Add 🟢 <Name> to <Category>" --body "..." --base main
```

The PR body contains:
- Service details table (name, URL, category, score).
- Warning block if Claude WebSearch was the evaluation source.
- `### Auto-generated detail pages` section listing the MDX path (and a
  "needs verification" flag if the web fetch failed).
- `Closes #<issue_number>`.

Idempotent: if a PR already exists for this branch, the step is skipped.

---

## Stage G — Maintainer Review

At this point a PR exists on GitHub. The maintainer:

1. Reads the evaluation comment on the original issue.
2. Reviews the README diff — checks alphabetical placement and badge.
3. **Optionally** pulls the branch and runs `npm run build` locally with `preview: true`
   in `site.config.mjs`. The draft MDX detail page is visible at `/<slug>/` with a
   yellow `DraftBanner` ("Auto-generated profile — pending human review").
4. Clicks through the detail page on the fork preview deploy
   (`https://<user>.github.io/<repo>/<slug>/`).
5. Verifies any specific claims in the MDX (pricing numbers, regions, socials).

### Admin override

If the score was < 2 (no PR opened), a maintainer can comment:

```
/approve
/approve 3           # override score to 3
/approve warp.dev 3  # target a specific URL in a multi-URL issue
```

The `admin-approve-submission.yml` workflow re-runs evaluation with `ADMIN_APPROVED=true`
and the override flags, then calls `create_submission_pr.py` directly.

---

## Stage H — Merge to Main

When the maintainer merges the PR:

1. **`close-issue-on-pr-close.yml`** fires on `pull_request: closed`.
   - Parses `Closes #N` from the PR body.
   - Closes the original submission issue with a comment.
   - If the issue was a child of a multi-URL tracking issue, checks for remaining
     open siblings — closes the parent when all children are resolved.

2. **`deploy-pages.yml`** fires on push to `main`.

---

## Stage I — Site Regeneration (`deploy-pages.yml`)

**Triggered by:** push to `main` (or `feat/astro-migration` during migration).

Steps:

| Step | Script | Output |
|---|---|---|
| Regenerate JSON | `parse_readme_to_json.py README.md public/clouds.json` | `public/clouds.json` — all 429+ entries with `dateAdded` from git history |
| Regenerate LLM files | `generate_llms.py public/clouds.json public/` | `public/llms.txt`, `public/llms-full.txt` |
| Regenerate watchlist | `generate_watchlist_json.py` | `public/watchlist.json` |
| Build Astro site | `npm run build` | `dist/` |
| Deploy | `actions/deploy-pages@v4` | Live on GitHub Pages |

During `npm run build`, Astro's `getStaticPaths()` in `src/pages/[slug].astro` calls
`getPublishableProfiles()`. Because the newly merged MDX has `status: draft` and the
**production** build has `preview: false` in `site.config.mjs`, the draft page is
**not built** into `dist/`. The cloud entry still appears in the directory card grid
(from `clouds.json`), but the card is not clickable — no detail page link.

---

## Stage J — Detail Page Goes Live

The draft MDX profile only becomes a production HTML page after a maintainer opens a
follow-up PR that flips `status: draft` → `status: reviewed`:

```yaml
---
status: reviewed   # was: draft
tagline: "..."
# ...
---
```

When that PR merges, `deploy-pages.yml` runs again. This time `getPublishableProfiles()`
includes the entry (status is `reviewed`) and `dist/<slug>/index.html` is generated.
The directory card becomes clickable and the detail page is live — without the
`DraftBanner`.

---

## Summary Timeline

```
T+0m    User submits on alt-cloud.org/submit
T+0m    GitHub issue created (label: submission)
T+1m    evaluate-submission.yml starts
T+1m    Duplicate check runs (check_duplicates.py)
T+2m    evaluate_submission.py fetches site, checks 3 criteria, calls Claude
T+3m    Evaluation comment posted on issue; score label applied
T+4m    create_submission_pr.py: inserts README entry
T+5m    generate_cloud_profile.py: fetches site again, calls Claude Sonnet
T+5m    Draft MDX written: src/content/clouds/<slug>.mdx (status: draft)
T+5m    PR opened: README.md + <slug>.mdx in one commit
T+?     Maintainer reviews and merges PR
T+?     deploy-pages.yml: parse README → JSON, build Astro, deploy
T+?     New cloud entry visible on alt-cloud.org (card, no detail link)
T+?     Maintainer opens follow-up PR: status: draft → status: reviewed
T+?     deploy-pages.yml: detail page HTML built, card link active
```

---

## Key Files Reference

| File | Role |
|---|---|
| `docs/submit/index.html` | Submission form |
| `.github/workflows/evaluate-submission.yml` | Orchestrates stages D–F |
| `scripts/check_duplicates.py` | Stage D |
| `scripts/evaluate_submission.py` | Stage E |
| `scripts/lib/fetcher.py` | Shared fetch cascade (Jina → requests) |
| `scripts/create_submission_pr.py` | Stage F — README edit + PR |
| `scripts/generate_cloud_profile.py` | Stage F — draft MDX generation |
| `scripts/lib/slugify.py` | Slug derivation (mirrors TS) |
| `src/content/clouds/<slug>.mdx` | Draft detail page (status: draft) |
| `src/content.config.ts` | MDX schema (`status: "draft" \| "reviewed"`) |
| `src/lib/profile.ts` | Publish gate (`getPublishableProfiles`, `getFeaturedSlugs`) |
| `src/pages/[slug].astro` | Detail page; `getStaticPaths` respects publish gate |
| `src/components/DraftBanner.astro` | Warning banner on draft pages |
| `site.config.mjs` | `preview: true/false` switch |
| `.github/workflows/deploy-pages.yml` | Stage I — build + deploy |
| `.github/workflows/close-issue-on-pr-close.yml` | Stage H — cascade close |

---

## Appendix — Phase 2a implementation commits

These commits landed the auto-profile pipeline on `feat/astro-migration`:

| Commit message |
|---|
| `feat(profiles): add status field to MDX schema, mark 5 seeds as reviewed` |
| `feat(profiles): gate draft MDX pages to preview builds only` |
| `feat(profiles): add DraftBanner component for auto-generated profiles` |
| `refactor(scripts): extract Jina+requests cascade into scripts/lib/fetcher.py` |
| `feat(scripts): add Python slugify mirror of src/lib/clouds.ts` |
| `feat(scripts): add generate_cloud_profile.py with Claude-based MDX generation` |
| `feat(scripts): add backfill_profiles.py batch driver` |
| `feat(workflows): add backfill-profiles.yml for batch MDX generation` |
| `feat(pipeline): auto-generate MDX profile alongside README PR on new submission` |
| `docs(workflows): wire ANTHROPIC_API_KEY into submission PR creation step` |
| `chore: expand Python gitignore patterns` |
| `docs(analysis): add Phase 2a plans, flow guide, and update project analysis` |
