# tests/test_evaluate_graduation.py
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from unittest.mock import patch

import evaluate_graduation as eg

SAMPLE_README = """# Awesome Alt Clouds

## Databases & Storage

* 🟢 [Alpha DB](https://alpha.example.com/) - A database.

## Emerging & Unverified Providers

* 🟢 [Turbopuffer](https://turbopuffer.com/) - Vector database, needs verification.
"""

GRADUATION_BODY = """## Graduation Request

**Service:** [Turbopuffer](https://turbopuffer.com/)

**Why they should graduate from Future Cloud to full listing:**
Pricing is transparent now.

---
*Reported via the Alt Cloud browser extension.*
"""


def _evaluate_result(score, criteria=None):
    return {
        "url": "https://turbopuffer.com/",
        "company_name": "Turbopuffer",
        "score": score,
        "criteria": criteria
        or [
            {
                "name": "Transparent Public Pricing",
                "passed": True,
                "evidence": "https://turbopuffer.com/pricing",
            },
            {"name": "Usage-based Self-Service", "passed": True, "evidence": "Sign up"},
            {
                "name": "Production Indicators",
                "passed": score == 3,
                "evidence": "status page" if score == 3 else "none",
            },
        ],
        "fetch_failed": False,
        "fetch_method": "requests",
        "page_content": "some content",
    }


class TestExtractServiceName:
    def test_prefers_service_field_in_body(self):
        name = eg.extract_service_name("[Graduation] Turbopuffer", GRADUATION_BODY)
        assert name == "Turbopuffer"

    def test_falls_back_to_title_when_body_field_missing(self):
        name = eg.extract_service_name("[Graduation] Turbopuffer", "no service field here")
        assert name == "Turbopuffer"

    def test_falls_back_to_title_with_request_suffix(self):
        name = eg.extract_service_name("[Graduation Request] Turbopuffer", "no service field here")
        assert name == "Turbopuffer"

    def test_returns_none_when_nothing_matches(self):
        assert eg.extract_service_name("Some random issue", "no service field here") is None


class TestMainFlow:
    def test_writes_error_when_name_not_extractable(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)
        monkeypatch.setenv("ISSUE_BODY", "nothing useful")
        monkeypatch.setenv("ISSUE_TITLE", "Some random issue")
        monkeypatch.setenv("ISSUE_NUMBER", "326")

        eg.main()

        assert (
            "Could not determine which service" in (tmp_path / "graduation_results.md").read_text()
        )
        assert (tmp_path / "graduation_score.txt").read_text() == "0"
        assert not (tmp_path / "graduation_data.json").exists()

    def test_writes_error_when_entry_not_in_readme(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)
        monkeypatch.setenv(
            "ISSUE_BODY", "**Service:** [Nonexistent](https://nonexistent.example.com/)"
        )
        monkeypatch.setenv("ISSUE_TITLE", "[Graduation] Nonexistent")
        monkeypatch.setenv("ISSUE_NUMBER", "326")

        eg.main()

        assert (
            "Could not find an existing README.md entry"
            in (tmp_path / "graduation_results.md").read_text()
        )
        assert not (tmp_path / "graduation_data.json").exists()

    def test_writes_error_when_entry_already_graduated(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)
        monkeypatch.setenv("ISSUE_BODY", "**Service:** [Alpha DB](https://alpha.example.com/)")
        monkeypatch.setenv("ISSUE_TITLE", "[Graduation] Alpha DB")
        monkeypatch.setenv("ISSUE_NUMBER", "326")

        eg.main()

        result = (tmp_path / "graduation_results.md").read_text()
        assert "already listed under" in result
        assert "Databases & Storage" in result

    def test_ready_to_graduate_writes_data_json(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)
        monkeypatch.setenv("ISSUE_BODY", GRADUATION_BODY)
        monkeypatch.setenv("ISSUE_TITLE", "[Graduation] Turbopuffer")
        monkeypatch.setenv("ISSUE_NUMBER", "326")

        ai_metadata = {
            "name": "Turbopuffer",
            "description": "Fast serverless vector database.",
            "category": "Databases & Storage",
        }

        with patch.object(eg, "evaluate_service", return_value=_evaluate_result(3)):
            with patch.object(eg, "generate_metadata", return_value=ai_metadata):
                eg.main()

        assert (tmp_path / "graduation_score.txt").read_text() == "3"
        data = json.loads((tmp_path / "graduation_data.json").read_text())
        assert data["name"] == "Turbopuffer"
        assert data["old_category"] == "Emerging & Unverified Providers"
        assert data["new_category"] == "Databases & Storage"
        assert data["score"] == 3

        comment = (tmp_path / "graduation_results.md").read_text()
        assert "ready to graduate" in comment
        assert "/approve-graduation" in comment

    def test_low_score_does_not_write_data_json(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)
        monkeypatch.setenv("ISSUE_BODY", GRADUATION_BODY)
        monkeypatch.setenv("ISSUE_TITLE", "[Graduation] Turbopuffer")
        monkeypatch.setenv("ISSUE_NUMBER", "326")

        with patch.object(eg, "evaluate_service", return_value=_evaluate_result(1)):
            with patch.object(eg, "generate_metadata", return_value=None):
                eg.main()

        assert (tmp_path / "graduation_score.txt").read_text() == "1"
        assert not (tmp_path / "graduation_data.json").exists()
        comment = (tmp_path / "graduation_results.md").read_text()
        assert "Still doesn't meet the bar" in comment

    def test_admin_approved_bypasses_score_gate(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)
        monkeypatch.setenv("ISSUE_BODY", GRADUATION_BODY)
        monkeypatch.setenv("ISSUE_TITLE", "[Graduation] Turbopuffer")
        monkeypatch.setenv("ISSUE_NUMBER", "326")
        monkeypatch.setenv("GRADUATION_ADMIN_APPROVED", "true")
        monkeypatch.setenv("GRADUATION_CATEGORY_OVERRIDE", "Databases & Storage")

        with patch.object(eg, "evaluate_service", return_value=_evaluate_result(1)):
            with patch.object(eg, "generate_metadata", return_value=None):
                eg.main()

        data = json.loads((tmp_path / "graduation_data.json").read_text())
        assert data["new_category"] == "Databases & Storage"

    def test_unknown_category_override_is_ignored(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)
        monkeypatch.setenv("ISSUE_BODY", GRADUATION_BODY)
        monkeypatch.setenv("ISSUE_TITLE", "[Graduation] Turbopuffer")
        monkeypatch.setenv("ISSUE_NUMBER", "326")
        monkeypatch.setenv("GRADUATION_CATEGORY_OVERRIDE", "Not A Real Category")

        ai_metadata = {
            "name": "Turbopuffer",
            "description": "Fast serverless vector database.",
            "category": "Databases & Storage",
        }

        with patch.object(eg, "evaluate_service", return_value=_evaluate_result(3)):
            with patch.object(eg, "generate_metadata", return_value=ai_metadata):
                eg.main()

        data = json.loads((tmp_path / "graduation_data.json").read_text())
        assert data["new_category"] == "Databases & Storage"
