#!/usr/bin/env python3
"""
Split a multi-URL submission issue into individual child issues.

When a submission contains more than one URL, this script:
  1. Creates one child issue per URL (labeled 'submission')
  2. Evaluates each URL inline (runs evaluate_submission.py)
  3. Posts evaluation results as a comment on the child issue
  4. Creates a PR for any service that passes (score >= 2)
  5. Converts the parent issue to a tracking issue

Environment variables required:
  ISSUE_BODY        - Body of the parent multi-URL issue
  ISSUE_NUMBER      - Number of the parent issue
  REPO              - GitHub repository in owner/repo format
  GH_TOKEN          - GitHub token (for gh CLI calls)
  ANTHROPIC_API_KEY - For Claude API calls inside evaluate_submission.py
"""

import json
import os
import re
import subprocess
import sys
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_urls(issue_body: str) -> list[str]:
    """Return the real (non-placeholder) URLs from a submission issue body."""
    # Numbered list format: "1. https://..."
    candidates = re.findall(r'^\d+\.\s*(https?://[^\s]+)', issue_body, re.MULTILINE)
    if not candidates:
        # Fallback: **URL:** pattern (single-URL format)
        m = re.search(r'\*\*URL:\*\*\s*(https?://[^\s]+)', issue_body)
        if m:
            candidates = [m.group(1).strip()]
    if not candidates:
        candidates = re.findall(r'https?://[^\s\)]+', issue_body)

    seen: set[str] = set()
    urls: list[str] = []
    for url in candidates:
        url = url.strip().rstrip('.,;:')
        if url and url not in seen and 'github.com' not in url:
            seen.add(url)
            urls.append(url)
    return urls[:5]


def extract_field(issue_body: str, field: str) -> str | None:
    m = re.search(rf'\*\*{field}:\*\*\s*(.+?)(?:\n|$)', issue_body)
    return m.group(1).strip() if m else None


def gh(*args: str) -> subprocess.CompletedProcess:
    """Run a gh CLI command, returning the CompletedProcess."""
    return subprocess.run(
        ['gh', *args],
        capture_output=True,
        text=True,
        env=os.environ,
    )


def run_script(script: str, extra_env: dict) -> subprocess.CompletedProcess:
    """Run a Python script with extra environment variables."""
    env = {**os.environ, **extra_env}
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        env=env,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result


def read_file(path: str, default: str = '') -> str:
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return default


def remove_files(*paths: str) -> None:
    for p in paths:
        try:
            os.remove(p)
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------------------
# Child issue creation
# ---------------------------------------------------------------------------

CHILD_BODY_TEMPLATE = """\
## Cloud Service Submission

### URLs
1. {url}

**Submitter:** {submitter}
**Submitted:** {submitted}
**Count:** 1

### Notes
Split from multi-service submission #{parent_number}.

---
*This issue was automatically created via the submission form. A GitHub Action will evaluate each service and use AI to generate name, description, and category. Services that pass (2/3 or 3/3 criteria) will be added to a PR.*"""


def create_child_issue(parent_number: int, url: str, submitter: str, submitted: str, repo: str) -> tuple[int, str] | tuple[None, None]:
    """Create a child issue for a single URL. Returns (issue_number, issue_url)."""
    domain = urlparse(url).netloc.replace('www.', '') or url
    title = f"[Submission] {domain}"
    body = CHILD_BODY_TEMPLATE.format(
        url=url,
        submitter=submitter or 'Unknown',
        submitted=submitted or 'Unknown',
        parent_number=parent_number,
    )
    result = gh(
        'issue', 'create',
        '--repo', repo,
        '--title', title,
        '--body', body,
        '--label', 'submission',
    )
    if result.returncode != 0:
        print(f"ERROR creating child issue for {url}: {result.stderr}", file=sys.stderr)
        return None, None

    issue_url = result.stdout.strip()
    try:
        issue_number = int(issue_url.rstrip('/').split('/')[-1])
    except ValueError:
        print(f"ERROR parsing issue number from: {issue_url}", file=sys.stderr)
        return None, None

    print(f"  Created child issue #{issue_number}: {issue_url}")
    return issue_number, issue_url


# ---------------------------------------------------------------------------
# Per-URL evaluation
# ---------------------------------------------------------------------------

def evaluate_url(url: str, child_number: int) -> tuple[int, str, dict | None]:
    """
    Run evaluate_submission.py for a single URL against the child issue.
    Returns (score, results_markdown, submission_data_or_None).
    """
    single_url_body = (
        "## Cloud Service Submission\n\n"
        "### URLs\n"
        f"1. {url}\n\n"
        "**Count:** 1"
    )

    remove_files('evaluation_results.md', 'evaluation_score.txt', 'submission_data.json')

    run_script('scripts/evaluate_submission.py', {
        'ISSUE_BODY': single_url_body,
        'ISSUE_NUMBER': str(child_number),
    })

    try:
        score = int(read_file('evaluation_score.txt', '0').strip())
    except ValueError:
        score = 0

    results_md = read_file('evaluation_results.md')
    submission_data: dict | None = None
    raw = read_file('submission_data.json')
    if raw:
        try:
            submission_data = json.loads(raw)
        except json.JSONDecodeError:
            pass

    return score, results_md, submission_data


