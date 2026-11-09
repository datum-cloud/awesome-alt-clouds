import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import migrate_readme as mr
from lib.entry_format import parse_entry
from lib.taxonomy import CATEGORIES

LEGACY = """# Alt Cloud

Intro text.

## Contents

* [Criteria](#criteria)
* [Watchlist](WATCHLIST.md) — candidates
* [Infrastructure Clouds](#infrastructure-clouds)
* [Emerging & Unverified Providers](#emerging--unverified-providers)

## Criteria

**Legend:** 🟢 = All 3 criteria met | 🟡 = 2 of 3 criteria met

## Infrastructure Clouds

Old intro.

* 🟢 [Zed Metal](https://zed.example/) - Bare metal servers.

## Databases & Storage

Old intro.

* 🟢 [Beta DB](https://beta.example/) - Managed Postgres.
* 🟢 [Cold Vault](https://cold.example/) - Object storage and backup.

## Authorization, Identity & Fraud

* 🟢 [Auth Co](https://auth.example/) - Authentication API.

## Emerging & Unverified Providers

Prose about emerging.

* 🟢 [Flagr](https://flagr.example/) - Open-source feature flags, verification needed.
* 🟡 [Chromo](https://chromo.example/) - Open-source vector database, verification needed.

## Contributing

Contribute here.
"""


def _migrate():
    content, entries = mr.migrate(LEGACY)
    return content, entries, content.split("\n")


class TestMigrate:
    def test_all_five_sections_in_taxonomy_order_with_definitions(self):
        content, _, lines = _migrate()
        headings = [line[3:] for line in lines if line.startswith("## ")]
        assert headings == ["Contents", "Criteria", *CATEGORIES, "Contributing"]
        assert "Old intro." not in content
        assert "Prose about emerging." not in content

    def test_entries_land_in_expected_categories(self):
        _, entries, _ = _migrate()
        where = {e.name: cat for cat, e in entries}
        assert where["Zed Metal"] == "Infrastructure Clouds"
        assert where["Cold Vault"] == "Infrastructure Clouds"
        assert where["Beta DB"] == "Workload Clouds"
        assert where["Auth Co"] == "Service Clouds"
        assert where["Flagr"] == "Service Clouds"
        assert where["Chromo"] == "Workload Clouds"

    def test_emerging_entries_get_unverified_badge_and_keep_score(self):
        content, _, _ = _migrate()
        flagr = parse_entry(next(x for x in content.split("\n") if "[Flagr]" in x))
        chromo = parse_entry(next(x for x in content.split("\n") if "[Chromo]" in x))
        assert flagr.unverified and flagr.score == 3
        assert chromo.unverified and chromo.score == 2
        beta = parse_entry(next(x for x in content.split("\n") if "[Beta DB]" in x))
        assert not beta.unverified

    def test_tags_written_with_workload_tags_only_on_workload(self):
        content, _, _ = _migrate()
        beta = parse_entry(next(x for x in content.split("\n") if "[Beta DB]" in x))
        flagr = parse_entry(next(x for x in content.split("\n") if "[Flagr]" in x))
        assert "postgres-sql" in beta.tags
        assert "open-source" in flagr.tags

    def test_entries_sorted_alphabetically_within_section(self):
        _, _, lines = _migrate()
        start = lines.index("## Infrastructure Clouds")
        names = []
        for line in lines[start + 1 :]:
            if line.startswith("## "):
                break
            entry = parse_entry(line)
            if entry:
                names.append(entry.name.lower())
        assert names == sorted(names)

    def test_contents_and_legend_regenerated(self):
        content, _, _ = _migrate()
        assert "* [Workload Clouds](#workload-clouds)" in content
        assert "[Emerging & Unverified Providers]" not in content
        assert "🔵 = Emerging & Unverified" in content
        assert "* [Criteria](#criteria)" in content and "(WATCHLIST.md)" in content

    def test_duplicate_url_across_sections_kept_once(self):
        text = LEGACY.replace(
            "## Authorization, Identity & Fraud",
            "## Monetization & Billing Clouds\n\n* 🟢 [Beta DB](https://beta.example/) - Dup.\n\n"
            "## Authorization, Identity & Fraud",
        )
        _, entries = mr.migrate(text)
        assert sum(1 for _, e in entries if e.url == "https://beta.example/") == 1

    def test_idempotent_entry_count_and_tail_preserved(self):
        content, entries, _ = _migrate()
        assert len(entries) == 6
        assert content.rstrip().endswith("Contribute here.")


class TestReviewCsv:
    def test_rows_describe_legacy_to_new_move(self):
        rows = {r["name"]: r for r in mr.review_rows(LEGACY)}
        assert len(rows) == 6
        assert rows["Beta DB"]["legacy_category"] == "Databases & Storage"
        assert rows["Beta DB"]["new_category"] == "Workload Clouds"
        assert rows["Beta DB"]["needs_review"] is True
        assert rows["Zed Metal"]["needs_review"] is False
        assert rows["Flagr"]["unverified"] is True
        assert "postgres-sql" in rows["Beta DB"]["tags"]

    def test_write_review_csv(self, tmp_path):
        path = tmp_path / "out" / "review.csv"
        assert mr.write_review_csv(LEGACY, str(path)) == 6
        header = path.read_text().splitlines()[0]
        assert header == ",".join(mr.REVIEW_FIELDS)


class TestSafety:
    def test_refuses_an_already_migrated_readme(self):
        migrated, _ = mr.migrate(LEGACY)
        assert mr.is_already_migrated(migrated)
        import pytest

        with pytest.raises(ValueError, match="already migrated"):
            mr.migrate(migrated)

    def test_legacy_readme_is_not_mistaken_for_migrated(self):
        # The legacy README also had "Infrastructure Clouds" / "Workload Clouds" headings.
        assert not mr.is_already_migrated(LEGACY)
        assert not mr.is_already_migrated("## Workload Clouds\n\n* 🟢 [A](https://a.io) - d.\n")

    def test_tags_comment_alone_marks_it_migrated(self):
        assert mr.is_already_migrated("* 🟢 [A](https://a.io) - d. <!-- tags: gpu -->")
