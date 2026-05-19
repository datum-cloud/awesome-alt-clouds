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

export const submitTitle = withPreviewTitle(seo.submit.title);
export const submitDescription = seo.submit.description;

/** Short title for Open Graph / Twitter (no preview suffix). */
export const socialTitle = "Awesome Alt Clouds - When you need something specialized";

export const socialDescription =
  "A curated directory of alternative cloud providers to help developers source solutions offering public pricing, self-service signup, and transparent uptime at a glance. Now accepting contributions to the list.";
