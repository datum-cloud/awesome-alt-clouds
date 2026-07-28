# Scripts & Local Testing Reference

> **Scope:** Inventory of all Python scripts, shared libraries, GitHub Actions wiring,
> and a practical local verification checklist. Complements
> [PROJECT_ANALYSIS.md](./PROJECT_ANALYSIS.md) and
> [2026-05-22-submission-to-mdx-flow.md](./2026-05-22-submission-to-mdx-flow.md).

---

## Prerequisites

Run all commands from the repository root:

```bash
cd "$(git rev-parse --show-toplevel)"
```

**Runtime versions:** Node.js ≥ 22.12.0, Python 3.11+ (CI uses 3.11).

**Python packages (once per machine, no venv):**

```bash
python3 -m pip install --user --break-system-packages -r requirements.txt
python3 -m pip install --user --break-system-packages -r requirements-dev.txt   # pytest, ruff
```

Ensure `python` resolves to `python3` (e.g. `alias python=python3` in `~/.zshrc`).
On Homebrew Python 3.14, add user scripts to PATH: `export PATH="$HOME/Library/Python/3.14/bin:$PATH"`.

---

## Overview

The repo has two stacks:

| Stack | Location | Primary verification |
|-------|----------|----------------------|
| **Website** | `src/`, Astro + TypeScript | `npm run lint`, `npm run build` |
| **Automation** | `scripts/`, Python 3.11 | `pytest`, `ruff` (local only today) |

`README.md` is the **source of truth** for directory listings. Most scripts derive
machine-readable exports or run the submission pipeline. MDX detail pages are
**committed to git** — they are not regenerated on every deploy.

**Git tracking for generated files:**

| File | Tracked in git | Regenerated on deploy |
|------|----------------|----------------------|
| `public/clouds.json` | Yes | Yes |
| `public/watchlist.json` | Yes | Yes |
| `public/llms.txt`, `public/llms-full.txt` | No (`.gitignore`) | Yes |
| `docs/llms.txt`, `docs/llms-full.txt` | No (`.gitignore`) | Legacy copies only |

---

## Script inventory

### Submission pipeline

| Script | Purpose | Triggered by |
|--------|---------|--------------|
| `check_duplicates.py` | Blocks re-submission of services already in `clouds.json`; flags watchlist re-submissions without blocking | `evaluate-submission.yml` |
| `evaluate_submission.py` | Evaluates a URL against 3 inclusion criteria (pricing, self-service, SLA/status). Uses fetch cascade → Claude WebSearch fallback | `evaluate-submission.yml`, `split-submission.yml`, `admin-approve-submission.yml` |
| `split_submission.py` | Splits multi-URL issues into child issues; evaluates each inline; opens PRs for passing scores | `split-submission.yml` |
| `create_submission_pr.py` | Inserts README entry (alphabetical), generates draft MDX via `generate_cloud_profile.py`, opens PR | `evaluate-submission.yml`, `split-submission.yml`, `admin-approve-submission.yml` |

**Key env vars (submission):** `ISSUE_BODY`, `ISSUE_NUMBER`, `GH_TOKEN`, `REPO`, `ANTHROPIC_API_KEY`

**Outputs:** `evaluation_results.md`, `evaluation_score.txt`, `submission_data.json`, optional `src/content/clouds/<slug>.mdx`

**Run locally — duplicate check:**

```bash
cd "$(git rev-parse --show-toplevel)"

export ISSUE_BODY="$(cat <<'EOF'
This issue was automatically created via the submission form.

1. https://neon.tech
EOF
)"
export ISSUE_NUMBER=999
export REPO="datum-cloud/awesome-alt-clouds"
export GH_TOKEN="${GH_TOKEN:-}"   # optional locally; required for GitHub API comments

python scripts/check_duplicates.py
```

**Run locally — evaluate a submission URL:**

```bash
cd "$(git rev-parse --show-toplevel)"

export ISSUE_BODY="$(cat <<'EOF'
This issue was automatically created via the submission form.

1. https://neon.tech
EOF
)"
export ISSUE_NUMBER=999
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY}"

python scripts/evaluate_submission.py

# Inspect outputs
cat evaluation_score.txt
head -40 evaluation_results.md
test -f submission_data.json && cat submission_data.json
```

