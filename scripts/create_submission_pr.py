#!/usr/bin/env python3
"""
Create a PR to add an approved submission to the README.md

Reads submission data from submission_data.json and creates a PR
that adds the service to the appropriate category in README.md.
"""

import json
import os
import re
import subprocess
import sys


def run_command(cmd, check=True):
    """Run a shell command and return output"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        raise Exception(f"Command failed: {cmd}")
    return result.stdout.strip()


def load_submission_data():
    """Load submission data from JSON file"""
    with open('submission_data.json', 'r') as f:
        return json.load(f)


def find_category_section(readme_content, category):
    """Find the start and end of a category section in README"""
    lines = readme_content.split('\n')

    # Find the category header
    category_header = f"## {category}"
    start_idx = None
    end_idx = None

    for i, line in enumerate(lines):
        if line.strip() == category_header:
            start_idx = i
        elif start_idx is not None and line.startswith('## ') and i > start_idx:
            end_idx = i
            break

    if start_idx is None:
        return None, None

    # If no next section found, go to end of file
    if end_idx is None:
        end_idx = len(lines)

    return start_idx, end_idx


def add_entry_to_readme(submission):
    """Add the submission entry to README.md in the correct category"""
    with open('README.md', 'r') as f:
        content = f.read()

    category = submission['category']
    start_idx, end_idx = find_category_section(content, category)

    if start_idx is None:
        print(f"Warning: Category '{category}' not found in README")
        return False

    lines = content.split('\n')

    # Determine badge based on score
    badge = '🟢' if submission['score'] == 3 else '🟡'

    # Create the new entry
    new_entry = f"* {badge} [{submission['name']}]({submission['url']}) - {submission['description']}"

    # Find all entries in this section (lines starting with "* ")
    entries = []
    insert_after_idx = start_idx

    for i in range(start_idx + 1, end_idx):
        line = lines[i].strip()
        if line.startswith('* '):
            entries.append((i, line))
            insert_after_idx = i

    # Find alphabetical position for new entry
    # Extract name for sorting (case-insensitive)
    new_name = submission['name'].lower()

    insert_idx = None
    for i, (line_idx, line) in enumerate(entries):
        # Extract name from entry: * 🟢 [Name](url) - desc
        match = re.search(r'\[([^\]]+)\]', line)
        if match:
            entry_name = match.group(1).lower()
            if new_name < entry_name:
                insert_idx = line_idx
                break

    # If not found, insert at end of section
    if insert_idx is None:
        insert_idx = insert_after_idx + 1

    # Insert the new entry
    lines.insert(insert_idx, new_entry)

    # Write back
    with open('README.md', 'w') as f:
        f.write('\n'.join(lines))

    return True


def create_pr(submission):
    """Create a branch and PR for the submission"""
    issue_number = submission.get('issue_number', 'unknown')
    branch_name = f"submission-{issue_number}-{submission['name'].lower().replace(' ', '-')[:30]}"

    # Configure git
    run_command('git config user.name "github-actions[bot]"')
    run_command('git config user.email "github-actions[bot]@users.noreply.github.com"')

    # Create and checkout new branch
    run_command(f'git checkout -b {branch_name}')

    # Add entry to README
    if not add_entry_to_readme(submission):
        print("Failed to add entry to README")
        return False

    # Commit changes
    run_command('git add README.md')

    badge = '🟢' if submission['score'] == 3 else '🟡'
    commit_msg = f"Add {submission['name']} to {submission['category']}\n\nCloses #{issue_number}"
    run_command(f'git commit -m "{commit_msg}"')

    # Push branch
    run_command(f'git push origin {branch_name}')

    # Create PR
    pr_title = f"Add {badge} {submission['name']} to {submission['category']}"
    pr_body = f"""## New Cloud Service Submission

This PR adds **{submission['name']}** to the **{submission['category']}** category.

| Field | Value |
|-------|-------|
| Name | {submission['name']} |
| URL | {submission['url']} |
| Category | {submission['category']} |
| Score | {submission['score']}/3 {badge} |
| Description | {submission['description']} |

---

Closes #{issue_number}

*This PR was automatically created by the submission bot.*
"""

    # Use gh CLI to create PR
    pr_body_escaped = pr_body.replace('"', '\\"').replace('`', '\\`')
    result = run_command(
        f'gh pr create --title "{pr_title}" --body "{pr_body_escaped}" --base main --head {branch_name}',
        check=False
    )

    print(f"PR creation result: {result}")
    return True


def main():
    # Load submission data
    try:
        submission = load_submission_data()
    except FileNotFoundError:
        print("No submission_data.json found, skipping PR creation")
        return 0

    print(f"Creating PR for: {submission['name']}")

    # Create PR
    try:
        create_pr(submission)
        print("PR created successfully!")
        return 0
    except Exception as e:
        print(f"Error creating PR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
