# ruff: noqa: E501  (regex rule tables are intentionally one rule per line)
"""Keyword rules that propose a category and tags for a README entry.

Heuristic, deterministic, and meant to be reviewed: every proposal is written
to a CSV before anything touches README.md. Rules read name + description
(lowercased) and the entry's legacy category.
"""

import re
from collections.abc import Sequence

from lib.taxonomy import (
    CATEGORIES,
    INFRASTRUCTURE,
    LEGACY_CATEGORY_MAP,
    SERVICE,
    SOVEREIGN,
    UNVERIFIED_LEGACY_CATEGORY,
    VERTICAL,
    WORKLOAD,
)

MAX_WORKLOAD_TAGS = 4

# Curated, per-entry overrides (lowercased name -> (category, tags)). These win over the keyword
# rules. Seeded from the examples in Notable's "rise of workload clouds" post and Jacob's brief.
CURATED_OVERRIDES: dict[str, tuple[str, tuple[str, ...]]] = {
    "supabase": (WORKLOAD, ("postgres-sql", "open-source")),
    "baseten": (WORKLOAD, ("llm-inference", "open-source", "gpu")),
    "modal": (WORKLOAD, ("llm-inference", "serverless-functions", "gpu")),
    "fal.ai": (WORKLOAD, ("generative-media", "batch-gpu", "gpu")),
    "cloudscale.ch": (SOVEREIGN, ("region:ch",)),
}

# tag -> regex over lowercased "name description". Order = priority.
WORKLOAD_TAG_RULES: tuple[tuple[str, str], ...] = (
    ("web-frontend", r"frontend|front-end|jamstack|static (site|web)|next\.js|nuxt|sveltekit|web applications?|(host|deploy|run)\w*[\w ,]{0,20}websites?"),
    ("app-hosting", r"paas|platform-as-a-service|app hosting|application hosting|deploy\w* (web )?(apps?|applications|containers)|git push"),
    ("serverless-functions", r"serverless (function|compute|platform|container)|functions-as-a-service|faas|lambda"),
    ("edge-functions", r"edge (function|compute|runtime|platform)|workers"),
    ("wasm-unikernel", r"wasm|webassembly|unikernel"),
    ("postgres-sql", r"postgres|mysql|mariadb|sql database|using sql|relational|distributed sql|cockroach|sqlite|managed database|database-as-a-service|database platform"),
    ("nosql-timeseries", r"nosql|document[- ]based|document database|time-series|multi-model|\bmongo"),
    ("key-value-cache", r"redis|key-value|valkey|memcached|caching|\bcache\b"),
    ("vector", r"vector"),
    ("warehouse-lakehouse", r"warehouse|lakehouse|olap|analytics database|clickhouse|data lake|business intelligence"),
    ("streaming-etl", r"\betl\b|\belt\b|\bcdc\b|data pipeline|kafka|event stream|streaming|message queue|data integration|ingest"),
    ("llm-inference", r"inference|\bllms?\b|language model|model api|open-source models|chat completion|machine learning models|ml models"),
    ("generative-media", r"image generation|video generation|generative media|text-to-image|text-to-video|diffusion|music generation|generative ai (for )?(image|video)"),
    ("training-finetuning", r"fine-tun|model training|training (platform|jobs)|train (models|ai)"),
    ("batch-gpu", r"batch (job|compute|processing)|serverless gpu|gpu jobs"),
    ("speech-voice", r"speech|voice|text-to-speech|transcription|\bstt\b|\btts\b|\basr\b"),
    ("agent-browser", r"browser (automation|infrastructure|session|api)|headless browser|web scraping|scraping|web data"),
    ("agent-sandbox", r"sandbox|code execution|code interpreter|microvm"),
    ("agent-search", r"search api|web search|content extraction|web crawl"),
    ("agent-memory", r"agent memory|memory layer|long-term memory"),
    ("app-generation", r"app generation|app builder|generates? (apps?|code|full-stack)|code generation|text-to-app|vibe cod"),
    ("ci-builds", r"ci/cd|continuous integration|build pipeline|github actions|ci runner|ci service|build minutes"),
    ("durable-workflow", r"workflow|orchestrat|durable|job queue|background job|cron|temporal"),
    ("observability", r"observability|\blogs?\b|logging|metrics|tracing|\bapm\b|telemetry"),
    ("media-processing", r"video (encoding|processing|transcod|api|platform)|media processing|image processing|transcod|image optimi"),
    ("realtime-rtc", r"real-time|realtime|webrtc|websocket|\brtc\b|live video|pub/sub|presence"),
)  # fmt: skip

# Legacy category -> workload tag implied before any keyword matching.
LEGACY_TAG_PRIORS = {
    "AI Inference & Model APIs": "llm-inference",
    "Analytics & Data Warehousing": "warehouse-lakehouse",
    "Data Integration & ETL": "streaming-etl",
    "PaaS & Application Hosting": "app-hosting",
    "Unikernels & WebAssembly": "wasm-unikernel",
    "Workflow & Operations Clouds": "durable-workflow",
    "AI Coding & App Generation": "app-generation",
    "Observability & Monitoring": "observability",
}

# Region tag -> regex.
REGION_RULES: tuple[tuple[str, str], ...] = (
    ("region:ch", r"swiss|switzerland"),
    ("region:de", r"german"),
    ("region:fr", r"french|\bfrance\b"),
    ("region:nl", r"dutch|netherlands"),
    ("region:uk", r"\buk\b|united kingdom|british"),
    ("region:eu", r"\beu\b|europe|\beu-"),
    ("region:in", r"indian|\bindia\b"),
    ("region:jp", r"japan"),
    ("region:sg", r"singapore"),
    ("region:au", r"australia"),
    ("region:ca", r"canad"),
    ("region:br", r"brazil"),
)

