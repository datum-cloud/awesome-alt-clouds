# Submission Validation Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the primary scraper fails, fall back to Jina Reader then Claude web search so the evaluation comment always contains actionable evidence URLs and a recommendation instead of "couldn't verify."

**Architecture:** Three-stage fetch cascade in `evaluate_service()`: requests → Jina Reader → Claude web_search. When Claude web search runs, it generates name/description/category metadata in the same call, eliminating the separate `generate_metadata_with_claude()` call. All comment rendering changes are isolated to `generate_single_result_markdown()`.

**Tech Stack:** Python 3.11, requests, BeautifulSoup4, anthropic SDK (web_search built-in tool), pytest, unittest.mock

---

## File Map

- **Modify:** `scripts/evaluate_submission.py`
  - Add `fetch_page_with_fallback()` (wraps existing `fetch_page()`, adds Jina fallback)
  - Add `evaluate_with_claude_websearch()` (new last-resort evaluator)
  - Modify `evaluate_service()` (use new fallback, embed metadata when Claude ran)
  - Modify `generate_single_result_markdown()` (render recommendation + evidence links)
  - Modify `main()` (remove redundant second `fetch_page()` call, skip metadata call when Claude already ran)
- **Create:** `tests/test_evaluate_submission.py` (all new tests)

---

## Task 1: Test infrastructure + `fetch_page_with_fallback`

**Files:**
- Create: `tests/test_evaluate_submission.py`
- Modify: `scripts/evaluate_submission.py` (add `fetch_page_with_fallback`, rename internal call in `evaluate_service`)

- [ ] **Step 1: Create test file with the failing tests**

```python
# tests/test_evaluate_submission.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import requests
import pytest
from unittest.mock import patch, MagicMock, call
from bs4 import BeautifulSoup

import evaluate_submission as ev


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(text, status=200):
    mock = MagicMock()
    mock.text = text
    mock.status_code = status
    mock.url = "https://example.com"
    mock.raise_for_status = MagicMock()
    return mock


# ---------------------------------------------------------------------------
# fetch_page_with_fallback
# ---------------------------------------------------------------------------

class TestFetchPageWithFallback:

    def test_returns_requests_result_when_requests_succeeds(self):
        html = '<html><body><p>Hello</p></body></html>'
        mock_resp = _make_response(html)
        with patch('requests.get', return_value=mock_resp):
            soup, final_url, method = ev.fetch_page_with_fallback('https://example.com')
        assert soup is not None
        assert method == 'requests'

    def test_falls_back_to_jina_when_requests_fails(self):
        html = '<html><body><a href="/pricing">Pricing</a></body></html>'

        def side_effect(url, **kwargs):
            if 'r.jina.ai' in url:
                return _make_response(html)
            raise requests.exceptions.ConnectionError('blocked')

        with patch('requests.get', side_effect=side_effect):
            soup, final_url, method = ev.fetch_page_with_fallback('https://example.com')

        assert soup is not None
        assert method == 'jina'

    def test_returns_none_triple_when_both_fail(self):
        def side_effect(url, **kwargs):
            raise requests.exceptions.ConnectionError('blocked')

        with patch('requests.get', side_effect=side_effect):
            soup, final_url, method = ev.fetch_page_with_fallback('https://example.com')

        assert soup is None
        assert final_url is None
        assert method is None

    def test_jina_url_is_correct(self):
        captured = []

        def side_effect(url, **kwargs):
            captured.append(url)
            raise requests.exceptions.ConnectionError('blocked')

        with patch('requests.get', side_effect=side_effect):
            ev.fetch_page_with_fallback('https://example.com/path')

        assert any('r.jina.ai' in u and 'example.com' in u for u in captured)
```

- [ ] **Step 2: Run the tests — verify they all fail**

```bash
cd /Users/felixwidjaja/Repositories/datum/awesome-alt-clouds
pip install pytest requests beautifulsoup4 anthropic 2>/dev/null
pytest tests/test_evaluate_submission.py::TestFetchPageWithFallback -v
```

