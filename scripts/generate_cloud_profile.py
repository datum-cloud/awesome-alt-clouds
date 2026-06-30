#!/usr/bin/env python3
"""
Generate a draft MDX profile for a cloud provider.

Env vars (required unless noted):
  CLOUD_NAME        — e.g. "Neon"
  CLOUD_URL         — e.g. "https://neon.tech"
  CLOUD_SCORE       — "2" or "3" (default: "3")
  CLOUD_CATEGORIES  — comma-separated, e.g. "Databases & Storage"
  CLOUD_DESCRIPTION — one-line description from clouds.json
  OUTPUT_PATH       — defaults to src/content/clouds/<slug>.mdx
  LLM_PROVIDER      — "claude" (default) or "qwen"
  ANTHROPIC_API_KEY — Claude API key (required when LLM_PROVIDER=claude)
  QWEN_BASE_URL     — self-hosted Qwen endpoint (OpenAI-compatible, required when LLM_PROVIDER=qwen)
  DRY_RUN           — if "true", print MDX to stdout instead of writing file

On success (non-dry-run), writes:
  - <OUTPUT_PATH> — the MDX file (starts with status: draft)
  - profile_generation_report.json — { slug, fetch_method, output_path, needs_verification }
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

from lib.fetcher import fetch_page_with_fallback
from lib.slugify import slugify

PROFILE_MAX_TOKENS = 2048
QWEN_MODEL = "qwen3.6-35b-a3b"
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# Set LLM_PROVIDER=qwen to use the self-hosted Qwen endpoint instead of Claude.
# Defaults to claude. The corresponding secret (ANTHROPIC_API_KEY or
# QWEN_BASE_URL) must be present for the selected provider.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "claude").lower()

PROFILE_SYSTEM_PROMPT = (
    "You are a technical writer creating cloud provider profiles for alt-cloud.org — "
    "a curated directory of alternative cloud providers that compete with AWS, GCP, and Azure.\n\n"
    "You write clear, accurate, developer-focused profiles. You cite concrete pricing numbers "
    "and region lists when you find them. You do not invent facts. If you cannot find specific "
    "data (e.g. exact founding year), omit that field rather than guessing.\n\n"
    "Your output is a YAML frontmatter block followed by Markdown body sections."
)


def build_profile_prompt(
    name: str,
    url: str,
    score: int,
    categories: list[str],
    description: str,
    page_text: str,
) -> str:
    has_content = len(page_text.strip()) > 200
    content_block = (
        f"\n\nPage content (first 12000 chars):\n{page_text[:12000]}" if has_content else ""
    )

    criteria_note = (
        "This provider meets all 3 inclusion criteria "
        "(transparent pricing, self-service signup, public SLA/status page)."
        if score == 3
        else "This provider meets 2 of 3 inclusion criteria "
             "(transparent pricing, self-service signup, public SLA/status page)."
    )

    return f"""Generate a cloud provider profile for the alt-cloud.org directory.

Provider: {name}
URL: {url}
Categories: {', '.join(categories)}
One-line description: {description}
Inclusion score: {score}/3. {criteria_note}{content_block}

---

OUTPUT FORMAT — return ONLY valid YAML frontmatter + Markdown, nothing else:

---
tagline: "<one sentence that captures the provider's core value proposition, ≤ 120 chars>"
headquarters: "<City, State/Country>" # omit if unknown
foundedYear: <YYYY> # omit if unknown
pricingModel: <hourly|monthly|usage-based|subscription|mixed>
openSource: <true|false> # omit if unknown
regions:
  - "<Region name>" # list all data center regions you found; omit section if none found
services:
  - "<Service name>" # list 4–10 key product offerings; omit section if none found
socials:
  website: "{url}"
  x: "<https://twitter.com/handle>" # omit if not found
  linkedin: "<https://linkedin.com/company/...>" # omit if not found
  github: "<https://github.com/org>" # omit if not found
---

## What makes {name} different