**Run locally — create PR from evaluation output (needs git + gh CLI):**

```bash
cd "$(git rev-parse --show-toplevel)"

# Requires submission_data.json from evaluate_submission.py above
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY}"
export GH_TOKEN="${GH_TOKEN:?set GH_TOKEN}"

python scripts/create_submission_pr.py
```

**Run locally — split multi-URL issue (needs gh CLI + API key):**

```bash
cd "$(git rev-parse --show-toplevel)"

export ISSUE_BODY="$(cat <<'EOF'
This issue was automatically created via the submission form.

1. https://neon.tech
2. https://render.com
EOF
)"
export ISSUE_NUMBER=999
export REPO="datum-cloud/awesome-alt-clouds"
export GH_TOKEN="${GH_TOKEN:?set GH_TOKEN}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY}"

python scripts/split_submission.py
```

---

### MDX profile generation (Phase 2a)

| Script | Purpose | Triggered by |
|--------|---------|--------------|
| `generate_cloud_profile.py` | Fetches provider site → Claude Sonnet → writes `src/content/clouds/<slug>.mdx` with `status: draft` | Called by `create_submission_pr.py`; also runnable standalone |
| `backfill_profiles.py` | Batch driver: reads `public/clouds.json`, skips existing MDX, processes up to `BATCH_SIZE` clouds | `backfill-profiles.yml` (`workflow_dispatch` only) |

**Key env vars:** `CLOUD_NAME`, `CLOUD_URL`, `CLOUD_SCORE`, `CLOUD_CATEGORIES`, `CLOUD_DESCRIPTION`, `OUTPUT_PATH`, `ANTHROPIC_API_KEY`, `DRY_RUN`

**Important behaviors:**

- Refuses to overwrite an existing MDX file (protects human `status: reviewed` edits)
- Requires `ANTHROPIC_API_KEY` and live API calls (not suitable for routine CI)
- Only **5 sample MDX files** exist today; most listed clouds have no detail page yet

**Not part of deploy:** `deploy-pages.yml` does **not** run these scripts. MDX is version-controlled.

**Run locally — dry-run single profile (stdout only, no API write):**

```bash
cd "$(git rev-parse --show-toplevel)"

DRY_RUN=true \
CLOUD_NAME="Neon" \
CLOUD_URL="https://neon.tech" \
CLOUD_SCORE="3" \
CLOUD_CATEGORIES="Databases & Storage" \
CLOUD_DESCRIPTION="Serverless Postgres." \
OUTPUT_PATH="/tmp/neon-test.mdx" \
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY}" \
python scripts/generate_cloud_profile.py
```

**Run locally — write a draft MDX file:**

```bash
cd "$(git rev-parse --show-toplevel)"

CLOUD_NAME="Neon" \
CLOUD_URL="https://neon.tech" \
CLOUD_SCORE="3" \
CLOUD_CATEGORIES="Databases & Storage" \
CLOUD_DESCRIPTION="Serverless Postgres." \
OUTPUT_PATH="src/content/clouds/neon-test.mdx" \
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY}" \
python scripts/generate_cloud_profile.py

# Remove test file when done
rm -f src/content/clouds/neon-test.mdx profile_generation_report.json
```

**Run locally — backfill dry-run (list candidates, no API calls):**

```bash
cd "$(git rev-parse --show-toplevel)"

DRY_RUN=true BATCH_SIZE=5 SCORE_FILTER=3 python scripts/backfill_profiles.py
```

**Run locally — backfill batch (live API, writes MDX):**

```bash
cd "$(git rev-parse --show-toplevel)"

BATCH_SIZE=5 \
SCORE_FILTER=3 \
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY}" \
python scripts/backfill_profiles.py

cat backfill_summary.json
```

---

### Data generation (deploy pipeline)

