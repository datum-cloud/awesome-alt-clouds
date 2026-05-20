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
docs/
  index.html                 # The alt-cloud.org website (vanilla JS SPA reading clouds.json)
  submit/index.html          # The submission form (creates GitHub issues)
  clouds.json                # Machine-readable export of README
  llms.txt, llms-full.txt    # AI-readable summaries for LLM consumption
  superpowers/{plans,specs}/ # Design docs for the validation + duplicate features
scripts/
  check_duplicates.py        # Pre-evaluation duplicate guard
  evaluate_submission.py     # Main 3-stage evaluator (requests → Jina → Claude WebSearch)
  create_submission_pr.py    # Builds the README PR from approved submission JSON
  split_submission.py        # Splits multi-URL issues into per-URL child issues
  parse_readme_to_json.py    # README → clouds.json (with dateAdded from git history)
  generate_llms.py           # clouds.json → llms.txt / llms-full.txt
  update_blog_posts.py       # Scrapes Datum blog into docs/index.html
.github/workflows/
  evaluate-submission.yml    # Single-URL pipeline
  split-submission.yml       # Multi-URL pipeline
  admin-approve-submission.yml  # /approve command handler
  close-issue-on-pr-close.yml   # Cascade close: PR → child issue → parent tracker
  deploy-pages.yml           # Regenerates JSON + llms.txt on push to main
  update-blog-posts.yml      # Daily cron to refresh blog cards
tests/                       # pytest suites for check_duplicates + evaluate_submission
data/candidates/             # Output of (apparent) auto-discovery scans
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

## 4. Frontend (`docs/index.html`)

A single-file vanilla-JS SPA:

- `fetch('clouds.json')` on load, renders cards into a grid.
- Client-side filtering by category (URL hash), search (URL query), and sort (alphabetical / recent via `dateAdded`).
- Rich SEO: Open Graph, Twitter cards, JSON-LD `Dataset` schema, canonical URL.
- Resources modal with auto-updated blog posts.

The submission form (`docs/submit/index.html`) is also a single-file form with anti-spam honeypot, URL normalization, mobile fallback, and constructs the GitHub `issues/new?...` URL directly — no backend.

---

## 5. Key Design Choices Worth Noting

1. **README as the single source of truth.** All derived artifacts (`clouds.json`, `llms*.txt`, the website) are regenerated from README on every merge. Contributors never edit JSON.
2. **`dateAdded` from git history.** No metadata fields are stored in README; the parser reconstructs entry age by walking `git log -p` for the first addition of each URL.
3. **Three-stage fetch cascade with cost-aware ordering.** Free scrapers first; expensive Claude WebSearch only when both fail. Documented in `docs/superpowers/specs/`.
4. **Fail-open duplicate detection.** A duplicate-check failure never blocks evaluation — robustness over strictness.
5. **GitHub App token (not `GITHUB_TOKEN`)** is used in workflows that need to bypass org rulesets / trigger downstream workflows (`APP_ID` + `APP_PRIVATE_KEY` secrets).
6. **Idempotent PR creation** (`git push --force` + skip-if-exists check) so re-runs after fixes don't create duplicates.
7. **Multi-category support.** A service listed under two `##` sections is deduplicated in `clouds.json` with both categories merged into one entry.
8. **AI-readability is a first-class concern.** `llms.txt` and `llms-full.txt` are intentionally generated for LLM crawler consumption alongside the JSON/HTML.

---

## 6. TL;DR

> A self-curating awesome list. Anyone submits a URL via a web form → GitHub issue → a Python+Claude bot scrapes the site, checks 3 objective inclusion criteria, generates name/description/category with AI, opens a PR. Maintainers can `/approve` to override. On merge, the website's JSON and LLM-readable files regenerate automatically. The README is the source of truth; everything else is derived.

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
│   - Open PR with Closes #N           │
└──────────┬───────────────────────────┘
           │ admin merges
           ▼
┌──────────────────────────────────────┐
│ deploy-pages.yml                     │
│   - parse_readme_to_json.py          │
│   - generate_llms.py                 │
│   - commit [skip ci]                 │
└──────────┬───────────────────────────┘
           │
           ▼
   alt-cloud.org refreshes
```
