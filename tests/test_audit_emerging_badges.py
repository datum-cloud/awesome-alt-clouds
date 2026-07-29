# tests/test_audit_emerging_badges.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from unittest.mock import patch

import audit_emerging_badges as aeb

SAMPLE_README = """# Alt Cloud

## Databases & Storage

* 🟢 [Alpha DB](https://alpha.example.com/) - A database.

## Emerging & Unverified Providers

* 🟢 [Turbopuffer](https://turbopuffer.com/) - Vector database, needs verification.
* 🟢 [LaunchDarkly](https://launchdarkly.com/) - Feature management, enterprise-only pricing.
* 🟢 [Oxide Computer](https://oxide.computer/) - Rack-scale computer, sold as hardware.
"""


def _result(score):
    return {
        "url": "x",
        "company_name": "x",
        "score": score,
        "criteria": [],
        "fetch_failed": False,
        "fetch_method": "requests",
        "page_content": "",
    }


class TestAudit:
    def test_corrects_mismatched_badges(self):
        def fake_evaluate(url):
            if "turbopuffer" in url:
                return _result(3)
            if "launchdarkly" in url:
                return _result(2)
            return _result(1)

        with patch.object(aeb, "evaluate_service", side_effect=fake_evaluate):
            new_content, changed, flagged, total = aeb.audit(SAMPLE_README)

        assert total == 3
        names_changed = {c["name"] for c in changed}
        assert names_changed == {"LaunchDarkly", "Oxide Computer"}
        assert "🟢 [Turbopuffer]" in new_content
        assert "🟡 [LaunchDarkly]" in new_content
        assert "🟡 [Oxide Computer]" in new_content

    def test_flags_entries_scoring_below_two(self):
        with patch.object(aeb, "evaluate_service", return_value=_result(1)):
            _, _, flagged, _ = aeb.audit(SAMPLE_README)

        assert len(flagged) == 3
        assert all(f["score"] == 1 for f in flagged)

    def test_leaves_readme_untouched_outside_emerging_section(self):
        with patch.object(aeb, "evaluate_service", return_value=_result(1)):
            new_content, _, _, _ = aeb.audit(SAMPLE_README)

        assert "🟢 [Alpha DB]" in new_content


class TestMain:
    def test_writes_report_and_updates_readme_on_change(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)

        with patch.object(aeb, "evaluate_service", return_value=_result(2)):
            aeb.main()

        report = (tmp_path / "audit_report.md").read_text()
        assert "Badges corrected" in report
        readme = (tmp_path / "README.md").read_text()
        assert "🟡 [Turbopuffer]" in readme

    def test_no_op_when_no_entries_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        no_emerging_section = (
            "# Alt Cloud\n\n"
            "## Databases & Storage\n\n"
            "* 🟢 [Alpha DB](https://alpha.example.com/) - A database.\n"
        )
        (tmp_path / "README.md").write_text(no_emerging_section)

        aeb.main()

        report = (tmp_path / "audit_report.md").read_text()
        assert "nothing to audit" in report
