# tests/test_create_submission_pr.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from unittest.mock import patch

import create_submission_pr as cs

# A submitted URL that carries a shell command substitution; it matches the
# extraction regex in evaluate_submission.py.
PAYLOAD_URL = "https://example.com/$(touch${IFS}/tmp/pwned)"

SUBMISSION_DATA = {
    "issue_number": "999",
    "services": [
        {
            "name": "Evil Cloud",
            "url": PAYLOAD_URL,
            "description": "A service.",
            "category": "Infrastructure Clouds",
            "score": 3,
            "needs_manual_review": False,
        }
    ],
}


class TestCreatePrUsesArgumentLists:
    def test_submitted_url_reaches_gh_pr_create_as_one_argument(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text("# Alt Cloud\n")
        commands = []

        def fake_run_command(cmd, check=True, input=None, strip=True):
            commands.append(cmd)
            return ""

        monkeypatch.setattr(cs, "add_entry_to_readme", lambda submission, **kw: True)
        monkeypatch.setattr(cs, "generate_and_stage_mdx", lambda service: None)

        with patch.object(cs, "run_command", side_effect=fake_run_command):
            assert cs.create_pr(SUBMISSION_DATA) is True

        for cmd in commands:
            assert isinstance(cmd, list), f"command is not an argument list: {cmd!r}"

        pr_create = [c for c in commands if c[:3] == ["gh", "pr", "create"]]
        assert len(pr_create) == 1
        args = pr_create[0]
        body = args[args.index("--body") + 1]
        assert isinstance(body, str)
        assert body.count(PAYLOAD_URL) == 1
        assert args.count("--body") == 1
