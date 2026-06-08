#!/usr/bin/env python3
"""
Fetch blog posts from Zac Smith's author page and update the Resources modal
in docs/index.html
"""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

AUTHOR_URL = "https://www.datum.net/authors/zachary-smith"
SITE_BASE = "https://www.datum.net"
INDEX_HTML_PATH = "docs/index.html"
MAX_POSTS = 5


def fetch_blog_posts():
    """Fetch blog posts from Zac Smith's author page"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(AUTHOR_URL, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching author page: {e}")
        return None

    # The site silently redirects unknown author slugs to /404, so check the
    # final URL rather than just the status code.
    if response.url.rstrip('/').endswith('/404'):
        print(f"Author page redirected to 404 — the slug in AUTHOR_URL may have changed: {AUTHOR_URL}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    posts = []

    for item in soup.select('div.entry-list-item'):
        link = item.find('a', class_='entry-list-item--wrapper', href=True)
        if link is None:
            continue

        href = link['href']
        full_url = f"{SITE_BASE}{href}" if href.startswith('/') else href

        title_elem = item.select_one('p.entry-list-item--title')
        title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)

        time_elem = item.find('time')
        date_text = time_elem.get_text(strip=True) if time_elem else ''

        posts.append({
            'title': title,
            'url': full_url,
            'date': date_text,
            'excerpt': '',
        })

        if len(posts) >= MAX_POSTS:
            break

    return posts


def generate_blog_html(posts):
    """Generate HTML for blog posts"""
    if not posts:
        return None

    html_parts = []
    for post in posts:
        excerpt = post.get('excerpt', '')
        if not excerpt:
            excerpt = "Read more about this topic on the Datum blog."

        date_html = f'<div class="resource-card-meta">{post["date"]}</div>' if post.get('date') else ''

        html_parts.append(f'''            <div class="resource-card">
              <h4 class="resource-card-title">
                <a href="{post['url']}" target="_blank">{post['title']}</a>
              </h4>
              <p class="resource-card-excerpt">{excerpt}</p>
              {date_html}
            </div>''')

    return '\n'.join(html_parts)


def update_index_html(posts_html):
    """Update the blog posts section in index.html"""
    with open(INDEX_HTML_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to match the blog posts container content. The trailing anchor
    # marker is the "View all posts" link, kept URL-agnostic so the replacement
    # keeps working if the author URL changes again.
    pattern = r'(<div id="blogPostsContainer">)\s*<!--.*?-->\s*(.*?)(</div>\s*<p style="margin-top: 1rem; text-align: center;">\s*<a href="https://www\.datum\.net/authors/[^"]+")'

    replacement = f'''\\1
            <!-- Blog posts auto-updated by GitHub Action -->
{posts_html}
          \\3'''

    new_content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)

    if count == 0:
        print("Warning: Could not find blog posts section to update")
        return False

    with open(INDEX_HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return True


def main():
    print("Fetching blog posts from Zac Smith's author page...")
    posts = fetch_blog_posts()

    if not posts:
        print("No posts found or error fetching posts")
        return 1

    print(f"Found {len(posts)} posts:")
    for post in posts:
        print(f"  - {post['title']}")

    posts_html = generate_blog_html(posts)
    if not posts_html:
        print("Error generating HTML")
        return 1

    print("\nUpdating index.html...")
    if update_index_html(posts_html):
        print("Successfully updated blog posts!")
        return 0
    else:
        print("Failed to update index.html")
        return 1


if __name__ == "__main__":
    exit(main())
