#!/usr/bin/env python3
"""
Duplicate detection for awesome-alt-clouds submissions.

Reads submission info from environment variables, checks clouds.json and
GitHub Issues for duplicates, posts a comment + label + optionally closes
the issue, then writes is_duplicate=true/false to $GITHUB_OUTPUT.

Exits 0 always — failures are non-fatal to avoid blocking submissions.
"""

import json
import logging
import os
import re
from urllib.parse import urlparse

import requests

# Noise words stripped during name normalisation.
# 'io' is included to collapse TLD-style suffixes (e.g. "Fly.io" -> "fly").
_NAME_NOISE = {'cloud', 'ai', 'labs', 'inc', 'io', 'the'}


def normalize_domain(url: str) -> str:
    """Normalise a URL to bare domain (no www, no path, no query).

    Examples:
        'https://www.stripe.com/billing?ref=x' -> 'stripe.com'
        'http://fly.io/docs/'                  -> 'fly.io'
    """
    url = url.strip().lower()
    # Prepend scheme if missing so urlparse works
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        # strip port if present
        domain = domain.split(':')[0]
        if domain.startswith('www.'):
            domain = domain[4:]
        # Reject anything that looks like plain text (contains spaces or lacks a dot)
        if ' ' in domain or '.' not in domain:
            return ''
        return domain
    except (ValueError, AttributeError):
        return ''


def normalize_name(name: str) -> str:
    """Normalise a service name for fuzzy matching.

    Lowercases, strips punctuation, removes noise words.
    Example: 'ZeroTier Labs' -> 'zerotier'
    """
    # lowercase
    name = name.lower()
    # replace punctuation with spaces (preserve word boundaries)
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    # remove noise words
    parts = [w for w in name.split() if w not in _NAME_NOISE]
    return ''.join(parts)


def check_clouds_json(
    submitted_domain: str,
    submitted_name: str,
    clouds: list[dict],
) -> tuple[str | None, dict | None]:
    """Check submitted domain/name against entries in clouds.json.

    Returns:
        ('exact_domain', entry) — submitted domain matches an existing entry
        ('fuzzy_name', entry)   — submitted name fuzzy-matches an existing entry
        (None, None)            — no match
    """
    norm_submitted_name = normalize_name(submitted_name)

    fuzzy_match = None  # save first fuzzy hit, return only if no exact hit

    for entry in clouds:
        entry_domain = normalize_domain(entry.get('url', ''))
        if entry_domain and entry_domain == submitted_domain:
            return ('exact_domain', entry)

        # Fuzzy name check (only keep first match, require min length to avoid false positives)
        if fuzzy_match is None and len(norm_submitted_name) >= 4:
            norm_entry_name = normalize_name(entry.get('name', ''))
            if norm_entry_name and len(norm_entry_name) >= 4 and (
                norm_submitted_name in norm_entry_name
                or norm_entry_name in norm_submitted_name
            ):
                fuzzy_match = entry

    if fuzzy_match is not None:
        return ('fuzzy_name', fuzzy_match)

    return (None, None)