# ---------------------------------------------------------------------------
# PR creation
# ---------------------------------------------------------------------------

def create_pr(child_number: int, submission_data: dict) -> bool:
    """Write submission_data.json with the child issue number and create the PR."""
    # Ensure issue_number points to the child
    submission_data['issue_number'] = child_number

    with open('submission_data.json', 'w') as f:
        json.dump(submission_data, f, indent=2)

    result = run_script('scripts/create_submission_pr.py', {
        'ISSUE_NUMBER': str(child_number),
    })
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Issue management helpers
# ---------------------------------------------------------------------------

def post_comment(issue_number: int, body: str, repo: str) -> None:
    result = gh('issue', 'comment', str(issue_number), '--repo', repo, '--body', body)
    if result.returncode != 0:
        print(f"WARNING: failed to comment on #{issue_number}: {result.stderr}", file=sys.stderr)


def add_labels(issue_number: int, labels: list[str], repo: str) -> None:
    gh('issue', 'edit', str(issue_number), '--repo', repo, '--add-label', ','.join(labels))


def convert_parent_to_tracking(parent_number: int, children: list[tuple[int, str, str]], repo: str) -> None:
    """Remove 'submission' label, add 'tracking', post a summary comment."""
    gh('issue', 'edit', str(parent_number), '--repo', repo,
       '--remove-label', 'submission',
       '--add-label', 'tracking')

    lines = [
        "## Multi-Service Submission — Split into Individual Issues",
        "",
        f"This submission contained {len(children)} service(s). "
        "Each has been split into its own issue for independent evaluation:",
        "",
    ]
    for number, url, issue_url in children:
        domain = urlparse(url).netloc.replace('www.', '') or url
        lines.append(f"- #{number} — **{domain}** ({url})")

    lines += [
        "",
        "This tracking issue will be closed automatically once all child issues are resolved.",
        "Admins can comment `/approve 3` on any child issue to override a failed evaluation.",
    ]

    post_comment(parent_number, '\n'.join(lines), repo)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    issue_body = os.environ.get('ISSUE_BODY', '')
    repo = os.environ.get('REPO', '')
    try:
        issue_number = int(os.environ.get('ISSUE_NUMBER', '0'))
    except ValueError:
        issue_number = 0

    if not issue_body or not issue_number or not repo:
        print("ERROR: ISSUE_BODY, ISSUE_NUMBER, and REPO must all be set.", file=sys.stderr)
        return 1

    urls = extract_urls(issue_body)
    print(f"Found {len(urls)} valid URL(s) in issue #{issue_number}")

    if len(urls) <= 1:
        print("Single-URL submission — leaving for evaluate-submission workflow.")
        return 0

    submitter = extract_field(issue_body, 'Submitter') or 'Unknown'
    submitted = extract_field(issue_body, 'Submitted') or 'Unknown'

    children: list[tuple[int, str, str]] = []  # (number, url, issue_url)

    for url in urls:
        print(f"\n{'='*60}")
        print(f"Processing: {url}")
        print('='*60)

        child_number, child_issue_url = create_child_issue(
            issue_number, url, submitter, submitted, repo
        )
        if child_number is None:
            print(f"Skipping {url} — could not create child issue.", file=sys.stderr)
            continue

        children.append((child_number, url, child_issue_url))

        # Evaluate
        score, results_md, submission_data = evaluate_url(url, child_number)
        print(f"Score: {score}/3")

        # Comment results on the child issue
        if results_md:
            post_comment(child_number, results_md, repo)

        if score >= 2 and submission_data:
            add_labels(child_number, ['auto-approved'], repo)
            pr_ok = create_pr(child_number, submission_data)
            if not pr_ok:
                print(f"WARNING: PR creation failed for #{child_number}", file=sys.stderr)
        else:
            add_labels(child_number, ['needs-review'], repo)
            post_comment(child_number, (
                "⚠️ **Admin Review Required**\n\n"
                f"This submission scored {score}/3 and needs manual verification.\n\n"
                "**To approve:** Comment `/approve 3` (to override score to 3/3)\n"
                "**To reject:** Add the `rejected` label and close the issue"
            ), repo)

    if children:
        convert_parent_to_tracking(issue_number, children, repo)
        print(f"\nSplit complete — created {len(children)} child issue(s).")
    else:
        print("No child issues were created.", file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
