import { siteConfig } from "../../site.config.mjs";

const { seo } = siteConfig;

function withPreviewTitle(title: string): string {
  if (siteConfig.preview && seo.previewTitleSuffix) {
    return `${title}${seo.previewTitleSuffix}`;
  }
  return title;
}

export const defaultTitle = withPreviewTitle(seo.title);
export const defaultDescription = seo.description;

/** Short brand suffix for templated per-page titles (cloud detail, category, compare). */
export const siteName = withPreviewTitle(seo.siteName);

export const submitTitle = withPreviewTitle(seo.submit.title);
export const submitDescription = seo.submit.description;

export const blogTitle = withPreviewTitle(seo.blog.title);
export const blogDescription = seo.blog.description;

export type PageMetaKey = "home" | "submit" | "blog";

export function getPageMeta(page: PageMetaKey): { title: string; description: string } {
  switch (page) {
    case "home":
      return { title: defaultTitle, description: defaultDescription };
    case "submit":
      return { title: submitTitle, description: submitDescription };
    case "blog":
      return { title: blogTitle, description: blogDescription };
    default: {
      const _exhaustive: never = page;
      throw new Error(`Unknown page meta key: ${_exhaustive}`);
    }
  }
}

/** Short title for Open Graph / Twitter (no preview suffix). */
export const socialTitle = "Awesome Alt Clouds - When you need something specialized";

export const socialDescription =
  "A curated directory of alternative cloud providers to help developers source solutions offering public pricing, self-service signup, and transparent uptime at a glance. Now accepting contributions to the list.";
