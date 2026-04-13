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
        # Jina markdown mode returns rendered content with markdown links
        markdown = (
            'Title: Example Cloud\n\n'
            'URL Source: https://example.com\n\n'
            'Markdown Content:\n'
            'Welcome to Example Cloud. We provide infrastructure services.\n'
            '[Pricing](https://example.com/pricing) starts at $9/mo.\n'
            '[Sign up](https://example.com/signup) today for transparent pricing.\n'
            'Our platform offers reliable cloud infrastructure with guaranteed uptime.\n'
        )

        def side_effect(url, **kwargs):
            if 'r.jina.ai' in url:
                return _make_response(markdown)
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

    def test_jina_tries_markdown_mode_first(self):
        """Jina markdown mode (which renders JS) should be tried before HTML mode."""
        captured_calls = []

        def side_effect(url, **kwargs):
            if 'r.jina.ai' in url:
                headers = kwargs.get('headers', {})
                mode = 'html' if headers.get('X-Return-Format') == 'html' else 'markdown'
                captured_calls.append(mode)
            raise requests.exceptions.ConnectionError('blocked')

        with patch('requests.get', side_effect=side_effect):
            ev.fetch_page_with_fallback('https://example.com')

        assert captured_calls, "Jina was never called"
        assert captured_calls[0] == 'markdown', f"Expected markdown first, got: {captured_calls}"

    def test_jina_is_tried_before_requests(self):
        """Jina must be the first attempt in the cascade."""
        call_order = []

        def side_effect(url, **kwargs):
            if 'r.jina.ai' in url:
                call_order.append('jina')
            else:
                call_order.append('requests')
            raise requests.exceptions.ConnectionError('blocked')

        with patch('requests.get', side_effect=side_effect):
            ev.fetch_page_with_fallback('https://example.com')

        assert call_order[0] == 'jina', f"Expected jina first, got: {call_order}"


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
        markdown = (
            'Title: Example Cloud\n\n'
            'URL Source: https://example.com\n\n'
            'Markdown Content:\n'
            'Welcome to Example Cloud. We provide infrastructure services.\n'
            '[Pricing](https://example.com/pricing) starts at $9/mo.\n'
            '[Sign up](https://example.com/signup) today for transparent pricing.\n'
            'Our platform offers reliable cloud infrastructure with a public SLA and 99.9% uptime.\n'
        )

        def side_effect(url, **kwargs):
            if 'r.jina.ai' in url:
                return _make_response(markdown)
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
