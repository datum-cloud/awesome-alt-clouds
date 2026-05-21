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

export interface CloudWithSlug extends Cloud {
  slug: string;
}

/**
 * Slugs that must remain owned by static routes / public files.
 * If a cloud's slug ever equals one of these, the build fails (see assertion below).
 * Items with dots cannot realistically collide with a slug (slugify strips dots),
 * but they are kept here for defense-in-depth and documentation.
 */
const RESERVED_SLUGS = new Set<string>([
  "submit",
  "watchlist",
  "404",
  "clouds.json",
  "llms.txt",
  "llms-full.txt",
  "watchlist.json",
  "og-image.png",
  "altclouds-logo.png",
  "robots.txt",
  "cname",
  "rss.xml",
  "sitemap-index.xml",
]);

/** Canonical slug derivation. Lowercase, alphanumeric, dash-separated. */
export function slugify(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function buildCloudsWithSlugs(): CloudWithSlug[] {
  const seen = new Map<string, string>();
  const result: CloudWithSlug[] = [];

  for (const cloud of cloudsData as Cloud[]) {
    const slug = slugify(cloud.name);

    if (!slug) {
      throw new Error(
        `[clouds] Cloud name "${cloud.name}" slugifies to an empty string. Rename in README.md.`
      );
    }

    if (RESERVED_SLUGS.has(slug)) {
      throw new Error(
        `[clouds] Cloud "${cloud.name}" slugifies to reserved path "${slug}". ` +
          `Reserved paths cannot be used as cloud slugs. Rename in README.md.`
      );
    }

    const prior = seen.get(slug);
    if (prior) {
      throw new Error(
        `[clouds] Slug collision detected: "${prior}" and "${cloud.name}" both produce slug "${slug}". ` +
          `Disambiguate one of the entries in README.md.`
      );
    }
    seen.set(slug, cloud.name);

    result.push({ ...cloud, slug });
  }

  return result;
}

export const clouds: CloudWithSlug[] = buildCloudsWithSlugs();

export const cloudsBySlug = new Map<string, CloudWithSlug>(clouds.map((c) => [c.slug, c]));

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
