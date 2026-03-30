# Design: Submission Validation Improvement

**Date:** 2026-03-30
**Status:** Approved
**Scope:** `scripts/evaluate_submission.py` only — no changes to workflows, PR creation, or admin commands

---

## Problem

The submission validation bot fails silently on ~80%+ of modern cloud sites due to Cloudflare protection, WAFs, and JS-rendered SPAs. When scraping fails, the bot:

- Hardcodes `score=2` and sets `needs_manual_review=True`
- Outputs all three criteria as "couldn't verify (site protected)"
- Gives the admin no actionable information

The result: nearly every submission lands in `needs-review` with an empty evaluation, creating a manual bottleneck that defeats the purpose of automation.

---

## Goal

When scraping fails, the evaluation comment should still provide:
- **Evidence URLs** (actual links to pricing page, status page, signup)
- **A one-line recommendation** ("Pricing and status page found — looks legit" / "No SLA evidence found — review carefully")

The admin's review time drops from "open the site, look around, decide" to "click two links, confirm, approve."

---

## Architecture

Three-stage fetch cascade, from cheapest to most expensive:

```
Stage 1: requests (current scraper, free)
    ✗ fails →
Stage 2: Jina Reader (r.jina.ai/{url}, free, handles JS/rendering)
    ✗ fails →
Stage 3: Claude web_search (API cost, last resort only)
```

Claude only fires when both scrapers fail, keeping API costs minimal.

---

## Component Changes

### 1. `fetch_page()` → `fetch_page_with_fallback(url)`

Replace the current `fetch_page(url)` with a wrapper that:

1. Tries existing `requests`-based scraping (unchanged logic)
2. If that returns `None`, tries Jina Reader via `GET https://r.jina.ai/{url}` with the same timeout/retry settings
3. Returns `(soup, final_url, fetch_method)` where `fetch_method` is `"requests"`, `"jina"`, or `None`

Jina Reader returns rendered markdown; parse it into a BeautifulSoup object (using `html.parser` on the raw text) so all existing `check_pricing_page()`, `check_self_service()`, and `check_production_indicators()` functions work without modification.

### 2. New `evaluate_with_claude_websearch(url)` function

Called only when `fetch_method is None` (both scrapers failed). Uses the existing `anthropic` client with the `web_search` tool enabled. Single API call that returns a dict:

```python
{
    "criteria": [
        {"name": "Transparent Public Pricing", "passed": True, "evidence": "https://stripe.com/pricing"},
        {"name": "Usage-based Self-Service",    "passed": True, "evidence": "https://stripe.com/register"},
        {"name": "Production Indicators",       "passed": True, "evidence": "https://status.stripe.com"},
    ],
    "score": 3,
    "recommendation": "Pricing and status page found — looks legit",
    "name": "Stripe",
    "description": "Payment infrastructure for the internet...",
    "category": "Monetization & Billing Clouds",
    "fetch_method": "claude_websearch",
}
```

The prompt instructs Claude to:
- Search for `{domain} pricing`, `{domain} status page`, `{domain} sign up`
- Return the actual URLs found as evidence (not just "found" / "not found")
- Assess each criterion based on what it finds
- Generate name, description (≤200 chars), and category from the valid categories list
- Write a one-line recommendation

If Claude cannot find evidence for a criterion, `passed` is `False` and `evidence` is `"Not found via web search"`.

### 3. Updated evaluation comment template

When `fetch_method == "claude_websearch"`, the comment renders:

- **Recommendation line** at the top, bolded (e.g., `> 🔍 Pricing and status page found — looks legit`)
- Criteria table with evidence URLs as clickable Markdown links
- A `🔍 Verified via web search` note in the score line

Example comment fragment:
```markdown
> 🔍 Pricing and status page found — looks legit

**Score:** 3/3 :green_circle: Ready to Merge *(verified via web search)*

| Criteria | Status | Evidence |
|---|---|---|
| Transparent Public Pricing | ✅ | [stripe.com/pricing](https://stripe.com/pricing) |
| Usage-based Self-Service | ✅ | [stripe.com/register](https://stripe.com/register) |
| Production Indicators | ✅ | [status.stripe.com](https://status.stripe.com) |
```

No changes to how `fetch_method == "requests"` or `"jina"` comments are rendered.

---

## What Does NOT Change

- `create_submission_pr.py`
- All GitHub Actions workflows (`.github/workflows/`)
- The `/approve` admin command
- Issue labels and labeling logic
- The `generate_metadata_with_claude()` function path (still used when Jina succeeds and metadata is needed)

---

## Error Handling

- If Jina Reader returns a non-200 or times out: fall through to Claude web search
- If Claude web search fails (API error, rate limit): fall back to the current `fetch_failed` behavior (score=2, all criteria "couldn't verify") — no regression from today
- If Claude returns malformed JSON: same fallback

---

## Testing

Manual test cases to verify before merging:

1. A site that currently passes scraping — behavior unchanged
2. A well-known site blocked by Cloudflare (e.g., a major SaaS) — Jina succeeds, existing criteria checks run
3. A site that blocks both scrapers — Claude web search fires, comment shows evidence URLs and recommendation
4. An unknown/obscure URL — Claude web search fires but finds nothing — comment shows "Not found via web search" and score ≤ 1
