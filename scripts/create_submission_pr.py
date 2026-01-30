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
        data = json.load(f)

    # Handle both old single-service format and new multi-service format
    if 'services' in data:
        return data
    else:
        # Convert old format to new format
        return {
            'services': [data],
            'issue_number': data.get('issue_number', 'unknown')
        }


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


def create_pr(data):
    """Create a branch and PR for the submission(s)"""
    services = data['services']
    issue_number = data.get('issue_number', 'unknown')

    if not services:
        print("No services to add")
        return False

    # Create branch name
    if len(services) == 1:
        branch_name = f"submission-{issue_number}-{services[0]['name'].lower().replace(' ', '-')[:30]}"
    else:
        branch_name = f"submission-{issue_number}-{len(services)}-services"

    # Configure git
    run_command('git config user.name "github-actions[bot]"')
    run_command('git config user.email "github-actions[bot]@users.noreply.github.com"')

    # Create and checkout new branch
    run_command(f'git checkout -b {branch_name}')

    # Add each entry to README
    added_services = []
    for service in services:
        if add_entry_to_readme(service):
            added_services.append(service)
        else:
            print(f"Failed to add {service['name']} to README")

    if not added_services:
        print("No services were added to README")
        return False

    # Commit changes
    run_command('git add README.md')

    if len(added_services) == 1:
        s = added_services[0]
        commit_msg = f"Add {s['name']} to {s['category']}\\n\\nCloses #{issue_number}"
    else:
        names = ', '.join(s['name'] for s in added_services)
        commit_msg = f"Add {len(added_services)} services: {names}\\n\\nCloses #{issue_number}"

    run_command(f'git commit -m "{commit_msg}"')

    # Push branch
    run_command(f'git push origin {branch_name}')

    # Create PR
    if len(added_services) == 1:
        s = added_services[0]
        badge = '🟢' if s['score'] == 3 else '🟡'
        pr_title = f"Add {badge} {s['name']} to {s['category']}"
    else:
        pr_title = f"Add {len(added_services)} new cloud services"

    # Build PR body
    pr_body = f"""## New Cloud Service Submission

"""
    if len(added_services) == 1:
        s = added_services[0]
        badge = '🟢' if s['score'] == 3 else '🟡'
        pr_body += f"""This PR adds **{s['name']}** to the **{s['category']}** category.

| Field | Value |
|-------|-------|
| Name | {s['name']} |
| URL | {s['url']} |
| Category | {s['category']} |
| Score | {s['score']}/3 {badge} |
| Description | {s['description']} |
"""
    else:
        pr_body += f"This PR adds **{len(added_services)} services**:\n\n"
        pr_body += "| Name | Category | Score | URL |\n"
        pr_body += "|------|----------|-------|-----|\n"
        for s in added_services:
            badge = '🟢' if s['score'] == 3 else '🟡'
            pr_body += f"| {s['name']} | {s['category']} | {s['score']}/3 {badge} | {s['url']} |\n"

    pr_body += f"""

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
        data = load_submission_data()
    except FileNotFoundError:
        print("No submission_data.json found, skipping PR creation")
        return 0

    services = data.get('services', [])
    if not services:
        print("No services to add")
        return 0

    print(f"Creating PR for {len(services)} service(s)")
    for s in services:
        print(f"  - {s['name']} ({s['category']})")

    # Create PR
    try:
        create_pr(data)
        print("PR created successfully!")
        return 0
    except Exception as e:
        print(f"Error creating PR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
