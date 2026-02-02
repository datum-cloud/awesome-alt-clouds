#!/usr/bin/env python3
"""
Fetch blog posts from Zac Smith's author page and update the Resources modal
in docs/index.html
"""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

AUTHOR_URL = "https://www.datum.net/authors/zac-smith/"
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

    soup = BeautifulSoup(response.text, 'html.parser')
    posts = []

    # Find article links - adjust selectors based on actual page structure
    # Common patterns for blog listing pages
    article_elements = soup.find_all('article') or soup.find_all('div', class_=re.compile(r'post|article|blog'))

    if not article_elements:
        # Try finding links that look like blog posts
        links = soup.find_all('a', href=re.compile(r'/blog/'))
        seen_urls = set()

        for link in links:
            href = link.get('href', '')
            if href in seen_urls or not href.startswith('/blog/') or href == '/blog/':
                continue

            # Skip if it's just a category or tag link
            if '/category/' in href or '/tag/' in href:
                continue

            seen_urls.add(href)
            title = link.get_text(strip=True)

            if title and len(title) > 5:  # Skip very short text (likely not titles)
                full_url = f"https://www.datum.net{href}" if href.startswith('/') else href

                # Try to find date near the link
                parent = link.find_parent(['article', 'div', 'li'])
                date_text = ""
                if parent:
                    date_elem = parent.find(string=re.compile(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}'))
                    if date_elem:
                        date_text = date_elem.strip()

                posts.append({
                    'title': title,
                    'url': full_url,
                    'date': date_text,
                    'excerpt': ''  # Will try to fetch from article page if needed
                })

                if len(posts) >= MAX_POSTS:
                    break

    else:
        for article in article_elements[:MAX_POSTS]:
            title_elem = article.find(['h1', 'h2', 'h3', 'a'])
            link_elem = article.find('a', href=re.compile(r'/blog/'))

            if not title_elem or not link_elem:
                continue

            title = title_elem.get_text(strip=True)
            href = link_elem.get('href', '')
            full_url = f"https://www.datum.net{href}" if href.startswith('/') else href

            # Find date
            date_elem = article.find(string=re.compile(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}'))
            date_text = date_elem.strip() if date_elem else ""

            # Find excerpt
            excerpt_elem = article.find('p')
            excerpt = excerpt_elem.get_text(strip=True)[:200] if excerpt_elem else ""

            posts.append({
                'title': title,
                'url': full_url,
                'date': date_text,
                'excerpt': excerpt
            })

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

    # Pattern to match the blog posts container content
    pattern = r'(<div id="blogPostsContainer">)\s*<!--.*?-->\s*(.*?)(</div>\s*<p style="margin-top: 1rem; text-align: center;">\s*<a href="https://www\.datum\.net/authors/zac-smith/")'

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
