#!/usr/bin/env python3
"""One-off maintenance: re-score every Emerging & Unverified Providers entry
and correct its badge to match.

Every entry in this README section currently shows a green (3/3) badge
regardless of its actual score, which contradicts both the badge legend
and the section's own "doesn't yet fully meet criteria" description. This
re-runs the same 3-criteria evaluation the submission pipeline uses and
fixes each badge in place.

Meant to run via the `audit-emerging-badges` workflow_dispatch workflow,
since it needs live network + LLM credentials — not on every push.

Never removes entries, even ones scoring below the 2/3 publish bar; that
call needs a maintainer, so sub-2/3 entries are flagged in the report
instead of touched.

Writes:
  README.md       - badges corrected in place (only if something changed)
  audit_report.md - summary of corrections and entries flagged for review
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from evaluate_submission import evaluate_service  # noqa: E402
from lib.readme_entries import badge_for_score, list_entries_in_category  # noqa: E402

EMERGING_CATEGORY = "Emerging & Unverified Providers"
README_FILE = "README.md"


def audit(content):
    """Re-score every entry in EMERGING_CATEGORY. Returns (new_content, changed, flagged)."""
    entries = list_entries_in_category(content, EMERGING_CATEGORY)
    lines = content.split("\n")
    changed = []
    flagged = []

    for entry in entries:
        print(f"Evaluating {entry['name']} ({entry['url']})...")
        result = evaluate_service(entry["url"])
        score = result["score"]
        new_badge = badge_for_score(score)

        if score < 2:
            flagged.append({**entry, "score": score})

        if new_badge != entry["badge"]:
            lines[entry["line_idx"]] = lines[entry["line_idx"]].replace(
                entry["badge"], new_badge, 1
            )
            changed.append({**entry, "score": score, "new_badge": new_badge})

    return "\n".join(lines), changed, flagged, len(entries)


def build_report(total, changed, flagged):
    report = [f"## {EMERGING_CATEGORY} badge audit\n", f"Re-evaluated {total} entries.\n"]

    if changed:
        report.append("### Badges corrected\n")
        report.append("| Name | Old | New | Score |\n|------|-----|-----|-------|\n")
        for c in changed:
            report.append(f"| {c['name']} | {c['badge']} | {c['new_badge']} | {c['score']}/3 |\n")
    else:
        report.append("No badge corrections needed.\n")

    if flagged:
        report.append(
            "\n### Needs manual review (scored below 2/3 — may not belong in the public list)\n"
        )
        report.append("| Name | URL | Score |\n|------|-----|-------|\n")
        for f in flagged:
            report.append(f"| {f['name']} | {f['url']} | {f['score']}/3 |\n")

    return "\n".join(report)


def main():
    with open(README_FILE) as f:
        content = f.read()

    new_content, changed, flagged, total = audit(content)

    if total == 0:
        print(f"No entries found in '{EMERGING_CATEGORY}'")
        with open("audit_report.md", "w") as f:
            f.write(f"No entries found in **{EMERGING_CATEGORY}** — nothing to audit.\n")
        return

    if changed:
        with open(README_FILE, "w") as f:
            f.write(new_content)

    with open("audit_report.md", "w") as f:
        f.write(build_report(total, changed, flagged))

    print(f"Corrected {len(changed)} badge(s), flagged {len(flagged)} entrie(s) for review")


if __name__ == "__main__":
    main()
