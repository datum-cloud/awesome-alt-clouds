"""Shared README.md category-section helpers.

Used by create_submission_pr.py (add a new service) and
create_graduation_pr.py (move an existing service between categories).
Both read/write the same `* <badge> [Name](url) - description` bullet
format documented in CLAUDE.md.
"""

import re

README_FILE = "README.md"


def find_category_section(readme_content, category):
    """Return (start_idx, end_idx) line range of a `## <category>` section."""
    lines = readme_content.split("\n")

    category_header = f"## {category}"
    start_idx = None
    end_idx = None

    for i, line in enumerate(lines):
        if line.strip() == category_header:
            start_idx = i
        elif start_idx is not None and line.startswith("## ") and i > start_idx:
            end_idx = i
            break

    if start_idx is None:
        return None, None

    if end_idx is None:
        end_idx = len(lines)

    return start_idx, end_idx


def badge_for_score(score):
    """3/3 -> green, 2/3 -> yellow. Matches the README legend."""
    return "🟢" if score == 3 else "🟡"


def add_entry_to_readme(submission, content=None):
    """Insert `submission` into its category section, alphabetically by name.

    Reads/writes README.md unless `content` is passed (then returns the new
    content instead of writing, letting callers batch a remove+add together).
    Returns None if the category section can't be found.
    """
    own_content = content is None
    if own_content:
        with open(README_FILE) as f:
            content = f.read()

    category = submission["category"]
    start_idx, end_idx = find_category_section(content, category)

    if start_idx is None:
        print(f"Warning: Category '{category}' not found in README")
        return None

    lines = content.split("\n")
    badge = badge_for_score(submission["score"])
    new_entry = (
        f"* {badge} [{submission['name']}]({submission['url']}) - {submission['description']}"
    )

    entries = []
    insert_after_idx = start_idx

    for i in range(start_idx + 1, end_idx):
        line = lines[i].strip()
        if line.startswith("* "):
            entries.append((i, line))
            insert_after_idx = i

    new_name = submission["name"].lower()
    insert_idx = None
    for line_idx, line in entries:
        match = re.search(r"\[([^\]]+)\]", line)
        if match and new_name < match.group(1).lower():
            insert_idx = line_idx
            break

    if insert_idx is None:
        insert_idx = insert_after_idx + 1

    lines.insert(insert_idx, new_entry)
    new_content = "\n".join(lines)

    if own_content:
        with open(README_FILE, "w") as f:
            f.write(new_content)
        return True

    return new_content


def _parse_bullet_line(line):
    """Parse `* <badge> [Name](url) - description`, or return None."""
    match = re.match(r"\*\s*(\S+)\s*\[([^\]]+)\]\(([^)]+)\)\s*-\s*(.+)", line.strip())
    if not match:
        return None
    return {
        "badge": match.group(1),
        "name": match.group(2).strip(),
        "url": match.group(3),
        "description": match.group(4),
    }


def find_entry_by_name(readme_content, name):
    """Find an existing `* <badge> [Name](url) - description` bullet by name.

    Name matching is case-insensitive and exact (not substring), since
    category names commonly overlap (e.g. "Split" vs "Splitwise"). Returns
    a dict with category/url/description/badge/line_idx, or None if no
    entry matches.
    """
    lines = readme_content.split("\n")
    target = name.strip().lower()

    current_category = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## "):
            current_category = stripped[3:].strip()
            continue

        parsed = _parse_bullet_line(stripped)
        if not parsed or parsed["name"].lower() != target:
            continue

        return {"line_idx": i, "category": current_category, **parsed}

    return None


def list_entries_in_category(readme_content, category):
    """Return every bullet entry within a `## <category>` section.

    Each item is a dict with line_idx/badge/name/url/description, in the
    order they appear in the file.
    """
    lines = readme_content.split("\n")
    start_idx, end_idx = find_category_section(readme_content, category)
    if start_idx is None:
        return []

    entries = []
    for i in range(start_idx + 1, end_idx):
        parsed = _parse_bullet_line(lines[i])
        if parsed:
            entries.append({"line_idx": i, **parsed})

    return entries


def remove_entry_from_readme(readme_content, line_idx):
    """Remove the bullet at `line_idx` and return the new content."""
    lines = readme_content.split("\n")
    del lines[line_idx]
    return "\n".join(lines)
