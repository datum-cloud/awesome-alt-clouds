# tests/test_create_graduation_pr.py
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from unittest.mock import patch

import create_graduation_pr as cg

SAMPLE_README = """# Awesome Alt Clouds

## Databases & Storage

* 🟢 [Alpha DB](https://alpha.example.com/) - A database.

## Emerging & Unverified Providers

* 🟢 [Turbopuffer](https://turbopuffer.com/) - Vector database, needs verification.
"""

GRADUATION_DATA = {
    "issue_number": "326",
    "name": "Turbopuffer",
    "url": "https://turbopuffer.com/",
    "old_category": "Emerging & Unverified Providers",
    "new_category": "Databases & Storage",
    "score": 3,
    "description": "Fast serverless vector database.",
    "needs_manual_review": False,
}


class TestMoveEntryInReadme:
    def test_moves_entry_between_categories(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        assert cg.move_entry_in_readme(GRADUATION_DATA) is True

        content = (tmp_path / "README.md").read_text()
        db_start = content.index("## Databases & Storage")
        emerging_start = content.index("## Emerging & Unverified Providers")
        turbopuffer_idx = content.index("Turbopuffer")
        assert db_start < turbopuffer_idx < emerging_start
        assert "Fast serverless vector database." in content

    def test_returns_false_when_entry_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        data = {**GRADUATION_DATA, "name": "Nonexistent"}
        assert cg.move_entry_in_readme(data) is False

    def test_returns_false_when_category_drifted(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        data = {**GRADUATION_DATA, "old_category": "Cloud Adjacent & Infrastructure Tooling"}
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

        def fake_run_command(cmd, check=True):
            commands.append(cmd)
            if cmd.startswith("gh pr list"):
                return ""
            return ""

        with patch.object(cg, "run_command", side_effect=fake_run_command):
            result = cg.create_pr(GRADUATION_DATA)

        assert result is True
        assert any(c.startswith("git checkout -b graduation-326-turbopuffer") for c in commands)
        assert any(c == "git add README.md" for c in commands)
        assert any("git commit" in c and "Graduate Turbopuffer" in c for c in commands)
        assert any(
            c.startswith("git push --force origin graduation-326-turbopuffer") for c in commands
        )
        assert any(c.startswith("gh pr create") for c in commands)

    def test_skips_pr_creation_if_branch_already_has_open_pr(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        commands = []

        def fake_run_command(cmd, check=True):
            commands.append(cmd)
            if cmd.startswith("gh pr list"):
                return "42"
            return ""

        with patch.object(cg, "run_command", side_effect=fake_run_command):
            result = cg.create_pr(GRADUATION_DATA)

        assert result is True
        assert not any(c.startswith("gh pr create") for c in commands)

    def test_returns_false_when_readme_move_fails(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        data = {**GRADUATION_DATA, "name": "Nonexistent"}
        commands = []

        with patch.object(
            cg, "run_command", side_effect=lambda cmd, check=True: commands.append(cmd)
        ):
            result = cg.create_pr(data)

        assert result is False
        assert not any("git commit" in c for c in commands)


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
