import { getCollection, type CollectionEntry } from "astro:content";
import { cloudsBySlug, type CloudWithSlug } from "./clouds";
import { sitePreview } from "./site";

export type CloudProfile = CollectionEntry<"clouds">;
export type ProfileStatus = "draft" | "reviewed";

/**
 * Loads MDX entries and validates each entry's id (file basename) matches
 * a cloud slug from clouds.json. Throws on orphans so the build fails loud.
 */
export async function loadProfiles(): Promise<CloudProfile[]> {
  const entries = await getCollection("clouds");
  const orphans: string[] = [];

  for (const entry of entries) {
    if (!cloudsBySlug.has(entry.id)) {
      orphans.push(entry.id);
    }
  }

  if (orphans.length > 0) {
    throw new Error(
      `[profile] Orphan MDX file(s) in src/content/clouds/ — no matching cloud in clouds.json: ` +
        orphans.map((o) => `"${o}.mdx"`).join(", ") +
        `. Either rename the file to match a cloud's slugified name, or add the cloud to README.md first.`
    );
  }

  return entries;
}

export function getProfileStatus(profile: CloudProfile): ProfileStatus {
  return profile.data.status ?? "draft";
}

/**
 * Whether a profile page should be built and linked in the current deploy.
 * Production (preview: false): reviewed only.
 * Preview (preview: true): reviewed + draft.
 */
export function isProfilePublished(profile: CloudProfile, preview = sitePreview): boolean {
  return getProfileStatus(profile) === "reviewed" || preview;
}

export async function getPublishableProfiles(): Promise<CloudProfile[]> {
  const profiles = await loadProfiles();
  return profiles.filter((profile) => isProfilePublished(profile, sitePreview));
}

export async function getFeaturedSlugs(): Promise<Set<string>> {
  const profiles = await getPublishableProfiles();
  return new Set(profiles.map((p) => p.id));
}

export async function getFeaturedClouds(): Promise<CloudWithSlug[]> {
  const featuredSet = await getFeaturedSlugs();
  return [...featuredSet]
    .map((slug) => cloudsBySlug.get(slug))
    .filter((c): c is CloudWithSlug => c !== undefined);
}

/**
 * Merges base data from clouds.json with optional MDX frontmatter overrides.
 * JSON wins for canonical fields (name, url, description, score, categories);
 * frontmatter wins for enrichment fields (headquarters, regions, etc.).
 */
export interface MergedCloud extends CloudWithSlug {
  status?: ProfileStatus;
  headquarters?: string;
  foundedYear?: number;
  regions?: string[];
  services?: string[];
  openSource?: boolean;
  pricingModel?: "hourly" | "monthly" | "usage-based" | "subscription" | "mixed";
  socials?: {
    x?: string;
    linkedin?: string;
    github?: string;
    website?: string;
  };
  logo?: string;
  tagline?: string;
}

export function mergeCloudWithProfile(
  cloud: CloudWithSlug,
  profile: CloudProfile | undefined
): MergedCloud {
  if (!profile) return cloud;
  const data = profile.data;
  return {
    ...cloud,
    status: getProfileStatus(profile),
    headquarters: data.headquarters,
    foundedYear: data.foundedYear,
    regions: data.regions,
    services: data.services,
    openSource: data.openSource,
    pricingModel: data.pricingModel,
    socials: data.socials,
    logo: data.logo,
    tagline: data.tagline,
  };
}