| Script | Input | Output | Triggered by |
|--------|-------|--------|--------------|
| `parse_readme_to_json.py` | `README.md` | `public/clouds.json` (+ `dateAdded` from git history) | `deploy-pages.yml` |
| `generate_llms.py` | `public/clouds.json` | `public/llms.txt`, `public/llms-full.txt` | `deploy-pages.yml` |
| `generate_watchlist_json.py` | `WATCHLIST.md` | `public/watchlist.json` | `deploy-pages.yml`, `watchlist.yml` |

**Run locally — full data regen (mirrors deploy-pages.yml Python steps):**

```bash
cd "$(git rev-parse --show-toplevel)"

python scripts/parse_readme_to_json.py README.md public/clouds.json
python scripts/generate_llms.py public/clouds.json public/
python scripts/generate_watchlist_json.py
```

**Individual commands:**

```bash
cd "$(git rev-parse --show-toplevel)"

python scripts/parse_readme_to_json.py README.md public/clouds.json
python scripts/generate_llms.py public/clouds.json public/
python scripts/generate_llms.py                                    # defaults: public/clouds.json → public/
python scripts/generate_watchlist_json.py                          # reads WATCHLIST.md → public/watchlist.json
```

Never hand-edit `public/clouds.json` or `public/llms*.txt` — regenerate from source files.

---

### Watchlist

| Script | Purpose | Triggered by |
|--------|---------|--------------|
| `watchlist_add.py` | Adds a declined (score 1/3) submission to `WATCHLIST.md` | `watchlist.yml` |

**Run locally (needs GitHub API access to read issue comments):**

```bash
cd "$(git rev-parse --show-toplevel)"

export ISSUE_NUMBER=123
export GITHUB_REPOSITORY="datum-cloud/awesome-alt-clouds"
export GH_TOKEN="${GH_TOKEN:?set GH_TOKEN}"

python scripts/watchlist_add.py
python scripts/generate_watchlist_json.py
```

---

### Legacy / ancillary

| Script | Purpose | Triggered by |
|--------|---------|--------------|
| `update_blog_posts.mjs` | Fetches Datum blog posts from Strapi; updates Resources modal in `docs/index.html` | `update-blog-posts.yml` (daily cron + `workflow_dispatch`) |

**Run locally:**

```bash
cd "$(git rev-parse --show-toplevel)"

node scripts/update_blog_posts.mjs
```

---

## Shared libraries (`scripts/lib/`)

| Module | Purpose | Used by |
|--------|---------|---------|
| `fetcher.py` | Page-fetch cascade: Jina markdown → Jina HTML → direct `requests` | `evaluate_submission.py`, `generate_cloud_profile.py` |
| `slugify.py` | URL/name → slug (mirrors `src/lib/clouds.ts`) | `create_submission_pr.py`, `backfill_profiles.py`, `generate_cloud_profile.py` |

Not invoked directly — imported by the scripts above.

---

## Python dependencies

Install from repo root (user site-packages, no venv):

```bash
cd "$(git rev-parse --show-toplevel)"
python3 -m pip install --user --break-system-packages -r requirements.txt
python3 -m pip install --user --break-system-packages -r requirements-dev.txt
```

| Package | Used by |
|---------|---------|
| `requests` | Most scripts |
| `beautifulsoup4` | `fetcher.py`, `evaluate_submission.py` |
| `anthropic` | `evaluate_submission.py`, `generate_cloud_profile.py` |
| `pytest` | `tests/` |
| `ruff` | Lint/format for `scripts/` and `tests/` (config in `pyproject.toml`) |

---

## Tests

| File | Covers |
|------|--------|
| `tests/test_check_duplicates.py` | `normalize_domain`, `normalize_name`, duplicate detection against `clouds.json` and GitHub issues (mocked) |
| `tests/test_evaluate_submission.py` | `fetch_page_with_fallback`, Claude WebSearch path, markdown generation (mocked) |

**Run all tests:**

```bash
cd "$(git rev-parse --show-toplevel)"
python -m pytest tests/ -v
```

**Run a single test file or test case:**

```bash
cd "$(git rev-parse --show-toplevel)"
python -m pytest tests/test_check_duplicates.py -v
python -m pytest tests/test_evaluate_submission.py::TestFetchPageWithFallback -v
```