Expected: `ERROR` — `ImportError` (function doesn't exist yet)

- [ ] **Step 3: Add `fetch_page_with_fallback` to `evaluate_submission.py`**

Add this function directly after the existing `fetch_page()` function (around line 146):

```python
def fetch_page_with_fallback(url, timeout=15, retries=2):
    """Try requests first, then Jina Reader. Returns (soup, final_url, fetch_method)."""
    # Stage 1: existing requests-based scraper
    soup, final_url = fetch_page(url, timeout=timeout, retries=retries)
    if soup is not None:
        return soup, final_url, "requests"

    # Stage 2: Jina Reader (handles JS-rendered pages)
    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; awesome-alt-clouds-bot/1.0)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try:
        response = requests.get(jina_url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        if response.text and len(response.text.strip()) > 100:
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup, url, "jina"
    except Exception as e:
        print(f"Jina Reader failed for {url}: {e}")

    return None, None, None
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_evaluate_submission.py::TestFetchPageWithFallback -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_evaluate_submission.py scripts/evaluate_submission.py
git commit -m "feat: add Jina Reader fallback in fetch_page_with_fallback"
```

---

## Task 2: `evaluate_with_claude_websearch`

**Files:**
- Modify: `scripts/evaluate_submission.py` (add new function)
- Modify: `tests/test_evaluate_submission.py` (add tests)

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_evaluate_submission.py`:

```python
# ---------------------------------------------------------------------------
# evaluate_with_claude_websearch
# ---------------------------------------------------------------------------

class TestEvaluateWithClaudeWebsearch:

    def _make_claude_response(self, json_text):
        """Build a fake anthropic Message with a text block."""
        block = MagicMock()
        block.text = json_text
        block.type = 'text'
        msg = MagicMock()
        msg.content = [block]
        return msg

    def test_returns_structured_result_on_success(self):
        json_payload = '''{
            "criteria": [
                {"name": "Transparent Public Pricing", "passed": true, "evidence": "https://example.com/pricing"},
                {"name": "Usage-based Self-Service", "passed": true, "evidence": "https://example.com/signup"},
                {"name": "Production Indicators", "passed": true, "evidence": "https://status.example.com"}
            ],
            "name": "Example Cloud",
            "description": "Provides cloud infrastructure for developers.",
            "category": "Infrastructure Clouds",
            "recommendation": "Pricing and status page found — looks legit"
        }'''

        mock_msg = self._make_claude_response(json_payload)
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            with patch('anthropic.Anthropic', return_value=mock_client):
                result = ev.evaluate_with_claude_websearch('https://example.com')

        assert result is not None
        assert result['score'] == 3
        assert result['name'] == 'Example Cloud'
        assert result['fetch_method'] == 'claude_websearch'
        assert result['recommendation'] == 'Pricing and status page found — looks legit'
        assert result['criteria'][0]['evidence'] == 'https://example.com/pricing'

    def test_returns_none_when_no_api_key(self):
        env = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_API_KEY'}
        with patch.dict(os.environ, env, clear=True):
            result = ev.evaluate_with_claude_websearch('https://example.com')
        assert result is None

    def test_returns_none_on_api_error(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception('API error')

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            with patch('anthropic.Anthropic', return_value=mock_client):
                result = ev.evaluate_with_claude_websearch('https://example.com')

        assert result is None

    def test_score_calculated_from_criteria(self):
        json_payload = '''{
            "criteria": [
                {"name": "Transparent Public Pricing", "passed": true, "evidence": "https://example.com/pricing"},
                {"name": "Usage-based Self-Service", "passed": false, "evidence": "Not found via web search"},
                {"name": "Production Indicators", "passed": true, "evidence": "https://status.example.com"}
            ],
            "name": "Example Cloud",
            "description": "Provides cloud infrastructure.",
            "category": "Infrastructure Clouds",
            "recommendation": "Partial — signup process unclear"
        }'''

        mock_msg = self._make_claude_response(json_payload)
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            with patch('anthropic.Anthropic', return_value=mock_client):
                result = ev.evaluate_with_claude_websearch('https://example.com')

        assert result['score'] == 2

    def test_invalid_category_defaults_to_infrastructure(self):
        json_payload = '''{
            "criteria": [
                {"name": "Transparent Public Pricing", "passed": true, "evidence": "https://example.com/pricing"},
                {"name": "Usage-based Self-Service", "passed": true, "evidence": "https://example.com/signup"},
                {"name": "Production Indicators", "passed": true, "evidence": "https://status.example.com"}
            ],
            "name": "Example Cloud",
            "description": "Provides cloud infrastructure.",
            "category": "Not A Real Category",
            "recommendation": "Looks good"
        }'''

        mock_msg = self._make_claude_response(json_payload)
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            with patch('anthropic.Anthropic', return_value=mock_client):
                result = ev.evaluate_with_claude_websearch('https://example.com')

        assert result['category'] == 'Infrastructure Clouds'
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_evaluate_submission.py::TestEvaluateWithClaudeWebsearch -v
```

Expected: `ERROR` — `ImportError` (function doesn't exist yet)

- [ ] **Step 3: Add `evaluate_with_claude_websearch` to `evaluate_submission.py`**

Add this function after `generate_metadata_with_claude()` (around line 377):

```python
def evaluate_with_claude_websearch(url):
    """Last-resort evaluation using Claude with web_search when both scrapers fail.

    Returns a dict with criteria, score, name, description, category,
    recommendation, and fetch_method='claude_websearch', or None on failure.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set, cannot use Claude web search")
        return None

    print(f"Falling back to Claude web search for {url}...")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        domain = urlparse(url).netloc.replace('www.', '')
        categories_list = "\n".join(f"- {cat}" for cat in CATEGORIES)

        prompt = f"""Evaluate this cloud service for an awesome list. Use web search to find real evidence.

URL: {url}
Domain: {domain}

Search for (in this order):
1. "{domain} pricing" to find their pricing page URL
2. "status.{domain}" OR "{domain} status page" to find their status/uptime page
3. "{domain} sign up" OR "{domain} register" to find their self-service signup URL

Then assess these 3 criteria and provide the actual URLs you found as evidence:
1. Transparent Public Pricing - public pricing page with actual prices shown
2. Usage-based Self-Service - can sign up and use without contacting sales
3. Production Indicators - public SLA or status page exists

Also provide:
- name: official service name (short, no taglines)
- description: what the service does (max 200 chars, start with "Provides", "Offers", "Delivers", etc.)
- category: best fit from this list:
{categories_list}
- recommendation: one sentence (e.g. "Pricing and status page found — looks legit" or "No SLA evidence found — review carefully")

If you cannot find evidence for a criterion, set passed to false and evidence to "Not found via web search".

Respond in this exact JSON format only, no other text:
{{
  "criteria": [
    {{"name": "Transparent Public Pricing", "passed": true, "evidence": "https://example.com/pricing"}},
    {{"name": "Usage-based Self-Service", "passed": true, "evidence": "https://example.com/signup"}},
    {{"name": "Production Indicators", "passed": false, "evidence": "Not found via web search"}}
  ],
  "name": "Service Name",
  "description": "Description under 200 chars.",
  "category": "Category Name",
  "recommendation": "One sentence recommendation"
}}"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract text from the last text block in the response
        response_text = next(
            (block.text for block in reversed(message.content) if hasattr(block, 'text')),
            ""
        ).strip()

        if not response_text:
            print(f"Claude web search returned no text for {url}")
            return None

        # Strip markdown code fences if present
        if "```" in response_text:
            json_match = re.search(r'\{[\s\S]+\}', response_text)
            if json_match:
                response_text = json_match.group(0)

        data = json.loads(response_text)

        # Validate and normalise
        score = sum(1 for c in data['criteria'] if c.get('passed'))
        if data.get('category') not in CATEGORIES:
            print(f"Warning: invalid category '{data.get('category')}', defaulting")
            data['category'] = "Infrastructure Clouds"
        if len(data.get('description', '')) > 200:
            data['description'] = data['description'][:197] + "..."

        print(f"Claude web search result: score={score}/3, name={data['name']}")
        return {
            'criteria': data['criteria'],
            'score': score,
            'name': data['name'],
            'description': data['description'],
            'category': data['category'],
            'recommendation': data.get('recommendation', ''),
            'fetch_method': 'claude_websearch',
        }

    except Exception as e:
        print(f"Error in Claude web search for {url}: {e}")
        return None
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_evaluate_submission.py::TestEvaluateWithClaudeWebsearch -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/evaluate_submission.py tests/test_evaluate_submission.py
git commit -m "feat: add evaluate_with_claude_websearch as last-resort evaluator"
```

---

## Task 3: Update comment template for web search results

**Files:**
- Modify: `scripts/evaluate_submission.py` (`generate_single_result_markdown`)
- Modify: `tests/test_evaluate_submission.py` (add tests)

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_evaluate_submission.py`:

```python
# ---------------------------------------------------------------------------
# generate_single_result_markdown — web search path
# ---------------------------------------------------------------------------

class TestGenerateSingleResultMarkdownWebSearch:

    def _ws_result(self, score=3):
        return {
            'url': 'https://example.com',
            'company_name': 'Example Cloud',
            'score': score,
            'fetch_method': 'claude_websearch',
            'needs_manual_review': score < 3,
            'recommendation': 'Pricing and status page found — looks legit',
            'criteria': [
                {'name': 'Transparent Public Pricing', 'passed': True,  'evidence': 'https://example.com/pricing'},
                {'name': 'Usage-based Self-Service',    'passed': True,  'evidence': 'https://example.com/signup'},
                {'name': 'Production Indicators',       'passed': True,  'evidence': 'https://status.example.com'},
            ],
            'fetch_failed': False,
        }

    def _ws_ai_metadata(self):
        return {
            'name': 'Example Cloud',
            'description': 'Provides cloud infrastructure.',
            'category': 'Infrastructure Clouds',
        }

    def test_recommendation_line_appears_in_comment(self):
        result = self._ws_result()
        md = ev.generate_single_result_markdown(result, self._ws_ai_metadata())
        assert 'Pricing and status page found' in md

    def test_evidence_urls_rendered_as_markdown_links(self):
        result = self._ws_result()
        md = ev.generate_single_result_markdown(result, self._ws_ai_metadata())
        assert '[https://example.com/pricing](https://example.com/pricing)' in md

    def test_web_search_badge_present(self):
        result = self._ws_result()
        md = ev.generate_single_result_markdown(result, self._ws_ai_metadata())
        assert 'web search' in md.lower()

    def test_non_url_evidence_rendered_as_plain_text(self):
        result = self._ws_result(score=1)
        result['criteria'][1]['passed'] = False
        result['criteria'][1]['evidence'] = 'Not found via web search'
        md = ev.generate_single_result_markdown(result, self._ws_ai_metadata())
        assert 'Not found via web search' in md
        # Should NOT wrap plain text in a Markdown link
        assert '[Not found' not in md

    def test_existing_requests_path_unchanged(self):
        result = {
            'url': 'https://example.com',
            'company_name': 'Example Cloud',
            'score': 3,
            'fetch_method': 'requests',
            'fetch_failed': False,
            'criteria': [
                {'name': 'Transparent Public Pricing', 'passed': True,  'evidence': 'Pricing page found at https://example.com/pricing'},
                {'name': 'Usage-based Self-Service',    'passed': True,  'evidence': 'Self-service signup available'},
                {'name': 'Production Indicators',       'passed': True,  'evidence': 'Status page found: https://status.example.com'},
            ],
        }
        md = ev.generate_single_result_markdown(result, self._ws_ai_metadata())
        # Recommendation block should NOT appear for non-websearch results
        assert 'Pricing and status page found' not in md
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_evaluate_submission.py::TestGenerateSingleResultMarkdownWebSearch -v
```

Expected: `FAILED` — recommendation/links not in output

- [ ] **Step 3: Update `generate_single_result_markdown` in `evaluate_submission.py`**

Replace the existing `generate_single_result_markdown` function (lines 421–479) with:

```python
def generate_single_result_markdown(result, ai_metadata=None):
    """Generate markdown for a single service result"""
    score = result['score']
    fetch_failed = result.get('fetch_failed', False)
    needs_manual = result.get('needs_manual_review', False)
    fetch_method = result.get('fetch_method')
    recommendation = result.get('recommendation', '')

    if fetch_failed:
        status = "Needs Manual Review"
        emoji = "orange_circle"
    elif score == 3:
        status = "Ready to Merge"
        emoji = "green_circle"
    elif score == 2:
        status = "Needs Review"
        emoji = "yellow_circle"
    else:
        status = "Does Not Meet Criteria"
        emoji = "red_circle"

    web_search_badge = " *(verified via web search)*" if fetch_method == "claude_websearch" else ""

    md = f"""### {result['company_name']}

**URL:** {result['url']}
**Score:** {score}/3 :{emoji}: {status}{web_search_badge}
"""

    if fetch_method == "claude_websearch" and recommendation:
        md += f"\n> :mag: {recommendation}\n"

    if fetch_failed:
        md += "\n:warning: **Could not fetch website** (likely Cloudflare protected). Criteria could not be verified automatically.\n\n"

    md += """
| Criteria | Status | Evidence |
|----------|--------|----------|
"""

    for c in result['criteria']:
        if c['passed'] is None:
            status_icon = ":grey_question:"
        elif c['passed']:
            status_icon = ":white_check_mark:"
        else:
            status_icon = ":x:"

        evidence = c['evidence']
        # Render evidence as a clickable link if it's a URL
        if fetch_method == "claude_websearch" and evidence.startswith("http"):
            evidence = f"[{evidence}]({evidence})"

        md += f"| {c['name']} | {status_icon} | {evidence} |\n"

    if ai_metadata:
        md += f"""
**AI-Generated Entry:**
- **Name:** {ai_metadata['name']}
- **Description:** {ai_metadata['description']}
- **Category:** {ai_metadata['category']}

"""
        if needs_manual:
            md += ":warning: Will be included in PR but **requires manual verification** of criteria\n"
        else:
            md += ":white_check_mark: Will be included in PR\n"
    elif score >= 2:
        md += "\n:warning: Could not generate AI metadata\n"
    else:
        md += "\n:x: Does not meet minimum criteria (2/3)\n"

    return md
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_evaluate_submission.py::TestGenerateSingleResultMarkdownWebSearch -v
```

Expected: `5 passed`

- [ ] **Step 5: Run full test suite to ensure no regressions**

```bash
pytest tests/test_evaluate_submission.py -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add scripts/evaluate_submission.py tests/test_evaluate_submission.py
git commit -m "feat: render recommendation and evidence links in web search evaluation comment"
```

---

## Task 4: Wire `evaluate_service()` and `main()` together

**Files:**
- Modify: `scripts/evaluate_submission.py` (`evaluate_service`, `main`)
- Modify: `tests/test_evaluate_submission.py` (add integration tests)

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_evaluate_submission.py`:

```python
# ---------------------------------------------------------------------------
# evaluate_service — cascade integration
# ---------------------------------------------------------------------------

class TestEvaluateServiceCascade:

    def test_uses_requests_when_it_succeeds(self):
        html = '<html><body><a href="/pricing">Pricing $9/mo</a><a href="/signup">Sign up</a></body></html>'
        mock_resp = _make_response(html)
        with patch('requests.get', return_value=mock_resp):
            result = ev.evaluate_service('https://example.com')
        assert result['fetch_method'] == 'requests'
        assert result['fetch_failed'] is False

    def test_uses_jina_when_requests_fails(self):
        html = '<html><body><a href="/pricing">Pricing $9/mo</a></body></html>'

        def side_effect(url, **kwargs):
            if 'r.jina.ai' in url:
                return _make_response(html)
            raise requests.exceptions.ConnectionError('blocked')

        with patch('requests.get', side_effect=side_effect):
            result = ev.evaluate_service('https://example.com')

        assert result['fetch_method'] == 'jina'
        assert result['fetch_failed'] is False

    def test_calls_claude_websearch_when_both_scrapers_fail(self):
        ws_result = {
            'criteria': [
                {'name': 'Transparent Public Pricing', 'passed': True, 'evidence': 'https://example.com/pricing'},
                {'name': 'Usage-based Self-Service', 'passed': True, 'evidence': 'https://example.com/signup'},
                {'name': 'Production Indicators', 'passed': True, 'evidence': 'https://status.example.com'},
            ],
            'score': 3,
            'name': 'Example Cloud',
            'description': 'Provides cloud infrastructure.',
            'category': 'Infrastructure Clouds',
            'recommendation': 'Pricing and status page found — looks legit',
            'fetch_method': 'claude_websearch',
        }

        def side_effect(url, **kwargs):
            raise requests.exceptions.ConnectionError('blocked')

        with patch('requests.get', side_effect=side_effect):
            with patch.object(ev, 'evaluate_with_claude_websearch', return_value=ws_result) as mock_ws:
                result = ev.evaluate_service('https://example.com')

        mock_ws.assert_called_once_with('https://example.com')
        assert result['fetch_method'] == 'claude_websearch'
        assert result['ai_metadata']['name'] == 'Example Cloud'
        assert result['recommendation'] == 'Pricing and status page found — looks legit'

    def test_falls_back_to_fetch_failed_when_all_stages_fail(self):
        def side_effect(url, **kwargs):
            raise requests.exceptions.ConnectionError('blocked')

        with patch('requests.get', side_effect=side_effect):
            with patch.object(ev, 'evaluate_with_claude_websearch', return_value=None):
                result = ev.evaluate_service('https://example.com')

        assert result['fetch_failed'] is True
        assert result['fetch_method'] is None

    def test_result_includes_page_content_when_scraped(self):
        html = '<html><body><p>Hello world</p></body></html>'
        with patch('requests.get', return_value=_make_response(html)):
            result = ev.evaluate_service('https://example.com')
        assert 'page_content' in result
        assert 'Hello world' in result['page_content']
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_evaluate_submission.py::TestEvaluateServiceCascade -v
```

Expected: `FAILED` — `evaluate_service` still uses old `fetch_page()` signature

- [ ] **Step 3: Replace `evaluate_service()` in `evaluate_submission.py`**

Replace the existing `evaluate_service` function (lines 380–418) with:

```python
def evaluate_service(url):
    """Evaluate a service against all 3 criteria using the fetch cascade."""
    print(f"Evaluating: {url}")

    soup, final_url, fetch_method = fetch_page_with_fallback(url)

    if fetch_method is None:
        # Both scrapers failed — try Claude web search as last resort
        ws_result = evaluate_with_claude_websearch(url)
        if ws_result:
            return {
                'url': url,
                'company_name': ws_result['name'],
                'score': ws_result['score'],
                'criteria': ws_result['criteria'],
                'fetch_failed': False,
                'fetch_method': 'claude_websearch',
                'needs_manual_review': ws_result['score'] < 3,
                'ai_metadata': {
                    'name': ws_result['name'],
                    'description': ws_result['description'],
                    'category': ws_result['category'],
                },
                'recommendation': ws_result['recommendation'],
                'page_content': '',
            }
        # All three stages failed — preserve existing behaviour
        return {
            'url': url,
            'company_name': extract_company_name(url, None),
            'score': 2,
            'criteria': [
                {'name': 'Transparent Public Pricing', 'passed': None, 'evidence': 'Could not verify (site protected)'},
                {'name': 'Usage-based Self-Service',    'passed': None, 'evidence': 'Could not verify (site protected)'},
                {'name': 'Production Indicators',       'passed': None, 'evidence': 'Could not verify (site protected)'},
            ],
            'fetch_failed': True,
            'fetch_method': None,
            'needs_manual_review': True,
            'page_content': '',
        }

    base_url = final_url or url
    criteria = [
        check_pricing_page(soup, base_url),
        check_self_service(soup, base_url),
        check_production_indicators(soup, base_url),
    ]
    score = sum(1 for c in criteria if c['passed'])

    return {
        'url': url,
        'company_name': extract_company_name(url, soup),
        'score': score,
        'criteria': criteria,
        'fetch_failed': False,
        'fetch_method': fetch_method,
        'page_content': soup.get_text()[:20000],
    }
```

- [ ] **Step 4: Update `main()` to use the new result shape**

In `main()`, find the block starting at `# Fetch page content` (around line 591) and replace the entire per-URL loop body with:

```python
    for url in urls:
        print(f"\n--- Evaluating: {url} ---")

        # Evaluate against criteria (fetch cascade is handled inside evaluate_service)
        result = evaluate_service(url)

        # Apply admin score override if provided
        if admin_approved and admin_score_override:
            original_score = result['score']
            result['score'] = int(admin_score_override)
            result['admin_override'] = True
            print(f"Admin override: {original_score}/3 -> {result['score']}/3")

        should_pass = admin_approved or result['score'] >= 2

        if should_pass:
            # Claude web search already generated metadata — use it directly
            if result.get('fetch_method') == 'claude_websearch' and result.get('ai_metadata'):
                ai_metadata = result['ai_metadata']
                result['company_name'] = ai_metadata['name']
                passing_services.append({
                    'name': ai_metadata['name'],
                    'url': url,
                    'description': ai_metadata['description'],
                    'category': ai_metadata['category'],
                    'score': result['score'],
                    'needs_manual_review': result.get('needs_manual_review', False),
                    'admin_approved': admin_approved,
                })
            else:
                # Scraped successfully — call Claude for metadata as before
                page_content = result.get('page_content', '')
                ai_metadata = generate_metadata_with_claude(url, page_content)
                if ai_metadata:
                    result['company_name'] = ai_metadata['name']
                    result['ai_metadata'] = ai_metadata
                    passing_services.append({
                        'name': ai_metadata['name'],
                        'url': url,
                        'description': ai_metadata['description'],
                        'category': ai_metadata['category'],
                        'score': result['score'],
                        'needs_manual_review': False if admin_approved else result.get('needs_manual_review', False),
                        'admin_approved': admin_approved,
                    })
                elif admin_approved:
                    fallback_name = result['company_name']
                    print(f"Warning: Claude API failed, using fallback for {fallback_name}")
                    passing_services.append({
                        'name': fallback_name,
                        'url': url,
                        'description': "Cloud service provider.",
                        'category': 'Infrastructure Clouds',
                        'score': result['score'],
                        'needs_manual_review': True,
                        'admin_approved': admin_approved,
                    })
                    result['ai_metadata'] = {
                        'name': fallback_name,
                        'description': 'Cloud service provider.',
                        'category': 'Infrastructure Clouds',
                        'fallback': True,
                    }

        results_list.append(result)
        print(f"Score: {result['score']}/3")
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/test_evaluate_submission.py -v
```

Expected: all tests pass

- [ ] **Step 6: Smoke test the script locally with a known Cloudflare-blocked domain**

```bash
cd /Users/felixwidjaja/Repositories/datum/awesome-alt-clouds
ISSUE_BODY="**URL:** https://cloudflare.com" ISSUE_NUMBER="999" ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python scripts/evaluate_submission.py
cat evaluation_results.md
```

Expected: comment contains a recommendation line and evidence URLs, not "couldn't verify"

- [ ] **Step 7: Commit**

```bash
git add scripts/evaluate_submission.py tests/test_evaluate_submission.py
git commit -m "feat: wire fetch cascade into evaluate_service and main"
```
