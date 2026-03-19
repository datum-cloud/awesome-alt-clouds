#!/usr/bin/env python3
"""
Parse README.md and generate clouds.json for the frontend.
Extracts: name, url, description, categories (array), and score (from circles).

Multi-category support: if the same URL appears under multiple ## sections,
the entry is deduplicated and both category names are merged into its
categories array.
"""

import json
import re


def parse_readme(readme_path):
    """Parse README.md and extract all cloud services."""

    with open(readme_path, 'r') as f:
        content = f.read()

    # url → entry dict (for deduplication)
    seen = {}
    order = []  # preserve first-seen order

    skip_sections = {'Contents', 'Criteria', 'Contributing', 'License'}
    current_category = None

    for line in content.split('\n'):
        # Track current category section
        if line.startswith('## '):
            name = line.replace('## ', '').strip()
            current_category = None if name in skip_sections else name
            continue

        # Parse service entries: * 🟢 [Name](url) - Description
        match = re.match(r'^\s*\*\s*(🟢|🟡)?\s*\[([^\]]+)\]\(([^)]+)\)\s+-\s+(.+)$', line)
        if not match or not current_category:
            continue

        badge = match.group(1)
        name = match.group(2)
        url = match.group(3)
        description = match.group(4)
        score = 2 if badge == '🟡' else 3

        if url in seen:
            # Same entry listed under a second section — merge the category
            if current_category not in seen[url]['categories']:
                seen[url]['categories'].append(current_category)
        else:
            entry = {
                'name': name,
                'url': url,
                'description': description,
                'score': score,
                'categories': [current_category],
            }
            seen[url] = entry
            order.append(url)

    return [seen[url] for url in order]


def generate_clouds_json(readme_path, output_path):
    """Generate clouds.json from README.md."""

    clouds = parse_readme(readme_path)

    with open(output_path, 'w') as f:
        json.dump(clouds, f, indent=2)

    total = len(clouds)
    score_3 = sum(1 for c in clouds if c['score'] == 3)
    score_2 = sum(1 for c in clouds if c['score'] == 2)
    multi = sum(1 for c in clouds if len(c['categories']) > 1)
    unique_cats = len({cat for c in clouds for cat in c['categories']})

    print(f"✅ Generated {output_path}")
    print(f"\n📊 Statistics:")
    print(f"   Total services:    {total}")
    print(f"   🟢 3/3 criteria:   {score_3} ({score_3/total*100:.0f}%)")
    print(f"   🟡 2/3 criteria:   {score_2} ({score_2/total*100:.0f}%)")
    print(f"   Categories:        {unique_cats}")
    print(f"   Multi-category:    {multi}")

    return clouds


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parse_readme_to_json.py <README.md> [clouds.json]")
        return 1

    readme_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'clouds.json'

    try:
        generate_clouds_json(readme_path, output_path)
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
