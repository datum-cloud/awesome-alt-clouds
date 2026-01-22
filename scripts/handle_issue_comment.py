#!/usr/bin/env python3
"""
Handle approve/reject comments on automation issues.
Creates PR when approved, closes issue when rejected.
"""

import json
import os
import re
import sys
from pathlib import Path
import requests

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
ISSUE_NUMBER = os.environ.get('ISSUE_NUMBER')
COMMENT_BODY = os.environ.get('COMMENT_BODY', '').lower()
ISSUE_BODY = os.environ.get('ISSUE_BODY', '')
ISSUE_TITLE = os.environ.get('ISSUE_TITLE', '')

REPO_OWNER = 'datum-cloud'
REPO_NAME = 'awesome-alt-clouds'

GITHUB_API = 'https://api.github.com'
headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}


def parse_issue_body(body):
    """Extract service details from issue body."""
    
    # Extract URL
    url_match = re.search(r'\*\*URL\*\*:\s*(.+)', body)
    url = url_match.group(1).strip() if url_match else None
    
    # Extract category
    category_match = re.search(r'\*\*Category\*\*:\s*(.+)', body)
    category = category_match.group(1).strip() if category_match else None
    
    # Extract proposed description
    desc_match = re.search(r'### Proposed Description\s*\n(.+?)(?:\n###|\n\n---|\Z)', body, re.DOTALL)
    description = desc_match.group(1).strip() if desc_match else None
    
    # Extract name from title
    title_match = re.search(r'Add\s+(.+?)\s+to', ISSUE_TITLE)
    name = title_match.group(1).strip() if title_match else None
    
    return {
        'name': name,
        'url': url,
        'category': category,
        'description': description
    }


def find_category_section(readme_content, category):
    """Find the line number where a category section starts."""
    lines = readme_content.split('\n')
    
    for i, line in enumerate(lines):
        if line.strip() == f'## {category}':
            return i
    
    return None


def add_to_readme(service):
    """Add service to README.md in alphabetical order within category."""
    
    # Read current README
    readme_path = Path('README.md')
    with open(readme_path) as f:
        content = f.read()
    
    lines = content.split('\n')
    
    # Find category section
    category_line = find_category_section(content, service['category'])
    if category_line is None:
        print(f"❌ Category '{service['category']}' not found in README")
        return False
    
    # Find where to insert (alphabetically within category)
    insert_line = category_line + 1
    while insert_line < len(lines):
        line = lines[insert_line]
        
        # Stop at next section or empty line after list
        if line.startswith('##') or (not line.strip() and insert_line > category_line + 1):
            break
            
        # Check if this is a service entry
        if line.strip().startswith('*'):
            # Extract name for comparison
            name_match = re.search(r'\[(.+?)\]', line)
            if name_match:
                existing_name = name_match.group(1)
                if service['name'].lower() < existing_name.lower():
                    break
        
        insert_line += 1
    
    # Create new entry
    new_entry = f"* [{service['name']}]({service['url']}) - {service['description']}"
    
    # Insert into lines
    lines.insert(insert_line, new_entry)
    
    # Write back
    with open(readme_path, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"✅ Added {service['name']} to README.md at line {insert_line}")
    return True


def create_pull_request(service):
    """Create a PR to add the service to README."""
    
    # Create a new branch
    branch_name = f"add-{service['name'].lower().replace(' ', '-')}-{ISSUE_NUMBER}"
    
    # Get default branch SHA
    response = requests.get(
        f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/ref/heads/main",
        headers=headers
    )
    main_sha = response.json()['object']['sha']
    
    # Create new branch
    requests.post(
        f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/refs",
        headers=headers,
        json={
            'ref': f'refs/heads/{branch_name}',
            'sha': main_sha
        }
    )
    
    # Add service to README
    if not add_to_readme(service):
        return False
    
    # Commit changes
    os.system('git config user.name "github-actions[bot]"')
    os.system('git config user.email "github-actions[bot]@users.noreply.github.com"')
    os.system(f'git checkout -b {branch_name}')
    os.system('git add README.md')
    os.system(f'git commit -m "Add {service["name"]} to {service["category"]}"')
    os.system(f'git push origin {branch_name}')
    
    # Create PR
    pr_data = {
        'title': f"Add {service['name']} to {service['category']}",
        'body': f"""Adds {service['name']} to the awesome-alt-clouds list.

**Service**: [{service['name']}]({service['url']})
**Category**: {service['category']}

Resolves #{ISSUE_NUMBER}

---
*This PR was automatically created from an approved automation issue.*
""",
        'head': branch_name,
        'base': 'main'
    }
    
    response = requests.post(
        f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/pulls",
        headers=headers,
        json=pr_data
    )
    
    if response.status_code == 201:
        pr = response.json()
        print(f"✅ Created PR #{pr['number']}: {service['name']}")
        
        # Comment on issue with PR link
        comment = f"✅ PR created: #{pr['number']}"
        requests.post(
            f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/issues/{ISSUE_NUMBER}/comments",
            headers=headers,
            json={'body': comment}
        )
        
        # Close issue
        requests.patch(
            f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/issues/{ISSUE_NUMBER}",
            headers=headers,
            json={'state': 'closed'}
        )
        
        return True
    else:
        print(f"❌ Failed to create PR: {response.text}")
        return False


def handle_rejection():
    """Close issue with rejection comment."""
    
    comment = "❌ This candidate has been rejected and will not be added."
    requests.post(
        f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/issues/{ISSUE_NUMBER}/comments",
        headers=headers,
        json={'body': comment}
    )
    
    # Close issue
    requests.patch(
        f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/issues/{ISSUE_NUMBER}",
        headers=headers,
        json={'state': 'closed'}
    )
    
    print(f"✅ Issue #{ISSUE_NUMBER} rejected and closed")


def main():
    if 'approve' in COMMENT_BODY:
        print("Processing approval...")
        service = parse_issue_body(ISSUE_BODY)
        
        if not all([service['name'], service['url'], service['category'], service['description']]):
            print("❌ Failed to parse issue body")
            sys.exit(1)
        
        create_pull_request(service)
        
    elif 'reject' in COMMENT_BODY:
        print("Processing rejection...")
        handle_rejection()
    else:
        print("No action needed")


if __name__ == '__main__':
    if not GITHUB_TOKEN or not ISSUE_NUMBER:
        print("Error: Required environment variables not found")
        sys.exit(1)
    main()
