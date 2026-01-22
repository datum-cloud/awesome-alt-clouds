#!/usr/bin/env python3
"""
Create GitHub issues for evaluated candidates.
ALWAYS creates issues for score 2/3 and 3/3 (no auto-PR).
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
import requests

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_OWNER = 'datum-cloud'
REPO_NAME = 'awesome-alt-clouds'

# GitHub API setup
GITHUB_API = 'https://api.github.com'
headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}


def create_issue(candidate):
    """Create a GitHub issue for a candidate cloud service."""
    
    score = candidate['evaluation']['score']
    name = candidate['name']
    url = candidate['url']
    category = candidate['category']
    description = candidate['evaluation']['description']
    
    # Determine label based on score
    if score == 3:
        label = 'ready-to-merge'
        emoji = '✅'
        status = 'Ready to Merge'
    elif score == 2:
        label = 'needs-review'
        emoji = '⚠️'
        status = 'Needs Review'
    else:
        # Don't create issues for score 0-1
        return None
    
    # Build issue title
    title = f"{emoji} Add {name} to {category}"
    
    # Build issue body
    body = f"""## {name}

**Status**: {status}
**Score**: {score}/3
**Category**: {category}
**URL**: {url}

### Proposed Description
{description}

### Evaluation Results

#### ✓ Criteria Met ({score}/3)

"""
    
    # Add criteria details
    for criterion in candidate['evaluation']['criteria']:
        check = "✅" if criterion['passed'] else "❌"
        body += f"{check} **{criterion['name']}**\n"
        body += f"- Evidence: {criterion['evidence']}\n"
        if criterion['url']:
            body += f"- Source: {criterion['url']}\n"
        body += "\n"
    
    # Add instructions
    if score == 3:
        body += """
### Next Steps
This candidate meets all 3 criteria and is ready to be added!

**To approve**: Comment `approve` and I'll create a PR to add this service.
**To reject**: Comment `reject` with a reason.
"""
    else:
        body += """
### Next Steps
This candidate meets 2/3 criteria and needs manual review.

**To approve**: Verify the missing criterion manually, then comment `approve` to create a PR.
**To reject**: Comment `reject` with a reason.
"""
    
    # Create the issue
    issue_data = {
        'title': title,
        'body': body,
        'labels': [label, 'automation']
    }
    
    response = requests.post(
        f'{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/issues',
        headers=headers,
        json=issue_data
    )
    
    if response.status_code == 201:
        issue = response.json()
        print(f"✅ Created issue #{issue['number']}: {name}")
        return issue['number']
    else:
        print(f"❌ Failed to create issue for {name}: {response.text}")
        return None


def main():
    # Find latest evaluation file
    eval_dir = Path('data/evaluations')
    if not eval_dir.exists():
        print("No evaluations directory found")
        return
    
    eval_files = sorted(eval_dir.glob('eval-*.json'))
    if not eval_files:
        print("No evaluation files found")
        return
    
    latest_eval = eval_files[-1]
    print(f"Processing: {latest_eval}")
    
    with open(latest_eval) as f:
        data = json.load(f)
    
    candidates = data.get('candidates', [])
    
    # Filter for score 2 or 3
    eligible = [c for c in candidates if c['evaluation']['score'] >= 2]
    
    if not eligible:
        print("No candidates with score 2+ found")
        return
    
    print(f"\nFound {len(eligible)} candidates to create issues for")
    
    issues_created = 0
    for candidate in eligible:
        issue_num = create_issue(candidate)
        if issue_num:
            issues_created += 1
    
    print(f"\n✅ Created {issues_created} issues")
    
    # Save summary
    summary = {
        'date': datetime.now().isoformat(),
        'total_evaluated': len(candidates),
        'issues_created': issues_created,
        'ready_to_merge': len([c for c in eligible if c['evaluation']['score'] == 3]),
        'needs_review': len([c for c in eligible if c['evaluation']['score'] == 2])
    }
    
    summary_file = eval_dir / f"summary-{datetime.now().strftime('%Y%m%d')}.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Summary saved to: {summary_file}")


if __name__ == '__main__':
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN not found")
        sys.exit(1)
    main()
