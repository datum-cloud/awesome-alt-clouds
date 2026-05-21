#!/usr/bin/env python3
"""Parse WATCHLIST.md and generate docs/watchlist.json."""

import json
import re
import sys
from pathlib import Path

WATCHLIST_MD = Path("WATCHLIST.md")
OUTPUT = Path("docs/watchlist.json")


def parse_watchlist(content: str) -> list[dict]:
    entries = []
    in_table = False

    for line in content.splitlines():
        line = line.strip()

        if line.startswith("| Name |"):
            in_table = True
            continue

        if not in_table:
            continue

        if not line.startswith("|"):
            in_table = False
            continue

        # Skip separator rows
        if re.match(r"^\|[-| ]+\|$", line):
            continue

        parts = [p.strip() for p in line.split("|")]
        # Remove empty strings from leading/trailing pipes
        parts = [p for p in parts if p]

        if len(parts) < 7:
            continue

        # Skip header row if we somehow re-encounter it
        if parts[0].lower() == "name":
            continue

        entries.append({
            "name": parts[0],
            "url": parts[1],
            "category": parts[2],
            "dateAdded": parts[3],
            "reasonNotQualifying": parts[4],
            "criteriaNeed": parts[5],
            "lastReviewed": parts[6],
        })

    return entries


def main() -> None:
    if not WATCHLIST_MD.exists():
        print(f"ERROR: {WATCHLIST_MD} not found", file=sys.stderr)
        sys.exit(1)

    content = WATCHLIST_MD.read_text(encoding="utf-8")
    entries = parse_watchlist(content)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Generated {OUTPUT} with {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}")


if __name__ == "__main__":
    main()
