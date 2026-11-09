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
