import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib import taxonomy
from lib.entry_format import Entry, format_entry, invalid_tags, parse_entry


class TestParseEntry:
    def test_legacy_entry_still_parses(self):
        e = parse_entry("* 🟢 [Acme](https://acme.io/) - Provides things.")
        assert e == Entry("Acme", "https://acme.io/", "Provides things.", 3, False, ())

    def test_yellow_score(self):
        assert parse_entry("* 🟡 [A](https://a.io) - D.").score == 2

    def test_unverified_badge(self):
        e = parse_entry("* 🟡🔵 [A](https://a.io) - D.")
        assert e.score == 2 and e.unverified is True

    def test_tags_extracted_and_stripped_from_description(self):
        e = parse_entry("* 🟢 [A](https://a.io) - Runs models. <!-- tags: llm-inference, gpu -->")
        assert e.description == "Runs models."
        assert e.tags == ("llm-inference", "gpu")

    def test_duplicate_tags_deduped_in_order(self):
        e = parse_entry("* 🟢 [A](https://a.io) - D. <!-- tags: gpu, vector, gpu -->")
        assert e.tags == ("gpu", "vector")

    def test_non_entry_returns_none(self):
        assert parse_entry("## Workload Clouds") is None
        assert parse_entry("plain text") is None

    def test_diff_plus_prefix_matches(self):
        assert parse_entry("+* 🟢 [A](https://a.io) - D.") is not None

    def test_description_containing_dash_and_parens(self):
        e = parse_entry("* 🟢 [A](https://a.io) - Edge - fast (really).")
        assert e.description == "Edge - fast (really)."


class TestFormatEntry:
    def test_roundtrip_with_tags_and_unverified(self):
        line = "* 🟡🔵 [A](https://a.io) - D. <!-- tags: gpu, region:ch -->"
        assert format_entry(parse_entry(line)) == line

    def test_roundtrip_plain(self):
        line = "* 🟢 [A](https://a.io) - D."
        assert format_entry(parse_entry(line)) == line


class TestTaxonomy:
    def test_five_categories_each_defined(self):
        assert len(taxonomy.CATEGORIES) == 5
        assert set(taxonomy.CATEGORY_DEFINITIONS) == set(taxonomy.CATEGORIES)

    def test_workload_tags_are_unique_and_five_families(self):
        assert len(taxonomy.WORKLOAD_TAGS) == len(set(taxonomy.WORKLOAD_TAGS))
        assert list(taxonomy.WORKLOAD_TAG_FAMILIES) == ["App", "Data", "AI", "Agent", "Build & Run"]

    def test_valid_tags(self):
        for tag in ("llm-inference", "agent-native", "gpu", "region:ch", "region:eu"):
            assert taxonomy.is_valid_tag(tag), tag

    def test_invalid_tags(self):
        for tag in ("nonsense", "region:", "region:X", "Region:ch", ""):
            assert not taxonomy.is_valid_tag(tag), tag
        assert invalid_tags(["gpu", "bogus"]) == ["bogus"]

    def test_tag_family(self):
        assert taxonomy.tag_family("vector") == "Data"
        assert taxonomy.tag_family("gpu") is None

    def test_legacy_map_covers_all_24_old_categories(self):
        assert len(taxonomy.LEGACY_CATEGORY_MAP) == 24
        for target in taxonomy.LEGACY_CATEGORY_MAP.values():
            assert target is None or target in taxonomy.CATEGORIES