def check_github_issues(
    submitted_domain: str,
    gh_token: str,
    repo: str,
    current_issue_number: int,
    max_issues: int = 500,
) -> tuple[str | None, dict | None]:
    """Check submitted domain against all GitHub Issues with label 'submission'.

    Paginates up to max_issues. Skips the current issue.

    Returns:
        ('existing_issue', issue) — domain matches an existing issue's URL
        (None, None)              — no match or API error
    """
    headers = {
        'Authorization': f'Bearer {gh_token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    url: str | None = f'https://api.github.com/repos/{repo}/issues'
    params = {'labels': 'submission', 'state': 'all', 'per_page': 100}

    fetched = 0
    try:
        while url and fetched < max_issues:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            issues = resp.json()
            fetched += len(issues)

            for issue in issues:
                if issue.get('number') == current_issue_number:
                    continue
                body = issue.get('body') or ''
                # Extract URLs from the issue body
                urls_in_body = re.findall(r'https?://[^\s\)]+', body)
                for raw_url in urls_in_body:
                    if normalize_domain(raw_url) == submitted_domain:
                        return ('existing_issue', issue)

            # Follow pagination via Link header
            link = resp.headers.get('Link', '')
            next_url = None
            for part in link.split(','):
                if 'rel="next"' in part:
                    match = re.search(r'<([^>]+)>', part)
                    if match:
                        next_url = match.group(1)
                        break
            url = next_url
            params = {}  # params already encoded in next_url

    except Exception as e:
        logging.warning('GitHub Issues API check failed: %s', e)
        return (None, None)

    return (None, None)


def _gh_headers(gh_token: str) -> dict:
    return {
        'Authorization': f'Bearer {gh_token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }


def post_comment(repo: str, issue_number: int, body: str, gh_token: str) -> None:
    """Post a comment on a GitHub issue. Silently ignores errors."""
    try:
        url = f'https://api.github.com/repos/{repo}/issues/{issue_number}/comments'
        resp = requests.post(url, headers=_gh_headers(gh_token), json={'body': body}, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logging.warning('Failed to post comment on issue %s: %s', issue_number, e)


def add_label(repo: str, issue_number: int, label: str, gh_token: str) -> None:
    """Add a label to a GitHub issue. Silently ignores errors."""
    try:
        url = f'https://api.github.com/repos/{repo}/issues/{issue_number}/labels'
        resp = requests.post(url, headers=_gh_headers(gh_token), json={'labels': [label]}, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logging.warning('Failed to add label to issue %s: %s', issue_number, e)


def close_issue(repo: str, issue_number: int, gh_token: str) -> None:
    """Close a GitHub issue. Silently ignores errors."""
    try:
        url = f'https://api.github.com/repos/{repo}/issues/{issue_number}'
        resp = requests.patch(url, headers=_gh_headers(gh_token), json={'state': 'closed'}, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logging.warning('Failed to close issue %s: %s', issue_number, e)


def build_comment(match_type: str, match: dict, source: str) -> str:
    """Build a GitHub comment body for a duplicate match.

    Args:
        match_type: 'exact_domain', 'fuzzy_name', or 'existing_issue'
        match:      the matching entry dict (from clouds.json or GitHub Issues)
        source:     'clouds_json' or 'github_issues'
    """
    if match_type in ('exact_domain', 'existing_issue'):
        if source == 'clouds_json':
            name = match.get('name', 'Unknown')
            url = match.get('url', '')
            desc = match.get('description', '')
            return (
                '⚠️ **Duplicate Submission**\n\n'
                'This service is already included in the Awesome Alt Clouds list:\n'
                f'- **[{name}]({url})** — {desc}\n\n'
                'Closing this issue as a duplicate. If you believe this is a different '
                'service or a significant update, please reopen with additional context.'
            )
        else:  # github_issues
            issue_url = match.get('html_url', '')
            issue_title = match.get('title', 'existing issue')
            return (
                '⚠️ **Duplicate Submission**\n\n'
                'This service has already been submitted:\n'
                f'- **[{issue_title}]({issue_url})**\n\n'
                'Closing this issue as a duplicate. If you believe this is a different '
                'service or a significant update, please reopen with additional context.'
            )
    else:
        if match_type != 'fuzzy_name':
            raise ValueError(f'Unknown match_type: {match_type!r}')
        name = match.get('name', 'Unknown')
        url = match.get('url', '')
        desc = match.get('description', '')
        return (
            '⚠️ **Possible Duplicate**\n\n'
            'A similar service may already be listed:\n'
            f'- **[{name}]({url})** — {desc}\n\n'
            'Proceeding with admin review, but flagging as a possible duplicate.'
        )


# Path to clouds.json — overridable in tests
_CLOUDS_JSON_PATH = os.path.join(os.path.dirname(__file__), '..', 'docs', 'clouds.json')


def _write_github_output(key: str, value: str) -> None:
    """Write a key=value pair to $GITHUB_OUTPUT (or stdout if not set)."""
    github_output = os.environ.get('GITHUB_OUTPUT', '')
    if github_output:
        with open(github_output, 'a', encoding='utf-8') as f:
            f.write(f'{key}={value}\n')
    else:
        logging.warning('GITHUB_OUTPUT not set; skipping output: %s=%s', key, value)


def main() -> None:
    issue_body = os.environ.get('ISSUE_BODY', '')
    issue_number = int(os.environ.get('ISSUE_NUMBER') or '0')
    issue_title = os.environ.get('ISSUE_TITLE', '')
    gh_token = os.environ.get('GH_TOKEN', '')
    repo = os.environ.get('REPO', '')

    # Extract URLs from issue body (same logic as evaluate_submission.py)
    urls = []
    numbered = re.findall(r'^\d+\.\s*(https?://[^\s]+)', issue_body, re.MULTILINE)
    if numbered:
        urls.extend(numbered)
    if not urls:
        m = re.search(r'\*\*URL:\*\*\s*(https?://[^\s]+)', issue_body)
        if m:
            urls.append(m.group(1).strip())
    if not urls:
        urls = re.findall(r'https?://[^\s\)]+', issue_body)
    urls = [u.strip().rstrip('.,;:') for u in urls if 'github.com' not in u][:5]

    if not urls:
        logging.info('No URLs found in issue body — skipping duplicate check.')
        _write_github_output('is_duplicate', 'false')
        _write_github_output('duplicate_reason', 'no_urls')
        return

    submitted_domain = normalize_domain(urls[0])
    submitted_name = issue_title

    # --- Check clouds.json ---
    clouds: list[dict] = []
    try:
        with open(_CLOUDS_JSON_PATH, 'r', encoding='utf-8') as f:
            clouds = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logging.warning('Could not read clouds.json: %s', e)

    match_type, match = check_clouds_json(submitted_domain, submitted_name, clouds)

    if match_type is None and gh_token and repo:
        match_type, match = check_github_issues(
            submitted_domain, gh_token, repo, current_issue_number=issue_number
        )

    if match_type is not None:
        assert match is not None, f"match_type is {match_type!r} but match is None"
        source = 'clouds_json' if match in clouds else 'github_issues'
        comment = build_comment(match_type, match, source=source)
        post_comment(repo, issue_number, comment, gh_token)
        add_label(repo, issue_number, 'duplicate', gh_token)
        if match_type in ('exact_domain', 'existing_issue'):
            close_issue(repo, issue_number, gh_token)
        _write_github_output('is_duplicate', 'true')
        _write_github_output('duplicate_reason', match_type)
    else:
        _write_github_output('is_duplicate', 'false')
        _write_github_output('duplicate_reason', 'no_match')


if __name__ == '__main__':
    main()
