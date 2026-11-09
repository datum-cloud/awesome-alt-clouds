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

export const WORKLOAD_TAG_FAMILIES = {
  App: ["web-frontend", "app-hosting", "serverless-functions", "edge-functions", "wasm-unikernel"],
  Data: ["postgres-sql", "key-value-cache", "vector", "warehouse-lakehouse", "streaming-etl"],
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
