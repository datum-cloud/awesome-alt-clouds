import { siteConfig } from "../../site.config.mjs";

const preview = siteConfig.preview;

const siteOrigin = (preview ? siteConfig.previewSite : siteConfig.productionSite).replace(/\/$/, "");
const siteBasePath = preview
  ? (siteConfig.previewBase ?? "/").replace(/^\/?/, "/").replace(/\/?$/, "/")
  : (siteConfig.productionBase ?? "/").replace(/^\/?/, "/").replace(/\/?$/, "/");

/** Absolute URL for a path under the current deploy profile (preview or production). */
export function absoluteUrl(pathname = "/"): string {
  const path = pathname.replace(/^\//, "");
  const joined =
    siteBasePath === "/" ? `${siteOrigin}/${path}` : `${siteOrigin}${siteBasePath}${path}`;
  return joined.replace(/([^:]\/)\/+/g, "$1").replace(/\/$/, "") || siteOrigin;
}

/** Homepage canonical URL (trailing slash). */
export function homepageUrl(): string {
  const root = siteBasePath === "/" ? siteOrigin : `${siteOrigin}${siteBasePath}`;
  return root.endsWith("/") ? root : `${root}/`;
}

export const defaultCanonical = homepageUrl();
export const defaultOgImage = `${absoluteUrl("og-image.png")}`;

/** Site root without trailing slash — for JSON-LD @id fragments. */
export const siteRoot = defaultCanonical.replace(/\/$/, "");
