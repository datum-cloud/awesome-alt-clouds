#!/usr/bin/env python3
"""Create a PR that moves a graduated service to its real category.

Reads graduation_data.json (written by evaluate_graduation.py) and opens a
PR that removes the entry from its current "Emerging & Unverified
Providers" bullet and re-inserts it, alphabetically, into the category it
now qualifies for.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from lib.readme_entries import (  # noqa: E402
    add_entry_to_readme,
    badge_for_score,
    find_entry_by_name,
    remove_entry_from_readme,
)
from lib.shell import run_command  # noqa: E402
from lib.slugify import slugify  # noqa: E402

README_FILE = "README.md"


def load_graduation_data():
    with open("graduation_data.json") as f:
        return json.load(f)


def move_entry_in_readme(data):
    """Remove the old bullet and insert the corrected one. Returns True on success."""
    with open(README_FILE) as f:
        content = f.read()

    entry = find_entry_by_name(content, data["name"])
    if entry is None:
        print(f"Warning: '{data['name']}' not found in README, nothing to graduate")
        return False

    if entry["category"] != data["old_category"]:
        print(
            f"Warning: '{data['name']}' is now in '{entry['category']}', "
            f"not '{data['old_category']}' — README changed since evaluation, skipping"
        )
        return False

    content = remove_entry_from_readme(content, entry["line_idx"])

    submission = {
        "name": data["name"],
        "url": data["url"],
        "category": data["new_category"],
        "score": data["score"],
        "description": data["description"],
    }
    new_content = add_entry_to_readme(submission, content=content)
    if new_content is None:
        print(f"Warning: target category '{data['new_category']}' not found in README")
        return False

    with open(README_FILE, "w") as f:
        f.write(new_content)

    return True


def create_pr(data):
    name = data["name"]
    issue_number = data.get("issue_number", "unknown")
    branch_name = f"graduation-{issue_number}-{slugify(name)[:30]}"

    run_command('git config user.name "github-actions[bot]"')
    run_command('git config user.email "github-actions[bot]@users.noreply.github.com"')
    run_command(f"git checkout -b {branch_name}")

    if not move_entry_in_readme(data):
        return False

    run_command("git add README.md")

    commit_msg = (
        f"Graduate {name} from {data['old_category']} to {data['new_category']}"
        f"\\n\\nCloses #{issue_number}"
    )
    run_command(f'git commit -m "{commit_msg}"')
    run_command(f"git push --force origin {branch_name}")

    existing_pr = run_command(
        f'gh pr list --head {branch_name} --state open --json number --jq ".[0].number"',
        check=False,
    )
    if existing_pr.strip():
        print(
            f"PR #{existing_pr.strip()} already exists for branch {branch_name}, skipping creation"
        )
        return True

    badge = badge_for_score(data["score"])
    pr_title = f"Graduate {badge} {name} from {data['old_category']} to {data['new_category']}"

    review_note = " ⚠️ needs verification" if data.get("needs_manual_review") else ""
    pr_body = f"""## Graduation Request

This PR moves **{name}** from **{data["old_category"]}** to **{data["new_category"]}**.

| Field | Value |
|-------|-------|
| Name | {name} |
| URL | {data["url"]} |
| From | {data["old_category"]} |
| To | {data["new_category"]} |
| Score | {data["score"]}/3 {badge}{review_note} |
| Description | {data["description"]} |

If a `src/content/clouds/` profile exists for this service, its `category`
frontmatter may need a follow-up update to match — this bot only edits
README.md.

Closes #{issue_number}

*This PR was automatically created by the graduation-request bot.*
"""

    pr_body_escaped = pr_body.replace('"', '\\"').replace("`", "\\`")
    result = run_command(
        f'gh pr create --title "{pr_title}" --body "{pr_body_escaped}" --base main --head {branch_name}'
    )
    print(f"PR creation result: {result}")
    return True


def main():
    try:
        data = load_graduation_data()
    except FileNotFoundError:
        print("No graduation_data.json found, skipping PR creation")
        return 0

    print(
        f"Creating graduation PR for {data['name']} ({data['old_category']} -> {data['new_category']})"
    )

    try:
        create_pr(data)
        print("PR created successfully!")
        return 0
    except Exception as e:
        print(f"Error creating PR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
