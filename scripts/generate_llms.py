#!/usr/bin/env python3
"""
Generate docs/llms.txt and docs/llms-full.txt from docs/clouds.json.

Called by deploy-pages.yml after clouds.json is regenerated so that
AI-readable files always reflect the current state of the directory.

Usage:
    python scripts/generate_llms.py [clouds.json] [output_dir]

Defaults:
    clouds.json  → docs/clouds.json
    output_dir   → docs/
"""

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path


# ---------------------------------------------------------------------------
# Static content blocks (not derived from clouds.json)
# ---------------------------------------------------------------------------

_CRITERIA_BLOCK = """\
## Evaluation Criteria

Services are scored against 3 criteria. A minimum score of 2/3 is required for inclusion:

1. **Transparent Public Pricing** — a publicly accessible pricing page with actual prices or tiers visible without signing up or contacting sales.
2. **Usage-Based Self-Service** — ability to sign up and start using the service without sales intervention; includes free trials, free tiers, or pay-as-you-go billing.
3. **Production Indicators** — a public SLA commitment, status page, or uptime transparency indicator (e.g. statuspage.io, status subdomain).

Score legend: 🟢 = 3/3 criteria met | 🟡 = 2/3 criteria met"""

_PIPELINE_BLOCK = """\
## Submission & Evaluation Pipeline

- Submission form at https://www.alt-cloud.org/submit/ creates a GitHub issue
- For single-URL submissions: evaluate-submission.yml workflow runs automatically
- For multi-URL submissions: split-submission.yml creates one child issue per URL, evaluates each independently
- Evaluation uses Python scripts with web scraping (Jina Reader + requests) and Claude AI for metadata generation
- Passing services (score ≥ 2) get an automatic PR; failing services get a needs-review label for admin override
- Admin override: comment `/approve 3` on any issue to force-approve with score override
- clouds.json is regenerated on every PR merge; dateAdded comes from git history"""