[2–3 paragraphs on the provider's core differentiator vs hyperscalers. Be specific. Mention architecture or design decisions if notable.]

## Pricing model

[Specific pricing tiers with actual numbers if found. If no numbers available, describe the model qualitatively. End with what makes it stand out vs typical cloud pricing.]

## When it fits

[3–5 bullet points describing ideal use cases for this provider.]

## When it doesn't

[1–2 sentences or bullet points on workload types that are a poor fit.]

## Inclusion criteria

[State which of the 3 criteria (transparent pricing / self-service signup / public SLA or status page) this provider meets. Link to specific pages found.]

RULES:
- Omit any frontmatter field you cannot fill with real data (do not guess or invent).
- Do not add an "## Open source" section unless openSource is true.
- Keep the body under 600 words total.
- Do not wrap the output in additional code fences — return the raw MDX starting with ---.
"""


def _strip_outer_code_fences(text: str) -> str:
    """If Claude wrapped the output in ```mdx ... ```, strip the fences."""
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    if not lines:
        return text
    # drop opening fence
    body = lines[1:]
    if body and body[-1].strip() == "```":
        body = body[:-1]
    return "\n".join(body)


def _prepend_status_draft(mdx: str) -> str:
    """Insert `status: draft` as the first frontmatter field. Idempotent."""
    if not mdx.startswith("---"):
        return mdx
    if "\nstatus:" in mdx.split("---", 2)[1] if mdx.count("---") >= 2 else False:
        return mdx
    return "---\nstatus: draft\n" + mdx[3:].lstrip("\n")


def _call_qwen_for_profile(user_prompt: str) -> tuple[str, bool]:
    """Call the self-hosted Qwen endpoint. Returns (raw_text, truncated)."""
    base_url = os.environ.get("QWEN_BASE_URL")
    if not base_url:
        print("ERROR: QWEN_BASE_URL not set", file=sys.stderr)
        sys.exit(1)

    import openai

    client = openai.OpenAI(base_url=base_url, api_key="not-needed")

    print(f"Calling Qwen ({QWEN_MODEL})...")
    message = client.chat.completions.create(
        model=QWEN_MODEL,
        max_tokens=PROFILE_MAX_TOKENS,
        messages=[
            {"role": "system", "content": PROFILE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )

    truncated = message.choices[0].finish_reason == "length"
    raw_text = (message.choices[0].message.content or "").strip()
    raw_text = re.sub(r'<think>[\s\S]*?</think>', '', raw_text).strip()
    return raw_text, truncated


def _call_claude_for_profile(user_prompt: str) -> tuple[str, bool]:
    """Call the Claude API. Returns (raw_text, truncated)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    print(f"Calling Claude ({CLAUDE_MODEL})...")
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=PROFILE_MAX_TOKENS,
        system=PROFILE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    truncated = message.stop_reason == "max_tokens"
    raw_text = (message.content[0].text if message.content else "").strip()
    return raw_text, truncated


def generate_profile(
    name: str,
    url: str,
    score: int,
    categories: list[str],
    description: str,
) -> dict:
    """Fetch the page and call the selected LLM. Returns {mdx, fetch_method, slug}."""
    print(f"Fetching {url}...")
    soup, _final_url, fetch_method = fetch_page_with_fallback(url)
    page_text = soup.get_text(separator="\n", strip=True) if soup else ""
    print(f"Fetch method: {fetch_method or 'failed'}, content length: {len(page_text)}")

    user_prompt = build_profile_prompt(
        name, url, score, categories, description, page_text
    )

    if LLM_PROVIDER == "qwen":
        mdx_raw, truncated = _call_qwen_for_profile(user_prompt)
    else:
        mdx_raw, truncated = _call_claude_for_profile(user_prompt)

    if truncated:
        print(
            f"WARNING: Response hit max_tokens ({PROFILE_MAX_TOKENS}) for {name} — "
            "output may be truncated. Review the MDX before publishing.",
            file=sys.stderr,
        )

    mdx_raw = _strip_outer_code_fences(mdx_raw)
    mdx_raw = _prepend_status_draft(mdx_raw)

    return {
        "mdx": mdx_raw,
        "fetch_method": fetch_method or "failed",
        "slug": slugify(name),
        "truncated": truncated,
    }


def main():
    name = os.environ.get("CLOUD_NAME")
    url = os.environ.get("CLOUD_URL")
    if not name or not url:
        print("ERROR: CLOUD_NAME and CLOUD_URL are required", file=sys.stderr)
        sys.exit(1)

    score = int(os.environ.get("CLOUD_SCORE", "3"))
    categories = [
        c.strip() for c in os.environ.get("CLOUD_CATEGORIES", "").split(",") if c.strip()
    ]
    description = os.environ.get("CLOUD_DESCRIPTION", "")
    output_path = os.environ.get(
        "OUTPUT_PATH", f"src/content/clouds/{slugify(name)}.mdx"
    )
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"

    result = generate_profile(name, url, score, categories, description)

    if dry_run:
        print("\n" + "=" * 60)
        print(f"SLUG: {result['slug']}")
        print(f"FETCH METHOD: {result['fetch_method']}")
        print("=" * 60)
        print(result["mdx"])
        return

    if os.path.exists(output_path):
        print(f"SKIP: {output_path} already exists.")
        sys.exit(0)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        f.write(result["mdx"])
        if not result["mdx"].endswith("\n"):
            f.write("\n")

    print(f"Written: {output_path}")

    report = {
        "slug": result["slug"],
        "fetch_method": result["fetch_method"],
        "output_path": output_path,
        "truncated": result["truncated"],
        "needs_verification": result["fetch_method"] == "failed" or result["truncated"],
    }
    with open("profile_generation_report.json", "w") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
