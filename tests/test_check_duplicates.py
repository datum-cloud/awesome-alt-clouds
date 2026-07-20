# tests/test_check_duplicates.py
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import pytest
from unittest.mock import patch, MagicMock

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

    def test_uppercase_scheme(self):
        assert cd.normalize_domain('HTTPS://EXAMPLE.COM') == 'example.com'

    def test_strips_port(self):
        assert cd.normalize_domain('https://example.com:8080/path') == 'example.com'


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

    def test_two_non_noise_words_space_joined(self):
        assert cd.normalize_name('Acme Storage') == 'acme storage'

    def test_namecheap(self):
        assert cd.normalize_name('Namecheap') == 'namecheap'


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
        assert entry['name'] == 'Fly.io'

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

    def test_substring_false_positive_namecheap_vs_heap(self):
        clouds = [{
            "name": "Heap",
            "url": "https://heap.io",
            "description": "Product analytics.",
            "score": 3,
            "categories": [],
        }]
        result = cd.check_clouds_json('namecheap.com', 'Namecheap', clouds)
        assert result == (None, None)

    def test_short_exact_name_match_below_token_length_gate(self):
        # 'Ory' normalises to 'ory' (3 chars) — below the >=4 token-overlap
        # gate, but an exact match after normalisation should still fire.
        clouds = [{
            "name": "Ory",
            "url": "https://www.ory.sh/",
            "description": "Open-source identity infrastructure.",
            "score": 3,
            "categories": [],
        }]
        match_type, entry = cd.check_clouds_json('ory.com', 'Ory', clouds)
        assert match_type == 'fuzzy_name'
        assert entry['name'] == 'Ory'

    def test_short_different_names_do_not_match(self):
        # Two distinct short names should not collide.
        clouds = [{
            "name": "Fly",
            "url": "https://fly.io",
            "description": "...",
            "score": 3,
            "categories": [],
        }]
        result = cd.check_clouds_json('other.io', 'Vex', clouds)
        assert result == (None, None)


# ---------------------------------------------------------------------------
# resolve_final_domain
# ---------------------------------------------------------------------------


class TestResolveFinalDomain:

    def _mock_response(self, final_url):
        mock = MagicMock()
        mock.url = final_url
        mock.close = MagicMock()
        return mock

    def test_no_redirect_returns_same_domain(self):
        with patch('requests.get', return_value=self._mock_response('https://ory.com/')):
            assert cd.resolve_final_domain('https://ory.com/') == 'ory.com'

    def test_redirect_returns_final_domain(self):
        with patch('requests.get', return_value=self._mock_response('https://www.ory.com/')):
            assert cd.resolve_final_domain('https://www.ory.sh/') == 'ory.com'

    def test_exception_returns_empty_string(self):
        with patch('requests.get', side_effect=Exception('connection error')):
            assert cd.resolve_final_domain('https://unreachable.example/') == ''

    def test_timeout_returns_empty_string(self):
        import requests as requests_module
        with patch('requests.get', side_effect=requests_module.exceptions.Timeout('timed out')):
            assert cd.resolve_final_domain('https://slow.example/') == ''


# ---------------------------------------------------------------------------
# check_clouds_json_with_redirects
# ---------------------------------------------------------------------------


class TestCheckCloudsJsonWithRedirects:

    ORY_CLOUDS = [{
        "name": "Different Name Entirely",
        "url": "https://www.ory.sh/",
        "description": "Open-source identity infrastructure.",
        "score": 3,
        "categories": [],
    }]

    def test_exact_domain_short_circuits_without_network(self):
        clouds = [{
            "name": "Fly.io",
            "url": "https://fly.io",
            "description": "...",
            "score": 3,
            "categories": [],
        }]
        with patch('requests.get') as mock_get:
            match_type, entry = cd.check_clouds_json_with_redirects(
                'fly.io', 'Fly.io', 'https://fly.io', clouds,
            )
        assert match_type == 'exact_domain'
        mock_get.assert_not_called()

    def test_fuzzy_name_upgraded_to_redirect_domain_when_final_domains_match(self):
        clouds = [{
            "name": "Ory",
            "url": "https://www.ory.sh/",
            "description": "...",
            "score": 3,
            "categories": [],
        }]

        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.close = MagicMock()
            # Both the submitted URL and the stored candidate URL resolve to ory.com
            resp.url = 'https://www.ory.com/'
            return resp

        with patch('requests.get', side_effect=fake_get):
            match_type, entry = cd.check_clouds_json_with_redirects(
                'ory.com', 'Ory', 'https://www.ory.com/', clouds,
            )
        assert match_type == 'redirect_domain'
        assert entry['name'] == 'Ory'

    def test_fuzzy_name_stays_fuzzy_when_redirect_check_fails(self):
        clouds = [{
            "name": "Ory",
            "url": "https://www.ory.sh/",
            "description": "...",
            "score": 3,
            "categories": [],
        }]
        with patch('requests.get', side_effect=Exception('network down')):
            match_type, entry = cd.check_clouds_json_with_redirects(
                'ory.com', 'Ory', 'https://www.ory.com/', clouds,
            )
        assert match_type == 'fuzzy_name'
        assert entry['name'] == 'Ory'

    def test_no_name_match_upgraded_via_submitted_url_redirect(self):
        # Submitted under a totally different name, but the URL redirects
        # to an already-listed entry's domain.
        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.close = MagicMock()
            resp.url = 'https://www.ory.sh/'
            return resp

        with patch('requests.get', side_effect=fake_get):
            match_type, entry = cd.check_clouds_json_with_redirects(
                'rebranded-name.com', 'Totally New Brand', 'https://rebranded-name.com', self.ORY_CLOUDS,
            )
        assert match_type == 'redirect_domain'
        assert entry['name'] == 'Different Name Entirely'

    def test_no_match_stays_none_when_redirect_resolution_fails(self):
        with patch('requests.get', side_effect=Exception('network down')):
            result = cd.check_clouds_json_with_redirects(
                'brandnew.io', 'Brand New Service', 'https://brandnew.io', self.ORY_CLOUDS,
            )
        assert result == (None, None)

    def test_no_match_stays_none_when_no_redirect_happens(self):
        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.close = MagicMock()
            resp.url = url  # no redirect
            return resp

        with patch('requests.get', side_effect=fake_get):
            result = cd.check_clouds_json_with_redirects(
                'brandnew.io', 'Brand New Service', 'https://brandnew.io', self.ORY_CLOUDS,
            )
        assert result == (None, None)


