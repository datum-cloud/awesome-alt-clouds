# Design: Submission Duplicate Detection

**Date:** 2026-03-31
**Status:** Approved
**Scope:** New `scripts/check_duplicates.py` + one new step in `.github/workflows/evaluate-submission.yml`

---

## Problem

Every submission triggers a full evaluation run: Jina Reader fetch, criteria checks, Claude API call, PR creation. Duplicate submissions (same service already listed, or submitted twice in parallel) waste CI minutes and API budget, and create noise in the issue tracker.

---

## Goal

When a new submission issue is opened, check for duplicates **before** evaluation starts. If a duplicate is found, short-circuit the job: post a clear comment, label the issue, close it (for exact matches), and prevent `evaluate_submission.py` from running.

---

## Duplicate Match Types

| Match Type | Condition | Action |
|---|---|---|
| Exact domain | Submitted URL domain == existing entry domain in `clouds.json` or GitHub Issues | Auto-close + `duplicate` label |
| Fuzzy name | Normalized submitted name matches existing entry name (contains/contained-by) | Comment + `duplicate` label + stop job |

Both match types set `is_duplicate=true` in GitHub Actions output, stopping all downstream steps.

**Domain normalisation:** strip `http(s)://`, strip `www.`, strip trailing path and query string. Example: `https://www.stripe.com/billing?ref=x` → `stripe.com`.

**Name normalisation:** lowercase, strip punctuation, remove noise words (`cloud`, `ai`, `labs`, `inc`, `io`, `the`, `platform`). Match if one normalised name contains the other. Example: `"ZeroTier Labs"` → `"zerotier"` matches existing `"ZeroTier"` → `"zerotier"`.

---

## Architecture

```
Issue opened (submission label)
    │
    ▼
Step: check_duplicates.py
    ├── Extract URL from issue body
    ├── Normalise to domain
    ├── Check exact domain in docs/clouds.json     → auto-close
    ├── Check fuzzy name in docs/clouds.json       → warn + stop
    ├── Check exact domain in GitHub Issues API    → auto-close
    └── No match → is_duplicate=false → continue
    │
    ▼ (only if is_duplicate=false)
Step: evaluate_submission.py   (unchanged)
Step: create_submission_pr.py  (unchanged)
```

---

## Component: `scripts/check_duplicates.py`

**Inputs (env vars):**
- `ISSUE_BODY` — full issue body text
- `ISSUE_NUMBER` — issue number for posting comments
- `ISSUE_TITLE` — issue title (used as fallback name when no URL parse yields a name)
- `GH_TOKEN` — GitHub token for API calls
- `REPO` — `owner/repo` string (e.g., `datum-cloud/awesome-alt-clouds`)

**Data sources:**
- `docs/clouds.json` — checked out in CI, 405 entries, each with `name`, `url`, `categories`
- GitHub Issues API: `GET /repos/{owner}/{repo}/issues?labels=submission&state=all&per_page=100` (paginate up to 500 issues)

**Output:**
- Writes `is_duplicate=true` or `is_duplicate=false` to `$GITHUB_OUTPUT`
- Writes `duplicate_reason=<string>` to `$GITHUB_OUTPUT` (for debugging/logging)

**Logic (in order):**

1. Extract URLs from issue body using the same regex logic as `evaluate_submission.py`
2. For each URL, normalise to domain
3. Load `docs/clouds.json`
4. For each entry in clouds.json:
   - Compare normalised domains → if match: `result = ("exact_domain", entry)`
   - If no domain match: compare normalised names → if match: `result = ("fuzzy_name", entry)`
5. If no clouds.json match: query GitHub Issues API, normalise each issue URL domain → if match: `result = ("existing_issue", issue)`
6. If `result` found: post comment, label, optionally close, write `is_duplicate=true`
7. If no match: write `is_duplicate=false`, exit 0

**Comment templates:**

Auto-close (exact domain match in clouds.json or issues):
```
⚠️ **Duplicate Submission**

This service is already included in the Awesome Alt Clouds list:
- **[{name}]({url})** — {description}

Closing this issue as a duplicate. If you believe this is a different
service or a significant update, please reopen with additional context.
```

Warn only (fuzzy name match):
```
⚠️ **Possible Duplicate**

A similar service may already be listed:
- **[{name}]({url})** — {description}

Proceeding with admin review, but flagging as a possible duplicate.
```

**GitHub API calls made:**
- `POST /repos/{repo}/issues/{number}/comments` — post comment
- `POST /repos/{repo}/issues/{number}/labels` — add `duplicate` label
- `PATCH /repos/{repo}/issues/{number}` — close issue (exact match only, set `state=closed`)

---

## Workflow Changes: `evaluate-submission.yml`

Add one new step **before** `Extract URL and evaluate`:

```yaml
- name: Check for duplicates
  id: check_duplicate
  env:
    ISSUE_BODY: ${{ github.event.issue.body }}
    ISSUE_NUMBER: ${{ github.event.issue.number }}
    ISSUE_TITLE: ${{ github.event.issue.title }}
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    REPO: ${{ github.repository }}
  run: |
    python scripts/check_duplicates.py
```

Add `if: steps.check_duplicate.outputs.is_duplicate != 'true'` to these existing steps:
- `Extract URL and evaluate`
- `Read evaluation outputs`
- `Post evaluation results`
- `Add result label`
- `Upload submission data as artifact`
- `Create PR if score >= 2`

---

## What Does NOT Change

- `scripts/evaluate_submission.py`
- `scripts/create_submission_pr.py`
- `.github/workflows/admin-approve-submission.yml`
- `.github/workflows/close-issue-on-pr-close.yml`
- Any other workflow or script

---

## Error Handling

- If `ISSUE_BODY` contains no URLs: skip duplicate check, write `is_duplicate=false`, continue to evaluation
- If `docs/clouds.json` cannot be read: log warning, write `is_duplicate=false`, continue (fail open)
- If GitHub Issues API call fails: log warning, skip issue-based check, continue with clouds.json check only
- All failures are non-fatal — duplicate detection must never block a legitimate submission

---

## Testing

Manual test cases before merging:

1. Submit a URL whose domain already exists in `clouds.json` → issue auto-closed, comment shows existing entry
2. Submit a URL with a similar name to an existing entry (different domain) → comment added, `duplicate` label applied, issue stays open
3. Submit a brand new URL not in the list → no duplicate action, evaluation proceeds normally
4. Submit the same URL twice (second issue) → second issue auto-closed pointing to first
5. `clouds.json` read failure (rename file in test) → evaluation proceeds normally (fail open)
