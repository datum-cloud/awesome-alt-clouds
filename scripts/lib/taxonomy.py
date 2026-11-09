"""Single source of truth (Python side) for the 5-cloud taxonomy and tag vocabulary.

Mirrored in `src/lib/taxonomy.ts`; a test asserts the two stay identical.
Framework: https://www.notablecap.com/blog/the-rise-of-workload-clouds

Categories answer "what kind of cloud is this?" (one per entry). Tags answer
"what does it do / what is it like?" (many per entry) and are stored on the
README bullet as a trailing HTML comment (see `lib/entry_format.py`).
"""

from types import MappingProxyType

# --- Categories -------------------------------------------------------------

INFRASTRUCTURE = "Infrastructure Clouds"
WORKLOAD = "Workload Clouds"
SOVEREIGN = "Sovereign Clouds"
SERVICE = "Service Clouds"
VERTICAL = "Vertical Clouds"

CATEGORIES = (INFRASTRUCTURE, WORKLOAD, SOVEREIGN, SERVICE, VERTICAL)

CATEGORY_DEFINITIONS = MappingProxyType(
    {
        INFRASTRUCTURE: (
            "Raw capacity (compute, GPU, bare metal, storage, network, edge) priced by "
            "resource unit: hours, GB, Gbps. You bring the workload."
        ),
        WORKLOAD: (
            "The provider owns a compute- or storage-heavy workload end to end. No "
            "provisioning or scaling for the customer, one bill, priced per unit of "
            "that workload."
        ),
        SOVEREIGN: (
            "Jurisdiction is the primary reason to buy: owned, operated, and "
            "data-resident in a specific country or region under its laws."
        ),
        SERVICE: (
            "Building-block services builders embed in their own cloud or product: "
            "identity, billing, communications, feature flags, API gateways, source "
            "control, security tooling. Lighter on compute; the value is correctness "
            "and reliability."
        ),
        VERTICAL: (
            "An industry-specific service that runs a regulated or specialized workload, "
            "priced on usage: payments and banking infrastructure, HIPAA-grade health "
            "data, legal document processing at scale."
        ),
    }
)

# --- Workload tags (grouped into families for the filter UI) ----------------

WORKLOAD_TAG_FAMILIES = MappingProxyType(
    {
        "App": (
            "web-frontend",
            "app-hosting",
            "serverless-functions",
            "edge-functions",
            "wasm-unikernel",
        ),
        "Data": (
            "postgres-sql",
            "key-value-cache",
            "vector",
            "warehouse-lakehouse",
            "streaming-etl",
        ),
        "AI": (
            "llm-inference",
            "generative-media",
            "training-finetuning",
            "batch-gpu",
            "speech-voice",
        ),
        "Agent": (
            "agent-browser",
            "agent-sandbox",
            "agent-search",
            "agent-memory",
            "app-generation",
        ),
        "Build & Run": (
            "ci-builds",
            "durable-workflow",
            "observability",
            "media-processing",
            "realtime-rtc",
        ),
    }
)

WORKLOAD_TAGS = tuple(tag for tags in WORKLOAD_TAG_FAMILIES.values() for tag in tags)

# --- Cross-cutting tags (valid on every category) ---------------------------

CROSS_CUTTING_TAGS = (
    "agent-native",  # agents can sign up, provision, and pay via API/MCP
    "open-source",  # open source core / self-host / BYOC
    "owns-hardware",  # operates hardware / owns datacenters
    "gpu",
)

# Region/sovereignty tags are `region:<code>` (e.g. `region:ch`, `region:eu`).
REGION_TAG_PREFIX = "region:"

_FIXED_TAGS = frozenset(WORKLOAD_TAGS) | frozenset(CROSS_CUTTING_TAGS)


def is_valid_tag(tag: str) -> bool:
    """True for a known workload/cross-cutting tag or a well-formed region tag."""
    if tag in _FIXED_TAGS:
        return True
    if tag.startswith(REGION_TAG_PREFIX):
        code = tag[len(REGION_TAG_PREFIX) :]
        return 2 <= len(code) <= 8 and code.replace("-", "").isalnum() and code == code.lower()
    return False


def tag_family(tag: str) -> str | None:
    """Return the workload family a tag belongs to, or None (cross-cutting/region)."""
    for family, tags in WORKLOAD_TAG_FAMILIES.items():
        if tag in tags:
            return family
    return None


# --- Legacy (24-category) -> new category -----------------------------------
# A string maps deterministically; None means the old bucket is split across
# several new categories and each entry needs per-entry classification.

LEGACY_CATEGORY_MAP = MappingProxyType(
    {
        "Infrastructure Clouds": INFRASTRUCTURE,
        "GPU & AI Compute Clouds": INFRASTRUCTURE,
        "Network & Connectivity Clouds": INFRASTRUCTURE,
        "Decentralized & Web3 Compute": INFRASTRUCTURE,
        "Workload Clouds": WORKLOAD,
        "PaaS & Application Hosting": WORKLOAD,
        "Analytics & Data Warehousing": WORKLOAD,
        "Data Integration & ETL": WORKLOAD,
        "AI Inference & Model APIs": WORKLOAD,
        "AI Coding & App Generation": WORKLOAD,
        "Unikernels & WebAssembly": WORKLOAD,
        "Workflow & Operations Clouds": WORKLOAD,
        "Authorization, Identity & Fraud": SERVICE,
        "Monetization & Billing Clouds": SERVICE,
        "Source Code Control": SERVICE,
        "Cloud Adjacent & Infrastructure Tooling": SERVICE,
        # Split buckets: classify per entry.
        "Databases & Storage": None,  # object/block -> Infra; managed DB -> Workload
        "Observability & Monitoring": None,  # heavy telemetry ingest -> Workload; else Service
        "Developer Tooling & CI/CD": None,  # CI runners -> Workload; else Service
        "Security, Compliance & Sovereignty Clouds": None,  # sovereignty test -> Sovereign
        "Communications, IoT & Media": None,  # light comms -> Service; RTC/video -> Workload
        "AI Assistants & Copilots": None,  # hosted agents -> Workload; else Service/Vertical
        "Customer, Marketing & eCommerce": None,  # mostly SaaS; Service or Vertical, per entry
        "Emerging & Unverified Providers": None,  # becomes the unverified badge; re-categorize
    }
)

UNVERIFIED_LEGACY_CATEGORY = "Emerging & Unverified Providers"
