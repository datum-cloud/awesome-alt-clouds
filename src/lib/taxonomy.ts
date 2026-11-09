/**
 * 5-cloud taxonomy + tag vocabulary (TypeScript side).
 * Mirrors `scripts/lib/taxonomy.py`; `tests/test_taxonomy_sync.py` fails if they drift.
 * Framework: https://www.notablecap.com/blog/the-rise-of-workload-clouds
 */

export const CATEGORIES = [
  "Infrastructure Clouds",
  "Workload Clouds",
  "Sovereign Clouds",
  "Service Clouds",
  "Vertical Clouds",
] as const;

export type Category = (typeof CATEGORIES)[number];

export const CATEGORY_DEFINITIONS: Record<Category, string> = {
  "Infrastructure Clouds":
    "Raw capacity (compute, GPU, bare metal, storage, network, edge) priced by resource unit: hours, GB, Gbps. You bring the workload.",
  "Workload Clouds":
    "The provider owns a compute- or storage-heavy workload end to end. No provisioning or scaling for the customer, one bill, priced per unit of that workload.",
  "Sovereign Clouds":
    "Jurisdiction is the primary reason to buy: owned, operated, and data-resident in a specific country or region under its laws.",
  "Service Clouds":
    "Building-block services builders embed in their own cloud or product: identity, billing, communications, feature flags, API gateways, source control, security tooling. Lighter on compute; the value is correctness and reliability.",
  "Vertical Clouds":
    "An industry-specific service that runs a regulated or specialized workload, priced on usage: payments and banking infrastructure, HIPAA-grade health data, legal document processing at scale.",
};

export const WORKLOAD_TAG_FAMILIES = {
  App: ["web-frontend", "app-hosting", "serverless-functions", "edge-functions", "wasm-unikernel"],
  Data: [
    "postgres-sql",
    "nosql-timeseries",
    "key-value-cache",
    "vector",
    "warehouse-lakehouse",
    "streaming-etl",
  ],
  AI: ["llm-inference", "generative-media", "training-finetuning", "batch-gpu", "speech-voice"],
  Agent: ["agent-browser", "agent-sandbox", "agent-search", "agent-memory", "app-generation"],
  "Build & Run": [
    "ci-builds",
    "durable-workflow",
    "observability",
    "media-processing",
    "realtime-rtc",
  ],
} as const;

export const CROSS_CUTTING_TAGS = ["agent-native", "open-source", "owns-hardware", "gpu"] as const;

export const REGION_TAG_PREFIX = "region:";

/** Pseudo-tags derived from entry flags rather than written in the README. */
export const STATUS_TAGS = ["unverified"] as const;

const FIXED_TAGS: ReadonlySet<string> = new Set([
  ...Object.values(WORKLOAD_TAG_FAMILIES).flat(),
  ...CROSS_CUTTING_TAGS,
]);

export function isValidTag(tag: string): boolean {
  if (FIXED_TAGS.has(tag)) return true;
  if (!tag.startsWith(REGION_TAG_PREFIX)) return false;
  const code = tag.slice(REGION_TAG_PREFIX.length);
  return /^[a-z0-9-]{2,8}$/.test(code) && /[a-z0-9]/.test(code.replace(/-/g, ""));
}

export function tagFamily(tag: string): string | undefined {
  return Object.entries(WORKLOAD_TAG_FAMILIES).find(([, tags]) =>
    (tags as readonly string[]).includes(tag)
  )?.[0];
}

const TAG_LABELS: Record<string, string> = {
  "web-frontend": "Web & frontend",
  "app-hosting": "App hosting",
  "serverless-functions": "Serverless functions",
  "edge-functions": "Edge functions",
  "wasm-unikernel": "Wasm & unikernel",
  "postgres-sql": "Postgres & SQL",
  "nosql-timeseries": "NoSQL & time-series",
  "key-value-cache": "Key-value & cache",
  vector: "Vector",
  "warehouse-lakehouse": "Warehouse & lakehouse",
  "streaming-etl": "Streaming & ETL",
  "llm-inference": "LLM inference",
  "generative-media": "Generative media",
  "training-finetuning": "Training & fine-tuning",
  "batch-gpu": "Batch GPU jobs",
  "speech-voice": "Speech & voice",
  "agent-browser": "Browser",
  "agent-sandbox": "Sandbox & code execution",
  "agent-search": "Search & extraction",
  "agent-memory": "Agent memory",
  "app-generation": "App generation",
  "ci-builds": "CI & builds",
  "durable-workflow": "Durable workflow",
  observability: "Observability",
  "media-processing": "Media & video",
  "realtime-rtc": "Real-time & RTC",
  "agent-native": "Agent-native",
  "open-source": "Open source / self-host",
  "owns-hardware": "Owns hardware",
  gpu: "GPU",
  unverified: "Emerging & Unverified 🔵",
};

/** Human-readable label for a tag slug (`region:ch` becomes "Region: CH"). */
export function tagLabel(tag: string): string {
  if (tag.startsWith(REGION_TAG_PREFIX)) {
    return `Region: ${tag.slice(REGION_TAG_PREFIX.length).toUpperCase()}`;
  }
  return TAG_LABELS[tag] ?? tag;
}

export interface TagGroup {
  /** "workload": only meaningful on Workload Clouds. "all": valid on every category. */
  scope: "workload" | "all";
  label: string;
  tags: { tag: string; count: number }[];
}

/** Group the tags that actually occur (with counts) by family, cross-cutting, then region. */
export function groupTagCounts(counts: ReadonlyMap<string, number>): TagGroup[] {
  const pick = (tags: readonly string[]) =>
    tags.filter((t) => counts.has(t)).map((tag) => ({ tag, count: counts.get(tag) ?? 0 }));
  const groups: TagGroup[] = Object.entries(WORKLOAD_TAG_FAMILIES).map(([label, tags]) => ({
    scope: "workload" as const,
    label,
    tags: pick(tags),
  }));
  groups.push({ scope: "all", label: "Capabilities", tags: pick(CROSS_CUTTING_TAGS) });
  groups.push({ scope: "all", label: "Status", tags: pick(STATUS_TAGS) });
  const regions = [...counts.keys()].filter((t) => t.startsWith(REGION_TAG_PREFIX)).sort();
  groups.push({ scope: "all", label: "Region", tags: pick(regions) });
  return groups.filter((g) => g.tags.length > 0);
}
