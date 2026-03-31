# Duplicate Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `check_duplicates.py` script that short-circuits the evaluate-submission workflow when a submitted URL or service name already exists in `clouds.json` or open/closed GitHub Issues.

**Architecture:** A new standalone script `scripts/check_duplicates.py` runs as the first step in `evaluate-submission.yml`. It normalises the submitted URL to a domain, compares against `docs/clouds.json` entries and GitHub Issues (via REST API), posts a comment + label + optionally closes the issue on match, then writes `is_duplicate=true/false` to `$GITHUB_OUTPUT`. All downstream steps get an `if:` guard on that output. Failures are non-fatal — the script exits 0 on any unexpected error to avoid blocking legitimate submissions.

**Tech Stack:** Python 3.11, `requests`, `json`, `re`, `os`, `urllib.parse` — no new dependencies required. Tests use `pytest` + `unittest.mock`.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `scripts/check_duplicates.py` | Create | All duplicate-detection logic + GitHub API calls + main() |
| `tests/test_check_duplicates.py` | Create | Full test suite for check_duplicates |
| `.github/workflows/evaluate-submission.yml` | Modify | Add check step + `if:` guards on all downstream steps |

---

### Task 1: Domain and name normalisation utilities

**Files:**
- Create: `scripts/check_duplicates.py`
- Create: `tests/test_check_duplicates.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_check_duplicates.py`:

```python
# tests/test_check_duplicates.py
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import pytest
import check_duplicates as cd


# ---------------------------------------------------------------------------
# normalize_domain
# ---------------------------------------------------------------------------

class TestNormalizeDomain:

    def test_strips_https_and_www(self):
        assert cd.normalize_domain('https://www.stripe.com/billing?ref=x') == 'stripe.com'

    def test_strips_http(self):
        assert cd.normalize_domain('http://example.com') == 'example.com'

    def test_strips_trailing_path(self):
        assert cd.normalize_domain('https://fly.io/docs/') == 'fly.io'

    def test_strips_query_string(self):
        assert cd.normalize_domain('https://render.com?foo=bar') == 'render.com'

    def test_bare_domain_unchanged(self):
        assert cd.normalize_domain('example.com') == 'example.com'

    def test_returns_empty_string_on_invalid_url(self):
        assert cd.normalize_domain('not a url') == ''

    def test_strips_www_only(self):
        assert cd.normalize_domain('www.example.com') == 'example.com'


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------

class TestNormalizeName:

    def test_lowercases(self):
        assert cd.normalize_name('ZeroTier') == 'zerotier'

    def test_strips_noise_words(self):
        assert cd.normalize_name('ZeroTier Labs') == 'zerotier'

    def test_strips_punctuation(self):
        assert cd.normalize_name('Fly.io') == 'fly'

    def test_strips_multiple_noise_words(self):
        assert cd.normalize_name('Acme Cloud AI Inc') == 'acme'

    def test_strips_the(self):
        assert cd.normalize_name('The Platform') == 'platform'

    def test_empty_string(self):
        assert cd.normalize_name('') == ''

    def test_only_noise_words_returns_empty(self):
        # "cloud ai labs" all stripped → empty
        assert cd.normalize_name('Cloud AI Labs') == ''
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /path/to/repo
pytest tests/test_check_duplicates.py::TestNormalizeDomain tests/test_check_duplicates.py::TestNormalizeName -v
```

Expected: `ModuleNotFoundError: No module named 'check_duplicates'`

- [ ] **Step 3: Write the minimal implementation**

Create `scripts/check_duplicates.py`:

