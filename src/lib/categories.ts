/**
 * Category taxonomy metadata for landing pages and SEO.
 * Keep in sync with `scripts/generate_llms.py:_CAT_DESCRIPTIONS` and
 * `scripts/evaluate_submission.py:CATEGORIES`.
 */
import { categoryToSlug, getCategories } from "./clouds";
import { CATEGORY_DEFINITIONS } from "./taxonomy";

export const DEFAULT_CAT_DESCRIPTION = "Cloud services in this category.";

export const categoryDescriptions: Record<string, string> = CATEGORY_DEFINITIONS;

export function getCategoryDescription(category: string): string {
  return categoryDescriptions[category] ?? DEFAULT_CAT_DESCRIPTION;
}

export function getCategoryBySlug(slug: string): string | undefined {
  return getCategories()
    .filter((cat) => cat !== "All")
    .find((cat) => categoryToSlug(cat) === slug);
}

export function getAllCategorySlugs(): string[] {
  return getCategories()
    .filter((cat) => cat !== "All")
    .map((cat) => categoryToSlug(cat));
}

/**
 * Short, builder-facing blurbs for the homepage "Browse by what you're building" row.
 * UI copy only: the canonical definitions stay in taxonomy.ts (mirrored in Python).
 */
export const CATEGORY_BLURBS: Record<string, string> = {
  "Infrastructure Clouds":
    "Rent GPUs, bare metal, storage, or networking. Bring your own workload.",
  "Workload Clouds":
    "Deploy an app, run a database, serve a model, or spin up an agent sandbox. The provider handles provisioning and scaling.",
  "Sovereign Clouds":
    "Find providers based on where they’re owned and operated, where your data lives, and which laws apply.",
  "Service Clouds":
    "Add building blocks like auth, billing, feature flags, or API gateways to your product.",
  "Vertical Clouds": "Find specialist services for industries like banking, healthcare, and legal.",
};
