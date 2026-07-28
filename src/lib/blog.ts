import { getCollection, type CollectionEntry } from "astro:content";
import { asset } from "./assets";
import { sitePreview } from "./site";

export type BlogPost = CollectionEntry<"blog">;

export function isPostPublished(post: BlogPost, preview = sitePreview): boolean {
  return !post.data.draft || preview;
}

export async function getPublishablePosts(): Promise<BlogPost[]> {
  const posts = await getCollection("blog");
  return posts.filter((post) => isPostPublished(post, sitePreview));
}

export function sortedByDate(posts: BlogPost[]): BlogPost[] {
  return [...posts].sort((a, b) => b.data.publishDate.getTime() - a.data.publishDate.getTime());
}

export function postUrl(slug: string): string {
  return asset(`blog/${slug}/`);
}

export function formatPostDate(date: Date): string {
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}
