# tests/test_create_graduation_pr.py
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from unittest.mock import patch

import create_graduation_pr as cg

SAMPLE_README = """# Alt Cloud

## Workload Clouds

* 🟢 [Alpha DB](https://alpha.example.com/) - A database.
* 🟡🔵 [Turbopuffer](https://turbopuffer.com/) - Vector database. <!-- tags: vector -->

## Service Clouds

* 🟢 [Zeta Auth](https://zeta.example.com/) - Authentication.
"""

GRADUATION_DATA = {
    "issue_number": "326",
    "name": "Turbopuffer",
    "url": "https://turbopuffer.com/",
    "old_category": "Workload Clouds",
    "new_category": "Workload Clouds",
    "tags": ["vector", "open-source"],
    "score": 3,
    "description": "Fast serverless vector database.",
    "needs_manual_review": False,
}


class TestMoveEntryInReadme:
    def test_graduation_removes_badge_and_refreshes_entry(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        assert cg.move_entry_in_readme(GRADUATION_DATA) is True

        content = (tmp_path / "README.md").read_text()
        line = next(line for line in content.split("\n") if "Turbopuffer" in line)
        assert line == (
            "* 🟢 [Turbopuffer](https://turbopuffer.com/) - Fast serverless vector database. "
            "<!-- tags: vector, open-source -->"
        )
        assert content.count("Turbopuffer") == 1
        assert content.index("## Workload Clouds") < content.index("Turbopuffer")
        assert content.index("Turbopuffer") < content.index("## Service Clouds")

    def test_graduation_can_re_file_into_another_category(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        data = {**GRADUATION_DATA, "new_category": "Service Clouds"}
        assert cg.move_entry_in_readme(data) is True

        content = (tmp_path / "README.md").read_text()
        assert content.index("## Service Clouds") < content.index("Turbopuffer")

    def test_returns_false_when_entry_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        data = {**GRADUATION_DATA, "name": "Nonexistent"}
        assert cg.move_entry_in_readme(data) is False

    def test_returns_false_when_category_drifted(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        data = {**GRADUATION_DATA, "old_category": "Service Clouds"}
        assert cg.move_entry_in_readme(data) is False

    def test_returns_false_when_target_category_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        data = {**GRADUATION_DATA, "new_category": "Nonexistent Category"}
        assert cg.move_entry_in_readme(data) is False


class TestCreatePr:
    def test_runs_expected_git_and_gh_commands(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        commands = []

        def fake_run_command(cmd, check=True, input=None, strip=True):
            commands.append(cmd)
            return ""

        with patch.object(cg, "run_command", side_effect=fake_run_command):
            result = cg.create_pr(GRADUATION_DATA)

        assert result is True
        assert any(c == ["git", "checkout", "-b", "graduation-326-turbopuffer"] for c in commands)
        assert any(c == ["git", "add", "README.md"] for c in commands)
        assert any(
            c[:3] == ["scripts/sign-commit", "-z", "graduation-326-turbopuffer"]
            and any("Graduate Turbopuffer" in str(arg) for arg in c)
            for c in commands
        )
        assert any(c[:3] == ["gh", "pr", "create"] for c in commands)

    def test_skips_pr_creation_if_branch_already_has_open_pr(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        commands = []

        def fake_run_command(cmd, check=True, input=None, strip=True):
            commands.append(cmd)
            if cmd[:3] == ["gh", "pr", "list"]:
                return "42"
            return ""

        with patch.object(cg, "run_command", side_effect=fake_run_command):
            result = cg.create_pr(GRADUATION_DATA)

        assert result is True
        assert not any(c[:3] == ["gh", "pr", "create"] for c in commands)

    def test_returns_false_when_readme_move_fails(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        data = {**GRADUATION_DATA, "name": "Nonexistent"}
        commands = []

        with patch.object(
            cg,
            "run_command",
            side_effect=lambda cmd, check=True, **kwargs: commands.append(cmd),
        ):
            result = cg.create_pr(data)

        assert result is False
        assert not any(any("sign-commit" in str(arg) for arg in c) for c in commands)


class TestMain:
    def test_no_op_when_no_data_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert cg.main() == 0

    def test_returns_zero_on_success(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "graduation_data.json").write_text(json.dumps(GRADUATION_DATA))

        with patch.object(cg, "create_pr", return_value=True) as mock_create:
            assert cg.main() == 0
        mock_create.assert_called_once_with(GRADUATION_DATA)

    def test_returns_one_on_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "graduation_data.json").write_text(json.dumps(GRADUATION_DATA))

        with patch.object(cg, "create_pr", side_effect=RuntimeError("boom")):
            assert cg.main() == 1
