#!/usr/bin/env python3
"""Re-evaluate a [Graduation] request against its current README.md entry.

A graduation request asks the bot to re-check a service that's currently
flagged 🔵 Emerging & Unverified and, if it now clears the bar, remove that
badge (and re-file it if its best-fit category changed). Unlike a fresh
submission, the URL and current category come from the existing README.md
entry, not the issue body — the issue only tells us *which* entry to re-check.

Reads from the environment:
  ISSUE_BODY, ISSUE_TITLE, ISSUE_NUMBER  - required
  LLM_PROVIDER, ANTHROPIC_API_KEY, QWEN_BASE_URL - passed through to the
    shared evaluate_submission fetch/metadata cascade
  GRADUATION_ADMIN_APPROVED - 'true' when a maintainer ran /approve-graduation;
    bypasses the 2/3 gate so graduation_data.json is always written
  GRADUATION_CATEGORY_OVERRIDE - maintainer-specified target category,
    overrides whatever category the LLM suggests (defaults to the entry's
    current category when the LLM has no suggestion)

Writes:
  graduation_results.md - markdown comment for the issue
  graduation_score.txt  - fresh score (0-3), or '0' if the entry couldn't
    be located at all
  graduation_data.json  - present only when the request is ready to move
    (score >= 2, or admin-approved); includes refreshed tags
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

from evaluate_submission import (  # noqa: E402
    CATEGORIES,
    evaluate_service,
    generate_metadata,
    generate_single_result_markdown,
)
from lib.classification import normalize_classification  # noqa: E402
from lib.readme_entries import find_entry_by_name  # noqa: E402


def extract_service_name(title, body):
    """Determine which service this graduation request is about.

    Prefers the **Service:** markdown link the browser extension writes into
    the body (ground truth for the name as it appears on the site); falls
    back to the issue title (strip a leading "[Graduation]"/"[Graduation
    Request]" tag) if that field is missing or malformed.
    """
    match = re.search(r"\*\*Service:\*\*\s*\[([^\]]+)\]\(([^)]+)\)", body)
    if match:
        return match.group(1).strip()

    title_match = re.match(r"^\[Graduation(?:\s+Request)?\]\s*(.+)", title, re.IGNORECASE)
    if title_match:
        return title_match.group(1).strip()

    return None


def write_error(message):
    with open("graduation_results.md", "w") as f:
        f.write(f"## Graduation Request\n\n:warning: {message}\n")
    with open("graduation_score.txt", "w") as f:
        f.write("0")


def build_comment(name, old_category, result, ai_metadata, new_category):
    score = result["score"]
    header = (
        f"## Graduation Request: {name}\n\n"
        f"Re-evaluating this 🔵 **Emerging & Unverified** entry (currently under "
        f"**{old_category}**) against the 3 criteria.\n\n"
    )
    body = generate_single_result_markdown(result, ai_metadata)

    if score >= 2:
        move = (
            f" It would also move from **{old_category}** to **{new_category}**."
            if new_category and new_category != old_category
            else ""
        )
        next_steps = (
            f"\n:rocket: This looks ready to graduate — the 🔵 badge would be removed.{move} "
            "A maintainer can comment `/approve-graduation` (or `/approve-graduation <Category Name>` "
            "to pick a different category) to open the PR.\n"
        )
    else:
        next_steps = (
            "\nStill doesn't meet the bar for graduation (needs 2/3). It keeps the 🔵 badge "
            "until re-evaluated with new evidence.\n"
        )

    return header + body + next_steps


def main():
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_title = os.environ.get("ISSUE_TITLE", "")
    admin_approved = os.environ.get("GRADUATION_ADMIN_APPROVED", "").lower() == "true"
    category_override = os.environ.get("GRADUATION_CATEGORY_OVERRIDE", "").strip()

    if not issue_body or not issue_title:
        print("Error: ISSUE_BODY / ISSUE_TITLE environment variables not set")
        sys.exit(1)

    name = extract_service_name(issue_title, issue_body)
    if not name:
        write_error(
            "Could not determine which service this graduation request is about "
            "(no `**Service:**` field in the body and no name after the `[Graduation]` title tag)."
        )
        return

    with open("README.md") as f:
        readme_content = f.read()

    entry = find_entry_by_name(readme_content, name)
    if entry is None:
        write_error(
            f"Could not find an existing README.md entry named **{name}**. "
            "Graduation requests re-evaluate a service that's already listed — "
            "use the submission form for new services."
        )
        return

    if not entry["unverified"]:
        write_error(
            f"**{name}** (listed under **{entry['category']}**) isn't flagged 🔵 Emerging & "
            "Unverified — nothing to graduate."
        )
        return

    print(f"Re-evaluating {name} ({entry['url']}), currently in {entry['category']} (🔵)")
    result = evaluate_service(entry["url"])
    score = result["score"]

    ai_metadata = result.get("ai_metadata")
    if not ai_metadata:
        ai_metadata = generate_metadata(entry["url"], result.get("page_content", ""))
        if ai_metadata:
            result["ai_metadata"] = ai_metadata

    new_category = category_override or (ai_metadata.get("category") if ai_metadata else None)
    if new_category and new_category not in CATEGORIES:
        print(f"Warning: '{new_category}' is not a known category, ignoring override")
        new_category = ai_metadata.get("category") if ai_metadata else None
    # Graduating removes the badge; the category only changes when there's a better fit.
    new_category = new_category or entry["category"]
    # Tags must be valid for the category the entry will actually land in (the maintainer's
    # override or the current category can differ from the one the LLM tagged against).
    classified = {
        "category": new_category,
        "tags": (ai_metadata.get("tags") if ai_metadata else None) or entry["tags"],
    }
    normalize_classification(classified)

    comment = build_comment(name, entry["category"], result, ai_metadata, new_category)
    with open("graduation_results.md", "w") as f:
        f.write(comment)
    with open("graduation_score.txt", "w") as f:
        f.write(str(score))

    ready = admin_approved or score >= 2
    if ready and new_category:
        description = (
            ai_metadata.get("description", entry["description"])
            if ai_metadata
            else entry["description"]
        )
        graduation_data = {
            "issue_number": os.environ.get("ISSUE_NUMBER", "unknown"),
            "name": name,
            "url": entry["url"],
            "old_category": entry["category"],
            "new_category": new_category,
            "tags": classified["tags"],
            "score": score if not admin_approved else max(score, 2),
            "description": description,
            "needs_manual_review": result.get("needs_manual_review", False),
        }
        with open("graduation_data.json", "w") as f:
            json.dump(graduation_data, f, indent=2)
        print(f"Graduation data saved: {name} -> {new_category}")
    else:
        print(f"Not ready to graduate ({score}/3, category={new_category})")


if __name__ == "__main__":
    main()
