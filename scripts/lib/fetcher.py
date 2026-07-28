"""
Reusable page-fetch cascade extracted from evaluate_submission.py.

Cascade order (most reliable first):
1. Jina Reader markdown mode (renders JS, bypasses CDN blocks)
2. Jina Reader HTML mode (good for static / server-rendered sites)
3. Direct requests with browser-like headers (cheap, no JS)

Public API:
    fetch_page(url, timeout, retries) -> (soup, final_url)
    fetch_page_with_fallback(url, timeout, retries) -> (soup, final_url, method)

Helpers (prefixed with `_` but exported for backward-compatibility with tests
that patch them on the evaluate_submission module):
    _jina_markdown_to_soup(markdown_text, base_url) -> BeautifulSoup
    _soup_has_meaningful_content(soup) -> bool
    _probe_url(url, timeout) -> (soup, final_url)
"""

import re

import requests
from bs4 import BeautifulSoup


def fetch_page(url, timeout=15, retries=2):
    """Fetch a page and return soup, handling Cloudflare and other protections"""
    # Headers that mimic a real browser to bypass basic bot detection
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

    for attempt in range(retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            response.raise_for_status()

            # Check if we got a Cloudflare challenge page
            if 'cloudflare' in response.text.lower() and 'challenge' in response.text.lower():
                print(f"Cloudflare challenge detected for {url}")
                if attempt < retries:
                    print(f"Retrying... ({attempt + 1}/{retries})")
                    continue
                return None, None

            return BeautifulSoup(response.text, 'html.parser'), response.url

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"Access denied (403) for {url} - likely Cloudflare protected")
            else:
                print(f"HTTP error fetching {url}: {e}")
        except requests.exceptions.Timeout:
            print(f"Timeout fetching {url}")
        except Exception as e:
            print(f"Error fetching {url}: {e}")

        if attempt < retries:
            print(f"Retrying... ({attempt + 1}/{retries})")

    return None, None


def _jina_markdown_to_soup(markdown_text, base_url):
    """Convert Jina Reader markdown output into a BeautifulSoup object.

    Jina's default (markdown) mode executes JavaScript and returns rendered
    content, but as markdown — not HTML.  This helper extracts all markdown
    links and builds a minimal HTML document so that the existing
    ``find_link_matching`` / ``find_all('a')`` logic keeps working.
    """
    # Extract markdown links: [text](url)
    links = re.findall(r'\[([^\]]*)\]\((https?://[^)]+)\)', markdown_text)

    # Build minimal HTML with the extracted links + full text
    html_parts = ['<html><body>']
    for text, href in links:
        html_parts.append(f'<a href="{href}">{text}</a>')
    # Preserve full text so that get_text() searches (SLA, pricing indicators) work
    html_parts.append(f'<div>{markdown_text}</div>')
    html_parts.append('</body></html>')

    return BeautifulSoup('\n'.join(html_parts), 'html.parser')


def _soup_has_meaningful_content(soup):
    """Return True if the soup contains real rendered content, not just an SPA shell."""
    text = soup.get_text(strip=True)
    links = soup.find_all('a', href=True)
    # An empty SPA shell typically has very little visible text and no links.
    # A real page has substantial text (>200 chars) and at least one link.
    return len(text) > 200 and len(links) >= 1


def fetch_page_with_fallback(url, timeout=15, retries=2):
    """Try Jina Reader first (renders JS, bypasses CDN blocks), then requests as fallback.
    Returns (soup, final_url, fetch_method)."""
    jina_url = f"https://r.jina.ai/{url}"

    # Stage 1a: Jina Reader in default markdown mode — actually executes JavaScript
    # and returns rendered content.  HTML mode (X-Return-Format: html) returns the
    # raw HTML *before* JS execution, which is an empty shell for SPAs.
    try:
        md_headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; awesome-alt-clouds-bot/1.0)',
            'Accept': 'text/plain',
        }
        response = requests.get(jina_url, headers=md_headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        if response.text and len(response.text) > 200:
            soup = _jina_markdown_to_soup(response.text, url)
            if _soup_has_meaningful_content(soup):
                return soup, url, "jina"
            else:
                print(f"Jina markdown response too thin for {url}, trying HTML mode")
    except Exception as e:
        print(f"Jina Reader (markdown) failed for {url}: {e}")

    # Stage 1b: Jina Reader in HTML mode — works well for static / server-rendered sites
    try:
        html_headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; awesome-alt-clouds-bot/1.0)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'X-Return-Format': 'html',
        }
        response = requests.get(jina_url, headers=html_headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        if response.text and len(response.text) > 100:
            soup = BeautifulSoup(response.text, 'html.parser')
            if _soup_has_meaningful_content(soup):
                return soup, url, "jina"
            else:
                print(f"Jina HTML response is an empty SPA shell for {url}, falling back")
    except Exception as e:
        print(f"Jina Reader (HTML) failed for {url}: {e}")

    # Stage 2: direct requests scraper (cheaper but fails on JS-heavy / CDN-blocked sites)
    soup, final_url = fetch_page(url, timeout=timeout, retries=retries)
    if soup is not None:
        return soup, final_url, "requests"

    return None, None, None


def _probe_url(url, timeout=10):
    """Try to fetch a URL and return (soup, final_url) if it returns 200."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if response.status_code == 200 and len(response.text) > 200:
            return BeautifulSoup(response.text, 'html.parser'), response.url
    except Exception:
        pass
    return None, None
