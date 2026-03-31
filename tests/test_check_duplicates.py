# tests/test_check_duplicates.py
import sys
import os
import json  # used by TestMain (added in a later task)
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

    def test_two_non_noise_words_concatenated(self):
        # Both words retained, joined without separator
        assert cd.normalize_name('Acme Storage') == 'acmestorage'


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


# ---------------------------------------------------------------------------
# check_github_issues
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# post_comment / add_label / close_issue
# ---------------------------------------------------------------------------

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

    ISSUE = {
        'number': 10,
        'title': 'Add Fly.io',
        'html_url': 'https://github.com/owner/repo/issues/10',
        'body': '**URL:** https://fly.io',
    }

    def test_exact_domain_clouds_json_comment_mentions_name(self):
        comment = cd.build_comment('exact_domain', self.ENTRY, source='clouds_json')
        assert 'Fly.io' in comment
        assert 'https://fly.io' in comment
        assert 'App hosting' in comment

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