_CONTACT_BLOCK = """\
## Contact

- Website: https://www.alt-cloud.org
- GitHub Issues: https://github.com/datum-cloud/awesome-alt-clouds/issues
- Submit a service: https://www.alt-cloud.org/submit/"""


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_clouds(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def category_stats(clouds: list[dict]) -> list[tuple[str, int, list[str]]]:
    """Return list of (category, count, [top service names]) sorted by count desc."""
    cat_entries: dict[str, list[str]] = defaultdict(list)
    for c in clouds:
        for cat in c.get("categories", []):
            cat_entries[cat].append(c["name"])

    result = []
    for cat, names in cat_entries.items():
        result.append((cat, len(names), names))
    result.sort(key=lambda x: -x[1])
    return result


# ---------------------------------------------------------------------------
# llms.txt generator
# ---------------------------------------------------------------------------

def generate_llms_txt(clouds: list[dict]) -> str:
    total = len(clouds)
    stats = category_stats(clouds)
    num_cats = len(stats)
    top5 = ", ".join(f"{cat} ({n})" for cat, n, _ in stats[:5])

    lines = [
        "# Awesome Alt Clouds",
        "",
        f"> Curated directory of {total}+ alternative cloud providers for developers — covering {num_cats} categories including infrastructure, GPU compute, databases, AI inference, observability, developer tooling, and more. Each service is evaluated against 3 public criteria.",
        "",
        "## Directory",
        "",
        "- [Full Cloud Directory](https://www.alt-cloud.org/): Interactive directory of "
        f"{total}+ alternative cloud providers across {num_cats} categories. "
        "Filter by category, search by name, sort by score or recently added.",
        "- [Submit a Cloud Service](https://www.alt-cloud.org/submit/): Form to submit a new cloud service for automated evaluation and inclusion in the directory.",
        "",
        "## Data",
        "",
        "- [clouds.json](https://www.alt-cloud.org/clouds.json): Machine-readable JSON file with all "
        f"{total}+ entries including name, URL, description, score (2 or 3), categories, and dateAdded. "
        "Updated automatically on each PR merge.",
        "- [README (Awesome List)](https://raw.githubusercontent.com/datum-cloud/awesome-alt-clouds/main/README.md): "
        "Canonical markdown source of the directory, organized by category with scoring badges. Hosted on GitHub.",
        "- [GitHub Repository](https://github.com/datum-cloud/awesome-alt-clouds): "
        "Source repository. Contains submission workflows, evaluation scripts, and contribution guidelines.",
        "",
        "## Key Facts",
        "",
        f"- {total}+ cloud services listed across {num_cats} categories",
        "- Services must meet at least 2 of 3 criteria to be included: "
        "(1) transparent public pricing, (2) usage-based self-service signup, (3) public SLA or status page",
        "- Score legend: 🟢 = all 3 criteria met, 🟡 = 2 of 3 criteria met",
        "- Automated submission pipeline: form → GitHub issue → AI evaluation → PR → merge",
        f"- Largest categories: {top5}",
        "- Community-maintained; maintained by Datum Cloud",
        "- Data available as JSON at /clouds.json and Markdown on GitHub",
        "",
        "## Contact",
        "",
        "- Website: https://www.alt-cloud.org",
        "- GitHub: https://github.com/datum-cloud/awesome-alt-clouds",
        "- Submit: https://www.alt-cloud.org/submit/",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# llms-full.txt generator
# ---------------------------------------------------------------------------

# Category descriptions (static; keyed by exact category name)
_CAT_DESCRIPTIONS: dict[str, str] = {
    "Infrastructure Clouds": (
        "General-purpose cloud compute, bare metal, and VPS providers. "
        "The original \"alt clouds\" offering virtualized compute, dedicated servers, "
        "GPU instances, storage, and Kubernetes services outside the hyperscaler ecosystem."
    ),
    "GPU & AI Compute Clouds": (
        "Specialized GPU compute platforms for AI training, model fine-tuning, and "
        "high-performance workloads. Includes serverless GPU inference, GPU clusters, "
        "and distributed compute networks."
    ),
    "Databases & Storage": (
        "Managed database services, vector databases, distributed SQL, time series, "
        "object storage, and data warehousing — all self-service with public pricing."
    ),
    "Developer Tooling & CI/CD": (
        "CI/CD platforms, code hosting, testing infrastructure, feature flags, "
        "error monitoring, and developer workflow automation."
    ),
    "Authorization, Identity & Fraud": (
        "Authentication, authorization, identity management, secrets management, "
        "and fraud detection services with self-service onboarding."
    ),
    "Observability & Monitoring": (
        "Logging, metrics, tracing, APM, uptime monitoring, and error tracking "
        "platforms with pay-as-you-go or free tiers."
    ),
    "AI Assistants & Copilots": (
        "AI assistant platforms, copilot APIs, and conversational AI services for "
        "building customer-facing or developer-facing intelligent experiences."
    ),
    "Network & Connectivity Clouds": (
        "CDN, edge networking, DNS, DDoS protection, VPN, and private networking platforms."
    ),
    "Monetization & Billing Clouds": (
        "Payment processing, subscription management, usage-based billing, metering, "
        "and revenue operations platforms."
    ),
    "Customer, Marketing & eCommerce": (
        "CRM, customer support, marketing automation, and e-commerce infrastructure platforms."
    ),
    "AI Coding & App Generation": (
        "AI-assisted code generation, app scaffolding, and developer productivity "
        "tools built on LLMs."
    ),
    "PaaS & Application Hosting": (
        "Platform-as-a-service offerings for deploying web applications, APIs, and "
        "backend services with minimal infrastructure management."
    ),
    "Security, Compliance & Sovereignty Clouds": (
        "Security-focused cloud platforms with compliance certifications, data "
        "sovereignty options, air-gapped deployments, and sovereign cloud infrastructure."
    ),
    "Communications, IoT & Media": (
        "Messaging APIs, email delivery, SMS, voice, video, push notifications, "
        "and IoT connectivity platforms."
    ),
    "Analytics & Data Warehousing": (
        "Cloud data warehouses, analytics databases, business intelligence platforms, "
        "and data lakehouse services."
    ),
    "Workflow & Operations Clouds": (
        "Workflow orchestration, job queues, event streaming, and operations "
        "automation platforms."
    ),
    "Data Integration & ETL": (
        "Data pipeline, ETL, CDC, and integration platforms with self-service onboarding."
    ),
    "AI Inference & Model APIs": (
        "Hosted inference APIs for open-source and proprietary models, optimized "
        "for speed, cost, and scale."
    ),
    "Unikernels & WebAssembly": (
        "Edge computing, WebAssembly runtimes, and unikernel deployment platforms."
    ),
    "Source Code Control": (
        "Git hosting platforms with CI/CD integration and collaboration features."
    ),
    "Cloud Adjacent & Infrastructure Tooling": (
        "Tools and platforms that extend or manage cloud infrastructure without "
        "being cloud providers themselves."
    ),
    "Decentralized & Web3 Compute": (
        "Blockchain-based and decentralized compute platforms."
    ),
    "Emerging & Unverified Providers": (
        "Services that passed automated evaluation but have limited track record or "
        "are early-stage. Scored 🟡 (2/3 criteria). Included for discovery; "
        "verify independently before production use."
    ),
}

_DEFAULT_CAT_DESCRIPTION = "Cloud services in this category."


def generate_llms_full_txt(clouds: list[dict]) -> str:
    total = len(clouds)
    stats = category_stats(clouds)
    num_cats = len(stats)
    today = date.today().isoformat()

    sections: list[str] = []

    # Header
    sections.append("# Awesome Alt Clouds — Full Reference")
    sections.append("")
    sections.append(
        f"> Curated directory of {total}+ alternative cloud providers for developers who need "
        "specialized infrastructure beyond AWS, GCP, and Azure. Each service is independently "
        "evaluated against 3 public criteria: transparent pricing, self-service signup, and a "
        "public SLA or status page."
    )
    sections.append("")

    # About
    sections.append("## About This Directory")
    sections.append("")
    sections.append(
        "- [Directory Homepage](https://www.alt-cloud.org/): Interactive searchable directory. "
        "Filter by category, search by name or description, sort alphabetically, by score, or by "
        "recently added date. All data loaded from /clouds.json."
    )
    sections.append(
        "- [Submit a Service](https://www.alt-cloud.org/submit/): Web form that creates a GitHub "
        "issue, triggers automated AI evaluation (pricing page detection, signup detection, status "
        "page detection), and opens a PR on pass."
    )
    sections.append(
        "- [GitHub Repository](https://github.com/datum-cloud/awesome-alt-clouds): Source of truth. "
        "Contains README.md (the awesome list), evaluation scripts in /scripts, and GitHub Actions "
        "workflows in .github/workflows."
    )
    sections.append(
        f"- [Machine-Readable Data](https://www.alt-cloud.org/clouds.json): JSON array of all "
        f"{total}+ entries with fields: name, url, description, score (2 or 3), categories (array), "
        "dateAdded (ISO date from git history)."
    )
    sections.append("")

    # Criteria
    sections.append(_CRITERIA_BLOCK)
    sections.append("")

    # Categories
    sections.append("## Categories")
    sections.append("")

    for cat, count, names in stats:
        desc = _CAT_DESCRIPTIONS.get(cat, _DEFAULT_CAT_DESCRIPTION)
        # Up to 15 key service names
        key_services = ", ".join(names[:15])
        if len(names) > 15:
            key_services += f", and {len(names) - 15} more"
        sections.append(f"### {cat} ({count} services)")
        sections.append("")
        sections.append(desc)
        sections.append("")
        sections.append(f"Services: {key_services}.")
        sections.append("")

    # Pipeline
    sections.append(_PIPELINE_BLOCK)
    sections.append("")

    # Key facts
    score3 = sum(1 for c in clouds if c.get("score", 3) == 3)
    score2 = sum(1 for c in clouds if c.get("score", 3) == 2)

    sections.append("## Key Facts")
    sections.append("")
    sections.append(f"- {total}+ services as of {today}")
    sections.append(f"- {num_cats} categories covering the full developer cloud ecosystem")
    sections.append(f"- {score3} services meet all 3 criteria (🟢); {score2} meet 2 of 3 (🟡)")
    sections.append("- Minimum inclusion score: 2/3 criteria")
    sections.append("- Machine-readable data: https://www.alt-cloud.org/clouds.json")
    sections.append("- Source: https://github.com/datum-cloud/awesome-alt-clouds")
    sections.append("- License: CC BY 4.0")
    sections.append("- Maintained by: Datum Cloud (https://github.com/datum-cloud)")
    sections.append("- Accepts community submissions via https://www.alt-cloud.org/submit/")
    sections.append("")

    # Contact
    sections.append(_CONTACT_BLOCK)

    return "\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    clouds_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/clouds.json")
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("docs")

    if not clouds_path.exists():
        print(f"ERROR: {clouds_path} not found", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    clouds = load_clouds(clouds_path)
    total = len(clouds)
    print(f"Loaded {total} services from {clouds_path}")

    llms_path = output_dir / "llms.txt"
    llms_path.write_text(generate_llms_txt(clouds))
    print(f"✅ Generated {llms_path}")

    llms_full_path = output_dir / "llms-full.txt"
    llms_full_path.write_text(generate_llms_full_txt(clouds))
    print(f"✅ Generated {llms_full_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
