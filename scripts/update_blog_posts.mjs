#!/usr/bin/env node
/**
 * Fetch blog posts by Zac Smith from Strapi and update the Resources modal
 * in docs/index.html.
 *
 * Replaces the old HTML-scraping approach with a direct Strapi GraphQL query
 * via @datum-cloud/strapi-revalidate.
 *
 * Required env vars: STRAPI_URL, STRAPI_TOKEN
 */

import { readFileSync, writeFileSync } from 'node:fs';
import { createStrapiRevalidate, fetchArticles } from '@datum-cloud/strapi-revalidate';

const AUTHOR_SLUG = 'zachary-smith';
const SITE_BASE = 'https://www.datum.net';
const INDEX_HTML_PATH = new URL('../docs/index.html', import.meta.url).pathname;
const MAX_POSTS = 5;

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

function generateBlogHtml(posts) {
  return posts
    .map((post) => {
      const excerpt = post.description?.trim() || 'Read more about this topic on the Datum blog.';
      const url = `${SITE_BASE}/blog/${post.slug}`;
      const dateMeta = post.originalPublishedAt
        ? `\n              <div class="resource-card-meta">${formatDate(post.originalPublishedAt)}</div>`
        : '';
      return `            <div class="resource-card">
              <h4 class="resource-card-title">
                <a href="${url}" target="_blank">${post.title}</a>
              </h4>
              <p class="resource-card-excerpt">${excerpt}</p>${dateMeta}
            </div>`;
    })
    .join('\n');
}

function updateIndexHtml(postsHtml) {
  const content = readFileSync(INDEX_HTML_PATH, 'utf8');

  // Match from the container opening tag through to (but not including) the
  // "View all posts" anchor, keeping the anchor intact.
  const pattern =
    /(<div id="blogPostsContainer">)\s*<!--.*?-->.*?(<\/div>\s*<p style="margin-top: 1rem; text-align: center;">\s*<a href="https:\/\/www\.datum\.net\/authors\/[^"]+\")/s;

  let matched = false;
  const newContent = content.replace(pattern, (_match, open, tail) => {
    matched = true;
    return `${open}\n            <!-- Blog posts auto-updated by GitHub Action -->\n${postsHtml}\n          ${tail}`;
  });

  if (!matched) {
    console.error('Warning: could not find blog posts section to update');
    return false;
  }

  writeFileSync(INDEX_HTML_PATH, newContent, 'utf8');
  return true;
}

async function main() {
  const { STRAPI_URL, STRAPI_TOKEN } = process.env;

  if (!STRAPI_URL || !STRAPI_TOKEN) {
    console.error('Error: STRAPI_URL and STRAPI_TOKEN environment variables are required');
    process.exit(1);
  }

  // Ensure the URL includes a protocol — the secret may be stored as a bare hostname.
  const strapiUrl =
    STRAPI_URL.startsWith('http://') || STRAPI_URL.startsWith('https://')
      ? STRAPI_URL
      : `https://${STRAPI_URL}`;

  console.log(`Fetching articles from Strapi for author "${AUTHOR_SLUG}"…`);

  const { client, cache } = createStrapiRevalidate({
    url: strapiUrl,
    token: STRAPI_TOKEN,
    cache: { driver: 'memory' },
  });

  const allArticles = await fetchArticles({ client, cache });

  if (!allArticles.length) {
    console.error('No articles returned from Strapi');
    process.exit(1);
  }

  const posts = allArticles
    .filter((a) => a.author?.slug === AUTHOR_SLUG)
    .sort((a, b) => new Date(b.originalPublishedAt) - new Date(a.originalPublishedAt))
    .slice(0, MAX_POSTS);

  if (!posts.length) {
    console.error(`No articles found for author "${AUTHOR_SLUG}"`);
    process.exit(1);
  }

  console.log(`Found ${posts.length} posts:`);
  posts.forEach((p) => console.log(`  - ${p.title}`));

  const html = generateBlogHtml(posts);

  console.log('\nUpdating docs/index.html…');
  if (updateIndexHtml(html)) {
    console.log('Successfully updated blog posts!');
  } else {
    console.error('Failed to update docs/index.html');
    process.exit(1);
  }
}

main();