SOVEREIGN_HINT = r"sovereign|data residency|in-country|gaia-x|swiss|german cloud|european cloud|\beu-(only|based)|data sovereignty"  # noqa: E501
VERTICAL_HINT = (
    r"health|hipaa|clinical|legal|bank|insurance|fintech|real estate|payments? infrastructure"  # noqa: E501
)
OBJECT_STORAGE_HINT = (
    r"object storage|\bs3\b|block storage|file storage|backup|cold storage|archive"
)
LIGHT_OBS_HINT = r"uptime|status page|error tracking|incident|alerting|on-call"
RTC_HINT = r"\bvideo\b|\bvoice\b|real-time|webrtc|\brtc\b|\bstreaming\b|\blive\b"
CI_HINT = r"\bci\b|ci/cd|ci runner|build (minutes|pipeline|server)|github actions|\brunners?\b"
HOSTED_AI_HINT = r"\bapis?\b|managed hosting|sandbox|inference|hosting for|runtime|infrastructure"
OPEN_SOURCE_HINT = r"open[- ]source|self-host|byoc|bring your own cloud|source-available"
AGENT_NATIVE_HINT = r"\bmcp\b|for (ai )?agents|agent-native|agents can|agentic"
HARDWARE_HINT = r"bare[- ]metal|data ?cent(er|re)s?|colocation|own hardware|dedicated servers|owns? (its|their) (own )?"  # noqa: E501
GPU_HINT = r"\bgpus?\b|h100|a100|b200|cuda"


def _text(name: str, description: str) -> str:
    return f"{name} {description}".lower()


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


def propose_category(legacy: str, name: str, description: str) -> tuple[str, bool]:
    """Return (new_category, needs_review). Split buckets are always flagged."""
    curated = CURATED_OVERRIDES.get(name.lower())
    if curated:
        return curated[0], False
    mapped = LEGACY_CATEGORY_MAP.get(legacy)
    if mapped:
        return mapped, False

    text = _text(name, description)
    if _has(SOVEREIGN_HINT, text) and legacy != "Databases & Storage":
        return SOVEREIGN, True

    if legacy == UNVERIFIED_LEGACY_CATEGORY:
        return _propose_for_unverified(text), True
    if legacy == "Databases & Storage":
        return (INFRASTRUCTURE if _has(OBJECT_STORAGE_HINT, text) else WORKLOAD), True
    if legacy == "Observability & Monitoring":
        return (SERVICE if _has(LIGHT_OBS_HINT, text) else WORKLOAD), True
    if legacy == "Developer Tooling & CI/CD":
        return (WORKLOAD if _has(CI_HINT, text) else SERVICE), True
    if legacy == "Communications, IoT & Media":
        return (WORKLOAD if _has(RTC_HINT, text) else SERVICE), True
    if legacy == "AI Assistants & Copilots":
        # Hosted models/agents/APIs are Workload; assistant apps are seat-priced SaaS.
        return (WORKLOAD if _has(HOSTED_AI_HINT, text) else SERVICE), True
    if _has(VERTICAL_HINT, text):
        return VERTICAL, True
    return SERVICE, True


def _propose_for_unverified(text: str) -> str:
    """Emerging entries have no real category yet: classify from the text alone."""
    if _has(r"feature flag|api gateway|api management|experimentation", text):
        return SERVICE
    if _has(r"rack-scale|bare[- ]metal|dedicated servers|object storage", text):
        return INFRASTRUCTURE
    if any(_has(pattern, text) for _, pattern in WORKLOAD_TAG_RULES):
        return WORKLOAD
    return SERVICE


def propose_workload_tags(legacy: str, name: str, description: str) -> list[str]:
    text = _text(name, description)
    tags: list[str] = []
    prior = LEGACY_TAG_PRIORS.get(legacy)
    if prior:
        tags.append(prior)
    for tag, pattern in WORKLOAD_TAG_RULES:
        if tag not in tags and _has(pattern, text):
            tags.append(tag)
    return tags[:MAX_WORKLOAD_TAGS]


def propose_cross_cutting_tags(legacy: str, name: str, description: str) -> list[str]:
    text = _text(name, description)
    tags: list[str] = []
    if _has(AGENT_NATIVE_HINT, text):
        tags.append("agent-native")
    if _has(OPEN_SOURCE_HINT, text):
        tags.append("open-source")
    owns = legacy in {"Infrastructure Clouds", "GPU & AI Compute Clouds"}
    if _has(HARDWARE_HINT, text) and owns:
        tags.append("owns-hardware")
    if _has(GPU_HINT, text) or legacy == "GPU & AI Compute Clouds":
        tags.append("gpu")
    tags.extend(tag for tag, pattern in REGION_RULES if _has(pattern, text))
    return tags


def propose_tags(legacy: str, name: str, description: str, category: str) -> tuple[str, ...]:
    """Workload tags only for Workload entries; cross-cutting tags for all."""
    curated = CURATED_OVERRIDES.get(name.lower())
    if curated and curated[0] == category:
        return curated[1]
    workload = propose_workload_tags(legacy, name, description) if category == WORKLOAD else []
    return tuple(dict.fromkeys([*workload, *propose_cross_cutting_tags(legacy, name, description)]))


def assert_known_categories(categories: Sequence[str]) -> None:
    unknown = [c for c in categories if c not in CATEGORIES]
    if unknown:
        raise ValueError(f"Unknown categories: {unknown}")
