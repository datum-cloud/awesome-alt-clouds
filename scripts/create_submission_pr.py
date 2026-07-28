#!/usr/bin/env python3
"""
Create a PR to add an approved submission to the README.md

Reads submission data from submission_data.json and creates a PR
that adds the service to the appropriate category in README.md.
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from lib.readme_entries import add_entry_to_readme  # noqa: E402
from lib.shell import run_command  # noqa: E402
from lib.slugify import slugify  # noqa: E402


def load_submission_data():
    """Load submission data from JSON file"""
    with open("submission_data.json") as f:
        data = json.load(f)

    # Handle both old single-service format and new multi-service format
    if "services" in data:
        return data
    else:
        # Convert old format to new format
        return {"services": [data], "issue_number": data.get("issue_number", "unknown")}


def generate_and_stage_mdx(service):
    """Generate a draft MDX profile for `service` and stage it for commit.

    Returns the generator's report dict (slug, output_path, fetch_method,
    needs_verification) on success, or None if generation was skipped or failed.
    Never raises — MDX generation must not block README PR creation.
    """
    name = service.get("name")
    if not name:
        return None

    slug = slugify(name)
    output_path = f"src/content/clouds/{slug}.mdx"

    if os.path.exists(output_path):
        print(f"MDX already exists for {slug}, skipping generation.")
        return None

    categories = service.get("categories")
    if not categories:
        categories = [service.get("category", "")] if service.get("category") else []

    env = os.environ.copy()
    env.update(
        {
            "CLOUD_NAME": name,
            "CLOUD_URL": service.get("url", ""),
            "CLOUD_SCORE": str(service.get("score", 3)),
            "CLOUD_CATEGORIES": ",".join(c for c in categories if c),
            "CLOUD_DESCRIPTION": service.get("description", ""),
            "OUTPUT_PATH": output_path,
            "DRY_RUN": "false",
        }
    )

    generator = os.path.join(os.path.dirname(__file__), "generate_cloud_profile.py")
    result = subprocess.run(
        [sys.executable, generator],
        env=env,
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print(result.stdout)
    if result.returncode != 0 or not os.path.exists(output_path):
        tail = (result.stderr or "")[-300:]
        print(f"MDX generation failed for {name}: {tail}")
        return None

    subprocess.run(["git", "add", output_path], check=True)
    print(f"Staged MDX: {output_path}")

    report_path = "profile_generation_report.json"
    if os.path.exists(report_path):
        with open(report_path) as f:
            return json.load(f)
    return {
        "slug": slug,
        "output_path": output_path,
        "fetch_method": "unknown",
        "needs_verification": False,
    }


def create_pr(data):
    """Create a branch and PR for the submission(s)"""
    services = data["services"]
    issue_number = data.get("issue_number", "unknown")

    if not services:
        print("No services to add")
        return False

    # Create branch name
    if len(services) == 1:
        branch_name = (
            f"submission-{issue_number}-{services[0]['name'].lower().replace(' ', '-')[:30]}"
        )
    else:
        branch_name = f"submission-{issue_number}-{len(services)}-services"

    # Configure git
    run_command('git config user.name "github-actions[bot]"')
    run_command('git config user.email "github-actions[bot]@users.noreply.github.com"')

    # Create and checkout new branch
    run_command(f"git checkout -b {branch_name}")

    # Add each entry to README
    added_services = []
    for service in services:
        if add_entry_to_readme(service):
            added_services.append(service)
        else:
            print(f"Failed to add {service['name']} to README")

    if not added_services:
        print("No services were added to README")
        return False

    # Auto-generate draft MDX detail page for each added service.
    # Failures here are non-fatal: the README PR still goes out.
    mdx_reports = []
    for service in added_services:
        report = generate_and_stage_mdx(service)
        if report:
            mdx_reports.append(report)

    # Commit changes
    run_command("git add README.md")

    if len(added_services) == 1:
        s = added_services[0]
        commit_msg = f"Add {s['name']} to {s['category']}\\n\\nCloses #{issue_number}"
    else:
        names = ", ".join(s["name"] for s in added_services)
        commit_msg = f"Add {len(added_services)} services: {names}\\n\\nCloses #{issue_number}"

    run_command(f'git commit -m "{commit_msg}"')

    # Push branch (force in case a previous run already pushed this branch)
    run_command(f"git push --force origin {branch_name}")

    # Skip PR creation if one already exists for this branch
    existing_pr = run_command(
        f'gh pr list --head {branch_name} --state open --json number --jq ".[0].number"',
        check=False,
    )
    if existing_pr.strip():
        print(
            f"PR #{existing_pr.strip()} already exists for branch {branch_name}, skipping creation"
        )
        return True

    # Create PR
    if len(added_services) == 1:
        s = added_services[0]
        badge = "🟢" if s["score"] == 3 else "🟡"
        pr_title = f"Add {badge} {s['name']} to {s['category']}"
    else:
        pr_title = f"Add {len(added_services)} new cloud services"

    # Check if any services need manual review
    needs_review = [s for s in added_services if s.get("needs_manual_review")]

    # Build PR body
    pr_body = """## New Cloud Service Submission

