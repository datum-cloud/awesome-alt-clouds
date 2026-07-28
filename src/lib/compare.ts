import type { MergedCloud } from "./profile";

/** Serializable cloud snapshot for client-side compare table. */
export interface CompareCloud {
  slug: string;
  name: string;
  url: string;
  description: string;
  score: 2 | 3;
  categories: string[];
  tagline?: string;
  pricingModel?: MergedCloud["pricingModel"];
  regions?: string[];
  services?: string[];
  openSource?: boolean;
  headquarters?: string;
  foundedYear?: number;
  dateAdded?: string;
  hasProfile: boolean;
}

export interface CompareRow {
  key: keyof CompareCloud | "categories" | "regions" | "services";
  label: string;
}

export const COMPARE_ROWS: CompareRow[] = [
  { key: "score", label: "Criteria score" },
  { key: "categories", label: "Categories" },
  { key: "description", label: "Description" },
  { key: "tagline", label: "Tagline" },
  { key: "pricingModel", label: "Pricing model" },
  { key: "headquarters", label: "Headquarters" },
  { key: "foundedYear", label: "Founded" },
  { key: "openSource", label: "Open source" },
  { key: "regions", label: "Regions" },
  { key: "services", label: "Services" },
  { key: "dateAdded", label: "Listed" },
];

const PRICING_LABELS: Record<string, string> = {
  hourly: "Hourly",
  monthly: "Monthly",
  "usage-based": "Usage-based",
  subscription: "Subscription",
  mixed: "Mixed",
};

export function toCompareCloud(cloud: MergedCloud, hasProfile: boolean): CompareCloud {
  return {
    slug: cloud.slug,
    name: cloud.name,
    url: cloud.url,
    description: cloud.description,
    score: cloud.score,
    categories: cloud.categories,
    tagline: cloud.tagline,
    pricingModel: cloud.pricingModel,
    regions: cloud.regions,
    services: cloud.services,
    openSource: cloud.openSource,
    headquarters: cloud.headquarters,
    foundedYear: cloud.foundedYear,
    dateAdded: cloud.dateAdded,
    hasProfile,
  };
}

export function formatCompareValue(
  key: CompareRow["key"],
  cloud: CompareCloud | undefined
): string {
  if (!cloud) return "—";

  switch (key) {
    case "score":
      return `${cloud.score}/3`;
    case "categories":
      return cloud.categories.length > 0 ? cloud.categories.join(" · ") : "—";
    case "description":
      return cloud.description || "—";
    case "tagline":
      return cloud.tagline || "—";
    case "pricingModel":
      return cloud.pricingModel ? (PRICING_LABELS[cloud.pricingModel] ?? cloud.pricingModel) : "—";
    case "headquarters":
      return cloud.headquarters || "—";
    case "foundedYear":
      return cloud.foundedYear != null ? String(cloud.foundedYear) : "—";
    case "openSource":
      return cloud.openSource === undefined ? "—" : cloud.openSource ? "Yes" : "No";
    case "regions":
      return cloud.regions && cloud.regions.length > 0 ? cloud.regions.join(", ") : "—";
    case "services":
      return cloud.services && cloud.services.length > 0 ? cloud.services.join(", ") : "—";
    case "dateAdded":
      return cloud.dateAdded || "—";
    default:
      return "—";
  }
}
