"""Fail if src/lib/taxonomy.ts drifts from scripts/lib/taxonomy.py."""

import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from lib import taxonomy  # noqa: E402

TS = open(os.path.join(ROOT, "src", "lib", "taxonomy.ts")).read()


def _strings(block: str) -> list[str]:
    return re.findall(r'"([^"]+)"', block)


def test_categories_match():
    block = re.search(r"CATEGORIES = \[(.*?)\] as const", TS, re.S).group(1)
    assert _strings(block) == list(taxonomy.CATEGORIES)


def test_workload_families_match():
    block = re.search(r"WORKLOAD_TAG_FAMILIES = \{(.*?)\} as const;", TS, re.S).group(1)
    ts = {}
    for m in re.finditer(r'"?([A-Za-z& ]+)"?:\s*\[(.*?)\]', block, re.S):
        ts[m.group(1).strip()] = _strings(m.group(2))
    assert ts == {k: list(v) for k, v in taxonomy.WORKLOAD_TAG_FAMILIES.items()}


def test_cross_cutting_tags_match():
    block = re.search(r"CROSS_CUTTING_TAGS = \[(.*?)\] as const", TS, re.S).group(1)
    assert _strings(block) == list(taxonomy.CROSS_CUTTING_TAGS)


def test_region_prefix_match():
    assert f'"{taxonomy.REGION_TAG_PREFIX}"' in TS


def test_category_definitions_match():
    block = re.search(r"CATEGORY_DEFINITIONS: .*? = \{(.*?)\n\};", TS, re.S).group(1)
    pairs = re.findall(r'"([^"]+)":\s*"([^"]+)"', block)
    assert dict(pairs) == dict(taxonomy.CATEGORY_DEFINITIONS)


def test_every_retired_category_has_a_redirect_to_a_real_target():
    def slug(name: str) -> str:
        return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", name.lower()))

    redirects_ts = open(os.path.join(ROOT, "src", "lib", "legacy-redirects.ts")).read()
    redirects = dict(re.findall(r'"(/categories/[^"]+)":\s*"([^"]+)"', redirects_ts))
    new_slugs = {slug(c) for c in taxonomy.CATEGORIES}
    for legacy in taxonomy.LEGACY_CATEGORY_MAP:
        key = f"/categories/{slug(legacy)}"
        if slug(legacy) in new_slugs:
            assert key not in redirects, f"{legacy} keeps its slug; redirecting would loop"
            continue
        assert key in redirects, f"missing redirect for retired category {legacy!r}"
        target = redirects[key]
        assert (
            target == "/?tags=unverified"
            or target.removeprefix("/categories/").rstrip("/") in new_slugs
        ), f"{legacy!r} redirects to unknown target {target!r}"


def test_astro_config_prefixes_base_onto_redirect_destinations():
    config = open(os.path.join(ROOT, "astro.config.mjs")).read()
    assert "withBase" in config and "redirects," in config
    assert "redirects: legacyCategoryRedirects" not in config  # would drop the preview base