```python
#!/usr/bin/env python3
"""
Duplicate detection for awesome-alt-clouds submissions.

Reads submission info from environment variables, checks clouds.json and
GitHub Issues for duplicates, posts a comment + label + optionally closes
the issue, then writes is_duplicate=true/false to $GITHUB_OUTPUT.

Exits 0 always — failures are non-fatal to avoid blocking submissions.
"""

import json
import os
import re
import sys
from urllib.parse import urlparse

import requests

# Noise words stripped during name normalisation
_NAME_NOISE = {'cloud', 'ai', 'labs', 'inc', 'io', 'the', 'platform'}


def normalize_domain(url: str) -> str:
    """Normalise a URL to bare domain (no www, no path, no query).

    Examples:
        'https://www.stripe.com/billing?ref=x' -> 'stripe.com'
        'http://fly.io/docs/'                  -> 'fly.io'
    """
    url = url.strip()
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
        return domain.lower()
    except Exception:
        return ''


def normalize_name(name: str) -> str:
    """Normalise a service name for fuzzy matching.

    Lowercases, strips punctuation, removes noise words.
    Example: 'ZeroTier Labs' -> 'zerotier'
    """
    # lowercase
    name = name.lower()
    # strip punctuation (keep letters, digits, spaces)
    name = re.sub(r'[^a-z0-9\s]', '', name)
    # remove noise words
    parts = [w for w in name.split() if w not in _NAME_NOISE]
    return ' '.join(parts).strip().replace(' ', '')
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_check_duplicates.py::TestNormalizeDomain tests/test_check_duplicates.py::TestNormalizeName -v
```

Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/check_duplicates.py tests/test_check_duplicates.py
git commit -m "feat: add check_duplicates script with domain/name normalisation"
```

---

### Task 2: clouds.json duplicate checker

**Files:**
- Modify: `scripts/check_duplicates.py`
- Modify: `tests/test_check_duplicates.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_check_duplicates.py`:

```python
# ---------------------------------------------------------------------------
# check_clouds_json
# ---------------------------------------------------------------------------

class TestCheckCloudsJson:

    CLOUDS = [
        {
            "name": "Fly.io",
            "url": "https://fly.io",
            "description": "App hosting with global anycast networking.",
            "score": 3,
            "categories": ["PaaS & Application Hosting"],
        },
        {
            "name": "ZeroTier",
            "url": "https://www.zerotier.com",
            "description": "Virtual networking for IoT and enterprise.",
            "score": 3,
            "categories": ["Network & Connectivity Clouds"],
        },
        {
            "name": "Render",
            "url": "https://render.com",
            "description": "Unified cloud to build and run apps.",
            "score": 3,
            "categories": ["PaaS & Application Hosting"],
        },
    ]

    def test_exact_domain_match_returns_exact_domain_result(self):
        match_type, entry = cd.check_clouds_json('fly.io', 'SomeName', self.CLOUDS)
        assert match_type == 'exact_domain'
        assert entry['name'] == 'Fly.io'

    def test_exact_domain_match_ignores_www_in_stored_url(self):
        match_type, entry = cd.check_clouds_json('zerotier.com', 'SomeName', self.CLOUDS)
        assert match_type == 'exact_domain'
        assert entry['name'] == 'ZeroTier'

    def test_fuzzy_name_match_returns_fuzzy_name_result(self):
        # 'ZeroTier Labs' normalises to 'zerotier', matches 'ZeroTier' -> 'zerotier'
        match_type, entry = cd.check_clouds_json('newdomain.com', 'ZeroTier Labs', self.CLOUDS)
        assert match_type == 'fuzzy_name'
        assert entry['name'] == 'ZeroTier'

    def test_exact_domain_takes_priority_over_fuzzy_name(self):
        # Both domain and name match Fly.io — should return exact_domain
        match_type, entry = cd.check_clouds_json('fly.io', 'Fly.io Platform', self.CLOUDS)
        assert match_type == 'exact_domain'

    def test_no_match_returns_none_tuple(self):
        result = cd.check_clouds_json('brandnew.io', 'Brand New Service', self.CLOUDS)
        assert result == (None, None)

    def test_empty_clouds_returns_none_tuple(self):
        result = cd.check_clouds_json('fly.io', 'Fly.io', [])
        assert result == (None, None)

    def test_fuzzy_match_contained_by(self):
        # submitted name 'Render' is contained in 'Render Cloud' — both normalise and one contains the other
        clouds = [{
            "name": "Render Cloud",
            "url": "https://render.com",
            "description": "...",
            "score": 3,
            "categories": [],
        }]
        match_type, entry = cd.check_clouds_json('other.io', 'Render', clouds)
        assert match_type == 'fuzzy_name'
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_check_duplicates.py::TestCheckCloudsJson -v
```

Expected: `AttributeError: module 'check_duplicates' has no attribute 'check_clouds_json'`

- [ ] **Step 3: Write the minimal implementation**

Add to `scripts/check_duplicates.py` (after `normalize_name`):

```python
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

        # Fuzzy name check (only keep first match)
        if fuzzy_match is None and norm_submitted_name:
            norm_entry_name = normalize_name(entry.get('name', ''))
            if norm_entry_name and (
                norm_submitted_name in norm_entry_name
                or norm_entry_name in norm_submitted_name
            ):
                fuzzy_match = entry

    if fuzzy_match is not None:
        return ('fuzzy_name', fuzzy_match)

    return (None, None)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_check_duplicates.py::TestCheckCloudsJson -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/check_duplicates.py tests/test_check_duplicates.py