# ---------------------------------------------------------------------------
# post_comment / add_label / close_issue
# ---------------------------------------------------------------------------


def _make_gh_response(issues, link_header=None):
    """Build a mock requests.Response for the GitHub API."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = issues
    mock.headers = {}
    if link_header:
        mock.headers['Link'] = link_header
    mock.raise_for_status = MagicMock()
    return mock

class TestGitHubApiActions:

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
        assert call_args[0][0].endswith('/issues/42')
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


# ---------------------------------------------------------------------------
# build_comment
# ---------------------------------------------------------------------------

class TestBuildComment:

    ENTRY = {
        'name': 'Fly.io',
        'url': 'https://fly.io',
        'description': 'App hosting with global anycast networking.',
    }

    def test_exact_domain_comment_mentions_name(self):
        comment = cd.build_comment('exact_domain', self.ENTRY)
        assert 'Fly.io' in comment
        assert 'https://fly.io' in comment
        assert 'App hosting' in comment

    def test_exact_domain_comment_contains_closing_text(self):
        comment = cd.build_comment('exact_domain', self.ENTRY)
        assert 'Closing' in comment or 'closing' in comment

    def test_fuzzy_name_comment_says_possible_duplicate(self):
        comment = cd.build_comment('fuzzy_name', self.ENTRY)
        assert 'Possible Duplicate' in comment or 'possible duplicate' in comment.lower()

    def test_fuzzy_name_comment_does_not_mention_closing(self):
        comment = cd.build_comment('fuzzy_name', self.ENTRY)
        assert 'Closing' not in comment

    def test_redirect_domain_comment_mentions_redirect(self):
        comment = cd.build_comment('redirect_domain', self.ENTRY)
        assert 'redirect' in comment.lower()
        assert 'Fly.io' in comment

    def test_redirect_domain_comment_does_not_mention_closing(self):
        comment = cd.build_comment('redirect_domain', self.ENTRY)
        assert 'Closing' not in comment

    def test_unknown_match_type_raises(self):
        with pytest.raises(ValueError):
            cd.build_comment('unknown_type', self.ENTRY)


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

    def _run_main(self, env, clouds_json_content=None, watchlist_json_content=None, resolve_final_domain=None):
        """Helper: run main() with patched env and data files.

        By default `resolve_final_domain` is patched to always return '' (as
        if every live redirect check failed/timed out), so existing tests
        keep their pre-redirect-detection behaviour without hitting the
        network. Pass a callable via `resolve_final_domain` to simulate
        specific redirect outcomes.
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(clouds_json_content or self.CLOUDS, f)
            clouds_path = f.name

        watchlist_path = None
        if watchlist_json_content is not None:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(watchlist_json_content, f)
                watchlist_path = f.name
        else:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump([], f)
                watchlist_path = f.name

        output_lines = []

        def fake_write_output(key, value):
            output_lines.append(f'{key}={value}')

        no_op = MagicMock()
        fake_resolve = resolve_final_domain or (lambda url, timeout=10: '')

        with patch.dict(os.environ, env, clear=True):
            with patch.object(cd, '_CLOUDS_JSON_PATH', clouds_path):
                with patch.object(cd, '_WATCHLIST_JSON_PATH', watchlist_path):
                    with patch.object(cd, '_write_github_output', side_effect=fake_write_output):
                        with patch.object(cd, 'post_comment', no_op):
                            with patch.object(cd, 'add_label', no_op):
                                with patch.object(cd, 'close_issue', no_op):
                                    with patch.object(cd, 'resolve_final_domain', side_effect=fake_resolve):
                                        cd.main()

        os.unlink(clouds_path)
        os.unlink(watchlist_path)
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
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([], f)
            watchlist_path = f.name
        with patch.dict(os.environ, env, clear=True):
            with patch.object(cd, '_CLOUDS_JSON_PATH', clouds_path):
                with patch.object(cd, '_WATCHLIST_JSON_PATH', watchlist_path):
                    with patch.object(cd, '_write_github_output', MagicMock()):
                        with patch.object(cd, 'post_comment', MagicMock()):
                            with patch.object(cd, 'add_label', MagicMock()):
                                with patch.object(cd, 'close_issue', close_mock):
                                    cd.main()
        os.unlink(clouds_path)
        os.unlink(watchlist_path)
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
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([], f)
            watchlist_path = f.name
        with patch.dict(os.environ, env, clear=True):
            with patch.object(cd, '_CLOUDS_JSON_PATH', clouds_path):
                with patch.object(cd, '_WATCHLIST_JSON_PATH', watchlist_path):
                    with patch.object(cd, '_write_github_output', MagicMock()):
                        with patch.object(cd, 'post_comment', MagicMock()):
                            with patch.object(cd, 'add_label', MagicMock()):
                                with patch.object(cd, 'close_issue', close_mock):
                                    with patch.object(cd, 'resolve_final_domain', return_value=''):
                                        cd.main()
        os.unlink(clouds_path)
        os.unlink(watchlist_path)
        close_mock.assert_not_called()

    def test_redirect_domain_match_sets_is_duplicate_true_without_closing(self):
        # Different name, but the submitted URL redirects to the listed domain.
        env = {
            'ISSUE_BODY': '**URL:** https://old-ory-domain.example',
            'ISSUE_NUMBER': '50',
            'ISSUE_TITLE': 'Totally Different Name',
            'GH_TOKEN': 'token',
            'REPO': 'owner/repo',
        }
        output_lines, mocks = self._run_main(
            env,
            resolve_final_domain=lambda url, timeout=10: 'fly.io',
        )
        assert any('is_duplicate=true' in line for line in output_lines)
        assert any('duplicate_reason=redirect_domain' in line for line in output_lines)

    def test_clouds_json_read_failure_sets_is_duplicate_false(self):
        env = {
            'ISSUE_BODY': '**URL:** https://fly.io',
            'ISSUE_NUMBER': '50',
            'ISSUE_TITLE': 'Fly.io',
            'GH_TOKEN': 'token',
            'REPO': 'owner/repo',
        }
        output_lines = []
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([], f)
            watchlist_path = f.name
        with patch.dict(os.environ, env, clear=True):
            with patch.object(cd, '_CLOUDS_JSON_PATH', '/nonexistent/path/clouds.json'):
                with patch.object(cd, '_WATCHLIST_JSON_PATH', watchlist_path):
                    with patch.object(cd, '_write_github_output', side_effect=lambda k, v: output_lines.append(f'{k}={v}')):
                        cd.main()
        os.unlink(watchlist_path)
        assert any('is_duplicate=false' in line for line in output_lines)

    def test_watchlist_resubmission_sets_is_duplicate_false(self):
        env = {
            'ISSUE_BODY': '**URL:** https://iren.com',
            'ISSUE_NUMBER': '50',
            'ISSUE_TITLE': 'Iren',
            'GH_TOKEN': 'token',
            'REPO': 'owner/repo',
        }
        watchlist = [{
            'name': 'Iren',
            'url': 'https://iren.com',
            'criteriaNeed': 'Public pricing page; self-service signup',
            'reasonNotQualifying': 'Score 1/3: no transparent pricing',
        }]
        output_lines, mocks = self._run_main(env, watchlist_json_content=watchlist)
        assert any('is_duplicate=false' in line for line in output_lines)
        assert any('duplicate_reason=watchlist_resubmission' in line for line in output_lines)
        mocks.assert_called()

    def test_watchlist_resubmission_adds_watchlist_label(self):
        env = {
            'ISSUE_BODY': '**URL:** https://iren.com',
            'ISSUE_NUMBER': '50',
            'ISSUE_TITLE': 'Iren',
            'GH_TOKEN': 'token',
            'REPO': 'owner/repo',
        }
        watchlist = [{'name': 'Iren', 'url': 'https://iren.com', 'criteriaNeed': 'pricing'}]
        label_mock = MagicMock()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.CLOUDS, f)
            clouds_path = f.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(watchlist, f)
            watchlist_path = f.name
        with patch.dict(os.environ, env, clear=True):
            with patch.object(cd, '_CLOUDS_JSON_PATH', clouds_path):
                with patch.object(cd, '_WATCHLIST_JSON_PATH', watchlist_path):
                    with patch.object(cd, '_write_github_output', MagicMock()):
                        with patch.object(cd, 'post_comment', MagicMock()):
                            with patch.object(cd, 'add_label', label_mock):
                                with patch.object(cd, 'close_issue', MagicMock()):
                                    cd.main()
        os.unlink(clouds_path)
        os.unlink(watchlist_path)
        label_mock.assert_called_once()
        assert label_mock.call_args[0][2] == 'watchlist'