**CI status:** `pytest` is **not** run in GitHub Actions today.

---

## Ruff (Python lint & format)

Configured in `pyproject.toml` for `scripts/` and `tests/`:

```bash
cd "$(git rev-parse --show-toplevel)"

ruff check scripts tests
ruff format --check scripts tests   # check only
ruff format scripts tests           # auto-fix formatting
```

**CI status:** Ruff is **not** run in GitHub Actions today (unlike ESLint/Prettier for the frontend).

---

## What CI runs today

| Workflow | Checks |
|----------|--------|
| `lint.yml` | `npm run lint` (ESLint + `astro check`), `npm run format:check` (Prettier) |
| `deploy-pages.yml` | Regen JSON/llms/watchlist + `npm run build` (on PRs: build only; deploy on push to main) |
| Submission workflows | Production pipeline on issue events — **not** a PR quality gate |

**Not in CI:** `pytest`, `ruff check`, `ruff format --check`, E2E browser tests.

**Run CI-equivalent checks locally:**

```bash
cd "$(git rev-parse --show-toplevel)"

npm ci
npm run lint
npm run format:check
python scripts/parse_readme_to_json.py README.md public/clouds.json
python scripts/generate_llms.py public/clouds.json public/
python scripts/generate_watchlist_json.py
npm run build
```

---

## Practical local "full test" checklist

Use this before opening a PR. Steps 1–4 need no API keys. Copy and run as one block:

```bash
cd "$(git rev-parse --show-toplevel)"
set -euo pipefail

# 1. Dependencies
npm ci
python3 -m pip install --user --break-system-packages -r requirements-dev.txt

# 2. Static analysis — frontend
npm run lint
npm run format:check

# 2. Static analysis — Python
ruff check scripts tests
ruff format --check scripts tests

# 3. Unit tests
python -m pytest tests/ -v

# 4. Build pipeline (mirrors deploy-pages.yml)
python scripts/parse_readme_to_json.py README.md public/clouds.json
python scripts/generate_llms.py public/clouds.json public/
python scripts/generate_watchlist_json.py
npm run build

echo "Full test passed."
```

**Optional — manual smoke after build:**

```bash
cd "$(git rev-parse --show-toplevel)"
npm run preview
# Open http://localhost:4321
```

### What this checklist intentionally excludes

| Excluded | Reason |
|----------|--------|
| `generate_cloud_profile.py` | Requires `ANTHROPIC_API_KEY`; generates new content, not verification |
| `backfill_profiles.py` | Batch API job; use `DRY_RUN=true` only when testing that pipeline specifically |
| Submission workflow scripts end-to-end | Needs GitHub issue context + secrets |

---

## MDX build validation (via `npm run build`)

Existing MDX files are validated at build time:

- **Zod schema** in `src/content.config.ts` (`status: "draft" | "reviewed"`)
- **Orphan check** in `src/lib/profile.ts` — MDX without a matching slug in `clouds.json` fails the build
- **Publish gate** in `src/lib/profile.ts`:
  - Production (`site.config.mjs` → `preview: false`): only `status: reviewed` pages are built and linked
  - Preview (`preview: true`): draft + reviewed pages are built (fork/staging deploys)

Current MDX files: `cloudflare`, `digital-ocean`, `hetzner`, `neon`, `render` under `src/content/clouds/`.

---

## End-to-end flow (submission → MDX)

See [2026-05-22-submission-to-mdx-flow.md](./2026-05-22-submission-to-mdx-flow.md) for the full diagram. Short version:

```
submit form → GitHub issue → check_duplicates → evaluate_submission
  → (score ≥ 2) create_submission_pr → README + draft MDX → PR
  → merge → deploy-pages (JSON/llms/build) → maintainer flips draft → reviewed
```

---

## Suggested CI improvements (not implemented)

1. Add `test.yml`: `pytest tests/ -v` + `ruff check` + `ruff format --check`
2. Add `requirements.txt` or `[project.dependencies]` in `pyproject.toml`
3. Add `npm run test` script wrapping pytest for discoverability
4. Optional: Playwright smoke tests for `/`, `/submit/`, `/watchlist/`, detail pages
