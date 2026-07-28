#!/usr/bin/env python3
"""
Duplicate detection for awesome-alt-clouds submissions.

Checks two sources in order:
  1. clouds.json — blocks re-submission of already-listed services. Matches
     on exact domain, fuzzy name (including exact-name equality for short
     brand names), or a live HTTP redirect proving the submitted URL and an
     existing entry resolve to the same domain (e.g. 'ory.sh' -> 'ory.com').
  2. watchlist.json — flags re-submissions of watched candidates without
     blocking them; lets the normal evaluation run so they can be promoted.

Closed GitHub Issues are intentionally NOT checked. A declined submission
must be able to re-submit freely — that is the whole point of the watchlist.

Writes is_duplicate=true/false to $GITHUB_OUTPUT.
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
    Returns space-separated tokens to preserve word boundaries.

    Examples:
        'ZeroTier Labs' -> 'zerotier'
        'Namecheap' -> 'namecheap'
        'Heap' -> 'heap'
    """
    name = name.lower()
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    parts = [w for w in name.split() if w not in _NAME_NOISE]
    return ' '.join(parts)


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

        # Fuzzy name check: token-set intersection (not character substring).
        # Character substring matching caused false positives like flagging
        # "Namecheap" as a duplicate of "Heap" because 'heap' ⊆ 'namecheap'.
        if fuzzy_match is None and norm_submitted_name:
            norm_entry_name = normalize_name(entry.get('name', ''))
            if not norm_entry_name:
                continue
            # Exact match after normalisation, regardless of length. Without
            # this, short brand names (e.g. "Ory" -> 'ory', 3 chars) never
            # reach the token-overlap check below and go undetected even
            # when submitted under the identical name.
            if norm_submitted_name == norm_entry_name:
                fuzzy_match = entry
                continue
            if len(norm_submitted_name) >= 4 and len(norm_entry_name) >= 4:
                submitted_tokens = {t for t in norm_submitted_name.split() if len(t) >= 4}
                entry_tokens = {t for t in norm_entry_name.split() if len(t) >= 4}
                if submitted_tokens and entry_tokens and submitted_tokens & entry_tokens:
                    fuzzy_match = entry

    if fuzzy_match is not None:
        return ('fuzzy_name', fuzzy_match)

    return (None, None)


