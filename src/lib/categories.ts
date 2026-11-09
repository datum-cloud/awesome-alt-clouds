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