git commit -m "feat: add clouds.json duplicate checker"
```

---

### Task 3: GitHub Issues duplicate checker

**Files:**
- Modify: `scripts/check_duplicates.py`
- Modify: `tests/test_check_duplicates.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_check_duplicates.py`:

```python
# ---------------------------------------------------------------------------
# check_github_issues
# ---------------------------------------------------------------------------

from unittest.mock import patch, MagicMock


def _make_gh_response(issues, link_header=None):
    """Build a mock requests.Response for the GitHub Issues API."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = issues
    mock.headers = {}
    if link_header:
        mock.headers['Link'] = link_header
    mock.raise_for_status = MagicMock()
    return mock


class TestCheckGithubIssues:

    ISSUES = [
        {
            "number": 10,
            "title": "Add Fly.io",
            "body": "**URL:** https://fly.io\n**Name:** Fly.io",
            "html_url": "https://github.com/owner/repo/issues/10",
        },
        {
            "number": 11,
            "title": "Add ZeroTier",
            "body": "**URL:** https://www.zerotier.com\n**Name:** ZeroTier",
            "html_url": "https://github.com/owner/repo/issues/11",
        },
        {
            "number": 99,
            "title": "Add something else",
            "body": "no url here",
            "html_url": "https://github.com/owner/repo/issues/99",
        },
    ]

    def test_exact_domain_match_in_issues(self):
        with patch('requests.get', return_value=_make_gh_response(self.ISSUES)):
            match_type, issue = cd.check_github_issues(
                'fly.io', 'token', 'owner/repo', current_issue_number=200
            )
        assert match_type == 'existing_issue'
        assert issue['number'] == 10

    def test_skips_current_issue(self):
        # If the current issue number matches, it should NOT be returned as a duplicate
        issues = [
            {
                "number": 200,
                "title": "Add Fly.io",
                "body": "**URL:** https://fly.io",
                "html_url": "https://github.com/owner/repo/issues/200",
            }
        ]
        with patch('requests.get', return_value=_make_gh_response(issues)):
            result = cd.check_github_issues(
                'fly.io', 'token', 'owner/repo', current_issue_number=200
            )
        assert result == (None, None)

    def test_no_match_returns_none_tuple(self):
        with patch('requests.get', return_value=_make_gh_response(self.ISSUES)):
            result = cd.check_github_issues(
                'brandnew.io', 'token', 'owner/repo', current_issue_number=999
            )
        assert result == (None, None)

    def test_api_failure_returns_none_tuple(self):
        with patch('requests.get', side_effect=Exception('network error')):
            result = cd.check_github_issues(
                'fly.io', 'token', 'owner/repo', current_issue_number=999
            )
        assert result == (None, None)

    def test_paginates_when_link_header_present(self):
        page1 = [
            {
                "number": 10,
                "title": "Add Something",
                "body": "**URL:** https://page1only.io",
                "html_url": "https://github.com/owner/repo/issues/10",
            }
        ]
        page2 = [
            {
                "number": 20,
                "title": "Add Fly.io",
                "body": "**URL:** https://fly.io",
                "html_url": "https://github.com/owner/repo/issues/20",
            }
        ]
        link_header = '<https://api.github.com/repos/owner/repo/issues?page=2>; rel="next"'

        responses = [
            _make_gh_response(page1, link_header=link_header),
            _make_gh_response(page2),  # no next link → stop
        ]

        with patch('requests.get', side_effect=responses):
            match_type, issue = cd.check_github_issues(
                'fly.io', 'token', 'owner/repo', current_issue_number=999
            )
        assert match_type == 'existing_issue'
        assert issue['number'] == 20
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_check_duplicates.py::TestCheckGithubIssues -v
```

Expected: `AttributeError: module 'check_duplicates' has no attribute 'check_github_issues'`

- [ ] **Step 3: Write the minimal implementation**

Add to `scripts/check_duplicates.py` (after `check_clouds_json`):

```python
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
    url = f'https://api.github.com/repos/{repo}/issues'
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
        print(f'Warning: GitHub Issues API check failed: {e}', file=sys.stderr)
        return (None, None)

    return (None, None)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_check_duplicates.py::TestCheckGithubIssues -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/check_duplicates.py tests/test_check_duplicates.py
git commit -m "feat: add GitHub Issues duplicate checker with pagination"
```

---

### Task 4: GitHub API actions (comment, label, close)

**Files:**
- Modify: `scripts/check_duplicates.py`
- Modify: `tests/test_check_duplicates.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_check_duplicates.py`:

```python
# ---------------------------------------------------------------------------
# post_comment / add_label / close_issue
# ---------------------------------------------------------------------------

class TestGitHubApiActions:

    HEADERS = {
        'Authorization': 'Bearer token',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }

    def _mock_post(self, status=201):
        mock = MagicMock()
        mock.status_code = status
        mock.raise_for_status = MagicMock()
        return mock

    def test_post_comment_calls_correct_endpoint(self):
        mock_resp = self._mock_post()
        with patch('requests.post', return_value=mock_resp) as mock_post:
            cd.post_comment('owner/repo', 42, 'Hello', 'token')
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert '/issues/42/comments' in call_args[0][0]
        assert call_args[1]['json']['body'] == 'Hello'

    def test_add_label_calls_correct_endpoint(self):
        mock_resp = self._mock_post()
        with patch('requests.post', return_value=mock_resp) as mock_post:
            cd.add_label('owner/repo', 42, 'duplicate', 'token')
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert '/issues/42/labels' in call_args[0][0]
        assert 'duplicate' in call_args[1]['json']['labels']

    def test_close_issue_calls_patch_endpoint(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        with patch('requests.patch', return_value=mock_resp) as mock_patch:
            cd.close_issue('owner/repo', 42, 'token')
        mock_patch.assert_called_once()
        call_args = mock_patch.call_args
        assert '/issues/42' in call_args[0][0]
        assert call_args[1]['json']['state'] == 'closed'

    def test_post_comment_does_not_raise_on_api_error(self):
        with patch('requests.post', side_effect=Exception('API error')):
            # Should not raise
            cd.post_comment('owner/repo', 42, 'Hello', 'token')

    def test_add_label_does_not_raise_on_api_error(self):
        with patch('requests.post', side_effect=Exception('API error')):
            cd.add_label('owner/repo', 42, 'duplicate', 'token')

    def test_close_issue_does_not_raise_on_api_error(self):
        with patch('requests.patch', side_effect=Exception('API error')):
            cd.close_issue('owner/repo', 42, 'token')
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_check_duplicates.py::TestGitHubApiActions -v
```

Expected: `AttributeError: module 'check_duplicates' has no attribute 'post_comment'`

- [ ] **Step 3: Write the minimal implementation**

Add to `scripts/check_duplicates.py` (after `check_github_issues`):

```python
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
        print(f'Warning: failed to post comment: {e}', file=sys.stderr)


def add_label(repo: str, issue_number: int, label: str, gh_token: str) -> None:
    """Add a label to a GitHub issue. Silently ignores errors."""
    try:
        url = f'https://api.github.com/repos/{repo}/issues/{issue_number}/labels'
        resp = requests.post(url, headers=_gh_headers(gh_token), json={'labels': [label]}, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f'Warning: failed to add label: {e}', file=sys.stderr)


def close_issue(repo: str, issue_number: int, gh_token: str) -> None:
    """Close a GitHub issue. Silently ignores errors."""
    try:
        url = f'https://api.github.com/repos/{repo}/issues/{issue_number}'
        resp = requests.patch(url, headers=_gh_headers(gh_token), json={'state': 'closed'}, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f'Warning: failed to close issue: {e}', file=sys.stderr)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_check_duplicates.py::TestGitHubApiActions -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/check_duplicates.py tests/test_check_duplicates.py
git commit -m "feat: add GitHub API action helpers (comment, label, close)"
```

---

### Task 5: Comment templates

**Files:**
- Modify: `scripts/check_duplicates.py`
- Modify: `tests/test_check_duplicates.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_check_duplicates.py`:

```python
# ---------------------------------------------------------------------------
# build_comment
# ---------------------------------------------------------------------------

class TestBuildComment:

    ENTRY = {
        'name': 'Fly.io',
        'url': 'https://fly.io',
        'description': 'App hosting with global anycast networking.',
    }

    ISSUE = {
        'number': 10,
        'title': 'Add Fly.io',
        'html_url': 'https://github.com/owner/repo/issues/10',
        'body': '**URL:** https://fly.io',
    }

    def test_exact_domain_clouds_json_comment_mentions_name(self):
        comment = cd.build_comment('exact_domain', self.ENTRY, source='clouds_json')
        assert 'Fly.io' in comment

    def test_exact_domain_clouds_json_comment_contains_closing_text(self):
        comment = cd.build_comment('exact_domain', self.ENTRY, source='clouds_json')
        assert 'Closing' in comment or 'closing' in comment

    def test_fuzzy_name_comment_says_possible_duplicate(self):
        comment = cd.build_comment('fuzzy_name', self.ENTRY, source='clouds_json')
        assert 'Possible Duplicate' in comment or 'possible duplicate' in comment.lower()

    def test_fuzzy_name_comment_does_not_mention_closing(self):
        comment = cd.build_comment('fuzzy_name', self.ENTRY, source='clouds_json')
        assert 'Closing' not in comment

    def test_existing_issue_comment_links_to_issue(self):
        comment = cd.build_comment('existing_issue', self.ISSUE, source='github_issues')
        assert 'https://github.com/owner/repo/issues/10' in comment

    def test_existing_issue_comment_contains_closing_text(self):
        comment = cd.build_comment('existing_issue', self.ISSUE, source='github_issues')
        assert 'Closing' in comment or 'closing' in comment
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_check_duplicates.py::TestBuildComment -v
```

Expected: `AttributeError: module 'check_duplicates' has no attribute 'build_comment'`

- [ ] **Step 3: Write the minimal implementation**

Add to `scripts/check_duplicates.py` (after `close_issue`):

```python
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
    else:  # fuzzy_name
        name = match.get('name', 'Unknown')
        url = match.get('url', '')
        desc = match.get('description', '')
        return (
            '⚠️ **Possible Duplicate**\n\n'
            'A similar service may already be listed:\n'
            f'- **[{name}]({url})** — {desc}\n\n'
            'Proceeding with admin review, but flagging as a possible duplicate.'
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_check_duplicates.py::TestBuildComment -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/check_duplicates.py tests/test_check_duplicates.py
git commit -m "feat: add duplicate comment templates"
```

---

### Task 6: Main orchestration + GITHUB_OUTPUT

**Files:**
- Modify: `scripts/check_duplicates.py`
- Modify: `tests/test_check_duplicates.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_check_duplicates.py`:

```python
# ---------------------------------------------------------------------------
# main() — integration
# ---------------------------------------------------------------------------

import tempfile


class TestMain:

    CLOUDS = [
        {
            "name": "Fly.io",
            "url": "https://fly.io",
            "description": "App hosting.",
            "score": 3,
            "categories": ["PaaS & Application Hosting"],
        }
    ]

    def _run_main(self, env, clouds_json_content=None, issues_response=None):
        """Helper: run main() with patched env, clouds.json, and GitHub API."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(clouds_json_content or self.CLOUDS, f)
            clouds_path = f.name

        output_lines = []

        def fake_write_output(key, value):
            output_lines.append(f'{key}={value}')

        no_op = MagicMock()

        with patch.dict(os.environ, env, clear=True):
            with patch.object(cd, '_CLOUDS_JSON_PATH', clouds_path):
                with patch.object(cd, '_write_github_output', side_effect=fake_write_output):
                    with patch.object(cd, 'post_comment', no_op):
                        with patch.object(cd, 'add_label', no_op):
                            with patch.object(cd, 'close_issue', no_op):
                                if issues_response is not None:
                                    with patch('requests.get', return_value=issues_response):
                                        cd.main()
                                else:
                                    with patch('requests.get', return_value=_make_gh_response([])):
                                        cd.main()

        os.unlink(clouds_path)
        return output_lines, no_op

    def test_exact_domain_match_sets_is_duplicate_true(self):
        env = {
            'ISSUE_BODY': '**URL:** https://fly.io',
            'ISSUE_NUMBER': '50',
            'ISSUE_TITLE': 'Add Fly',
            'GH_TOKEN': 'token',
            'REPO': 'owner/repo',
        }
        output_lines, _ = self._run_main(env)
        assert any('is_duplicate=true' in line for line in output_lines)

    def test_exact_domain_match_closes_issue(self):
        env = {
            'ISSUE_BODY': '**URL:** https://fly.io',
            'ISSUE_NUMBER': '50',
            'ISSUE_TITLE': 'Add Fly',
            'GH_TOKEN': 'token',
            'REPO': 'owner/repo',
        }
        close_mock = MagicMock()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.CLOUDS, f)
            clouds_path = f.name
        with patch.dict(os.environ, env, clear=True):
            with patch.object(cd, '_CLOUDS_JSON_PATH', clouds_path):
                with patch.object(cd, '_write_github_output', MagicMock()):
                    with patch.object(cd, 'post_comment', MagicMock()):
                        with patch.object(cd, 'add_label', MagicMock()):
                            with patch.object(cd, 'close_issue', close_mock):
                                with patch('requests.get', return_value=_make_gh_response([])):
                                    cd.main()
        os.unlink(clouds_path)
        close_mock.assert_called_once()

    def test_no_url_in_body_sets_is_duplicate_false(self):
        env = {
            'ISSUE_BODY': 'This submission has no URL at all.',
            'ISSUE_NUMBER': '50',
            'ISSUE_TITLE': 'Something',
            'GH_TOKEN': 'token',
            'REPO': 'owner/repo',
        }
        output_lines, _ = self._run_main(env)
        assert any('is_duplicate=false' in line for line in output_lines)

    def test_brand_new_submission_sets_is_duplicate_false(self):
        env = {
            'ISSUE_BODY': '**URL:** https://brandnew-cloud-xyz.io',
            'ISSUE_NUMBER': '50',
            'ISSUE_TITLE': 'Brand New Service',
            'GH_TOKEN': 'token',
            'REPO': 'owner/repo',
        }
        output_lines, _ = self._run_main(env)
        assert any('is_duplicate=false' in line for line in output_lines)

    def test_fuzzy_match_does_not_close_issue(self):
        env = {
            'ISSUE_BODY': '**URL:** https://totally-different.io',
            'ISSUE_NUMBER': '50',
            'ISSUE_TITLE': 'Fly.io Platform',  # fuzzy match to 'Fly.io'
            'GH_TOKEN': 'token',
            'REPO': 'owner/repo',
        }
        close_mock = MagicMock()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.CLOUDS, f)
            clouds_path = f.name
        with patch.dict(os.environ, env, clear=True):
            with patch.object(cd, '_CLOUDS_JSON_PATH', clouds_path):
                with patch.object(cd, '_write_github_output', MagicMock()):
                    with patch.object(cd, 'post_comment', MagicMock()):
                        with patch.object(cd, 'add_label', MagicMock()):
                            with patch.object(cd, 'close_issue', close_mock):
                                with patch('requests.get', return_value=_make_gh_response([])):
                                    cd.main()
        os.unlink(clouds_path)
        close_mock.assert_not_called()

    def test_clouds_json_read_failure_sets_is_duplicate_false(self):
        env = {
            'ISSUE_BODY': '**URL:** https://fly.io',
            'ISSUE_NUMBER': '50',
            'ISSUE_TITLE': 'Fly.io',
            'GH_TOKEN': 'token',
            'REPO': 'owner/repo',
        }
        output_lines = []
        with patch.dict(os.environ, env, clear=True):
            with patch.object(cd, '_CLOUDS_JSON_PATH', '/nonexistent/path/clouds.json'):
                with patch.object(cd, '_write_github_output', side_effect=lambda k, v: output_lines.append(f'{k}={v}')):
                    with patch('requests.get', return_value=_make_gh_response([])):
                        cd.main()
        assert any('is_duplicate=false' in line for line in output_lines)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_check_duplicates.py::TestMain -v
