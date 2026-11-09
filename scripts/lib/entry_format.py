"""Parse and format a README bullet, including the unverified badge and tags.

Entry format (superset of the original, so old bullets still parse):

    * 🟢 [Name](https://example.com/) - Description. <!-- tags: llm-inference, gpu -->
    * 🟡🔵 [Name](https://example.com/) - Description.

Score badge: 🟢 (3/3) or 🟡 (2/3). 🔵 marks the entry as unverified.
Tags live in a trailing HTML comment so the rendered README stays clean.
"""

import re
from dataclasses import dataclass

from lib.taxonomy import is_valid_tag

UNVERIFIED_BADGE = "🔵"

ENTRY_RE = re.compile(
    r"^\+?\s*\*\s*(?P<score>🟢|🟡)?(?P<unverified>🔵)?\s*"
    r"\[(?P<name>[^\]]+)\]\((?P<url>[^)]+)\)\s+-\s+(?P<rest>.+)$"
)
_TAGS_RE = re.compile(r"\s*<!--\s*tags:\s*(?P<tags>[^>]*?)\s*-->\s*$")


@dataclass(frozen=True)
class Entry:
    name: str
    url: str
    description: str
    score: int
    unverified: bool
    tags: tuple[str, ...]


def split_description_and_tags(rest: str) -> tuple[str, tuple[str, ...]]:
    """Split `desc <!-- tags: a, b -->` into (desc, ("a", "b")). Order preserved, deduped."""
    match = _TAGS_RE.search(rest)
    if not match:
        return rest.strip(), ()
    seen: dict[str, None] = {}
    for raw in match.group("tags").split(","):
        tag = raw.strip()
        if tag:
            seen.setdefault(tag, None)
    return rest[: match.start()].strip(), tuple(seen)


def parse_entry(line: str) -> Entry | None:
    """Parse a README bullet line, or return None if it isn't an entry."""
    match = ENTRY_RE.match(line)
    if not match:
        return None
    description, tags = split_description_and_tags(match.group("rest"))
    return Entry(
        name=match.group("name"),
        url=match.group("url"),
        description=description,
        score=2 if match.group("score") == "🟡" else 3,
        unverified=bool(match.group("unverified")),
        tags=tags,
    )


def invalid_tags(tags: tuple[str, ...] | list[str]) -> list[str]:
    """Return tags that aren't in the vocabulary (callers decide whether to drop or fail)."""
    return [t for t in tags if not is_valid_tag(t)]


def format_entry(entry: Entry) -> str:
    """Render an Entry back to its README bullet."""
    badge = ("🟢" if entry.score == 3 else "🟡") + (UNVERIFIED_BADGE if entry.unverified else "")
    line = f"* {badge} [{entry.name}]({entry.url}) - {entry.description}"
    if entry.tags:
        line += f" <!-- tags: {', '.join(entry.tags)} -->"
    return line
