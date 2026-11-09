#!/usr/bin/env python3
"""Restructure README.md from the legacy 24 categories into the 5-cloud taxonomy.

Usage:
    python scripts/migrate_readme.py [--dry-run]
    python scripts/migrate_readme.py --review-csv analysis/taxonomy-migration.csv \
        --source <legacy README> --dry-run

- Every entry moves to its proposed category (see lib/tag_rules.py).
- Entries from "Emerging & Unverified Providers" get the 🔵 badge instead of a section.
- Tags are written as a trailing `<!-- tags: ... -->` comment.
- Within each section entries are sorted alphabetically (case-insensitive).
- The preamble (Contents, Criteria) and the Contributing tail are preserved;
  Contents and the badge legend are regenerated.
"""

import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.entry_format import Entry, format_entry, parse_entry  # noqa: E402
from lib.tag_rules import propose_category, propose_tags  # noqa: E402
from lib.taxonomy import (  # noqa: E402
    CATEGORIES,
    CATEGORY_DEFINITIONS,
    UNVERIFIED_LEGACY_CATEGORY,
)

README = "README.md"
LEGEND_OLD = "**Legend:** 🟢 = All 3 criteria met | 🟡 = 2 of 3 criteria met"
LEGEND_NEW = (
    "**Legend:** 🟢 = All 3 criteria met | 🟡 = 2 of 3 criteria met | "
    "🔵 = Emerging & Unverified: promising, but a criterion still needs independent verification"
)
FIRST_CATEGORY_RE = re.compile(r"^\* \[Criteria\]")


def anchor(title: str) -> str:
    """GitHub heading anchor: lowercase, drop punctuation, spaces to dashes."""
    return re.sub(r"[^a-z0-9 -]", "", title.lower()).replace(" ", "-")


def split_readme(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Return (head, category_sections, tail) where head ends at the first category."""
    headings = [i for i, line in enumerate(lines) if line.startswith("## ")]
    names = {i: lines[i][3:].strip() for i in headings}
    first = next(i for i in headings if names[i] not in {"Contents", "Criteria"})
    tail_start = next(i for i in headings if names[i] == "Contributing")
    return lines[:first], lines[first:tail_start], lines[tail_start:]


def classify(legacy: str, entry: Entry) -> tuple[str, bool, Entry]:
    """Return (new_category, needs_review, migrated entry with tags + unverified flag)."""
    category, review = propose_category(legacy, entry.name, entry.description)
    tags = propose_tags(legacy, entry.name, entry.description, category)
    unverified = legacy == UNVERIFIED_LEGACY_CATEGORY
    migrated = Entry(entry.name, entry.url, entry.description, entry.score, unverified, tags)
    return category, review, migrated


def iter_legacy_entries(section_lines: list[str]):
    """Yield (legacy_category, Entry) for every entry bullet, deduped by URL."""
    seen: set[str] = set()
    legacy = None
    for line in section_lines:
        if line.startswith("## "):
            legacy = line[3:].strip()
            continue
        entry = parse_entry(line)
        if entry and entry.url not in seen:
            seen.add(entry.url)
            yield legacy, entry


def collect_entries(section_lines: list[str]) -> list[tuple[str, Entry]]:
    """Parse every legacy entry, assign category/tags/unverified; dedupe by URL."""
    out = []
    for legacy, entry in iter_legacy_entries(section_lines):
        category, _, migrated = classify(legacy, entry)
        out.append((category, migrated))
    return out


REVIEW_FIELDS = [
    "name",
    "url",
    "legacy_category",
    "new_category",
    "needs_review",
    "unverified",
    "tags",
]


def review_rows(content: str) -> list[dict]:
    """One row per entry describing the proposed move, for human review."""
    _, body, _ = split_readme(content.split("\n"))
    rows = []
    for legacy, entry in iter_legacy_entries(body):
        category, review, migrated = classify(legacy, entry)
        rows.append(
            {
                "name": entry.name,
                "url": entry.url,
                "legacy_category": legacy,
                "new_category": category,
                "needs_review": review,
                "unverified": migrated.unverified,
                "tags": ", ".join(migrated.tags),
            }
        )
    return rows


def write_review_csv(content: str, path: str) -> int:
    rows = review_rows(content)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def render_sections(entries: list[tuple[str, Entry]]) -> list[str]:
    out: list[str] = []
    for category in CATEGORIES:
        members = sorted((e for c, e in entries if c == category), key=lambda e: e.name.lower())
        out += [f"## {category}", "", CATEGORY_DEFINITIONS[category], ""]
        out += [format_entry(e) for e in members]
        out.append("")
    return out


def rewrite_head(head: list[str]) -> list[str]:
    """Regenerate the Contents bullets and the legend inside the preserved preamble."""
    out: list[str] = []
    in_contents = False
    for line in head:
        if line.strip() == "## Contents":
            in_contents = True
            out.append(line)
            continue
        if in_contents and line.startswith("## "):
            in_contents = False
        if in_contents and line.startswith("* ") and "](#" in line and "#criteria" not in line:
            continue  # category bullets are regenerated below
        out.append(line.replace(LEGEND_OLD, LEGEND_NEW))
        if in_contents and "(WATCHLIST.md)" in line:
            out += [f"* [{c}](#{anchor(c)})" for c in CATEGORIES]
    return out


NEW_ONLY_HEADINGS = ("## Sovereign Clouds", "## Service Clouds", "## Vertical Clouds")


def is_already_migrated(content: str) -> bool:
    """True if the README already uses the 5-cloud taxonomy or carries tags.

    The legacy README also had "Infrastructure Clouds" and "Workload Clouds" sections, so only
    the headings (or tags comments) that did not exist before identify a migrated file.
    """
    has_new_heading = any(line.strip() in NEW_ONLY_HEADINGS for line in content.split("\n"))
    return has_new_heading or "<!-- tags:" in content


def migrate(content: str) -> tuple[str, list[tuple[str, Entry]]]:
    if is_already_migrated(content):
        raise ValueError(
            "README is already migrated (5-cloud headings or tags found); re-running would "
            "drop 🔵 badges and overwrite tags. Pass a legacy README via --source."
        )
    lines = content.split("\n")
    head, body, tail = split_readme(lines)
    entries = collect_entries(body)
    new_lines = rewrite_head(head) + render_sections(entries) + tail
    return "\n".join(new_lines), entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source", default=README, help="README to read (default: README.md)")
    parser.add_argument("--output", default=README, help="file to write (default: README.md)")
    parser.add_argument("--review-csv", help="also write a review CSV of every proposed move")
    args = parser.parse_args()
    with open(args.source) as f:
        source = f.read()
    if is_already_migrated(source):
        sys.exit(f"Refusing to run: {args.source} is already migrated to the 5-cloud taxonomy.")
    if args.review_csv:
        print(f"Wrote {args.review_csv} ({write_review_csv(source, args.review_csv)} rows)")
    new_content, entries = migrate(source)
    dropped = sum(1 for line in source.split("\n") if parse_entry(line)) - len(entries)
    if dropped:
        print(f"Warning: {dropped} duplicate URL listing(s) collapsed to one category each")
    counts = {c: sum(1 for cat, _ in entries if cat == c) for c in CATEGORIES}
    print(f"{len(entries)} entries ->", counts)
    if not args.dry_run:
        with open(args.output, "w") as f:
            f.write(new_content)
        print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