```

Expected: `AttributeError: module 'check_duplicates' has no attribute 'main'` (or similar)

- [ ] **Step 3: Write the minimal implementation**

Add to `scripts/check_duplicates.py` (at the bottom, after `build_comment`):

```python
# Path to clouds.json — overridable in tests
_CLOUDS_JSON_PATH = os.path.join(os.path.dirname(__file__), '..', 'docs', 'clouds.json')


def _write_github_output(key: str, value: str) -> None:
    """Write a key=value pair to $GITHUB_OUTPUT (or stdout if not set)."""
    github_output = os.environ.get('GITHUB_OUTPUT', '')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f'{key}={value}\n')
    else:
        print(f'::set-output name={key}::{value}')


def main() -> None:
    issue_body = os.environ.get('ISSUE_BODY', '')
    issue_number = int(os.environ.get('ISSUE_NUMBER', '0'))
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
        print('No URLs found in issue body — skipping duplicate check.')
        _write_github_output('is_duplicate', 'false')
        _write_github_output('duplicate_reason', 'no_urls')
        return

    submitted_domain = normalize_domain(urls[0])
    submitted_name = issue_title

    # --- Check clouds.json ---
    clouds: list[dict] = []
    try:
        with open(_CLOUDS_JSON_PATH, 'r') as f:
            clouds = json.load(f)
    except Exception as e:
        print(f'Warning: could not read clouds.json: {e}', file=sys.stderr)

    match_type, match = check_clouds_json(submitted_domain, submitted_name, clouds)

    if match_type is None and gh_token and repo:
        match_type, match = check_github_issues(
            submitted_domain, gh_token, repo, current_issue_number=issue_number
        )

    if match_type is not None:
        comment = build_comment(match_type, match, source='clouds_json' if clouds and match in clouds else 'github_issues')
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
```

- [ ] **Step 4: Run ALL tests to verify they pass**

```bash
pytest tests/test_check_duplicates.py -v
```

Expected: all tests pass (at least 34 tests)

Also verify existing tests still pass:

```bash
pytest tests/test_evaluate_submission.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add scripts/check_duplicates.py tests/test_check_duplicates.py
git commit -m "feat: add main() orchestration for duplicate detection"
```

---

### Task 7: Workflow integration

**Files:**
- Modify: `.github/workflows/evaluate-submission.yml`

> No tests for this task — the YAML change is verified by reading the file after editing.

- [ ] **Step 1: Read the current workflow**

```bash
cat .github/workflows/evaluate-submission.yml
```

Identify the step named `Extract URL and evaluate` — the new step goes immediately before it, after `Install dependencies`.

- [ ] **Step 2: Add the duplicate-check step**

Edit `.github/workflows/evaluate-submission.yml`. Insert the following block immediately after the `Install dependencies` step and before the `Extract URL and evaluate` step:

```yaml
      - name: Check for duplicates
        id: check_duplicate
        env:
          ISSUE_BODY: ${{ github.event.issue.body }}
          ISSUE_NUMBER: ${{ github.event.issue.number }}
          ISSUE_TITLE: ${{ github.event.issue.title }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          REPO: ${{ github.repository }}
        run: |
          python scripts/check_duplicates.py
```

- [ ] **Step 3: Add `if:` guards to all downstream steps**

Add `if: steps.check_duplicate.outputs.is_duplicate != 'true'` to each of these steps:

1. `Extract URL and evaluate`
2. `Read evaluation outputs`
3. `Post evaluation results`
4. `Add result label`
5. `Upload submission data as artifact` (already has an `if:` — combine with `&&`)
6. `Create PR if score >= 2` (already has an `if:` — combine with `&&`)

For steps 5 and 6 that already have `if:`, combine like this:

```yaml
      - name: Upload submission data as artifact
        if: steps.check_duplicate.outputs.is_duplicate != 'true' && steps.read_outputs.outputs.has_data == 'true'
```

```yaml
      - name: Create PR if score >= 2
        if: steps.check_duplicate.outputs.is_duplicate != 'true' && steps.read_outputs.outputs.score >= 2 && steps.read_outputs.outputs.has_data == 'true'
```

- [ ] **Step 4: Verify the final workflow looks correct**

```bash
cat .github/workflows/evaluate-submission.yml
```

Confirm:
- `check_duplicate` step appears between `Install dependencies` and `Extract URL and evaluate`
- All 6 downstream steps have `if: steps.check_duplicate.outputs.is_duplicate != 'true'` (or combined form)
- No other steps were accidentally modified

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/evaluate-submission.yml
git commit -m "ci: add duplicate detection step to evaluate-submission workflow"
```

---

## Final Verification

Run the full test suite one more time to confirm nothing is broken:

```bash
pytest tests/ -v
```

Expected: all tests pass.
