/**
 * Build-time view model shared by the List/Grid page and category pages.
 * One record per cloud, with everything the row, the tile and the client filter need.
 */
import { asset } from "./assets";
import { cloudLink, clouds, logoUrl, type CloudWithSlug } from "./clouds";
import { getPublishableProfiles, mergeCloudWithProfile, type MergedCloud } from "./profile";
import { tagLabel } from "./taxonomy";

const PRICING_LABELS: Record<NonNullable<MergedCloud["pricingModel"]>, string> = {
  hourly: "Hourly",
  monthly: "Monthly",
  "usage-based": "Usage-based",
  subscription: "Subscription",
  mixed: "Mixed",
};

export interface ListItem {
  slug: string;
  name: string;
  description: string;
  category: string;
  categories: string[];
  /** Tags for filtering, including the derived `unverified` pseudo-tag. */
  filterTags: string[];
  /** Up to two human-readable tags for the Tags column. */
  displayTags: string[];
  extraTagCount: number;
  pricing: string | null;
  unverified: boolean;
  dateAdded: string;
  logo: string;
  href: string;
  external: boolean;
}

export async function getListItems(source: CloudWithSlug[] = clouds): Promise<ListItem[]> {
  // Pricing comes only from published (reviewed in production) profiles, matching the link rule.
  const profiles = await getPublishableProfiles();
  const profileBySlug = new Map(profiles.map((p) => [p.id, p]));
  const publishedSlugs = new Set(profileBySlug.keys());
  const base = asset("");

  return [...source]
    .sort((a, b) => a.name.localeCompare(b.name, "en", { sensitivity: "base" }))
    .map((cloud) => {
      const merged = mergeCloudWithProfile(cloud, profileBySlug.get(cloud.slug));
      const tags = cloud.tags ?? [];
      const { href, external } = cloudLink(cloud, publishedSlugs, base);
      return {
        slug: cloud.slug,
        name: cloud.name,
        description: cloud.description,
        category: cloud.categories[0] ?? "",
        categories: cloud.categories,
        filterTags: cloud.unverified ? [...tags, "unverified"] : tags,
        displayTags: tags.slice(0, 2).map(tagLabel),
        extraTagCount: Math.max(0, tags.length - 2),
        pricing: merged.pricingModel ? PRICING_LABELS[merged.pricingModel] : null,
        unverified: Boolean(cloud.unverified),
        dateAdded: cloud.dateAdded ?? "",
        logo: logoUrl(cloud.url),
        href,
        external,
      };
    });
}

/** Spread onto an <a> that may leave the site. */
export function linkAttrs(item: Pick<ListItem, "href" | "external">) {
  return item.external
    ? { href: item.href, target: "_blank", rel: "noopener noreferrer" }
    : { href: item.href };
}
