import rss from "@astrojs/rss";
import type { APIContext } from "astro";
import { siteConfig } from "../../site.config.mjs";
import { getPublishablePosts, postUrl, sortedByDate } from "../lib/blog";

export async function GET(context: APIContext) {
  const posts = sortedByDate(await getPublishablePosts());

  return rss({
    title: siteConfig.seo.title,
    description: siteConfig.seo.description,
    site: context.site ?? siteConfig.previewSite,
    items: posts.map((post) => ({
      title: post.data.title,
      pubDate: post.data.publishDate,
      description: post.data.description,
      link: postUrl(post.id),
    })),
  });
}