def resolve_final_domain(url: str, timeout: int = 10) -> str:
    """Follow redirects for `url` and return the normalised domain it lands on.

    Used to catch cases where two different domains are actually the same
    site (e.g. 'ory.sh' 301-redirects to 'ory.com'). This is a live HTTP
    check, not a heuristic — a matched result is verified, not guessed.

    Returns '' on any failure (timeout, connection error, invalid URL, etc.)
    so callers can fail open and fall back to non-redirect-based matching.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; AwesomeAltCloudsBot/1.0)'}
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
        resp.close()
        return normalize_domain(resp.url)
    except Exception as e:
        logging.warning('Failed to resolve redirects for %s: %s', url, e)
        return ''


def check_clouds_json_with_redirects(
    submitted_domain: str,
    submitted_name: str,
    submitted_url: str,
    clouds: list[dict],
) -> tuple[str | None, dict | None]:
    """Wrap check_clouds_json with a targeted, live redirect check.

    Never scans all entries over the network — at most two live requests:
    one for the submitted URL, and (only if a fuzzy name candidate was
    found) one for that candidate's stored URL.

    Adds a third match type:
        ('redirect_domain', entry) — an HTTP redirect proves the submitted
        URL and an existing entry resolve to the same domain.
    """
    match_type, match = check_clouds_json(submitted_domain, submitted_name, clouds)

    if match_type == 'exact_domain':
        return (match_type, match)

    submitted_final = resolve_final_domain(submitted_url)

    if match_type == 'fuzzy_name':
        candidate_final = resolve_final_domain(match.get('url', ''))
        if submitted_final and candidate_final and submitted_final == candidate_final:
            return ('redirect_domain', match)
        return (match_type, match)

    # No name/domain match at all — check whether the submitted URL silently
    # redirects to an already-listed domain (e.g. a rebrand with a new name
    # but a forwarding old domain).
    if submitted_final and submitted_final != submitted_domain:
        redirect_match = next(
            (entry for entry in clouds if normalize_domain(entry.get('url', '')) == submitted_final),
            None,
        )
        if redirect_match:
            return ('redirect_domain', redirect_match)

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


def build_comment(match_type: str, match: dict) -> str:
    """Build a GitHub comment body for a duplicate match.

    Args:
        match_type: 'exact_domain' or 'fuzzy_name'
        match:      the matching entry dict from clouds.json
    """
    name = match.get('name', 'Unknown')
    url = match.get('url', '')
    desc = match.get('description', '')

    if match_type == 'exact_domain':
        return (
            '⚠️ **Duplicate Submission**\n\n'
            'This service is already included in the Awesome Alt Clouds list:\n'
            f'- **[{name}]({url})** — {desc}\n\n'
            'Closing this issue as a duplicate. If you believe this is a different '
            'service or a significant update, please reopen with additional context.'
        )
    elif match_type == 'fuzzy_name':
        return (
            '⚠️ **Possible Duplicate**\n\n'
            'A similar service may already be listed:\n'
            f'- **[{name}]({url})** — {desc}\n\n'
            'Proceeding with admin review, but flagging as a possible duplicate.'
        )
    elif match_type == 'redirect_domain':
        return (
            '🔁 **Duplicate via Domain Redirect**\n\n'
            'This URL redirects to a service already listed in Awesome Alt Clouds '
            '(confirmed via HTTP redirect, not just name similarity):\n'
            f'- **[{name}]({url})** — {desc}\n\n'
            'Proceeding with admin review, but flagging as a likely duplicate.'
        )
    else:
        raise ValueError(f'Unknown match_type: {match_type!r}')


# Paths to data files — overridable in tests.
# Live in public/ since the Astro migration (Phase 1, see analysis/2026-05-19-astro-migration-rfc.md).
_CLOUDS_JSON_PATH = os.path.join(os.path.dirname(__file__), '..', 'public', 'clouds.json')
_WATCHLIST_JSON_PATH = os.path.join(os.path.dirname(__file__), '..', 'public', 'watchlist.json')


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

    # 1. Check clouds.json — the authoritative list derived from README.md.
    # Closed GitHub Issues are intentionally NOT checked: a previously-rejected
    # submission must be able to re-submit freely.
    clouds: list[dict] = []
    try:
        with open(_CLOUDS_JSON_PATH, 'r', encoding='utf-8') as f:
            clouds = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logging.warning('Could not read clouds.json: %s', e)

    match_type, match = check_clouds_json_with_redirects(submitted_domain, submitted_name, urls[0], clouds)

    if match_type is not None:
        assert match is not None, f"match_type is {match_type!r} but match is None"
        comment = build_comment(match_type, match)
        post_comment(repo, issue_number, comment, gh_token)
        add_label(repo, issue_number, 'duplicate', gh_token)
        if match_type == 'exact_domain':
            close_issue(repo, issue_number, gh_token)
        _write_github_output('is_duplicate', 'true')
        _write_github_output('duplicate_reason', match_type)
        return

    # 2. Check watchlist.json — flag re-submissions of watched candidates so
    # reviewers know this is a repeat attempt, but do NOT block evaluation.
    # The service may have improved; let the evaluator decide.
    watchlist: list[dict] = []
    try:
        with open(_WATCHLIST_JSON_PATH, 'r', encoding='utf-8') as f:
            watchlist = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logging.warning('Could not read watchlist.json: %s', e)

    watchlist_match = next(
        (entry for entry in watchlist if normalize_domain(entry.get('url', '')) == submitted_domain),
        None,
    )

    if watchlist_match:
        criteria = watchlist_match.get('criteriaNeed', 'see watchlist')
        comment = (
            '📋 **Watchlist Re-submission**\n\n'
            'This service is currently on the [Watchlist](https://www.alt-cloud.org/watchlist/) '
            f'and is being re-evaluated. Previously it did not qualify because: '
            f'_{watchlist_match.get("reasonNotQualifying", "criteria not met")}_\n\n'
            f'**Criteria still needed:** {criteria}\n\n'
            'Proceeding with a fresh evaluation — if the criteria above are now met, '
            'this submission will be promoted to the main list automatically.'
        )
        post_comment(repo, issue_number, comment, gh_token)
        add_label(repo, issue_number, 'watchlist', gh_token)
        _write_github_output('is_duplicate', 'false')
        _write_github_output('duplicate_reason', 'watchlist_resubmission')
    else:
        _write_github_output('is_duplicate', 'false')
        _write_github_output('duplicate_reason', 'no_match')


if __name__ == '__main__':
    main()
