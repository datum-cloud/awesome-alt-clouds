"""Prompt text and response normalization for category + tag classification.

Shared by the four LLM call sites in evaluate_submission.py (Claude/Qwen, metadata-only
and full-evaluation) so the taxonomy is described, and validated, in exactly one place.
"""

from lib.taxonomy import (
    CATEGORIES,
    CATEGORY_DEFINITIONS,
    CROSS_CUTTING_TAGS,
    REGION_TAG_PREFIX,
    WORKLOAD,
    WORKLOAD_TAG_FAMILIES,
    WORKLOAD_TAGS,
    is_valid_tag,
)

DEFAULT_CATEGORY = "Infrastructure Clouds"
MAX_WORKLOAD_TAGS = 4
MAX_TAGS = 8


def classification_prompt_block() -> str:
    """Categories (with definitions) plus the tag vocabulary and rules, for LLM prompts."""
    categories = "\n".join(f"- {cat}: {CATEGORY_DEFINITIONS[cat]}" for cat in CATEGORIES)
    families = "\n".join(
        f"  - {family}: {', '.join(tags)}" for family, tags in WORKLOAD_TAG_FAMILIES.items()
    )
    return f"""{categories}

Pick exactly one category. Hosting country alone does not make a cloud Sovereign: choose
Sovereign only when jurisdiction is the main reason to buy it. Seat- or contract-priced SaaS
is not Vertical.

Also provide "tags": a JSON array of tag slugs from these vocabularies (use [] if none fit):
- Workload tags (ONLY when the category is {WORKLOAD}; at most {MAX_WORKLOAD_TAGS}):
{families}
- Tags valid for any category: {", ".join(CROSS_CUTTING_TAGS)}
  (agent-native = agents can sign up, provision and pay via API/MCP)
- Region tags: "{REGION_TAG_PREFIX}<code>", e.g. region:ch, region:de, region:eu (lowercase)
Never invent tags outside these lists."""


def normalize_classification(data: dict) -> list[str]:
    """Validate/repair `category` and `tags` in place. Returns human-readable warnings.

    Fail-open: invalid categories fall back to DEFAULT_CATEGORY, unknown tags are dropped,
    and workload tags on a non-Workload entry are dropped. Never raises.
    """
    warnings: list[str] = []
    category = data.get("category")
    if category not in CATEGORIES:
        warnings.append(f"invalid category {category!r}, defaulting to {DEFAULT_CATEGORY}")
        data["category"] = DEFAULT_CATEGORY

    raw = data.get("tags")
    candidates = raw if isinstance(raw, list) else []
    kept: list[str] = []
    workload_count = 0
    for tag in candidates:
        if not isinstance(tag, str) or tag in kept:
            continue
        if not is_valid_tag(tag):
            warnings.append(f"dropped unknown tag {tag!r}")
        elif tag in WORKLOAD_TAGS and data["category"] != WORKLOAD:
            warnings.append(f"dropped workload tag {tag!r} on {data['category']}")
        elif tag in WORKLOAD_TAGS and workload_count >= MAX_WORKLOAD_TAGS:
            warnings.append(f"dropped {tag!r}: more than {MAX_WORKLOAD_TAGS} workload tags")
        else:
            workload_count += tag in WORKLOAD_TAGS
            kept.append(tag)
    data["tags"] = kept[:MAX_TAGS]
    for warning in warnings:
        print(f"Warning: {warning}")
    return warnings