"""

    if needs_review:
        pr_body += """:warning: **Manual Review Required**

Some services could not be automatically verified (website protected by Cloudflare or similar).
Please manually verify the 3 criteria before merging:
1. Transparent Public Pricing
2. Usage-based Self-Service
3. Production Indicators (SLA/Status page)

"""

    if len(added_services) == 1:
        s = added_services[0]
        badge = "🟢" if s["score"] == 3 else "🟡"
        review_note = " ⚠️ needs verification" if s.get("needs_manual_review") else ""
        pr_body += f"""This PR adds **{s["name"]}** to the **{s["category"]}** category.

| Field | Value |
|-------|-------|
| Name | {s["name"]} |
| URL | {s["url"]} |
| Category | {s["category"]} |
| Score | {s["score"]}/3 {badge}{review_note} |
| Description | {s["description"]} |
"""
    else:
        pr_body += f"This PR adds **{len(added_services)} services**:\n\n"
        pr_body += "| Name | Category | Score | URL | Status |\n"
        pr_body += "|------|----------|-------|-----|--------|\n"
        for s in added_services:
            badge = "🟢" if s["score"] == 3 else "🟡"
            status = "⚠️ Needs verification" if s.get("needs_manual_review") else "✅ Verified"
            pr_body += f"| {s['name']} | {s['category']} | {s['score']}/3 {badge} | {s['url']} | {status} |\n"

    if mdx_reports:
        pr_body += "\n\n### Auto-generated detail pages\n\n"
        pr_body += "Each service below also has a `status: draft` MDX profile staged in this PR. "
        pr_body += "Draft profiles are only built on preview deploys; they ship to production after a maintainer flips `status: reviewed`.\n\n"
        for r in mdx_reports:
            flag = (
                " (needs verification — WebSearch fallback)" if r.get("needs_verification") else ""
            )
            pr_body += f"- `{r['output_path']}`{flag}\n"

    pr_body += f"""

---

Closes #{issue_number}

*This PR was automatically created by the submission bot.*
"""

    # Use gh CLI to create PR. check=True (default) so a failure here — e.g. the repo's
    # "Allow GitHub Actions to create and approve pull requests" setting being off —
    # raises, prints stderr, and fails the workflow step instead of silently no-opping
    # after the branch has already been pushed.
    pr_body_escaped = pr_body.replace('"', '\\"').replace("`", "\\`")
    result = run_command(
        f'gh pr create --title "{pr_title}" --body "{pr_body_escaped}" --base main --head {branch_name}'
    )

    print(f"PR creation result: {result}")
    return True


def main():
    # Load submission data
    try:
        data = load_submission_data()
    except FileNotFoundError:
        print("No submission_data.json found, skipping PR creation")
        return 0

    services = data.get("services", [])
    if not services:
        print("No services to add")
        return 0

    print(f"Creating PR for {len(services)} service(s)")
    for s in services:
        print(f"  - {s['name']} ({s['category']})")

    # Create PR
    try:
        create_pr(data)
        print("PR created successfully!")
        return 0
    except Exception as e:
        print(f"Error creating PR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
