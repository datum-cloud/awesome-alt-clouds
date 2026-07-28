# tests/test_readme_entries.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib import readme_entries as re_lib

SAMPLE_README = """# Awesome Alt Clouds

## Databases & Storage

* 🟢 [Alpha DB](https://alpha.example.com/) - A database.
* 🟢 [Zeta Storage](https://zeta.example.com/) - Storage service.

## Emerging & Unverified Providers

* 🟢 [Turbopuffer](https://turbopuffer.com/) - Vector database, needs verification.
* 🟢 [Uptrace](https://uptrace.dev/) - Tracing platform, needs verification.

## Cloud Adjacent & Infrastructure Tooling

* 🟢 [ngrok](https://ngrok.com/) - Tunnels local services.
"""


class TestFindCategorySection:
    def test_finds_section_bounds(self):
        start, end = re_lib.find_category_section(SAMPLE_README, "Emerging & Unverified Providers")
        lines = SAMPLE_README.split("\n")
        assert lines[start].strip() == "## Emerging & Unverified Providers"
        assert lines[end].strip() == "## Cloud Adjacent & Infrastructure Tooling"

    def test_last_section_runs_to_end_of_file(self):
        start, end = re_lib.find_category_section(
            SAMPLE_README, "Cloud Adjacent & Infrastructure Tooling"
        )
        assert end == len(SAMPLE_README.split("\n"))

    def test_missing_category_returns_none(self):
        start, end = re_lib.find_category_section(SAMPLE_README, "Nonexistent Category")
        assert start is None
        assert end is None


class TestBadgeForScore:
    def test_three_of_three_is_green(self):
        assert re_lib.badge_for_score(3) == "🟢"

    def test_two_of_three_is_yellow(self):
        assert re_lib.badge_for_score(2) == "🟡"

    def test_below_two_is_yellow(self):
        assert re_lib.badge_for_score(1) == "🟡"


class TestAddEntryToReadme:
    def test_inserts_alphabetically_within_category(self):
        submission = {
            "name": "Beta Cloud",
            "url": "https://beta.example.com/",
            "category": "Databases & Storage",
            "score": 3,
            "description": "A cloud.",
        }
        new_content = re_lib.add_entry_to_readme(submission, content=SAMPLE_README)
        lines = new_content.split("\n")
        alpha_idx = next(i for i, line in enumerate(lines) if "Alpha DB" in line)
        beta_idx = next(i for i, line in enumerate(lines) if "Beta Cloud" in line)
        zeta_idx = next(i for i, line in enumerate(lines) if "Zeta Storage" in line)
        assert alpha_idx < beta_idx < zeta_idx

    def test_uses_yellow_badge_for_score_two(self):
        submission = {
            "name": "Beta Cloud",
            "url": "https://beta.example.com/",
            "category": "Databases & Storage",
            "score": 2,
            "description": "A cloud.",
        }
        new_content = re_lib.add_entry_to_readme(submission, content=SAMPLE_README)
        assert "🟡 [Beta Cloud]" in new_content

    def test_returns_none_when_category_missing(self):
        submission = {
            "name": "Beta Cloud",
            "url": "https://beta.example.com/",
            "category": "Nonexistent Category",
            "score": 3,
            "description": "A cloud.",
        }
        assert re_lib.add_entry_to_readme(submission, content=SAMPLE_README) is None

    def test_writes_to_file_when_no_content_given(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text(SAMPLE_README)
        submission = {
            "name": "Beta Cloud",
            "url": "https://beta.example.com/",
            "category": "Databases & Storage",
            "score": 3,
            "description": "A cloud.",
        }
        result = re_lib.add_entry_to_readme(submission)
        assert result is True
        assert "Beta Cloud" in (tmp_path / "README.md").read_text()


class TestFindEntryByName:
    def test_finds_entry_and_its_category(self):
        entry = re_lib.find_entry_by_name(SAMPLE_README, "Turbopuffer")
        assert entry["category"] == "Emerging & Unverified Providers"
        assert entry["url"] == "https://turbopuffer.com/"
        assert entry["badge"] == "🟢"

    def test_is_case_insensitive(self):
        entry = re_lib.find_entry_by_name(SAMPLE_README, "turbopuffer")
        assert entry is not None

    def test_exact_match_not_substring(self):
        # "Split" must not match a hypothetical "Splitwise" entry.
        content = SAMPLE_README + "\n* 🟢 [Splitwise](https://splitwise.com/) - Bill splitting.\n"
        assert re_lib.find_entry_by_name(content, "Split") is None

    def test_returns_none_when_not_found(self):
        assert re_lib.find_entry_by_name(SAMPLE_README, "Nonexistent Service") is None


class TestRemoveEntryFromReadme:
    def test_removes_the_line(self):
        entry = re_lib.find_entry_by_name(SAMPLE_README, "Turbopuffer")
        new_content = re_lib.remove_entry_from_readme(SAMPLE_README, entry["line_idx"])
        assert "Turbopuffer" not in new_content
        assert "Uptrace" in new_content


class TestListEntriesInCategory:
    def test_lists_all_entries_in_order(self):
        entries = re_lib.list_entries_in_category(SAMPLE_README, "Emerging & Unverified Providers")
        assert [e["name"] for e in entries] == ["Turbopuffer", "Uptrace"]

    def test_empty_for_missing_category(self):
        assert re_lib.list_entries_in_category(SAMPLE_README, "Nonexistent Category") == []
