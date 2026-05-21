#!/usr/bin/env python3
"""Add a declined submission to WATCHLIST.md.

Required env vars:
  ISSUE_NUMBER              - GitHub issue number
  GH_TOKEN or GITHUB_TOKEN  - GitHub token for API access
  REPO or GITHUB_REPOSITORY - GitHub repo in owner/name format
"""

import os
import re
import sys
import requests
from datetime import date

WATCHLIST_FILE = "WATCHLIST.md"
TABLE_SEP_PREFIX = "|------|-----|"


def get_comments(repo, issue_number, token):
    headers = {"Authorization": f"token {token}"}
    r = requests.get(
        f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
        headers=headers,
    )
    r.raise_for_status()
    return r.json()


def parse_evaluation(comments):
    for comment in comments:
        body = comment.get("body", "")
        if "Evaluation Results" not in body:
            continue

        name_m = re.search(r"###\s+(.+)", body)
        url_m = re.search(r"\*\*URL:\*\*\s*(https?://[^\s\n]+)", body)
        score_m = re.search(r"\*\*Score:\*\*\s*(\d)/3", body)
        cat_m = re.search(r"\*\*Category:\*\*\s*(.+)", body)

        failed = []
        for line in body.split("\n"):
            if ":x:" not in line and "❌" not in line:
                continue
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2 and (":x:" in parts[1] or "❌" in parts[1]):
                criteria_name = parts[0]
                if criteria_name and criteria_name.lower() != "status":
                    failed.append(criteria_name)

        return {
            "name": name_m.group(1).strip() if name_m else None,
            "url": url_m.group(1).strip() if url_m else None,
            "score": score_m.group(1) if score_m else "?",
            "category": cat_m.group(1).strip() if cat_m else "To be determined",
            "failed": failed,
        }
    return {}


def add_to_watchlist(name, url, category, reason, criteria, today):
    with open(WATCHLIST_FILE) as f:
        content = f.read()

    url_base = url.rstrip("/")
    if url_base in content:
        print(f"  {url} already in watchlist — skipping.")
        return False

    sep_pos = content.find(TABLE_SEP_PREFIX)
    if sep_pos == -1:
        print(f"ERROR: Could not find table separator in {WATCHLIST_FILE}")
        sys.exit(1)

    # Find end of the separator line
    newline_pos = content.index("\n", sep_pos)
    new_row = f"\n| {name} | {url} | {category} | {today} | {reason} | {criteria} | {today} |"
    content = content[:newline_pos] + new_row + content[newline_pos:]

    with open(WATCHLIST_FILE, "w") as f:
        f.write(content)

    print(f"  Added {name} ({url}) to watchlist.")
    return True


def main():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("REPO") or os.environ.get("GITHUB_REPOSITORY")
    issue_number = os.environ.get("ISSUE_NUMBER")

    if not all([token, repo, issue_number]):
        print("ERROR: Required env vars: GH_TOKEN, REPO (or GITHUB_REPOSITORY), ISSUE_NUMBER")
        sys.exit(1)

    print(f"Processing issue #{issue_number} in {repo}")
    comments = get_comments(repo, issue_number, token)
    data = parse_evaluation(comments)

    if not data.get("url"):
        print("ERROR: No evaluation comment found or could not parse URL. "
              "Ensure the bot has evaluated this issue before running /watchlist.")
        sys.exit(1)

    name = data["name"] or f"Issue #{issue_number}"
    url = data["url"]
    category = data.get("category", "To be determined")
    score = data.get("score", "?")
    failed = data.get("failed", [])

    if failed:
        reason = f"Score {score}/3: {'; '.join(c.lower() for c in failed)}"
        criteria = "; ".join(failed)
    else:
        reason = f"Score {score}/3: criteria not met"
        criteria = "See evaluation results"

    today = date.today().isoformat()
    added = add_to_watchlist(name, url, category, reason, criteria, today)

    # Write name for use in commit message
    with open("/tmp/watchlist_name.txt", "w") as f:
        f.write(name)

    if not added:
        # Nothing changed — signal to workflow to skip commit
        with open("/tmp/watchlist_changed.txt", "w") as f:
            f.write("false")
    else:
        with open("/tmp/watchlist_changed.txt", "w") as f:
            f.write("true")


if __name__ == "__main__":
    main()
