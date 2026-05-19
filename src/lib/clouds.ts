import cloudsData from "../../public/clouds.json";

export interface Cloud {
  name: string;
  url: string;
  description: string;
  score: 2 | 3;
  categories: string[];
  dateAdded?: string;
  favorite?: boolean;
}

export const clouds = cloudsData as Cloud[];

export function getCategories(): string[] {
  const set = new Set<string>();
  for (const cloud of clouds) {
    for (const cat of cloud.categories) set.add(cat);
  }
  return ["All", ...[...set].sort()];
}

export function categoryToSlug(cat: string): string {
  return cat
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function countByCategory(category: string): number {
  if (category === "All") return clouds.length;
  return clouds.filter((c) => c.categories.includes(category)).length;
}
