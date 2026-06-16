import { ChangeFreqEnum, type SitemapItem } from "@astrojs/sitemap";
import { siteConfig } from "../../site.config.mjs";
import { clouds } from "./clouds";

const preview = siteConfig.preview;

const siteBasePath = preview
  ? (siteConfig.previewBase ?? "/").replace(/^\/?/, "/").replace(/\/?$/, "/")
  : (siteConfig.productionBase ?? "/").replace(/^\/?/, "/").replace(/\/?$/, "/");

const cloudSlugs = new Set(clouds.map((cloud) => cloud.slug));

/** Path under the deploy base, without leading/trailing slashes (empty string = homepage). */
export function relativeSitePath(absoluteUrl: string): string {
  const pathname = new URL(absoluteUrl).pathname;

  if (siteBasePath === "/") {
    return pathname.replace(/^\/|\/$/g, "");
  }

  const basePrefix = siteBasePath.replace(/\/$/, "");
  if (pathname === basePrefix || pathname === `${basePrefix}/`) {
    return "";
  }

  if (pathname.startsWith(`${basePrefix}/`)) {
    return pathname.slice(basePrefix.length + 1).replace(/\/$/, "");
  }

  return pathname.replace(/^\/|\/$/g, "");
}

export function isBlogSitemapUrl(url: string): boolean {
  const rel = relativeSitePath(url);
  return rel === "blog" || rel.startsWith("blog/");
}

export function isCloudProfileSitemapUrl(url: string): boolean {
  const rel = relativeSitePath(url);
  if (!rel || rel.includes("/")) return false;
  return cloudSlugs.has(rel);
}

type SitemapChunkFn = (item: SitemapItem) => SitemapItem | undefined;

function blogChunk(item: SitemapItem): SitemapItem | undefined {
  if (!isBlogSitemapUrl(item.url)) return undefined;
  return { ...item, changefreq: ChangeFreqEnum.WEEKLY, priority: 0.8 };
}

function cloudsChunk(item: SitemapItem): SitemapItem | undefined {
  if (!isCloudProfileSitemapUrl(item.url)) return undefined;
  return { ...item, changefreq: ChangeFreqEnum.MONTHLY, priority: 0.7 };
}

/** Named sitemap files: sitemap-blog-0.xml, sitemap-clouds-0.xml; remainder → sitemap-pages-0.xml */
export const sitemapChunks: Record<string, SitemapChunkFn> = {
  blog: blogChunk,
  clouds: cloudsChunk,
};
